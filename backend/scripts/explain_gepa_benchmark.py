"""Explain saved control scores using cached features and the trusted frozen P1.

No provider calls: cache misses fail visibly. Run from the repository root.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_gepa_controls import Replay
from app.embeddings import semantic_features
from app.extraction import extract_document
from app.gepa.datasets import load_dataset
from app.rewriting import rewrite
from app.scoring import _load_model
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from trad_ml_scorer import robust_features as features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a fresh output path')
    os.environ['EMBEDDING_CACHE_ROOT'] = args.cache_root
    os.environ['P1_ENABLE_LIVE_EMBEDDINGS'] = '0'
    controls = json.loads(args.controls.read_text())
    benchmark = json.loads(args.benchmark.read_text())
    assert benchmark['complete']
    import hashlib
    assert hashlib.sha256(args.controls.read_bytes()).hexdigest() == benchmark['controls_sha256']
    pages = {p['snapshot_id']: p for p in load_dataset(controls['dataset_id'])['pages']}
    results = {r['page_id']: r for r in benchmark['cases']}
    path = Path(os.getenv('P1_MODEL_PATH', 'backend/data/scoring/model.joblib'))
    stat = path.stat()
    bundle = _load_model(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    pipeline = bundle['pipeline']
    names = bundle['feature_names']
    transformed_names = pipeline[:-1].get_feature_names_out(names)
    coefficients = pipeline[-1].coef_[0]
    report = {'diagnostic_only': True, 'provider_calls': 0,
              'feature_names': names, 'cases': [],
              'limits': ['Additive contributions explain frozen classifier output, not content quality.',
                         'Three fixed reflection controls cannot establish an attainable ceiling.']}

    def no_provider():
        raise AssertionError('Offline diagnostic attempted a provider call')

    for case in controls['cases']:
        page = pages[case['page_id']]
        assert page['role'] == 'reflection'
        saved = results[case['page_id']]
        assert saved['applied']
        document, chunks = extract_document(page['content'], page['format'], page['href'], page['hostname'])
        outcome = rewrite(document, chunks, page['queries'], 'Preserve original', False,
                          client=Replay(case['edits']))
        assert outcome['status'] == 'succeeded'
        matrices = []
        for doc in (document, outcome['document']):
            doc = deepcopy(doc)
            doc['scorer_source_word_count'] = len(words(source_inventory(
                page['content'], doc['source']['href'], page['format'])['body_text']))
            semantics, telemetry = semantic_features(doc, page['queries'], before_call=no_provider)
            assert telemetry['calls'] == 0
            rows = [{**features.robust_features(q, doc), **semantic}
                    for q, semantic in zip(page['queries'], semantics)]
            matrices.append(np.array([[row[name] for name in names] for row in rows]))
        before, after = matrices
        for matrix, scores in ((before, saved['original']), (after, saved['after'])):
            assert np.allclose(pipeline.predict_proba(matrix)[:, 1],
                               [q['score'] for q in scores['per_query']], rtol=0, atol=1e-12)
        transformed_delta = pipeline[:-1].transform(after) - pipeline[:-1].transform(before)
        contributions = transformed_delta * coefficients
        logit_delta = pipeline.decision_function(after) - pipeline.decision_function(before)
        assert np.allclose(contributions.sum(axis=1), logit_delta, rtol=0, atol=1e-12)
        changed = ~np.isclose(before, after, rtol=0, atol=0, equal_nan=True)
        effects = [{'feature': str(name), 'mean_logit_delta': float(values.mean()),
                    'max_abs_logit_delta': float(np.abs(values).max())}
                   for name, values in zip(transformed_names, contributions.T)
                   if np.any(values != 0)]
        effects.sort(key=lambda x: x['max_abs_logit_delta'], reverse=True)
        report['cases'].append({'hostname': page['hostname'], 'page_id': page['snapshot_id'],
                                'query_count': len(page['queries']),
                                'score_reproduced_within': 1e-12,
                                'changed_input_features': [name for name, flag in zip(names, changed.any(axis=0)) if flag],
                                'unchanged_input_count': int((~changed.any(axis=0)).sum()),
                                'mean_logit_delta': float(logit_delta.mean()),
                                'feature_contributions': effects})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([{'hostname': c['hostname'], 'unchanged': c['unchanged_input_count'],
                       'mean_logit_delta': c['mean_logit_delta']} for c in report['cases']]))


if __name__ == '__main__':
    main()
