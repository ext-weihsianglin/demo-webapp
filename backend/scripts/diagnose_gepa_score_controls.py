"""Replay saved faithful validation controls through the real rewrite/scoring path.

Run from the repository root; provider calls are embeddings only.
"""
import argparse
import os,sys,json
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import numpy as np
sys.path.insert(0,str(Path('backend').resolve()))
from app.gepa.datasets import load_dataset
from app.extraction import extract_document
from app.rewriting import rewrite
from app.scoring import score_document,_load_model
from app.embeddings import semantic_features
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from trad_ml_scorer import robust_features as features
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live-embeddings',action='store_true')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--cache-root',default=os.getenv('EMBEDDING_CACHE_ROOT'))
args=parser.parse_args()
if not args.live_embeddings:
 parser.error('--live-embeddings explicitly enables bounded embedding cache misses')
if args.output.exists():
 parser.error('Choose a fresh output path; historical reports are immutable')
if not args.cache_root:
 parser.error('Set --cache-root or EMBEDDING_CACHE_ROOT to the shared embedding store')
os.environ['EMBEDDING_CACHE_ROOT']=args.cache_root
os.environ['P1_ENABLE_LIVE_EMBEDDINGS']='1'
os.environ['P1_MAX_EMBEDDING_REQUESTS']='32'
controls=json.loads(Path('verification/gepa-fidelity-v4-live-controls-v1.json').read_text())
data=load_dataset('validation-90-v2')
pages={p['snapshot_id']:p for p in data['pages']}
model=Path('backend/data/scoring/model.joblib'); st=model.stat(); bundle=_load_model(str(model.resolve()),st.st_size,st.st_mtime_ns)
report={'diagnostic_only':True,'source_controls':'verification/gepa-fidelity-v4-live-controls-v1.json','rewrite_provider_calls':0,'judge_calls':0,'heldout_calls':0,'cases':[],'limits':['These small faithful paraphrases are sensitivity controls, not an achievable-score ceiling or GEPA superiority proof.','Judge acceptance of saved controls is bounded evidence, not factual certification.']}
for c in controls['cases']:
 if 'control' not in c['case']:continue
 assert c['result']['status']=='passed'
 page=pages[c['snapshot_id']]; doc,chunks=extract_document(page['content'],page['format'],page['href'],page['hostname'])
 edits={e['source_id']:e for e in c['changes']}
 class Replay:
  def __init__(self):self.responses=self
  def create(self,**kw):
   payload=json.loads(kw['input'][0]['content'])
   body={'status':'proposed','summary':'Saved faithful sensitivity control.','review_flags':[], 'blocks':{b['block_id']:None for b in payload['editable_blocks']}}
   for identity,e in edits.items():
    body['blocks'][identity]={'after':e['after'],'reason':'Saved faithful paraphrase control.','evidence':[{'block_id':r['block_id']} for r in e['evidence']],'review_flags':[],'heading_level':None}
   return SimpleNamespace(status='completed',output=[],output_text=json.dumps(body),usage=SimpleNamespace(input_tokens=0,output_tokens=0))
 out=rewrite(doc,chunks,page['queries'],'Preserve original',False,client=Replay())
 assert out['status']=='succeeded',out['status']
 before=score_document(doc,page['content'],page['format'],page['queries']); after=score_document(out['document'],page['content'],page['format'],page['queries'])
 assert before['status']==after['status']=='scored',(before['status'],after['status'])
 matrices=[]
 for document in (doc,out['document']):
  d=deepcopy(document); d['scorer_source_word_count']=len(words(source_inventory(page['content'],d['source']['href'],page['format'])['body_text']))
  sem,_=semantic_features(d,page['queries'])
  rows=[{**features.robust_features(q,d),**s} for q,s in zip(page['queries'],sem)]
  matrices.append(np.array([[r[n] for n in bundle['feature_names']] for r in rows]))
 changes=[]
 for i,name in enumerate(bundle['feature_names']):
  delta=matrices[1][:,i]-matrices[0][:,i]
  if np.any(delta!=0):changes.append({'name':name,'max_abs_delta':float(np.max(np.abs(delta))),'mean_delta':float(np.mean(delta))})
 result={'case':c['case'],'page_id':page['snapshot_id'],'hostname':page['hostname'],'role':page['role'],'edit_count':len(edits),'original_mean':before['mean_score'],'control_mean':after['mean_score'],'mean_delta':after['mean_score']-before['mean_score'],'per_query':[{'query':b['query'],'delta':a['score']-b['score']} for b,a in zip(before['per_query'],after['per_query'])],'changed_features':changes,'unchanged_feature_count':55-len(changes),'embedding_before':before['embedding'],'embedding_after':after['embedding']}
 report['cases'].append(result); args.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({k:result[k] for k in ('case','original_mean','control_mean','mean_delta','unchanged_feature_count')}),flush=True)
