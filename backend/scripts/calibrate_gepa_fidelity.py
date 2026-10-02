"""Opt-in replay of frozen source-audited edits through the served fidelity gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.fidelity import check_fidelity, PROMPT, MODEL
from openai import OpenAI
from app.prompt_registry import atomic_json, digest


def run(fixture, output, workers, timeout_seconds=60):
    if output.exists():
        raise ValueError('Choose a fresh output path')
    raw=fixture.read_bytes()
    data=json.loads(raw)
    cases=data['cases']
    if not 1 <= len(cases) <= 12 or len({c['id'] for c in cases})!=len(cases):
        raise ValueError('Expected 1–12 uniquely identified frozen calibration cases')
    for c in cases:
        if c['provenance']['role']!='reflection':
            raise ValueError('Calibration must not use selection/test examples')
        blocks={b['block_id']:b for b in c['document']['blocks']}
        if blocks[c['change']['source_id']]['text']!=c['change']['before']:
            raise ValueError('Changed original source')
    report={'fixture_sha256':hashlib.sha256(raw).hexdigest(),'scope':data['scope'],
            'model':MODEL,'prompt_hash':digest(PROMPT),'results':[],
            'timeout_seconds':timeout_seconds,'sdk_retries':0,
            'p2_calls':0,'embedding_calls':0,'heldout_calls':0}
    atomic_json(output,report)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(check_fidelity,c['document'],[c['change']],client=OpenAI(timeout=timeout_seconds,max_retries=0)):c for c in cases}
        for future in as_completed(pending):
            c=pending[future]
            result=future.result()
            verdict=result['findings'][0]['verdict'] if result['findings'] else None
            row={'id':c['id'],'group':c['group'],'expected':c['expected'],
                 'saved_verdict':c['saved_finding']['verdict'],'observed':verdict,
                 'matches_assessment':verdict==c['expected'],'result':result}
            report['results'].append(row)
            atomic_json(output,report)
            print(json.dumps({k:row[k] for k in ('id','expected','observed','matches_assessment')}),flush=True)
    report['complete']=True
    report['matches_assessment']=sum(r['matches_assessment'] for r in report['results'])
    report['calls']=sum(r['result']['telemetry']['calls'] for r in report['results'])
    atomic_json(output,report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=3)
    parser.add_argument('--timeout-seconds',type=int,choices=(60,120),default=60)
    args=parser.parse_args()
    if not args.live:parser.error('--live explicitly enables up to 12 fidelity calls')
    run(args.fixture,args.output,args.workers,args.timeout_seconds)
