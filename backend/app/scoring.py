"""Frozen upstream P1 features on the original or proposed structured document.

Only the pinned, trusted model is deserialized. Never load models from requests.
Original source inventory stays fixed when scoring a proposal; do not reparse its
Markdown as a new snapshot or change metadata to inflate a score.
"""
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import hashlib
import os
from pathlib import Path

import joblib
import numpy as np
import preprocessing
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from trad_ml_scorer import retention_features as features

MODEL_SHA256 = 'f78ca1f8e51f147a5b52a16cafed6819d165f18eff8bf6e0f5ed61cf5c918b92'
INTERPRETATION = 'Frozen P1 v2: sampled within-host top class among already-cited pages. Not citation probability, factual verification or causal uplift. Extraction-held-out does not imply P1-test-held-out.'
OBJECTIVE = 'Equal-weight mean across distinct usable target queries. Review every per-query regression.'


@lru_cache(maxsize=2)
def _load_model(path, size, mtime):
    # Verify bytes before joblib deserialization (which can execute code).
    model_path = Path(path)
    payload = model_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != MODEL_SHA256:
        raise ValueError('Frozen P1 model hash mismatch')
    bundle = joblib.load(BytesIO(payload))
    if (bundle['feature_version'] != features.FEATURE_VERSION
            or bundle['parser_policy'] != features.PARSER_POLICY
            or bundle['feature_names'] != features.FEATURE_NAMES):
        raise ValueError('Unsupported P1 feature contract')
    root = Path(preprocessing.__file__).resolve().parent.parent
    checked = set()
    for filename, expected in bundle['parser_hashes'].items():
        if filename.startswith('preprocessing/'):
            local = root / filename
        elif filename.endswith('retention_features.py'):
            local = Path(features.__file__)
        else:
            continue
        if hashlib.sha256(local.read_bytes()).hexdigest() != expected:
            raise ValueError('P1 parser or feature fingerprint mismatch')
        checked.add(local.resolve())
    required = {root / name for name in ('preprocessing/schema.py', 'preprocessing/blocks.py',
                'preprocessing/quality.py', 'preprocessing/select.py', 'preprocessing/downstream.py',
                'preprocessing/adapters/local.py')}
    required.add(Path(features.__file__).resolve())
    if not required.issubset(checked):
        raise ValueError('Incomplete P1 parser fingerprints')
    return bundle


def score_document(document, content, format, queries):
    common = {'feature_version': features.FEATURE_VERSION, 'model_sha256': MODEL_SHA256,
              'interpretation': INTERPRETATION, 'objective': OBJECTIVE,
              'query_count': len(queries), 'unique_query_count': len(set(queries))}
    if document['selection']['status'] == 'source_insufficient' or not document['blocks']:
        return {**common, 'status': 'source_insufficient', 'summary': 'No retained source to score.', 'per_query': []}
    path = Path(os.getenv('P1_MODEL_PATH', Path(__file__).resolve().parents[1] / 'data/scoring/model.joblib'))
    if not path.is_file():
        return {**common, 'status': 'unavailable', 'summary': 'Install the pinned P1 v2 model to measure scores. No mock scores substituted.', 'per_query': []}
    try:
        # Cache by path + modification identity, checking the model bytes on cache misses.
        stat = path.stat()
        bundle = _load_model(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        doc = deepcopy(document)
        inventory = source_inventory(content, document['source']['href'], format)
        doc['scorer_source_word_count'] = len(words(inventory['body_text']))
        rows = [features.features_from_document(query, doc) for query in queries]
        matrix = np.array([[row[name] for name in bundle['feature_names']] for row in rows], dtype=float)
        probabilities = bundle['pipeline'].predict_proba(matrix)[:, 1]
        results = [{'query_index': i, 'query': query, 'score': float(probabilities[i])}
                   for i, query in enumerate(queries)]
        return {**common, 'status': 'scored', 'per_query': results,
                'mean_score': float(np.mean(probabilities)), 'min_score': float(np.min(probabilities)),
                'max_score': float(np.max(probabilities))}
    except (ValueError, KeyError, TypeError, OSError):
        return {**common, 'status': 'unavailable', 'summary': 'P1 model or feature validation failed. No mock scores substituted.', 'per_query': []}


def compare_scores(before, after):
    if before['status'] != 'scored' or after['status'] != 'scored':
        return {'status': 'unavailable', 'summary': 'Before/after P1 scores could not both be measured.'}
    if [r['query'] for r in before['per_query']] != [r['query'] for r in after['per_query']]:
        raise ValueError('P1 comparisons require the same ordered query observations')
    results = [{**b, 'before': b['score'], 'after': a['score'], 'delta': a['score'] - b['score']}
               for b, a in zip(before['per_query'], after['per_query'])]
    return {'status': 'scored', 'objective': OBJECTIVE, 'per_query': results,
            'mean_before': before['mean_score'], 'mean_after': after['mean_score'],
            'mean_delta': after['mean_score'] - before['mean_score'],
            'regression_count': sum(r['delta'] < -1e-9 for r in results),
            'improvement_count': sum(r['delta'] > 1e-9 for r in results)}
