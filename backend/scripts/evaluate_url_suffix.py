"""Cache-only P1 evaluation; predeclared partitions; fresh artifacts only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction import extract_document
from app.rewriting import Proposal
from app.url_proposals import POLICY, body_view, experiment
from app.scoring import MODEL_SHA256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['development', 'validation', 'final'], required=True)
    parser.add_argument('--final', action='store_true', help='Acknowledge policy is frozen; do not tune on final outputs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.split == 'final' and not args.final:
        parser.error('Final evaluation requires --final after freezing policy')
    if args.output.exists():
        parser.error('Use a fresh output path; frozen reports cannot be overwritten')
    # This harness cannot call a provider even if the shell enables live embeddings.
    os.environ.pop('P1_ENABLE_LIVE_EMBEDDINGS', None)
    declaration = Path(__file__).resolve().parents[1] / 'evaluation/url-suffix/predeclared.json'
    payload = declaration.read_bytes()
    fixtures = json.loads(payload)
    if fixtures['policy'] != POLICY:
        raise ValueError('Predeclared policy mismatch')
    reports = []
    for item in fixtures['examples']:
        if item['split'] != args.split:
            continue
        source = '# ' + item['heading'] + '\n\n' + item['body']
        document, chunks = extract_document(source, 'markdown', item['href'], 'example.com')
        block = next(b for b in document['blocks'] if b['type'] == 'paragraph')
        chunk = next(c for c in chunks if block['block_id'] in c['block_ids'])
        proposal = Proposal(status='proposed', summary='Predeclared diagnostic body edit; not a model-generated draft.', review_flags=[], edits=[{
            'snapshot_id':document['snapshot_id'], 'chunk_id':chunk['chunk_id'], 'block_id':block['block_id'],
            'before':block['text'], 'after':item['body_after'], 'reason':'Predeclared same-topic wording experiment.',
            'evidence':[{'snapshot_id':document['snapshot_id'],'block_id':block['block_id'],'quote':block['text']}],
            'heading_level':None,'review_flags':[]}])
        reports.append({'id':item['id'], **experiment(document, source, 'markdown', item['queries'], body=body_view(document, proposal))})
    result = {'declaration_sha256':hashlib.sha256(payload).hexdigest(), 'policy':POLICY, 'split':args.split,
              'model_sha256':MODEL_SHA256, 'live_calls_enabled':False,
              'interpretation':'Synthetic diagnostic fixtures; no citation measurement, no population-quality conclusion.', 'reports':reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write('\n')
    print(json.dumps({'split':args.split,'examples':len(reports),'scored':sum(r['original']['status']=='scored' for r in reports),'output':str(args.output)}))


if __name__ == '__main__':
    main()
