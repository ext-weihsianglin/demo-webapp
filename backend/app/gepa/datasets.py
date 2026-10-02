"""Hash-verified, immutable GEPA reflection/selection data; never the test catalog."""
import json
import os
import re
from pathlib import Path
from preprocessing.schema import snapshot_identity
from app.extraction import UPSTREAM
from app.prompt_registry import digest
from app.scoring import FEATURE_VERSION, MODEL_SHA256, SERVING_POLICY


def root():
    return Path(os.getenv('GEPA_DATA_ROOT', Path(__file__).resolve().parents[2] / 'data/gepa'))


def manifest_hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':')))


def load_dataset(identity, *, directory=None):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',identity):
        raise ValueError('Invalid dataset ID')
    path = Path(directory or root()/'datasets') / identity
    data = json.loads((path/'manifest.json').read_text())
    expected = data['manifest_hash']
    if manifest_hash({k:v for k,v in data.items() if k!='manifest_hash'}) != expected:
        raise ValueError('Dataset manifest changed')
    if data['upstream'] != UPSTREAM or data['p1'] != {'version':FEATURE_VERSION,'model_sha256':MODEL_SHA256,'serving_policy':SERVING_POLICY}:
        raise ValueError('Dataset frozen parser/scorer incompatible')
    pages = data['pages']
    if len(pages)!=90 or sum(p['role']=='reflection' for p in pages)!=60 or sum(p['role']=='selection' for p in pages)!=30:
        raise ValueError('Dataset must have 60 reflection and 30 selection pages')
    for key in ('hostname','snapshot_id','payload_hash'):
        if len({p[key] for p in pages}) != len(pages):
            raise ValueError('Dataset hosts/snapshots/payloads overlap')
    for page in pages:
        if page['p1_split'] != 'validation' or not re.fullmatch(r'[a-f0-9]{64}',page['snapshot_id']):
            raise ValueError('GEPA requires P1 validation identities')
        records = page['query_records']
        if len(records) != 10:
            raise ValueError('GEPA requires ten original host observations')
        if manifest_hash(records) != page['query_set_hash']:
            # Legacy helper uses the same sorted JSON with ensure_ascii=True.
            import hashlib
            old_hash = hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if old_hash != page['query_set_hash']:
                raise ValueError('Frozen host queries changed')
        queries = list(dict.fromkeys(r['query'].strip() for r in records if r['usable']))
        if page['queries'] != queries or not 1 <= len(queries) <= 20 or any(not 3<=len(q)<=1000 for q in queries):
            raise ValueError('Invalid frozen queries')
        content = (path / (page['snapshot_id']+'.txt')).read_text()
        payload_hash, snapshot_id = snapshot_identity(content,page['href'])
        if payload_hash != page['payload_hash'] or snapshot_id != page['snapshot_id']:
            raise ValueError('Frozen source changed')
        page['content'] = content
    return data


def list_datasets():
    output = []
    for path in sorted((root()/'datasets').glob('*/manifest.json')):
        try:
            data = load_dataset(path.parent.name)
            output.append({'id':data['id'],'manifest_hash':data['manifest_hash'],'reflection':60,'selection':30})
        except (ValueError,KeyError,OSError):
            continue
    return output
