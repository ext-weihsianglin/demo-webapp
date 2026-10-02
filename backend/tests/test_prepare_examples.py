"""Test-only selection and provenance checks against a tiny saved corpus."""
import gzip
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest
from preprocessing.api import parse_snapshot
from preprocessing.schema import snapshot_identity, stable_hash
from representations.storage import file_hash

spec = importlib.util.spec_from_file_location('prepare_examples', Path(__file__).resolve().parents[1]/'scripts/prepare_examples.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


@pytest.fixture
def corpus(tmp_path):
    root, splits, raw = (tmp_path / name for name in ('corpus', 'splits', 'raw'))
    for folder in (root / 'documents', splits, raw):
        folder.mkdir(parents=True)
    connection = duckdb.connect()
    connection.execute('CREATE TABLE raw (prompt VARCHAR, href VARCHAR, hostname VARCHAR, html_content VARCHAR)')
    observations = []
    for host, split in (('test.example', 'test'), ('train.example', 'train'), ('val.example', 'validation')):
        content = f'<main><h1>{host}</h1><p>Original qualified evidence for {host} remains intact.</p></main>'
        observations.extend((f'Query {i}?' if i else 'First query?', f'https://{host}/{i}', host, content, split) for i in range(10))
    connection.executemany('INSERT INTO raw VALUES (?, ?, ?, ?)', [r[:4] for r in observations])
    path = raw / 'sources.parquet'
    connection.execute('COPY raw TO ? (FORMAT PARQUET)', [str(path)]); connection.close()
    records, assignments = [], []
    for index, (query, href, host, content, split) in enumerate(observations):
        payload_hash, identity = snapshot_identity(content, href)
        doc, _ = parse_snapshot(content, href, host, source_format='html')
        doc['extraction'] = {'run_identity': 'fixture'}
        doc['extraction']['content_hash'] = stable_hash(doc)
        destination = root / 'documents' / f'{identity}.json.gz'
        with gzip.open(destination, 'wt') as stream:
            json.dump(doc, stream)
        row = {'source_file': path.name, 'source_file_hash': file_hash(path), 'source_row': index,
            'snapshot_id': identity, 'payload_hash': payload_hash, 'href': href, 'hostname': host,
            'prompt': query, 'document_path': str(destination.relative_to(root))}
        records.append(row)
        assignments.append({**row, 'split': split, 'extraction_status': 'selected'})
    (root / 'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    (root / 'manifest.json').write_text(json.dumps({'status': 'complete', 'pipeline_version': 'retention-markdownify-corpus-v1',
        'run_identity': 'fixture', 'artifacts': [{'path': 'records.jsonl', 'sha256': file_hash(root/'records.jsonl')}]}))
    (splits / 'joined_records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in assignments))
    (splits / 'manifest.json').write_text(json.dumps({'version': 'lr-semantic-v7',
        'joined_records_sha256': file_hash(splits/'joined_records.jsonl'),
        'corpus_hashes': {'manifest.json': file_hash(root/'manifest.json')}}))
    return root, splits, raw


def test_only_test_hosts_served_with_full_query_provenance(corpus, tmp_path, monkeypatch):
    output = tmp_path/'bundle'
    module.prepare(*corpus, output)
    listing = json.loads((output/'catalog.json').read_text())
    assert listing['bundle_version'] == 3
    assert [r['hostname'] for r in listing['examples']] == ['test.example']
    example = listing['examples'][0]
    assert example['split'] == example['p1_split'] == 'test'
    assert len(example['query_records']) == len(example['queries']) == 10
    assert (output/f"{example['snapshot_id']}.txt").is_file()
    from app.examples import catalog
    monkeypatch.setenv('CONTENT_EXAMPLES_DIR', str(output))
    assert catalog()['examples'] == listing['examples']
    with pytest.raises(ValueError, match='already exists'):
        module.prepare(*corpus, output)
    (corpus[2]/'sources.parquet').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='parquet hash mismatch'):
        module.prepare(*corpus, tmp_path/'tampered')


def test_changed_split_manifest_rejected(corpus, tmp_path):
    (corpus[1]/'joined_records.jsonl').write_text('{}\n')
    with pytest.raises(ValueError, match='split record checksum'):
        module.prepare(*corpus, tmp_path/'bundle')
