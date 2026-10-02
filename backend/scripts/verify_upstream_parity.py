"""Bounded offline corpus/parser/semantic parity audit; never calls providers."""
import argparse
import json
import os
from pathlib import Path
import sys

import duckdb
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.embeddings import semantic_features
from app.extraction import extract_document, UPSTREAM
from preprocessing.corpus import read_document, validate_document
from representations.storage import file_hash
from trad_ml_scorer.markdownify_context import FEATURE_ORDER, feature_row
from trad_ml_scorer.predict_markdownify import load_model, predict_document


def verify(corpus, split_root, raw_root, cache_root, output, limit=5):
    if limit < 1:
        raise ValueError('Audit limit must be positive')
    if output.exists():
        raise ValueError('Output exists; preserve prior evidence')
    os.environ['P1_ENABLE_LIVE_EMBEDDINGS'] = '0'
    manifest = json.loads((corpus/'manifest.json').read_text())
    model_manifest = json.loads((split_root/'manifest.json').read_text())
    expected_corpus_hash = model_manifest.get('corpus_manifest_sha256') or model_manifest['corpus_hashes']['manifest.json']
    if file_hash(corpus/'manifest.json') != expected_corpus_hash:
        raise ValueError('Frozen corpus checksum mismatch')
    if file_hash(split_root/'features.npz') != model_manifest['features_sha256']:
        raise ValueError('Frozen semantic feature checksum mismatch')
    if file_hash(split_root/'joined_records.jsonl') != model_manifest['joined_records_sha256']:
        raise ValueError('Frozen row identity checksum mismatch')
    with (corpus/'records.jsonl').open() as stream:
        records = {(r['source_file_hash'], r['source_row']): r for r in map(json.loads, stream)}
    with (split_root/'joined_records.jsonl').open() as stream:
        joined_records = list(map(json.loads, stream))
    with np.load(split_root/'features.npz', allow_pickle=False) as archive:
        lookup = {str(identity): i for i, identity in enumerate(archive['ids'])}
        expected = archive['X'].copy()
        selected = [record for index, record in enumerate(joined_records)
                    if archive['splits'][index] == 'validation'][:limit]
    if not selected:
        raise ValueError('No validation records available')
    model = load_model(split_root/'model.joblib')
    if model['feature_names'] != FEATURE_ORDER or model_manifest['feature_names'] != FEATURE_ORDER:
        raise ValueError('Frozen v7.1 feature order mismatch')
    results, verified = [], set()
    connection = duckdb.connect()
    try:
        for joined in selected:
            row = records[(joined['source_file_hash'], joined['source_row'])]
            path = raw_root / Path(row['source_file']).name
            if path not in verified:
                if file_hash(path) != row['source_file_hash']:
                    raise ValueError('Original raw file checksum mismatch')
                verified.add(path)
            payload = connection.execute('SELECT html_content FROM read_parquet(?, file_row_number=true) WHERE file_row_number = ?',
                [str(path), row['source_row']]).fetchone()[0]
            saved = read_document(corpus / row['document_path'])
            validate_document(saved, row['snapshot_id'], row['payload_hash'], manifest['run_identity'])
            parsed, _ = extract_document(payload, saved['source']['format'], row['href'], row['hostname'])
            fields = ('snapshot_id', 'blocks', 'chunks', 'chunk_ids', 'outline', 'text', 'markdown', 'selection', 'source_metadata', 'representation', 'scorer_source_word_count')
            checks = {field: parsed[field] == saved[field] for field in fields}
            if not all(checks.values()):
                raise ValueError('Online parser differs from saved corpus: ' + ','.join(k for k,v in checks.items() if not v))
            features, telemetry = semantic_features(parsed, [row['prompt']], cache_root=cache_root)
            semantic = features[0]
            actual = feature_row(row['prompt'], parsed, semantic)
            baseline = expected[lookup[joined['record_id']]]
            np.testing.assert_allclose(actual, baseline, atol=1e-6, rtol=0, equal_nan=True)
            expected_score = float(model['pipeline'].predict_proba(baseline.reshape(1, -1))[0, 1])
            actual_score = predict_document(model, row['prompt'], parsed, semantic)
            np.testing.assert_allclose(actual_score, expected_score, atol=1e-6, rtol=0)
            if telemetry['calls']:
                raise ValueError('Parity audit must be cache-only')
            delta = np.abs(actual - baseline)
            results.append({'snapshot_id': row['snapshot_id'], 'record_id': joined['record_id'], 'split': 'validation',
                'parser_checks': checks, 'feature_max_absolute_error': float(np.nanmax(delta)),
                'score': actual_score, 'score_absolute_error': float(abs(actual_score - expected_score)),
                'embedding': telemetry})
    finally:
        connection.close()
    report = {'status': 'passed', 'upstream': UPSTREAM, 'records': results,
        'scope': 'Offline parser, all 55 v7.1 features and canonical prediction; not quality or citation uplift',
        'live_calls': 0, 'corpus_manifest_sha256': file_hash(corpus/'manifest.json')}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Passed offline parser/feature/prediction parity for {len(results)} validation records')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('corpus', 'split-root', 'raw-root', 'cache-root', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    verify(args.corpus, args.split_root, args.raw_root, args.cache_root, args.output, args.limit)
