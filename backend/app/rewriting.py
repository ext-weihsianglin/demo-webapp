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
from app.language_guard import confident_language, compare_language

PROMPT_VERSION = 'rewrite-page-v7'
PROMPT = (Path(__file__).parent / 'prompts' / f'{PROMPT_VERSION}.txt').read_text()

SUPPORTED_REWRITE_MODELS = ('gpt-4.1-mini', 'gpt-4.1', 'gpt-4.1-nano', 'gpt-5', 'gpt-5-mini', 'gpt-5-nano')


def model_options():
    """Configuration can narrow the tested model catalog, never expand it."""
    default = os.getenv('OPENAI_REWRITE_MODEL', 'gpt-4.1-mini')
    if default not in SUPPORTED_REWRITE_MODELS:
        raise ValueError('OPENAI_REWRITE_MODEL must be in the supported P2 model catalog')
    configured = os.getenv('OPENAI_REWRITE_MODELS', ','.join(SUPPORTED_REWRITE_MODELS))
    models = list(dict.fromkeys([default, *(m.strip() for m in configured.split(',') if m.strip() in SUPPORTED_REWRITE_MODELS)]))
    return {'default_model': default, 'models': models}


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

class EvidenceReference(StrictModel):
    block_id: str

class ProviderEdit(StrictModel):
    block_id: str
    after: str = Field(min_length=1, max_length=20000, pattern=r'^[^\r\n]*\S[^\r\n]*$')
    reason: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    evidence: list[EvidenceReference] = Field(min_length=1)
    review_flags: list[str]
    heading_level: int | None = Field(ge=1, le=6)

class ProviderProposal(StrictModel):
    status: Literal['proposed', 'abstained']
    summary: str
    edits: list[ProviderEdit]
    review_flags: list[str]


def assemble_proposal(proposal, document, chunks):
    """Resolve model-selected IDs to immutable source data, never model-written quotes."""
    blocks = {b['block_id']: b for b in document['blocks']}
    memberships = {identity: c['chunk_id'] for c in chunks for identity in c['block_ids']}
    edits = []
    for edit in proposal.edits:
        source = blocks.get(edit.block_id)
        if source is None or edit.block_id not in memberships:
            raise RewriteFailure('invalid_output', 'Unknown edit block ID.', {'edit_block_id': edit.block_id, 'checks_failed': ['unknown_edit_block']})
        evidence = []
        for reference in edit.evidence:
            block = blocks.get(reference.block_id)
            if block is None:
                raise RewriteFailure('invalid_output', 'Unknown evidence block ID.', {'edit_block_id': edit.block_id, 'evidence_block_id': reference.block_id, 'checks_failed': ['unknown_block']})
            if not block['text'].strip():
                raise RewriteFailure('invalid_output', 'Selected evidence block has no text.', {'edit_block_id': edit.block_id, 'evidence_block_id': reference.block_id, 'checks_failed': ['empty_quote']})
            evidence.append(Evidence(snapshot_id=document['snapshot_id'], block_id=reference.block_id, quote=block['text']))
        edits.append(Edit(**edit.model_dump(exclude={'evidence'}), before=source['text'],
                          snapshot_id=document['snapshot_id'], chunk_id=memberships[edit.block_id], evidence=evidence))
    return Proposal(status=proposal.status, summary=proposal.summary, review_flags=proposal.review_flags, edits=edits)


@dataclass(frozen=True)
class Settings:
    model: str = 'gpt-4.1-mini'
    context_tokens: int = 128000
    output_tokens: int = 16000
    timeout: float = 120
    input_price: float | None = None
    output_price: float | None = None

    def __post_init__(self):
        if not (1000 <= self.context_tokens <= 128000 and 256 <= self.output_tokens < self.context_tokens
                and 1 <= self.timeout <= 120):
            raise ValueError('Invalid rewrite limits')
        if any(p is not None and p < 0 for p in (self.input_price, self.output_price)):
            raise ValueError('Invalid rewrite prices')

    @classmethod
    def from_env(cls, selected_model=None):
        def price(name):
            return float(os.environ[name]) if os.environ.get(name) else None
        options = model_options()
        model = selected_model or options['default_model']
        if model not in options['models']:
            raise ValueError('Model is not enabled on this server')
        # Global price configuration applies only to the configured default model.
        default_pricing = model == options['default_model']
        return cls(model=model,
                   context_tokens=int(os.getenv('REWRITE_CONTEXT_TOKENS', '128000')),
                   output_tokens=int(os.getenv('REWRITE_OUTPUT_TOKENS', '16000')),
                   timeout=float(os.getenv('REWRITE_TIMEOUT_SECONDS', '120')),
                   input_price=price('REWRITE_INPUT_USD_PER_MILLION') if default_pricing else None,
                   output_price=price('REWRITE_OUTPUT_USD_PER_MILLION') if default_pricing else None)

