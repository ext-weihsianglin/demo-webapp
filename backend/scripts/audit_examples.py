"""Reproduce mechanical diagnostics without changing the frozen examples or parser."""
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.examples import catalog, load_example
from app.main import Source, analyze
from app.extraction import UPSTREAM


def audit():
    listing = catalog()
    counts = Counter()
    summaries = Counter()
    documents = []
    for item in listing['examples']:
        result = analyze(Source(example_id=item['snapshot_id'], query=item['query']))
        verification = result['verification']
        summary = verification['summary']
        counts.update(summary['source_status_counts'])
        summaries.update({key: value for key, value in summary.items() if isinstance(value, int)})
        documents.append({'snapshot_id': item['snapshot_id'], 'hostname': item['hostname'],
                          'summary': summary, 'failed_checks': [check['name'] for check in verification['checks'] if not check['passed']],
                          'comparison_review_blocks': [identity for identity, evidence in verification['blocks'].items() if evidence['status'] == 'text_mismatch'],
                          'hidden_source_hints': sum(any(hint.startswith('Hidden-source') for hint in evidence['review_hints']) for evidence in verification['blocks'].values()),
                          'oversized_chunk_ids': [chunk['chunk_id'] for chunk in result['chunks'] if chunk['oversized']]})
    return {'audit_version': 'source-audit-v1', 'parser': UPSTREAM, 'manifest_hash': listing.get('manifest_hash'),
            'scope': 'Development diagnostics on extraction held-out snapshots; not a human gold evaluation, factual verification or coverage proof.',
            'documents_count': len(documents), 'summary': dict(summaries), 'source_status_counts': dict(counts), 'documents': documents}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
