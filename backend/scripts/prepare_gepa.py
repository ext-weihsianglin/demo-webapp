"""Freeze 90 P1-validation hosts, without model calls, as 60/30 GEPA pages."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.prepare_examples import prepare
from preprocessing.corpus import read_document
from app.gepa.datasets import manifest_hash, load_dataset
from app.extraction import extract_document, UPSTREAM
from app.rewriting import Settings, plan_requests, editable
from app.scoring import FEATURE_VERSION, MODEL_SHA256, SERVING_POLICY
import tiktoken


def freeze(corpus, split_root, raw_root, output, seed=0):
    if output.exists():
        raise ValueError('Choose a fresh dataset path')
    excluded = []
    encoding = tiktoken.get_encoding('o200k_base')
    def eligible(row):
        doc = read_document(corpus/row['document_path'])
        try:
            if doc['source']['format']!='html' or not any(editable(b) and b['type']=='paragraph' for b in doc['blocks']):
                raise ValueError('No editable HTML prose')
            plan_requests(doc,doc['chunks'],[row['prompt']],'Preserve original',False,Settings(),encoding)
            return True
        except Exception as error:
            # Record safe categories only; no source/provider data in reasons.
            excluded.append({'snapshot_id':row['snapshot_id'],'reason':type(error).__name__})
            return False
    with tempfile.TemporaryDirectory(prefix='gepa-prepare-') as temporary:
        bundle=Path(temporary)/'bundle'
        prepare(corpus,split_root,raw_root,bundle,split='validation',row_filter=eligible)
        listing=json.loads((bundle/'catalog.json').read_text())
        buckets=defaultdict(list)
        for row in listing['examples']:
            content=(bundle/(row['snapshot_id']+'.txt')).read_text()
            doc,chunks=extract_document(content,row['format'],row['href'],row['hostname'])
            try:
                plan_requests(doc,chunks,row['queries'],'Preserve original',False,Settings(),encoding)
            except Exception:
                excluded.append({'snapshot_id':row['snapshot_id'],'reason':'full_query_preflight_failed'})
                continue
            bucket=(min(len(chunks)//5,4),min(len(row['queries'])//3,3))
            buckets[bucket].append(row)
        for bucket in buckets.values():
            bucket.sort(key=lambda r:manifest_hash([seed,r['snapshot_id']]))
        selected=[]
        while len(selected)<90 and any(buckets.values()):
            for key in sorted(buckets):
                if buckets[key] and len(selected)<90:
                    selected.append(buckets[key].pop(0))
        if len(selected)<90:
            raise ValueError(f'Only {len(selected)} eligible hosts; require 90, exclusions={len(excluded)}')
        selected.sort(key=lambda r:manifest_hash([seed,'role',r['snapshot_id']]))
        data={'id':output.name,'schema_version':1,'seed':seed,'upstream':UPSTREAM,
              'p1':{'version':FEATURE_VERSION,'model_sha256':MODEL_SHA256,'serving_policy':SERVING_POLICY},
              'corpus_hash':listing['manifest_hash'],'p1_split_hash':listing['p1_split_hash'],
              'context_contract_issue':'https://github.com/ext-weihsianglin/content-optimization-system/issues/15',
              'preparation_version':'gepa-validation-60-30-v1','exclusions':excluded,
              'pages':[{**row,'role':'reflection' if i<60 else 'selection'} for i,row in enumerate(selected)]}
        data['manifest_hash']=manifest_hash(data)
        output.mkdir(parents=True)
        for row in selected:
            shutil.copyfile(bundle/(row['snapshot_id']+'.txt'),output/(row['snapshot_id']+'.txt'))
        (output/'manifest.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
        load_dataset(output.name,directory=output.parent)
        print(f'Frozen {len(selected)} P1-validation hosts: 60 reflection / 30 selection')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('corpus','split-root','raw-root','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args()
    freeze(args.corpus,args.split_root,args.raw_root,args.output,args.seed)
