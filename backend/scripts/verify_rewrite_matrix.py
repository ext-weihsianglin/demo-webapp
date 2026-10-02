"""Explicit live compatibility checks on immutable extraction-held-out examples."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib
from pathlib import Path
import sys
from openai import OpenAI
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.examples import load_example
from app.extraction import extract_document
from app.rewriting import rewrite, Settings, PROMPT_VERSION, PROMPT, SUPPORTED_REWRITE_MODELS
from app.scoring import score_document, compare_scores


def verify(sample, document, chunks, before, model, artifacts):
    settings = Settings(model=model)
    class CapturedClient:
        def __init__(self):
            self.responses = self
            self.client = OpenAI(timeout=settings.timeout, max_retries=0)
        def create(self, **kwargs):
            response = self.client.responses.create(**kwargs)
            if artifacts:
                (artifacts / f'{sample["snapshot_id"]}-{model}-provider.json').write_text(json.dumps({'output_text': response.output_text, 'status': response.status}, ensure_ascii=False))
            return response
    result = rewrite(document, chunks, sample['queries'], 'Preserve original', False,
                     settings=settings, client=CapturedClient(), p1_feedback=before)
    if artifacts:
        (artifacts / f'{sample["snapshot_id"]}-{model}.json').write_text(json.dumps(result, ensure_ascii=False))
    row = {'snapshot_id': sample['snapshot_id'], 'hostname': sample['hostname'],
           'payload_hash': sample['payload_hash'], 'query_count': len(sample['queries']),
           'model': model, 'status': result['status'], 'telemetry': result['telemetry'],
           'change_count': len(result.get('changes', []))}
    if result['status'] != 'succeeded':
        row['summary'] = result['summary']
        return row
    source = {b['block_id']: b for b in document['blocks']}
    changed = {e['block_id'] for e in result['changes']}
    memberships = {i: c['chunk_id'] for c in chunks for i in c['block_ids']}
    proposed = result['document']
    row['checks'] = {
        'one_call': result['telemetry']['calls'] == 1,
        'unique_edits': len(changed) == len(result['changes']),
        'unchanged_blocks_exact': all(b == source[b['block_id']] for b in proposed['blocks'] if b['block_id'] not in changed),
        'metadata_exact': proposed['source_metadata'] == document['source_metadata'],
        'structure_exact': [(b['block_id'], b['parent_id'], b['type'], b['heading_level']) for b in proposed['blocks']] == [(b['block_id'], b['parent_id'], b['type'], b['heading_level']) for b in document['blocks']],
        'original_before_exact': all(e['before'] == source[e['block_id']]['text'] for e in result['changes']),
        'evidence_exact_same_chunk': all(q['quote'] == source[q['block_id']]['text'] and q['snapshot_id'] == document['snapshot_id'] and memberships[q['block_id']] == e['chunk_id'] == memberships[e['block_id']] for e in result['changes'] for q in e['evidence']),
        'body_edit': any(source[i]['type'] == 'paragraph' for i in changed),
    }
    if not all(row['checks'].values()):
        row['status'] = 'verification_failed'
    after = score_document(proposed, sample['content'], sample['format'], sample['queries'])
    row['p1_comparison'] = compare_scores(before, after)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--example-id', action='append', required=True)
    parser.add_argument('--model', action='append', choices=SUPPORTED_REWRITE_MODELS, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--artifacts-dir')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error('Choose a fresh output path; existing evidence is never overwritten.')
    artifacts = Path(args.artifacts_dir) if args.artifacts_dir else None
    if artifacts:
        artifacts.mkdir(parents=True, exist_ok=False)
    prepared = []
    for identity in dict.fromkeys(args.example_id):
        sample = load_example(identity)
        document, chunks = extract_document(sample['content'], sample['format'], sample['href'], sample['hostname'])
        before = score_document(document, sample['content'], sample['format'], sample['queries'])
        prepared.append((sample, document, chunks, before))
    report = {'prompt_version': PROMPT_VERSION, 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(), 'live': True, 'scope': 'Exploratory checks of extraction-held-out examples; not a reserved P2 quality benchmark.', 'runs': []}
    with output.open('x') as handle:
        json.dump(report, handle)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(verify, *prepared_sample, model, artifacts) for prepared_sample in prepared for model in dict.fromkeys(args.model)]
        for job in as_completed(jobs):
            row = job.result()
            report['runs'].append(row)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
            print(json.dumps({k: row[k] for k in ('hostname', 'model', 'status', 'change_count', 'telemetry')}), flush=True)
    return 0 if all(r['status'] == 'succeeded' for r in report['runs']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
