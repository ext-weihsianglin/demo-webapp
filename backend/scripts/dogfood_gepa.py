"""Opt-in paired held-out comparisons through the actual Content Studio API."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.prompt_registry import atomic_json


def request(base, path, body):
    started=time.monotonic()
    query=urllib.request.Request(base.rstrip('/')+'/api/'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(query,timeout=330) as response:
            return response.status,json.load(response),round(time.monotonic()-started,3)
    except urllib.error.HTTPError as response:
        # Non-JSON proxy errors fail explicitly; no retries or hidden mock fallback.
        return response.code,json.load(response),round(time.monotonic()-started,3)


def evaluate(base, example, protocol, candidate_id, artifacts):
    identity=example['snapshot_id']
    code,original,_=request(base,'analyze',{'example_id':identity})
    if code!=200 or original['p1']['status']!='scored' or original['source_origin']['split']!='test':
        raise ValueError('Held-out original score/test provenance unavailable')
    atomic_json(artifacts/(identity+'-original.json'),original)
    baseline_id=protocol['baseline_prompt_id']
    rows=[]
    for repeat in range(protocol['repetitions']):
        order=[('baseline',baseline_id),('candidate',candidate_id)]
        if repeat%2: order.reverse()
        for kind,prompt_id in order:
            code,result,elapsed=request(base,'draft',{'example_id':identity,'model':protocol['model'],'prompt_id':prompt_id})
            atomic_json(artifacts/(identity+f'-{repeat}-{kind}.json'),{'http_status':code,'response':result})
            body=result if code==200 else result.get('detail',{})
            if not isinstance(body,dict): raise ValueError('Unexpected draft failure envelope')
            succeeded=code==200 and body.get('status')=='succeeded'
            if succeeded:
                if body['fidelity']['status']!='passed' or body['telemetry']['prompt_id']!=prompt_id:
                    raise ValueError('Draft gate/prompt identity mismatch')
                if body['target_queries']!=original['target_queries'] or body['p1_after']['status']!='scored':
                    raise ValueError('Draft score/query contract mismatch')
                after=body['p1_after']
            else:
                if body.get('status') not in ('fidelity_rejected','fidelity_unavailable','abstained','invalid_output','unsupported_output','incomplete_output','api_error','refused','source_insufficient','context_limit'):
                    raise ValueError('Unclassified failure; no invented fallback score')
                after=original['p1']
            rows.append({'kind':kind,'repeat':repeat,'hostname':example['hostname'],'snapshot_id':identity,
                         'http_status':code,'status':body.get('status'),'fidelity_status':body.get('fidelity',{}).get('status'),
                         'prompt_id':prompt_id,'prompt_hash':body.get('telemetry',{}).get('prompt_hash'),
                         'latency_seconds':elapsed,'failed':not succeeded and body.get('status')!='abstained',
                         'retained_original':not succeeded,'mean_p1':after['mean_score'],
                         'original_mean_p1':original['p1']['mean_score'],'query_count':len(original['target_queries']),
                         'per_query':[{'query':b['query'],'original':b['score'],'after':a['score'],'delta':a['score']-b['score']}
                                      for b,a in zip(original['p1']['per_query'],after['per_query'])],
                         'rewrite_usage':body.get('telemetry'), 'fidelity_usage':body.get('fidelity',{}).get('telemetry')})
    return rows


def run(protocol_path, candidate_id, base, output, artifacts):
    if output.exists() or artifacts.exists(): raise ValueError('Choose fresh output/artifact paths')
    protocol=json.loads(protocol_path.read_text())
    artifacts.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=[row for batch in pool.map(lambda example:evaluate(base,example,protocol,candidate_id,artifacts),protocol['examples']) for row in batch]
    totals={}
    for kind in ('baseline','candidate'):
        selected=[r for r in rows if r['kind']==kind]
        totals[kind]={'mean_p1':sum(r['mean_p1'] for r in selected)/len(selected),
                      'failure_rate':sum(r['failed'] for r in selected)/len(selected),
                      'accepted':sum(not r['retained_original'] for r in selected),'attempts':len(selected)}
    page_deltas=[]
    for example in protocol['examples']:
        means={kind:sum(r['mean_p1'] for r in rows if r['kind']==kind and r['snapshot_id']==example['snapshot_id'])/protocol['repetitions'] for kind in totals}
        page_deltas.append({**example,**means,'candidate_minus_baseline':means['candidate']-means['baseline']})
    report={'created_at':datetime.now(timezone.utc).isoformat(),'protocol':protocol,'candidate_id':candidate_id,
            'api':base,'rows':rows,'totals':totals,'page_deltas':page_deltas,
            'candidate_minus_baseline':totals['candidate']['mean_p1']-totals['baseline']['mean_p1'],
            'bounded_check_passed':totals['candidate']['mean_p1']>totals['baseline']['mean_p1'] and totals['candidate']['failure_rate']<=totals['baseline']['failure_rate'],
            'interpretation':'Predeclared two-host, two-repeat dogfood; not general superiority, factual certification or citation uplift.'}
    atomic_json(output,report)
    print(json.dumps({'report':str(output),'totals':totals,'candidate_minus_baseline':report['candidate_minus_baseline'],'bounded_check_passed':report['bounded_check_passed']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--candidate-id',required=True)
    parser.add_argument('--api',default='http://127.0.0.1:3000')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    args=parser.parse_args()
    if not args.live: parser.error('--live is required to enable provider calls')
    run(args.protocol,args.candidate_id,args.api,args.output,args.artifacts)