class RewriteFailure(Exception):
    def __init__(self, status, message, details=None):
        self.status, self.message, self.details = status, message, details
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
            raise RewriteFailure('invalid_output', f'Invalid source reference for block {edit.block_id}: snapshot_match={edit.snapshot_id == document["snapshot_id"]}, chunk_match={edit.chunk_id == chunk["chunk_id"]}, member={edit.block_id in chunk["block_ids"]}, duplicate={edit.block_id in seen}.')
        seen.add(edit.block_id)
        if not editable(b):
            raise RewriteFailure('invalid_output', f'Block {edit.block_id} is protected and cannot be edited.')
        if edit.before != b['text']:
            raise RewriteFailure('invalid_output', f'Block {edit.block_id}: before text does not exactly match the original source.')
        if not edit.after.strip() or not edit.reason.strip() or '\n' in edit.after:
            raise RewriteFailure('invalid_output', 'Prose edits must retain one nonempty block and a reason.')
        if edit.heading_level is not None and (b['type'] != 'heading' or not allow_structure):
            raise RewriteFailure('invalid_output', 'Structural change requires explicit permission.')
        for evidence_index, evidence in enumerate(edit.evidence):
            source = blocks.get(evidence.block_id)
            checks = {
                'snapshot_mismatch': evidence.snapshot_id != document['snapshot_id'],
                'unknown_block': source is None,
                'cross_chunk_evidence': source is not None and evidence.block_id not in chunk['block_ids'],
                'empty_quote': not evidence.quote.strip(),
                'quote_mismatch': source is not None and bool(evidence.quote.strip()) and evidence.quote not in source['text'],
            }
            failures = [name for name, failed in checks.items() if failed]
            if failures:
                details = {'edit_block_id': edit.block_id, 'evidence_block_id': evidence.block_id,
                           'evidence_index': evidence_index, 'checks_failed': failures}
                raise RewriteFailure('invalid_output',
                    f'Evidence for edit {edit.block_id} failed: {", ".join(failures)}. No draft applied.', details)
        # Evidence validity is mechanical, not a semantic entailment guarantee.
        if any(f in edit.review_flags for f in ('unsupported_addition', 'missing_evidence')):
            raise RewriteFailure('unsupported_output', 'Model flagged unsupported additions or missing evidence; no draft applied.')




def response_schema(document, batch, allow_structure=False):
    """One required nullable property per editable block; identity is the key."""
    blocks = {b['block_id']: b for b in document['blocks']}
    base = ProviderEdit.model_json_schema()
    definitions = base.pop('$defs')
    base['properties'].pop('block_id')
    base['required'].remove('block_id')
    if not allow_structure:
        base['properties']['heading_level'] = {'type': 'null'}
    properties = {}
    # Evidence enums occur once per chunk, not once per editable block.
    constrain_evidence = sum(len(c['block_ids']) for c in batch) <= 900
    for index, chunk in enumerate(batch):
        targets = [i for i in chunk['block_ids'] if editable(blocks[i])]
        if not targets:
            continue
        definition = deepcopy(base)
        if constrain_evidence:
            evidence_ids = [i for i in chunk['block_ids'] if blocks[i]['text'].strip()]
            definition['properties']['evidence']['items'] = {
                'type': 'object', 'properties': {'block_id': {'type': 'string', 'enum': evidence_ids}},
                'required': ['block_id'], 'additionalProperties': False}
        name = f'ChunkEdit{index}'
        definitions[name] = definition
        for identity in targets:
            properties[identity] = {'anyOf': [{'$ref': f'#/$defs/{name}'}, {'type': 'null'}]}
    schema = {'type': 'object', 'properties': {
        'status': {'type': 'string', 'enum': ['proposed', 'abstained']},
        'summary': {'type': 'string'}, 'review_flags': {'type': 'array', 'items': {'type': 'string'}},
        'blocks': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}},
        'required': ['status', 'summary', 'review_flags', 'blocks'], 'additionalProperties': False, '$defs': definitions}
    # Fail before the provider when a page cannot fit the strict keyed contract.
    property_count = len(properties) + 4 + sum(len(d.get('properties', {})) + 1 for d in definitions.values())
    if property_count > 4500 or len(json.dumps(schema)) > 110000:
        raise RewriteFailure('context_limit', 'Page exceeds the keyed response schema budget; no source was truncated and no call was made.')
    return schema


