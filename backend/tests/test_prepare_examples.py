"""Exercise host-query joins across shards without touching the frozen dataset."""
import hashlib
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest
from preprocessing.schema import snapshot_identity

spec = importlib.util.spec_from_file_location('prepare_examples', Path(__file__).resolve().parents[1]/'scripts/prepare_examples.py')
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_all_host_records_deduplicated_with_provenance_and_hashes(tmp_path, monkeypatch):
    root = tmp_path/'research';(root/'data/raw').mkdir(parents=True)
    (root/'data/evaluation').mkdir();(root/'evaluation/extraction').mkdir(parents=True)
    content = '# Frozen page\n\nOriginal evidence remains unchanged.'
    href = 'https://heldout.example/selected'
    payload_hash, identity = snapshot_identity(content, href)
    (root/f'data/evaluation/{identity}.txt').write_text(content)
    (root/f'data/evaluation/{identity}.source.json').write_text(json.dumps({'title':'Frozen page'}))
    connection = duckdb.connect()
    connection.execute('CREATE TABLE raw (prompt VARCHAR, href VARCHAR, hostname VARCHAR, html_content VARCHAR)')
    rows = [('First query?', href, 'heldout.example', content),
            *[(f'Query number {i}?', f'https://heldout.example/{i}', 'heldout.example', content) for i in range(1,5)]]
    connection.executemany('INSERT INTO raw VALUES (?, ?, ?, ?)', rows)
    first = root/'data/raw/first.parquet';connection.execute('COPY raw TO ? (FORMAT PARQUET)',[str(first)])
    connection.execute('DELETE FROM raw')
    second = root/'data/raw/second.parquet'
    rows = [('  First query? ', 'https://heldout.example/other', 'heldout.example', content),
            ('', 'https://heldout.example/blank', 'heldout.example', content),
            *[(f'Query number {i}?', f'https://heldout.example/{i}', 'heldout.example', content) for i in range(5,8)],
            ('Development query?', 'https://dev.example/page', 'dev.example', 'Development snapshot differs.')]
    connection.executemany('INSERT INTO raw VALUES (?, ?, ?, ?)', rows)
    connection.execute('COPY raw TO ? (FORMAT PARQUET)',[str(second)]);connection.close()
    manifest = {'snapshots':[
        {'snapshot_id':identity, 'payload_hash':payload_hash, 'href':href,'hostname':'heldout.example','format':'markdown','split':'heldout','source_file':'data/raw/first.parquet','source_file_hash':hashlib.sha256(first.read_bytes()).hexdigest(),'source_row':0},
        {'snapshot_id':'a'*64,'payload_hash':'c'*64,'hostname':'dev.example','split':'dev','source_file':'data/raw/second.parquet','source_file_hash':hashlib.sha256(second.read_bytes()).hexdigest()}]}
    manifest['manifest_hash'] = hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    (root/'evaluation/extraction/manifest.json').write_text(json.dumps(manifest))
    output = tmp_path/'bundle';module.prepare(root,output)
    listing = json.loads((output/'catalog.json').read_text());example = listing['examples'][0]
    assert listing['bundle_version'] == 2 and example['query_record_count'] == 10
    assert example['queries'] == ['First query?', *[f'Query number {i}?' for i in range(1,8)]]
    assert example['unusable_query_count'] == 1 and len(example['query_records']) == 10
    assert example['query_records'][5]['href'].endswith('/other')
    assert (output/f'{identity}.txt').read_text() == content
    from app.examples import catalog
    from fastapi import HTTPException
    monkeypatch.setenv('CONTENT_EXAMPLES_DIR',str(output))
    assert catalog()['examples'][0]['queries'] == example['queries']
    example['queries'][0] = 'Tampered catalog query?'
    (output/'catalog.json').write_text(json.dumps(listing))
    with pytest.raises(HTTPException) as failure:
        catalog()
    assert failure.value.status_code == 503
    with pytest.raises(ValueError,match='already exists'):
        module.prepare(root,output)
    second.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='parquet hash mismatch'):
        module.prepare(root,tmp_path/'tampered-bundle')
