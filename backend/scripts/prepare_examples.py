"""Build test-only examples from the completed corpus and frozen P1 assignments."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import duckdb
from preprocessing.corpus import read_document, validate_document
from preprocessing.schema import snapshot_identity
from representations.storage import file_hash


def prepare(corpus: Path, split_root: Path, raw_root: Path, output: Path, *, split="test", row_filter=None):
    if output.exists():
        raise ValueError('Output already exists; choose a fresh bundle path.')
    manifest = json.loads((corpus / 'manifest.json').read_text())
    if manifest.get('status') != 'complete' or manifest.get('pipeline_version') != 'retention-markdownify-corpus-v1':
        raise ValueError('Require a completed Markdownify corpus')
    split_manifest = json.loads((split_root / 'manifest.json').read_text())
    split_path = split_root / 'joined_records.jsonl'
    split_hash = file_hash(split_path)
    if split_hash != split_manifest['joined_records_sha256']:
        raise ValueError('P1 split record checksum mismatch')
    if file_hash(corpus / 'manifest.json') != split_manifest['corpus_hashes']['manifest.json']:
        raise ValueError('Corpus differs from frozen P1 input')
    records_path = corpus / 'records.jsonl'
    expected = next(a['sha256'] for a in manifest['artifacts'] if a['path'] == 'records.jsonl')
    if file_hash(records_path) != expected:
        raise ValueError('Corpus record checksum mismatch')
    with records_path.open() as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    by_key = {(r['source_file_hash'], r['source_row']): r for r in records}
    if len(by_key) != len(records):
        raise ValueError('Duplicate corpus row identity')
    hosts, eligible = {}, defaultdict(list)
    with split_path.open() as stream:
        for line in stream:
            if not line.strip():
                continue
            assignment = json.loads(line)
            row = by_key[(assignment['source_file_hash'], assignment['source_row'])]
            row_split = assignment['split']
            if row_split not in ('train', 'validation', 'test') or row['snapshot_id'] != assignment['snapshot_id']:
                raise ValueError('Invalid P1 row assignment')
            host = row['hostname']
            if host in hosts and hosts[host] != row_split:
                raise ValueError('P1 host overlaps splits')
            hosts[host] = row_split
            if row_split == split and assignment['extraction_status'] in ('selected', 'needs_review'):
                eligible[host].append(row)
    test_payloads = {row['payload_hash'] for rows in eligible.values() for row in rows}
    other_payloads = {row['payload_hash'] for row in records if hosts.get(row['hostname']) in ({'train', 'validation', 'test'} - {split})}
    if test_payloads & other_payloads:
        raise ValueError('P1 test payload overlaps train/validation')
    host_records = defaultdict(list)
    for row in records:
        if row['hostname'] in eligible:
            host_records[row['hostname']].append(row)
    selected = []
    for host, rows in sorted(eligible.items()):
        usable = [r for r in rows if isinstance(r['prompt'], str) and 3 <= len(r['prompt'].strip()) <= 1000 and (row_filter is None or row_filter(r))]
        if usable:
            selected.append(min(usable, key=lambda r: (r['source_file'], r['source_row'])))
    verified = set()
    connection = duckdb.connect()
    examples, payloads = [], []
    try:
        for row in selected:
            path = raw_root / Path(row['source_file']).name
            if path not in verified:
                if file_hash(path) != row['source_file_hash']:
                    raise ValueError('Source parquet hash mismatch')
                verified.add(path)
            raw = connection.execute('SELECT prompt, href, hostname, html_content FROM read_parquet(?, file_row_number=true) WHERE file_row_number = ?',
                [str(path), row['source_row']]).fetchone()
            if raw is None or raw[1:3] != (row['href'], row['hostname']):
                raise ValueError('Original source row mismatch')
            payload = raw[3]
            payload_hash, identity = snapshot_identity(payload, row['href'])
            if identity != row['snapshot_id'] or payload_hash != row['payload_hash']:
                raise ValueError('Original snapshot hash mismatch')
            doc = read_document(corpus / row['document_path'])
            validate_document(doc, identity, payload_hash, manifest['run_identity'])
            queries = []
            for observation in sorted(host_records[row['hostname']], key=lambda r: (r['source_file'], r['source_row'])):
                query = (observation['prompt'] or '').strip()
                queries.append({'query': query, 'href': observation['href'], 'source_file': observation['source_file'],
                    'source_file_hash': observation['source_file_hash'], 'source_row': observation['source_row'],
                    'usable': 3 <= len(query) <= 1000})
            if len(queries) != 10:
                raise ValueError('Expected ten original observations per test host')
            examples.append({'snapshot_id': identity, 'payload_hash': payload_hash, 'href': row['href'],
                'source_file': row['source_file'], 'source_file_hash': row['source_file_hash'],
                'source_row': row['source_row'], 'document_path': row['document_path'],
                'hostname': row['hostname'], 'format': doc['source']['format'], 'split': split, 'p1_split': split,
                'title': doc['source_metadata'].get('title') or row['href'], 'query': raw[0], 'characters': len(payload),
                'queries': list(dict.fromkeys(q['query'] for q in queries if q['usable'])), 'query_records': queries,
                'query_scope': 'host', 'query_record_count': len(queries), 'unusable_query_count': sum(not q['usable'] for q in queries),
                'query_set_hash': hashlib.sha256(json.dumps(queries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()})
            payloads.append((identity, payload))
    finally:
        connection.close()
    output.mkdir(parents=True)
    for identity, payload in payloads:
        (output / f'{identity}.txt').write_text(payload)
    (output / 'catalog.json').write_text(json.dumps({'bundle_version': 3,
        'manifest_hash': file_hash(corpus / 'manifest.json'), 'p1_split_hash': split_hash,
        'p1_version': split_manifest['version'], 'examples': examples}, indent=2) + '\n')
    print(f'Prepared {len(examples)} P1-{split}-only examples in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', required=True, type=Path)
    parser.add_argument('--split-root', required=True, type=Path)
    parser.add_argument('--raw-root', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/examples')
    args = parser.parse_args()
    prepare(args.corpus, args.split_root, args.raw_root, args.output)
