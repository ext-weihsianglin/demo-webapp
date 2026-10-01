"""Versioned baseline rewrite orchestration. Source payloads never become instructions."""
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Literal

from openai import OpenAI, APIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
import tiktoken
from preprocessing.blocks import blocks_to_markdown, blocks_to_text
from preprocessing.downstream import structure_chunks

PROMPT_VERSION = 'rewrite-baseline-v1'
PROMPT = (Path(__file__).parent / 'prompts' / f'{PROMPT_VERSION}.txt').read_text()

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Evidence(StrictModel):
    snapshot_id: str
    block_id: str
    quote: str = Field(min_length=1)

class Edit(StrictModel):
    snapshot_id: str
    chunk_id: str
    block_id: str
    before: str
    after: str = Field(min_length=1, max_length=20000)
    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[Evidence] = Field(min_length=1)
    review_flags: list[str]
    heading_level: int | None = Field(ge=1, le=6)

class Proposal(StrictModel):
    status: Literal['proposed', 'abstained']
    summary: str
    edits: list[Edit]
    review_flags: list[str]

@dataclass(frozen=True)
class Settings:
    model: str = 'gpt-4.1-mini'
    context_tokens: int = 16000
    output_tokens: int = 4000
    timeout: float = 45
    retries: int = 1
    max_calls: int = 12
    input_price: float | None = None
    output_price: float | None = None

    def __post_init__(self):
        if not (1000 <= self.context_tokens <= 128000 and 256 <= self.output_tokens < self.context_tokens
                and 1 <= self.timeout <= 120 and 0 <= self.retries <= 2 and 1 <= self.max_calls <= 20):
            raise ValueError('Invalid rewrite limits')
        if any(p is not None and p < 0 for p in (self.input_price, self.output_price)):
            raise ValueError('Invalid rewrite prices')

    @classmethod
    def from_env(cls):
        def price(name):
            return float(os.environ[name]) if os.environ.get(name) else None
        return cls(model=os.getenv('OPENAI_REWRITE_MODEL', cls.model),
                   context_tokens=int(os.getenv('REWRITE_CONTEXT_TOKENS', '16000')),
                   output_tokens=int(os.getenv('REWRITE_OUTPUT_TOKENS', '4000')),
                   timeout=float(os.getenv('REWRITE_TIMEOUT_SECONDS', '45')),
                   retries=int(os.getenv('REWRITE_MAX_RETRIES', '1')),
                   max_calls=int(os.getenv('REWRITE_MAX_CALLS', '12')),
                   input_price=price('REWRITE_INPUT_USD_PER_MILLION'),
                   output_price=price('REWRITE_OUTPUT_USD_PER_MILLION'))

