"""Repeatable exploratory baseline; live calls require --live. No citation uplift grading."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction import extract_document
from app.examples import load_example
from app.rewriting import rewrite, PROMPT_VERSION


def checks(original, result, sample):
    if result['status'] != 'succeeded':
        return {'failure': result['status'], 'factual_support': 'not measured', 'omission': 'not measured', 'query_usefulness': 'not measured'}
    new = result['document']; original_by_id={b['block_id']:b for b in original['blocks']}
    changed={e['block_id'] for e in result['changes']}
    text=' '.join(b['text'] for b in new['blocks']).lower()
    return {
        'valid_evidence_quotes': all(e['evidence'] for e in result['changes']),
        'factual_support': 'Exact quote/reference validation passed; human entailment review required.',
        'omission_proxy_missing_terms': [q for q in sample.get('qualifiers',[]) if q.lower() not in text],
        'query_usefulness_proxy_terms_present': {q:q.lower() in text for q in sample.get('query_terms',[])},
        'substantive_body_edit_count': sum(original_by_id[i]['type']=='paragraph' for i in changed),
        'structure_preserved': [(b['block_id'],b['parent_id'],b['type'],b['heading_level']) for b in original['blocks']]==[(b['block_id'],b['parent_id'],b['type'],b['heading_level']) for b in new['blocks']],
        'unchanged_blocks_preserved': all(b==original_by_id[b['block_id']] for b in new['blocks'] if b['block_id'] not in changed),
        'metadata_preserved': original['source_metadata']==new['source_metadata'],
        'citation_uplift': 'Not measured; mock grades and relative labels are not citation uplift.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--example-id');parser.add_argument('--example-query');parser.add_argument('--only-example',action='store_true');parser.add_argument('--output',default='evaluation/baseline-report.json');parser.add_argument('--samples',default='evaluation/samples.json');args=parser.parse_args()
    samples=json.loads(Path(args.samples).read_text())['samples']
    if args.only_example:
        samples=[]
    if args.example_id:
        samples.append({'id':'extraction-heldout-'+args.example_id,**load_example(args.example_id)})
    if args.example_query and args.example_id:
        samples[-1]['query']=args.example_query
    report={'prompt_version':PROMPT_VERSION,'live_enabled':args.live,'quality_scope':'Exploratory baseline; lexical proxies are not quality grades. Human review required. No measured citation uplift.','runs':[]}
    for sample in samples:
        document,chunks=extract_document(sample['content'],sample['format'],sample['href'],sample['hostname']); before=deepcopy(document)
        if args.live:
            result=rewrite(document,chunks,sample['query'],'Preserve original',False)
        else:
            result={'status':'not_run','summary':'Pass --live to enable OpenAI calls. Stub tests do not measure rewrite quality.'}
        report['runs'].append({'sample':sample,'snapshot_id':document['snapshot_id'],'original_document':before,'result':result,'checks':checks(before,result,sample),'input_unchanged':before==document})
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'report':str(path),'statuses':[r['result']['status'] for r in report['runs']]}))
    return 0 if all(r['result']['status']=='succeeded' for r in report['runs']) else 1

if __name__=='__main__': sys.exit(main())
