"""Immutable model-specific editorial prompts and explicit local promotion."""
from pathlib import Path
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2] / 'prompt-registry'
BASE = Path(__file__).parent / 'prompts/rewrite-page-v7.txt'
CONTRACT = 'rewrite-page-v7'
PROCEDURE_CONTRACT = 'query-procedure-v1'
LOCK = threading.RLock()


class ReflectionTraceReference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: str = Field(pattern=r'^[a-zA-Z0-9._-]+$')
    artifact: str = Field(pattern=r'^reflection-input-[0-9]+$')


class OptimizationContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rationale: str = Field(min_length=1,max_length=2000)
    reflection_model: str = Field(min_length=1,max_length=100)
    reflection_instruction_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    reflection_trace: ReflectionTraceReference


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class PromptRegistry:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv('PROMPT_REGISTRY_ROOT', ROOT))
        self.text = BASE.read_text()
        self.editorial, self.fixed = self.text.split('\n\n', 1)
        contract = json.loads((ROOT / 'contracts/rewrite-page-v7/manifest.json').read_text())
        if digest(self.text) != contract['baseline_sha256'] or digest(self.fixed) != contract['fixed_sha256']:
            raise ValueError('Prompt fixed contract changed')
        self.procedure_contract = json.loads((ROOT / 'contracts' / PROCEDURE_CONTRACT / 'manifest.json').read_text())
        if self.procedure_contract['version'] != PROCEDURE_CONTRACT or self.procedure_contract['fixed_sha256'] != digest(self.fixed):
            raise ValueError('Procedure fixed contract changed')
        self.models = json.loads((ROOT / 'models.json').read_text())['models']

    def baseline(self, model):
        if model not in self.models:
            raise ValueError('No baseline registered for model')
        return self._record(model, self.editorial, f'{model}--{CONTRACT}', None, [])

    def _record(self, model, text, identity, run, parents, optimization_context=None):
        effective = text + '\n\n' + self.fixed
        context = ({'optimization_context':optimization_context} if optimization_context is not None else {})
        context_text = json.dumps(optimization_context,sort_keys=True) if context else ''
        return {'id': identity, 'model': model, 'run_id': run, 'parents': parents,
                'baseline_id': f'{model}--{CONTRACT}', 'contract_version': CONTRACT,
                'contract_hash': digest(self.fixed), 'editorial_strategy': text,
                'effective_prompt': effective, 'prompt_hash': digest(effective + context_text),
                'mutable_hash': digest(text), 'characters': len(text), **context}

    def create(self, model, text, run, parents, multiplier=1.5, *, character_limit=None, optimization_context=None):
        self.baseline(model)
        if character_limit is not None and (type(character_limit) is not int or not 1000 <= character_limit <= 16000):
            raise ValueError('Procedure length limit must be 1,000–16,000 characters')
        limit = character_limit if character_limit is not None else len(self.editorial) * multiplier
        if not isinstance(text, str) or not text.strip() or len(text) > limit:
            raise ValueError('Candidate editorial length exceeds bound or is empty')
        component = ({'component_contract':PROCEDURE_CONTRACT,'character_limit':character_limit}
                     if character_limit is not None else {})
        if optimization_context is not None:
            if not component or not isinstance(optimization_context,dict):
                raise ValueError('Optimization context requires a procedure contract')
            optimization_context = OptimizationContext.model_validate(optimization_context).model_dump()
            component['optimization_context'] = optimization_context
        content_identity = json.dumps({'text':text, **component},sort_keys=True) if component else text
        identity = f"{model}--{'procedure--' if component else ''}{digest(content_identity)[:24]}"
        record = {**self._record(model, text, identity, run, parents, optimization_context),
                  **component, 'length_multiplier': multiplier, 'created_at': datetime.now(timezone.utc).isoformat()}
        with LOCK:
            path = self.root / 'p2' / model / 'candidates' / identity / 'prompt.json'
            if path.exists():
                return self.resolve(identity, model)
            atomic_json(path, record)
        return record

    def resolve(self, identity, model):
        baseline = self.baseline(model)
        if identity is None:
            path = self.root / 'p2' / model / 'selected.json'
            if not path.exists():
                return baseline
            pointer = json.loads(path.read_text())
            selected = self.resolve(pointer['id'], model)
            if pointer.get('prompt_hash') != selected['prompt_hash']:
                raise ValueError('Selected prompt pointer changed')
            return selected
        if identity == baseline['id']:
            return baseline
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', identity) or not identity.startswith(model + '--'):
            raise ValueError('Prompt is incompatible with model')
        path = self.root / 'p2' / model / 'candidates' / identity / 'prompt.json'
        if not path.is_file():
            raise ValueError('Unknown prompt ID')
        record = json.loads(path.read_text())
        component = record.get('component_contract')
        if component is not None:
            limit = record['character_limit']
            if component != PROCEDURE_CONTRACT or type(limit) is not int or not 1000 <= limit <= 16000:
                raise ValueError('Prompt artifact changed or component contract mismatch')
            if 'optimization_context' in record:
                OptimizationContext.model_validate(record['optimization_context'])
            content_identity = json.dumps({'text':record['editorial_strategy'],
                'component_contract':component,'character_limit':limit,
                **({'optimization_context':record['optimization_context']} if 'optimization_context' in record else {})},sort_keys=True)
            expected_id = f'{model}--procedure--{digest(content_identity)[:24]}'
        else:
            limit = len(self.editorial) * record['length_multiplier']
            expected_id = f"{model}--{digest(record['editorial_strategy'])[:24]}"
        if identity != expected_id:
            raise ValueError('Prompt content identity changed')
        expected = self._record(model, record['editorial_strategy'], identity, record['run_id'], record['parents'], record.get('optimization_context'))
        if any(record.get(k) != v for k, v in expected.items()) or len(record['editorial_strategy']) > limit:
            raise ValueError('Prompt artifact changed or contract mismatch')
        return record

    def catalog(self, model):
        baseline = self.baseline(model)
        entries = [baseline]
        for path in sorted((self.root / 'p2' / model / 'candidates').glob('*/prompt.json')):
            try:
                entries.append(self.resolve(path.parent.name, model))
            except (ValueError, KeyError, OSError):
                continue
        selected = self.resolve(None, model)['id']
        return {'model': model, 'selected_id': selected, 'prompts': [
            {k: r[k] for k in ('id', 'model', 'prompt_hash', 'baseline_id', 'run_id', 'contract_version')} |
            {'kind': 'baseline' if r['id'] == baseline['id'] else 'experimental', 'selected': r['id'] == selected}
            for r in entries]}

    def promote(self, identity, model):
        record = self.resolve(identity, model)
        with LOCK:
            atomic_json(self.root / 'p2' / model / 'selected.json', {'id': record['id'], 'prompt_hash': record['prompt_hash']})
        return record
