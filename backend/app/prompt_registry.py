"""Immutable model-specific editorial prompts and explicit local promotion."""
from pathlib import Path
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2] / 'prompt-registry'
BASE = Path(__file__).parent / 'prompts/rewrite-page-v7.txt'
CONTRACT = 'rewrite-page-v7'
LOCK = threading.RLock()


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
        self.models = json.loads((ROOT / 'models.json').read_text())['models']

    def baseline(self, model):
        if model not in self.models:
            raise ValueError('No baseline registered for model')
        return self._record(model, self.editorial, f'{model}--{CONTRACT}', None, [])

    def _record(self, model, text, identity, run, parents):
        effective = text + '\n\n' + self.fixed
        return {'id': identity, 'model': model, 'run_id': run, 'parents': parents,
                'baseline_id': f'{model}--{CONTRACT}', 'contract_version': CONTRACT,
                'contract_hash': digest(self.fixed), 'editorial_strategy': text,
                'effective_prompt': effective, 'prompt_hash': digest(effective),
                'mutable_hash': digest(text), 'characters': len(text)}

    def create(self, model, text, run, parents, multiplier=1.5):
        self.baseline(model)
        if not isinstance(text, str) or not text.strip() or len(text) > len(self.editorial) * multiplier:
            raise ValueError('Candidate editorial length exceeds bound or is empty')
        identity = f'{model}--{digest(text)[:24]}'
        record = {**self._record(model, text, identity, run, parents),
                  'length_multiplier': multiplier, 'created_at': datetime.now(timezone.utc).isoformat()}
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
        if identity != f"{model}--{digest(record['editorial_strategy'])[:24]}":
            raise ValueError('Prompt content identity changed')
        expected = self._record(model, record['editorial_strategy'], identity, record['run_id'], record['parents'])
        if any(record.get(k) != v for k, v in expected.items()) or len(record['editorial_strategy']) > len(self.editorial) * record['length_multiplier']:
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
