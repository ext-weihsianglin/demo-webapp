"""Frozen upstream P1 features on the original or proposed structured document.

Only the pinned, trusted model is deserialized. Never load models from requests.
Original source inventory stays fixed when scoring a proposal; do not reparse its
Markdown as a new snapshot or change metadata to inflate a score.
"""
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import preprocessing
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from trad_ml_scorer import robust_features as features
from trad_ml_scorer.feature_dependencies import feature_group
from trad_ml_scorer.semantic_features import NAMES
from app.embeddings import EmbeddingUnavailable, EMBEDDING_IDENTITY, semantic_features

MODEL_SHA256 = '2ff334173b83364fb49685fcdca7339f71b1c88bcef154d71e0a21d595587d6b'
FEATURE_VERSION = 'lr-semantic-v7'
SERVING_POLICY = 'markdownify-context-v1'
INTERPRETATION = 'P1 v7 experimental classifier: sampled within-host top class among already-cited pages. Not citation probability, factual verification or causal uplift. Context features use current Markdownify documents; frozen-training parser mismatch is deferred in upstream issue #15.'
OBJECTIVE = 'Equal-weight mean across distinct usable target queries. Review every per-query regression.'


@lru_cache(maxsize=2)
def _load_model(path, size, mtime):
    # Verify bytes before joblib deserialization (which can execute code).
    model_path = Path(path)
    payload = model_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != MODEL_SHA256:
        raise ValueError('Frozen P1 model hash mismatch')
    bundle = joblib.load(BytesIO(payload))
    if (bundle['version'] != FEATURE_VERSION or bundle['variant'] != 'semantic_context'
            or bundle['serializer_version'] != 'blocks-v3-markdownify'
            or bundle['embedding_model']['embedding_identity'] != EMBEDDING_IDENTITY
            or bundle['feature_names'][:10] != NAMES or len(bundle['feature_names']) != 55
            or any(feature_group(name) not in ('prompt', 'doc') for name in bundle['feature_names'][10:])):
        raise ValueError('Unsupported P1 feature contract')
    root = Path(preprocessing.__file__).resolve().parent.parent
    provenance = json.loads((Path(__file__).resolve().parents[1] / 'packages/provenance-v2.json').read_text())
    for filename, expected in provenance['module_sha256'].items():
        if not filename.endswith('.py'):
            continue
        local = root / filename
        if hashlib.sha256(local.read_bytes()).hexdigest() != expected:
            raise ValueError('P1 parser or feature fingerprint mismatch')
    return bundle


def score_document(document, content, format, queries, *, provider=None, cache_root=None, before_call=None, on_embedding=None):
    common = {'feature_version': FEATURE_VERSION, 'model_sha256': MODEL_SHA256,
              'serving_policy': SERVING_POLICY, 'context_contract_issue': 'https://github.com/ext-weihsianglin/content-optimization-system/issues/15',
              'interpretation': INTERPRETATION, 'objective': OBJECTIVE,
              'query_count': len(queries), 'unique_query_count': len(set(queries))}
    if document['selection']['status'] == 'source_insufficient' or not document['blocks']:
        return {**common, 'status': 'source_insufficient', 'summary': 'No retained source to score.', 'per_query': []}
    path = Path(os.getenv('P1_MODEL_PATH', Path(__file__).resolve().parents[1] / 'data/scoring/model.joblib'))
    if not path.is_file():
        return {**common, 'status': 'unavailable', 'summary': 'Install the pinned P1 v7 semantic_context model to measure scores. No mock scores substituted.', 'per_query': []}
    try:
        # Cache by path + modification identity, checking the model bytes on cache misses.
        stat = path.stat()
        bundle = _load_model(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        doc = deepcopy(document)
        inventory = source_inventory(content, document['source']['href'], format)
        doc['scorer_source_word_count'] = len(words(inventory['body_text']))
        semantics, telemetry = semantic_features(doc, queries, provider=provider, cache_root=cache_root, before_call=before_call, on_telemetry=on_embedding)
        rows = [{**features.robust_features(query, doc), **semantic} for query, semantic in zip(queries, semantics)]
        matrix = np.array([[row[name] for name in bundle['feature_names']] for row in rows], dtype=float)
        probabilities = bundle['pipeline'].predict_proba(matrix)[:, 1]
        results = [{'query_index': i, 'query': query, 'score': float(probabilities[i])}
                   for i, query in enumerate(queries)]
        return {**common, 'status': 'scored', 'per_query': results, 'embedding': telemetry,
                'mean_score': float(np.mean(probabilities)), 'min_score': float(np.min(probabilities)),
                'max_score': float(np.max(probabilities))}
    except EmbeddingUnavailable as error:
        return {**common, 'status': 'unavailable', 'reason': error.status, 'embedding': error.telemetry,
                'summary': 'P1 embedding inputs unavailable. Cache misses require explicitly enabled live embeddings; no scores substituted.', 'per_query': []}
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
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
