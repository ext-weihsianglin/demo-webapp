"""Exact local explanations for the frozen logistic-regression P1 scorer."""
import math

import numpy as np

from trad_ml_scorer.semantic_features import NAMES


VERSION = 'p1-linear-explanation-v1'
FIXED_METADATA = frozenset({
    'title_similarity', 'log_title_words', 'empty_title', 'has_jsonld', 'has_article_schema',
})
SOURCE_DIAGNOSTICS = frozenset({
    'log_source_script_count', 'retained_text_fraction', 'needs_review',
    'possible_error_response', 'sparse_body', 'format_html',
})


def _raw_feature(term):
    return str(term).removeprefix('missingindicator_')


def _metadata(term):
    raw = _raw_feature(term)
    missing = str(term).startswith('missingindicator_')
    if raw == 'path_similarity' or raw.startswith('path_'):
        family, role = 'fixed_url', 'fixed'
    elif raw.startswith('prompt_') or raw == 'log_prompt_words':
        family, role = 'prompt_context', 'fixed'
    elif raw in FIXED_METADATA:
        family, role = 'fixed_metadata', 'fixed'
    elif raw in SOURCE_DIAGNOSTICS:
        family, role = 'source_context', 'diagnostic'
    elif raw in NAMES:
        family, role = 'semantic_similarity', 'editable'
    else:
        family, role = 'document_context', 'editable'
    return {'term': str(term), 'raw_feature': raw,
            'label': raw.replace('_', ' ').capitalize() + (' · missing' if missing else ''),
            'kind': 'missing_indicator' if missing else 'value',
            'family': family, 'rewrite_role': role}


def _optional(value):
    value = float(value)
    return value if math.isfinite(value) else None


def _require_close(actual, expected, message, tolerance=1e-10):
    if not np.allclose(actual, expected, atol=tolerance, rtol=0):
        raise ValueError(message)


def build_basis(bundle, matrix, probabilities, identity):
    """Capture exact raw/transformed rows behind already-computed P1 scores."""
    matrix = np.asarray(matrix, dtype=float)
    pipeline = bundle['pipeline']
    imputed = pipeline[0].transform(matrix)
    transformed = pipeline[:-1].transform(matrix)
    names = [str(name) for name in pipeline[:-1].get_feature_names_out(bundle['feature_names'])]
    coefficients = np.asarray(pipeline[-1].coef_[0], dtype=float)
    if transformed.shape[1] != len(names) or len(names) != len(coefficients):
        raise ValueError('P1 transformed feature contract mismatch')
    logits = np.asarray(pipeline.decision_function(matrix), dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    expected = 1 / (1 + np.exp(-logits))
    _require_close(probabilities, expected, 'P1 probability accounting mismatch', 1e-12)
    contributions = transformed * coefficients
    intercept = float(pipeline[-1].intercept_[0])
    _require_close(intercept + contributions.sum(axis=1), logits, 'P1 logit accounting mismatch')
    return {
        'identity': identity,
        'raw_names': list(bundle['feature_names']),
        'term_names': names,
        'coefficients': coefficients,
        'intercept': intercept,
        'raw': matrix,
        'imputed': imputed,
        'transformed': transformed,
        'contributions': contributions,
        'logits': logits,
        'probabilities': probabilities,
    }


def compare_basis(before, after, queries):
    """Return a JSON-safe exact explanation for the same ordered queries."""
    for key in ('identity', 'raw_names', 'term_names'):
        if before[key] != after[key]:
            raise ValueError('P1 explanations require the same frozen feature contract')
    if before['raw'].shape != after['raw'].shape or before['raw'].shape[0] != len(queries):
        raise ValueError('P1 explanations require one before/after row per query')
    if not np.array_equal(before['coefficients'], after['coefficients']):
        raise ValueError('P1 explanations require identical model weights')
    term_meta = [_metadata(term) for term in before['term_names']]
    raw_indices = {name: index for index, name in enumerate(before['raw_names'])}
    delta = after['contributions'] - before['contributions']
    delta_logits = after['logits'] - before['logits']
    _require_close(delta.sum(axis=1), delta_logits, 'P1 rewrite-effect accounting mismatch')
    per_query = []
    for row, query in enumerate(queries):
        terms = []
        for column, meta in enumerate(term_meta):
            raw_index = raw_indices[meta['raw_feature']]
            raw_before = _optional(before['raw'][row, raw_index])
            raw_after = _optional(after['raw'][row, raw_index])
            terms.append({
                **meta,
                'raw_before': raw_before,
                'raw_after': raw_after,
                'raw_delta': raw_after - raw_before if raw_before is not None and raw_after is not None else None,
                'raw_missing_before': raw_before is None,
                'raw_missing_after': raw_after is None,
                'imputed_before': float(before['imputed'][row, column]),
                'imputed_after': float(after['imputed'][row, column]),
                'standardized_before': float(before['transformed'][row, column]),
                'standardized_after': float(after['transformed'][row, column]),
                'contribution_before': float(before['contributions'][row, column]),
                'contribution_after': float(after['contributions'][row, column]),
                'delta_log_odds': float(delta[row, column]),
            })
        per_query.append({
            'query_index': row, 'query': query,
            'before_logit': float(before['logits'][row]),
            'after_logit': float(after['logits'][row]),
            'delta_logit': float(delta_logits[row]),
            'terms': terms,
        })
    aggregate = []
    for column, meta in enumerate(term_meta):
        values = delta[:, column]
        aggregate.append({
            **meta,
            'mean_delta_log_odds': float(values.mean()),
            'max_abs_delta_log_odds': float(np.abs(values).max()),
            'positive_query_count': int(np.sum(values > 1e-12)),
            'negative_query_count': int(np.sum(values < -1e-12)),
        })
    return {
        'version': VERSION,
        **before['identity'],
        'space': 'log_odds',
        'intercept': before['intercept'],
        'global_terms': [{**meta, 'coefficient': float(coefficient)}
                         for meta, coefficient in zip(term_meta, before['coefficients'])],
        'per_query': per_query,
        'aggregate_terms': aggregate,
        'interpretation': 'Exact frozen-model arithmetic. Model weights and rewrite effects are not causal importance, factual verification or citation uplift.',
    }