def parse_provider_proposal(raw, document):
    """Normalize identical duplicate keys; reject conflicts before JSON can discard them."""
    duplicates = 0
    def unique_object(pairs):
        nonlocal duplicates
        result = {}
        for key, value in pairs:
            if key in result:
                if json.dumps(result[key], sort_keys=True) != json.dumps(value, sort_keys=True):
                    raise RewriteFailure('invalid_output', 'Conflicting duplicate JSON key; no draft applied.',
                                         {'checks_failed': ['conflicting_duplicate_key'], 'key': key})
                duplicates += 1
            result[key] = value
        return result
    payload = json.loads(raw, object_pairs_hook=unique_object)
    expected = {b['block_id'] for b in document['blocks'] if editable(b)}
    if not isinstance(payload, dict) or set(payload) != {'status', 'summary', 'review_flags', 'blocks'}:
        raise RewriteFailure('invalid_output', 'Invalid keyed proposal envelope.')
    values = payload['blocks']
    if not isinstance(values, dict) or set(values) != expected:
        raise RewriteFailure('invalid_output', 'Proposal must include exactly the editable block IDs, using null for unchanged blocks.',
                             {'checks_failed': ['editable_key_set_mismatch']})
    edits = []
    for identity, value in values.items():
        if value is None:
            continue
        if not isinstance(value, dict) or 'block_id' in value:
            raise RewriteFailure('invalid_output', 'Edit identity must appear only as its object key.')
        edits.append({**value, 'block_id': identity})
    proposal = ProviderProposal.model_validate({**{k: payload[k] for k in ('status', 'summary', 'review_flags')}, 'edits': edits})
    return proposal, duplicates


def plan_requests(document, chunks, queries, tone, allow_structure, settings, encoding, p1_feedback=None):
    """Build exactly one whole-page request, preserving all text and queries.

    Source locators, HTML serialization, JSON-LD and visibility diagnostics are
    retained in the document but are not editable rewrite evidence. Send each
    block's text once; never send duplicate chunk text/Markdown or raw DOM paths.
    """
    blocks = {b['block_id']: b for b in document['blocks']}
    metadata = {k: document['source_metadata'].get(k) for k in ('title', 'language', 'description', 'canonical')}

    def serialize(batch):
        ids = [i for chunk in batch for i in chunk['block_ids']]
        chunk_alias = {chunk['chunk_id']: f'c{index:03d}' for index, chunk in enumerate(batch)}
        chunk_for = {i: chunk_alias[chunk['chunk_id']] for chunk in batch for i in chunk['block_ids']}
        payload = {'task': 'Rewrite this entire page in one coordinated proposal for all target queries.', 'scope': 'whole_page', 'target_queries': queries, 'p1_feedback': p1_feedback or {'status': 'unavailable'},
                   'optimization_objective': 'Increase the equal-weight mean P1 score across every distinct target query; avoid per-query regressions. Preserve source evidence even if scores cannot improve.',
                   'editorial_tone': tone, 'allow_structure': allow_structure,
                   'language_policy': {'mode': 'preserve_each_source_block', 'translation_allowed': False, 'target_queries_do_not_set_output_language': True},
                   'snapshot_id': document['snapshot_id'], 'extraction': document['selection'],
                   'source_metadata': metadata, 'heading_outline': document.get('outline', []),
                   'chunks': [{**{k: chunk[k] for k in ('order', 'block_ids', 'heading_path')}, 'chunk_id': chunk_alias[chunk['chunk_id']]} for chunk in batch],
                   'edit_boundary': 'Return edits only for IDs in editable_blocks. Never return edits for read_only_context. Read-only content may supply evidence from the same original chunk but must remain unchanged.',
                   'editable_blocks': [], 'read_only_context': []}
        for identity in ids:
            block = blocks[identity]
            item = {k: block.get(k) for k in ('block_id', 'order', 'parent_id', 'type', 'text', 'heading_level')}
            item['chunk_id'] = chunk_for[identity]
            if editable(block):
                item['source_language_hint'] = confident_language(block['text'])
            payload['editable_blocks' if editable(block) else 'read_only_context'].append(item)
        data = json.dumps(payload, ensure_ascii=False)
        count = len(encoding.encode(PROMPT + data + json.dumps(response_schema(document, batch, allow_structure)))) + 256
        # Estimate space if each editable block receives one ordinary edit.
        # Output remains strictly capped, and incomplete output never applies.
        output_estimate = 256
        for chunk in batch:
            for identity in chunk['block_ids']:
                b = blocks[identity]
                if editable(b):
                    template = {'snapshot_id': document['snapshot_id'], 'chunk_id': chunk['chunk_id'],
                                'block_id': identity, 'before': b['text'], 'after': b['text'],
                                'reason': 'Source-supported rephrasing across the target query set.',
                                'evidence': [{'snapshot_id': document['snapshot_id'], 'block_id': identity, 'quote': b['text']}],
                                'review_flags': [], 'heading_level': None}
                    output_estimate += len(encoding.encode(json.dumps(template, ensure_ascii=False))) + 64
        return batch, data, count, output_estimate

    request = serialize(chunks)
    if request[2] + settings.output_tokens > settings.context_tokens:
        raise RewriteFailure('context_limit', f'Whole page needs {request[2]} input tokens + {settings.output_tokens} output reserve; budget is {settings.context_tokens}. No source or queries were truncated and no call was made.')
    return [request]


