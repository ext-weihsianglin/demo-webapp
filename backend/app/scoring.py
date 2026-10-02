"""Frozen upstream P1 features on the original or proposed structured document.

Only the pinned, trusted model is deserialized. Never load models from requests.
Original source inventory stays fixed when scoring a proposal; do not reparse its
Markdown as a new snapshot or change metadata to inflate a score.
"""
from copy import deepcopy
from functools import lru_cache
import errno
import hashlib
import os
import sqlite3
from pathlib import Path

import numpy as np
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from trad_ml_scorer.markdownify_context import FEATURE_ORDER, feature_row
from trad_ml_scorer.predict_markdownify import load_model, predict_document
from app.embeddings import EmbeddingUnavailable, EMBEDDING_IDENTITY, semantic_features
from app.p1_explanations import build_basis, compare_basis

MODEL_SHA256 = 'd1c4b25480a1579239b8fd9c8bfa7d3beac11bfa2ec591d8540941b6f89493cc'
FEATURE_VERSION = 'lr-semantic-v7.1'
SERVING_POLICY = 'markdownify-v7.1'
INTERPRETATION = 'P1 v7.1 experimental classifier: sampled within-host top class among already-cited pages. Not citation probability, factual verification or causal uplift. Semantic and context inputs use the same Markdownify feature contract.'
OBJECTIVE = 'Equal-weight mean across distinct usable target queries. Review every per-query regression.'


@lru_cache(maxsize=2)
def _load_model(path, size, mtime):
    # Verify bytes before joblib deserialization (which can execute code).
    model_path = Path(path)
    payload = model_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != MODEL_SHA256:
        raise ValueError('Frozen P1 model hash mismatch')
    bundle = load_model(model_path)
    if (bundle['version'] != FEATURE_VERSION or bundle['variant'] != 'semantic_context'
            or bundle['serializer_version'] != 'blocks-v3-markdownify'
            or bundle['embedding_model']['embedding_identity'] != EMBEDDING_IDENTITY
            or bundle['feature_names'] != FEATURE_ORDER):
        raise ValueError('Unsupported P1 feature contract')
    return bundle


def score_document(document, content, format, queries, *, provider=None, cache_root=None,
                   before_call=None, on_embedding=None, explain=False):
    common = {'feature_version': FEATURE_VERSION, 'model_sha256': MODEL_SHA256,
              'serving_policy': SERVING_POLICY,
              'interpretation': INTERPRETATION, 'objective': OBJECTIVE,
              'query_count': len(queries), 'unique_query_count': len(set(queries))}
    if document['selection']['status'] == 'source_insufficient' or not document['blocks']:
        return {**common, 'status': 'source_insufficient', 'summary': 'No retained source to score.', 'per_query': []}
    path = Path(os.getenv('P1_MODEL_PATH', Path(__file__).resolve().parents[1] / 'data/scoring/model.joblib'))
    if not path.is_file():
        return {**common, 'status': 'unavailable', 'summary': 'Install the pinned P1 v7.1 semantic_context model to measure scores. No mock scores substituted.', 'per_query': []}
    try:
        # Cache by path + modification identity, checking the model bytes on cache misses.
        stat = path.stat()
        bundle = _load_model(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        doc = deepcopy(document)
        inventory = source_inventory(content, document['source']['href'], format)
        doc['scorer_source_word_count'] = len(words(inventory['body_text']))
        semantics, telemetry = semantic_features(doc, queries, provider=provider, cache_root=cache_root, before_call=before_call, on_telemetry=on_embedding)
        matrix = np.stack([feature_row(query, doc, semantic) for query, semantic in zip(queries, semantics)])
        probabilities = np.array([predict_document(bundle, query, doc, semantic)
                                  for query, semantic in zip(queries, semantics)])
        results = [{'query_index': i, 'query': query, 'score': float(probabilities[i])}
                   for i, query in enumerate(queries)]
        result = {**common, 'status': 'scored', 'per_query': results, 'embedding': telemetry,
                  'mean_score': float(np.mean(probabilities)), 'min_score': float(np.min(probabilities)),
                  'max_score': float(np.max(probabilities))}
        if explain:
            identity = {key: result[key] for key in ('feature_version', 'model_sha256', 'serving_policy')}
            result['_explanation_basis'] = build_basis(bundle, matrix, probabilities, identity)
        return result
    except EmbeddingUnavailable as error:
        return {**common, 'status': 'unavailable', 'reason': error.status, 'embedding': error.telemetry,
                'summary': 'P1 embedding inputs unavailable. Cache misses require explicitly enabled live embeddings; no scores substituted.', 'per_query': []}
    except OSError as error:
        reason = 'file_descriptor_limit' if error.errno in (errno.EMFILE, errno.ENFILE) else 'scoring_io_error'
        return {**common, 'status': 'unavailable', 'reason': reason,
                'summary': 'P1 local file access failed; no scores substituted.', 'per_query': []}
    except (ValueError, KeyError, TypeError, sqlite3.Error):
        return {**common, 'status': 'unavailable', 'summary': 'P1 model or feature validation failed. No mock scores substituted.', 'per_query': []}


def compare_scores(before, after):
    if before['status'] != 'scored' or after['status'] != 'scored':
        return {'status': 'unavailable', 'summary': 'Before/after P1 scores could not both be measured.'}
    if [r['query'] for r in before['per_query']] != [r['query'] for r in after['per_query']]:
        raise ValueError('P1 comparisons require the same ordered query observations')
    results = [{**b, 'before': b['score'], 'after': a['score'], 'delta': a['score'] - b['score']}
               for b, a in zip(before['per_query'], after['per_query'])]
    comparison = {'status': 'scored', 'objective': OBJECTIVE, 'per_query': results,
                  'mean_before': before['mean_score'], 'mean_after': after['mean_score'],
                  'mean_delta': after['mean_score'] - before['mean_score'],
                  'regression_count': sum(r['delta'] < -1e-9 for r in results),
                  'improvement_count': sum(r['delta'] > 1e-9 for r in results)}
    if '_explanation_basis' in before and '_explanation_basis' in after:
        try:
            comparison['explanation'] = compare_basis(before['_explanation_basis'], after['_explanation_basis'],
                                                      [row['query'] for row in before['per_query']])
        except (ValueError, KeyError, TypeError):
            comparison['explanation_status'] = 'unavailable'
            comparison['explanation_summary'] = 'P1 scores are available, but their exact explanation failed validation.'
    return comparison


def public_scores(scores):
    """Remove request-local explanation matrices before serialization or prompting."""
    return {key: value for key, value in scores.items() if key != '_explanation_basis'}
