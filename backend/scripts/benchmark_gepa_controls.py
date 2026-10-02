"""Score fixed reflection-only editorial controls, retaining every gate outcome.

Run from the repository root. --live enables judge and embedding calls, never P2
generation. Controls are diagnostic edits, not an optimized prompt or a ceiling.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction import extract_document
from app.fidelity import check_fidelity
from app.gepa.datasets import load_dataset
from app.gepa.runs import fidelity_profile
from app.rewriting import rewrite
from app.scoring import score_document


class Replay:
    """Supply fixed edits through actual proposal/schema validation, without P2."""
    def __init__(self, edits):
        self.edits = deepcopy(edits)
        self.responses = self

    def create(self, **request):
        payload = json.loads(request['input'][0]['content'])
        slots = {b['block_id']: None for b in payload['editable_blocks']}
        for edit in self.edits:
            assert edit['block_id'] in slots
            slots[edit['block_id']] = {
                'after': edit['after'], 'reason': 'Fixed answer-first control.',
                'evidence': [{'block_id': edit['block_id']}],
                'review_flags': [], 'heading_level': None,
            }
        body = {'status': 'proposed', 'summary': 'Fixed editorial control.',
                'review_flags': [], 'blocks': slots}
        return SimpleNamespace(status='completed', output=[],
                               output_text=json.dumps(body),
                               usage=SimpleNamespace(input_tokens=0, output_tokens=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live explicitly enables judge and embedding calls')
    if args.output.exists():
        parser.error('Choose a fresh output; historical reports are immutable')
    os.environ['EMBEDDING_CACHE_ROOT'] = args.cache_root
    os.environ['P1_ENABLE_LIVE_EMBEDDINGS'] = '1'
    os.environ['P1_MAX_EMBEDDING_REQUESTS'] = '32'
    payload = args.controls.read_bytes()
    controls = json.loads(payload)
    dataset = load_dataset(controls['dataset_id'])
    pages = {p['snapshot_id']: p for p in dataset['pages']}
    # Validate all roles and exact before texts before any provider dispatch.
    prepared = []
    for case in controls['cases']:
        page = pages[case['page_id']]
        assert page['role'] == 'reflection' and page['hostname'] == case['hostname']
        document, chunks = extract_document(page['content'], page['format'],
                                            page['href'], page['hostname'])
        blocks = {b['block_id']: b for b in document['blocks']}
        assert all(blocks[e['block_id']]['text'] == e['before'] for e in case['edits'])
        prepared.append((case, page, document, chunks))
    report = {'diagnostic_only': True, 'controls_sha256': hashlib.sha256(payload).hexdigest(),
              'dataset_manifest_hash': dataset['manifest_hash'],
              'fidelity_profile': fidelity_profile(), 'rewrite_provider_calls': 0,
              'heldout_calls': 0, 'complete': False, 'cases': [],
              'limits': ['Fixed manual edits are not a learned prompt or an attainable ceiling.',
                         'No retries, omitted outcomes or revisions based on scores.',
                         'A passed LLM judge is not factual verification.']}
    for case, page, document, chunks in prepared:
        outcome = rewrite(document, chunks, page['queries'], 'Preserve original',
                          False, client=Replay(case['edits']))
        row = {'hostname': case['hostname'], 'page_id': case['page_id'],
               'role': page['role'], 'edits': case['edits'],
               'rewrite_validation_status': outcome['status']}
        if outcome['status'] == 'succeeded':
            gate = check_fidelity(document, outcome['changes'])
            row['fidelity'] = gate
            before = score_document(document, page['content'], page['format'], page['queries'])
            row['original'] = before
            after = before
            if gate['status'] == 'passed':
                after = score_document(outcome['document'], page['content'], page['format'], page['queries'])
            row['after'] = after
            row['applied'] = gate['status'] == 'passed' and after['status'] == 'scored'
            if before['status'] == after['status'] == 'scored':
                row['mean_delta'] = after['mean_score'] - before['mean_score']
                row['per_query'] = [{'query': b['query'], 'before': b['score'],
                                     'after': a['score'], 'delta': a['score'] - b['score']}
                                    for b, a in zip(before['per_query'], after['per_query'])]
        report['cases'].append(row)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'hostname': row['hostname'], 'gate': row.get('fidelity', {}).get('status'),
                          'mean_delta': row.get('mean_delta')}), flush=True)
    report['complete'] = True
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