def rewrite(document, chunks, query, tone, allow_structure, *, client=None, settings=None, model=None, p1_feedback=None):
    queries = list(dict.fromkeys([query] if isinstance(query, str) else query))
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
                'Human review required: evidence passages are copied by the backend from model-selected block IDs; this does not prove factual entailment.',
                'Markdown content proposal; source HTML/CSS is not patched.'], **extra}
    try:
        settings = settings or Settings.from_env(model)
        telemetry['model'] = settings.model
        reasoning = {'reasoning': {'effort': 'low'}} if settings.model in ('gpt-5-mini', 'gpt-5-nano') else {}
        telemetry['reasoning_effort'] = 'low' if reasoning else None
        if document['selection']['status'] == 'source_insufficient' or not chunks or not any(editable(b) and b['type']=='paragraph' for b in document['blocks']):
            raise RewriteFailure('source_insufficient', 'Insufficient editable source prose; choose a fuller source snapshot.')
        try:
            encoding = tiktoken.encoding_for_model(settings.model)
            telemetry['tokenizer'] = encoding.name
        except KeyError:
            # Explicit conservative fallback for unknown model aliases.
            encoding = tiktoken.get_encoding('o200k_base')
            telemetry['tokenizer'] = 'o200k_base (fallback; verify model compatibility)'
        blocks = {b['block_id']: b for b in document['blocks']}
        requests = plan_requests(document, chunks, queries, tone, allow_structure, settings, encoding, p1_feedback)
        telemetry.update(budgeted_input_tokens=sum(r[2] for r in requests),
                         planned_calls=len(requests), original_chunks=len(chunks),
                         context_tokens=settings.context_tokens, output_reserve_tokens=settings.output_tokens)
        if client is None:
            if not os.environ.get('OPENAI_API_KEY'):
                raise RewriteFailure('missing_credentials', 'Set OPENAI_API_KEY on the backend to generate a real draft.')
            client = OpenAI(timeout=settings.timeout, max_retries=0)
        edits, summaries = [], []
        for batch, data, _, _ in requests:
            if not any(editable(blocks[i]) for chunk in batch for i in chunk['block_ids']):
                telemetry['skipped_protected_batches'] = telemetry.get('skipped_protected_batches', 0) + 1
                continue
            schema = response_schema(document, batch, allow_structure)
            telemetry['calls'] += 1
            response = client.responses.create(model=settings.model, instructions=PROMPT,
                input=[{'role': 'user', 'content': data}], store=False, max_output_tokens=settings.output_tokens,
                text={'format': {'type': 'json_schema', 'name': 'rewrite_proposal', 'strict': True, 'schema': schema}}, **reasoning)
            if response.usage:
                telemetry['input_tokens'] += response.usage.input_tokens
                telemetry['output_tokens'] += response.usage.output_tokens
            else:
                telemetry['usage_complete'] = False
            if any(getattr(c, 'type', '') == 'refusal' for o in response.output for c in getattr(o, 'content', [])):
                raise RewriteFailure('refused', 'The model refused this rewrite.')
            if response.status != 'completed':
                raise RewriteFailure('incomplete_output', 'The model did not complete its output; no partial draft applied.')
            provider_proposal, duplicates = parse_provider_proposal(response.output_text, document)
            telemetry['normalized_duplicate_keys'] = duplicates
            proposal = assemble_proposal(provider_proposal, document, chunks)
            accumulated_flags.extend(proposal.review_flags)
            accumulated_flags.extend(f for e in proposal.edits for f in e.review_flags)
            batch_ids = {chunk['chunk_id'] for chunk in batch}
            if any(edit.chunk_id not in batch_ids for edit in proposal.edits):
                raise RewriteFailure('invalid_output', 'Edit references a chunk outside this request batch.')
            for chunk in batch:
                chunk_proposal = proposal.model_copy(update={'edits': [edit for edit in proposal.edits if edit.chunk_id == chunk['chunk_id']]})
                validate_edits(chunk_proposal, document, chunk, allow_structure)
            changed = [edit for edit in proposal.edits if edit.after.strip() != edit.before.strip()
                       or (edit.heading_level is not None and edit.heading_level != blocks[edit.block_id]['heading_level'])]
            telemetry['ignored_unchanged_edits'] = telemetry.get('ignored_unchanged_edits', 0) + len(proposal.edits) - len(changed)
            for edit in changed:
                language = compare_language(blocks[edit.block_id]['text'], edit.after)
                if language['status'] == 'changed':
                    raise RewriteFailure('invalid_output',
                        f'Block {edit.block_id} changed language from {language["source_language"]} to {language["proposed_language"]}; no draft applied.',
                        {'edit_block_id': edit.block_id, 'checks_failed': ['language_changed'], **language})
                if language['status'] == 'unverified':
                    edit.review_flags.append('language_preservation_unverified')
                    telemetry['language_unverified_edits'] = telemetry.get('language_unverified_edits', 0) + 1
            if telemetry.get('language_unverified_edits'):
                accumulated_flags.append('Language preservation could not be verified for short, mixed or ambiguous edits; review required.')
            edits.extend(changed)
            summaries.append(proposal.summary)
        if len({e.block_id for e in edits}) != len(edits):
            raise RewriteFailure('invalid_output', 'Duplicate edits across chunks.')
        if not any(blocks[e.block_id]['type']=='paragraph' for e in edits):
            raise RewriteFailure('abstained', 'Model supplied no substantive body edits; source may not answer the target queries.')
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
        if exc.details:
            telemetry['validation_error'] = exc.details
        return finish(exc.status, exc.message)
    except ValidationError as exc:
        telemetry['validation_error'] = {'checks_failed': ['schema_validation'], 'fields': [{'location': list(e['loc']), 'type': e['type']} for e in exc.errors()]}
        return finish('invalid_output', 'Invalid structured proposal; no draft applied.')
    except (ValueError, TypeError):
        return finish('invalid_output', 'Invalid model output or server rewrite configuration; no draft applied.')
    except APIError as exc:
        telemetry['usage_complete'] = False
        known_codes = {'invalid_json_schema', 'rate_limit_exceeded', 'insufficient_quota', 'context_length_exceeded', 'invalid_request_error', 'model_not_found'}
        code = getattr(exc, 'code', None)
        telemetry['provider_error'] = {'type': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None),
                                       'code': code if code in known_codes else None}
        # Only safe diagnostic categories are logged; never raw provider bodies or source text.
        import logging
        logging.getLogger('uvicorn.error').warning('Rewrite provider failure: %s', json.dumps(telemetry['provider_error']))
        if getattr(exc, 'code', None) == 'model_not_found':
            return finish('model_unavailable', f'The server credentials cannot access {settings.model}. Choose another model or configure credentials with model access; no draft applied.')
        return finish('api_error', 'OpenAI request failed or timed out. Check server configuration and retry; no draft applied.')