class RewriteFailure(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def editable(block):
    # Preserve containers, code, links, table HTML and inline formatting byte-for-byte.
    return (block['type'] in ('paragraph', 'heading') and not block.get('parent_id')
            and not block.get('links') and block.get('inline_markdown', block['text']) == block['text'])


def validate_edits(proposal, document, chunk, allow_structure):
    blocks = {b['block_id']: b for b in document['blocks']}
    seen = set()
    if proposal.status == 'abstained' and proposal.edits:
        raise RewriteFailure('invalid_output', 'Abstention contained edits.')
    for edit in proposal.edits:
        b = blocks.get(edit.block_id)
        if (edit.snapshot_id != document['snapshot_id'] or edit.chunk_id != chunk['chunk_id']
                or edit.block_id not in chunk['block_ids'] or b is None or edit.block_id in seen):
            raise RewriteFailure('invalid_output', 'Invalid or duplicate source reference.')
        seen.add(edit.block_id)
        if not editable(b) or edit.before != b['text'] or edit.after.strip() == edit.before.strip():
            raise RewriteFailure('invalid_output', 'Edit does not match an editable source block.')
        if not edit.after.strip() or not edit.reason.strip() or '\n' in edit.after:
            raise RewriteFailure('invalid_output', 'Prose edits must retain one nonempty block and a reason.')
        if edit.heading_level is not None and (b['type'] != 'heading' or not allow_structure):
            raise RewriteFailure('invalid_output', 'Structural change requires explicit permission.')
        for evidence in edit.evidence:
            source = blocks.get(evidence.block_id)
            if (evidence.snapshot_id != document['snapshot_id'] or evidence.block_id not in chunk['block_ids']
                    or source is None or not evidence.quote.strip() or evidence.quote not in source['text']):
                raise RewriteFailure('invalid_output', 'Evidence must quote a valid source block in this chunk.')
        # Evidence validity is mechanical, not a semantic entailment guarantee.
        if any(f in edit.review_flags for f in ('unsupported_addition', 'missing_evidence')):
            raise RewriteFailure('unsupported_output', 'Model flagged unsupported additions or missing evidence; no draft applied.')


def rewrite(document, chunks, query, tone, allow_structure, *, client=None, settings=None):
    start = time.monotonic()
    accumulated_flags = []
    telemetry = {'prompt_version': PROMPT_VERSION, 'model': None, 'status': 'started', 'calls': 0,
                 'input_tokens': 0, 'output_tokens': 0, 'estimated_cost_usd': None, 'usage_complete': True}
    def finish(status, message, **extra):
        telemetry.update(status=status, latency_ms=round((time.monotonic()-start)*1000))
        if settings and settings.input_price is not None and settings.output_price is not None and telemetry['usage_complete']:
            telemetry['estimated_cost_usd'] = (telemetry['input_tokens']*settings.input_price + telemetry['output_tokens']*settings.output_price)/1_000_000
        return {'mode': 'openai', 'status': status, 'summary': message, 'telemetry': telemetry,
                'snapshot_id': document['snapshot_id'], 'review_items': [*document['selection']['quality_flags'], *accumulated_flags,
                'Human review required: source quotes do not prove factual entailment.',
                'Markdown content proposal; source HTML/CSS is not patched.'], **extra}
    try:
        settings = settings or Settings.from_env()
        telemetry['model'] = settings.model
        if document['selection']['status'] == 'source_insufficient' or not chunks or not any(editable(b) and b['type']=='paragraph' for b in document['blocks']):
            raise RewriteFailure('source_insufficient', 'Insufficient editable source prose; choose a fuller source snapshot.')
        try:
            encoding = tiktoken.encoding_for_model(settings.model)
            telemetry['tokenizer'] = encoding.name
        except KeyError:
            # Explicit conservative fallback for unknown model aliases.
            encoding = tiktoken.get_encoding('o200k_base')
            telemetry['tokenizer'] = 'o200k_base (fallback; verify model compatibility)'
        schema = Proposal.model_json_schema()
        blocks = {b['block_id']: b for b in document['blocks']}
        requests = []
        for chunk in chunks:
            payload = {'target_query': query, 'editorial_tone': tone, 'allow_structure': allow_structure,
                       'snapshot_id': document['snapshot_id'], 'extraction': document['selection'],
                       'source_metadata': document['source_metadata'], 'heading_outline': document.get('outline', []),
                       'chunk': chunk, 'blocks': [{**blocks[i], 'editable': editable(blocks[i])} for i in chunk['block_ids']]}
            data = json.dumps(payload, ensure_ascii=False)
            count = len(encoding.encode(PROMPT + data + json.dumps(schema))) + 256
            if count + settings.output_tokens > settings.context_tokens:
                raise RewriteFailure('context_limit', f'Chunk {chunk["chunk_id"]} needs {count} input tokens plus output reserve. Oversized tables/code/list groups are retained intact; increase the verified model budget or choose a smaller snapshot.')
            requests.append((chunk, data, count))
        if len(requests) > settings.max_calls:
            raise RewriteFailure('context_limit', f'Source needs {len(requests)} calls; configured maximum is {settings.max_calls}. No source was truncated.')
        telemetry['budgeted_input_tokens'] = sum(r[2] for r in requests)
        if client is None:
            if not os.environ.get('OPENAI_API_KEY'):
                raise RewriteFailure('missing_credentials', 'Set OPENAI_API_KEY on the backend to generate a real draft.')
            client = OpenAI(timeout=settings.timeout, max_retries=settings.retries)
        edits, summaries = [], []
        for chunk, data, _ in requests:
            telemetry['calls'] += 1
            response = client.responses.create(model=settings.model, instructions=PROMPT,
                input=[{'role': 'user', 'content': data}], store=False, max_output_tokens=settings.output_tokens,
                text={'format': {'type': 'json_schema', 'name': 'rewrite_proposal', 'strict': True, 'schema': schema}})
            if response.usage:
                telemetry['input_tokens'] += response.usage.input_tokens
                telemetry['output_tokens'] += response.usage.output_tokens
            else:
                telemetry['usage_complete'] = False
            if any(getattr(c, 'type', '') == 'refusal' for o in response.output for c in getattr(o, 'content', [])):
                raise RewriteFailure('refused', 'The model refused this rewrite.')
            if response.status != 'completed':
                raise RewriteFailure('incomplete_output', 'The model did not complete its output; no partial draft applied.')
            proposal = Proposal.model_validate_json(response.output_text)
            accumulated_flags.extend(proposal.review_flags)
            accumulated_flags.extend(f for e in proposal.edits for f in e.review_flags)
            validate_edits(proposal, document, chunk, allow_structure)
            edits.extend(proposal.edits)
            summaries.append(proposal.summary)
        if len({e.block_id for e in edits}) != len(edits):
            raise RewriteFailure('invalid_output', 'Duplicate edits across chunks.')
        if not any(blocks[e.block_id]['type']=='paragraph' for e in edits):
            raise RewriteFailure('abstained', 'Model supplied no substantive body edits; source may not answer the target query.')
        result = deepcopy(document)
        by_id = {b['block_id']: b for b in result['blocks']}
        for edit in edits:
            block = by_id[edit.block_id]; block['text'] = edit.after; block.pop('inline_markdown', None)
            if edit.heading_level is not None:
                block['heading_level'] = edit.heading_level
        result['text'] = blocks_to_text(result['blocks'])
        result['markdown'] = blocks_to_markdown(result['blocks'])
        result['outline'], _ = structure_chunks(result['snapshot_id'], result['selection']['method'], result['blocks'], 6000)
        result['artifact_kind'] = 'proposed_content_based_on_source_snapshot'
        output = finish('succeeded', ' '.join(summaries), document=result, markdown=result['markdown'],
                        changes=[{**e.model_dump(), 'source_id': e.block_id} for e in edits],
                        preservation=['Tables, lists, code, links and source metadata retained', 'Original snapshot remains intact'])
        return output
    except RewriteFailure as exc:
        return finish(exc.status, exc.message)
    except (ValidationError, ValueError, TypeError):
        return finish('invalid_output', 'Invalid model output or server rewrite configuration; no draft applied.')
    except APIError:
        telemetry['usage_complete'] = False
        return finish('api_error', 'OpenAI request failed or timed out. Check server configuration and retry; no draft applied.')
