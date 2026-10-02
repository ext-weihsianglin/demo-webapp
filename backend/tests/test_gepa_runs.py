import json
import time
from types import SimpleNamespace as NS
from app.extraction import extract_document, UPSTREAM
from app.gepa.datasets import manifest_hash, load_dataset
from app.gepa.runs import RunManager, RunConfig
from app.prompt_registry import PromptRegistry
from app.scoring import FEATURE_VERSION, MODEL_SHA256, SERVING_POLICY
from test_rewriting import StubClient


def make_dataset(tmp_path, monkeypatch):
    monkeypatch.setenv('GEPA_DATA_ROOT',str(tmp_path))
    path=tmp_path/'datasets'/'fixture'
    path.mkdir(parents=True)
    pages=[]
    for i in range(90):
        host=f'host{i}.example.com'
        content=f'<main><h1>Road shoes at {host}</h1><p>For everyday road runs, choose a comfortable fit. No single shoe is best for every runner.</p></main>'
        href=f'https://{host}/shoes'
        doc,_=extract_document(content,'html',href,host)
        records=[{'query':'How should I choose road shoes?','usable':True, 'source_row':j} for j in range(10)]
        pages.append({'hostname':host,'href':href,'format':'html','snapshot_id':doc['snapshot_id'],
            'payload_hash':doc['source']['payload_hash'],'p1_split':'validation','queries':[records[0]['query']],
            'query_records':records,'query_set_hash':manifest_hash(records),'role':'reflection' if i<60 else 'selection'})
        (path/(doc['snapshot_id']+'.txt')).write_text(content)
    data={'id':'fixture','pages':pages,'upstream':UPSTREAM,'p1':{'version':FEATURE_VERSION,'model_sha256':MODEL_SHA256,'serving_policy':SERVING_POLICY}}
    data['manifest_hash']=manifest_hash(data)
    (path/'manifest.json').write_text(json.dumps(data))
    return data


class ResearchClient(StubClient):
    def __init__(self, verdict='supported'):
        super().__init__()
        self.reflection_examples=[]
        self.verdict=verdict
    def create(self,**kwargs):
        name=kwargs['text']['format']['name']
        data=json.loads(kwargs['input'][0]['content'])
        if name=='rewrite_proposal':
            response=super().create(**kwargs)
            if kwargs['instructions'].startswith('Clarify'):
                response.output_text=response.output_text.replace('prioritize a comfortable fit','choose a comfortable fit')
            return response
        if name=='fidelity':
            body={'edits':{c['source_id']:{'verdict':self.verdict,'category':'fidelity',
                'reason':'Meaning matches source.' if self.verdict=='supported' else 'Unsupported certainty.',
                'source_ids':[c['source_id']] if self.verdict=='supported' else []} for c in data['changes']}}
        else:
            self.reflection_examples.extend(data['examples']['editorial_strategy'])
            body={'editorial_strategy':'Clarify supported answers while preserving every factual qualifier.', 'summary':'Clarify answer wording.'}
        return NS(status='completed',output=[],usage=NS(input_tokens=10,output_tokens=10),output_text=json.dumps(body))


def scorer(document,content,format,queries):
    score=.6 if 'choose a comfortable fit;' in document['text'] else .4 if 'prioritize a comfortable fit' in document['text'] else .2
    return {'status':'scored','mean_score':score,'per_query':[{'query':q,'score':score} for q in queries]}


def wait(manager,identity):
    for _ in range(1500):
        value=manager.status(identity)
        if value['status'] in ('completed','failed','stopped'):
            return value
        time.sleep(.02)
    raise AssertionError('Run did not finish')


def test_real_gepa_mutates_selects_and_saves_without_reflection_leakage(tmp_path,monkeypatch):
    dataset=make_dataset(tmp_path,monkeypatch)
    client=ResearchClient()
    manager=RunManager(registry=PromptRegistry(tmp_path/'registry'),client=client,scorer=scorer,directory=tmp_path/'runs')
    run=manager.start(RunConfig(dataset_id='fixture',candidates=1,enable_live_calls=True))
    final=wait(manager,run['id'])
    assert final['status']=='completed',final
    assert final['recommendation'] and final['budget']['attempts']==64
    assert len(client.reflection_examples)==2
    reflection_ids={p['snapshot_id'] for p in dataset['pages'] if p['role']=='reflection'}
    assert all(e['Inputs']['page_id'] in reflection_ids for e in client.reflection_examples)
    candidate=next(c for c in final['candidates'] if c['id']==final['recommendation'])
    assert candidate['selection_mean']==.6 and candidate['selection_pages']==30
    assert candidate['query_deltas'][0]['queries'][0]['baseline']==.4
    assert abs(candidate['query_deltas'][0]['queries'][0]['baseline_delta']-.2)<1e-10
    manager.promote(run['id'],candidate['id'])
    assert manager.registry.resolve(None,'gpt-4.1-mini')['id']==candidate['id']
    assert manager.store(run['id']).export()['events']


def test_semantic_rejection_keeps_original_reward_without_technical_breaker(tmp_path,monkeypatch):
    make_dataset(tmp_path,monkeypatch)
    manager=RunManager(registry=PromptRegistry(tmp_path/'registry'),client=ResearchClient('unsupported'),scorer=scorer,directory=tmp_path/'runs')
    final=wait(manager,manager.start(RunConfig(dataset_id='fixture',candidates=1,enable_live_calls=True))['id'])
    assert final['status']=='completed'
    assert final['recommendation'] is None and final['budget']['technical_failures']==0
    baseline=next(c for c in final['candidates'] if c.get('selection_pages')==30)
    assert baseline['selection_mean']==.2 and baseline['failure_rate']==1


def test_stop_preserves_dispatched_result_and_does_not_call_next_phase(tmp_path,monkeypatch):
    import threading
    from app.gepa.evaluation import PageEvaluator, AttemptBudget, RunStopped
    from concurrent.futures import ThreadPoolExecutor
    import pytest
    make_dataset(tmp_path,monkeypatch)
    page=load_dataset('fixture')['pages'][0]
    started,release=threading.Event(),threading.Event()
    class SlowClient(ResearchClient):
        def create(self,**kwargs):
            started.set()
            assert release.wait(5)
            return super().create(**kwargs)
    budget=AttemptBudget(100)
    records=[]
    evaluator=PageEvaluator(budget,1,client=SlowClient(),scorer=scorer,record=records.append)
    with ThreadPoolExecutor(max_workers=1) as pool:
        job=pool.submit(evaluator.evaluate,[page],PromptRegistry(tmp_path/'registry').baseline('gpt-4.1-mini'))
        assert started.wait(3)
        budget.stop()
        release.set()
        with pytest.raises(RunStopped):
            job.result()
    assert records[0]['status']=='interrupted' and records[0]['rewrite']['status']=='succeeded'
    assert 'fidelity' not in records[0] and budget.snapshot()['attempts']==1


def test_dataset_tampering_and_test_assignment_are_rejected(tmp_path,monkeypatch):
    import pytest
    data=make_dataset(tmp_path,monkeypatch)
    path=tmp_path/'datasets/fixture/manifest.json'
    data['pages'][0]['p1_split']='test'
    data['manifest_hash']=manifest_hash({k:v for k,v in data.items() if k!='manifest_hash'})
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='validation'):
        load_dataset('fixture')


def test_repeated_mutation_preserves_existing_selection_winner(tmp_path, monkeypatch):
    make_dataset(tmp_path, monkeypatch)
    manager = RunManager(registry=PromptRegistry(tmp_path/'registry'), client=ResearchClient(),
                         scorer=scorer, directory=tmp_path/'runs')
    final = wait(manager, manager.start(RunConfig(dataset_id='fixture', candidates=2, enable_live_calls=True))['id'])
    assert final['status'] == 'completed'
    assert final['proposals'] == 2
    assert final['recommendation']
    winner = next(c for c in final['candidates'] if c['id'] == final['recommendation'])
    assert winner['selection_pages'] == 30 and winner['selection_mean'] == .6


def test_post_embedding_score_failure_preserves_dispatched_usage(tmp_path, monkeypatch):
    import pytest
    import app.gepa.evaluation as evaluation
    make_dataset(tmp_path, monkeypatch)
    records = []
    def unavailable_proposal(document, content, format, queries, **options):
        proposed = document.get('artifact_kind') == 'proposed_content_based_on_source_snapshot'
        options['on_embedding']({'calls':2 if proposed else 0,'input_tokens':10 if proposed else 0})
        return {'status':'unavailable','per_query':[]} if proposed else scorer(document, content, format, queries)
    monkeypatch.setattr(evaluation, 'score_document', unavailable_proposal)
    evaluator = evaluation.PageEvaluator(evaluation.AttemptBudget(100), 1, client=ResearchClient(), record=records.append)
    with pytest.raises(ValueError, match='Proposed P1 unavailable'):
        evaluator.evaluate([load_dataset('fixture')['pages'][0]], PromptRegistry(tmp_path/'registry').baseline('gpt-4.1-mini'))
    assert records[0]['proposed_embedding']['calls'] == 2
    assert records[0]['proposed_embedding']['input_tokens'] == 10


def test_server_shutdown_stops_next_phase_and_saved_progress_is_recoverable(tmp_path, monkeypatch):
    import threading
    make_dataset(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()
    class SlowClient(ResearchClient):
        def create(self, **kwargs):
            started.set()
            assert release.wait(5)
            return super().create(**kwargs)
    registry = PromptRegistry(tmp_path/'registry')
    manager = RunManager(registry=registry, client=SlowClient(), scorer=scorer, directory=tmp_path/'runs')
    run = manager.start(RunConfig(dataset_id='fixture', concurrency=1, enable_live_calls=True))
    assert started.wait(3)
    manager.shutdown()
    release.set()
    final = wait(manager, run['id'])
    assert final['status'] == 'stopped' and final['stop_reason'] == 'server_shutdown'
    assert final['budget']['attempts'] == 1 and final['usage']['fidelity']['calls'] == 0
    # An interrupted coordinator's persisted summary can lag page/candidate files.
    store = manager.store(run['id'])
    store.write('summary', {**final,'status':'running','budget':{'attempts':0,'reserved':30,'limit':100},'candidates':[]})
    fresh = RunManager(registry=registry, directory=tmp_path/'runs')
    recovered = fresh.status(run['id'])
    assert recovered['status'] == 'interrupted' and recovered['budget']['attempts'] == 1
    assert recovered['budget']['reserved'] == 0 and recovered['candidates']


def test_reflection_uses_complete_relevant_source_text_once_and_schema_length_bound(tmp_path, monkeypatch):
    from app.gepa.adapter import Adapter
    from app.gepa.evaluation import PageEvaluator, AttemptBudget
    from app.gepa.storage import RunStore
    from gepa.core.adapter import EvaluationBatch
    class Capture(ResearchClient):
        def create(self, **request):
            self.schema = request['text']['format']['schema']
            return super().create(**request)
    registry = PromptRegistry(tmp_path/'registry')
    client = Capture()
    adapter = Adapter(PageEvaluator(AttemptBudget(100), client=client), registry,
        registry.baseline('gpt-4.1-mini'), RunStore('reflection-fixture',tmp_path/'runs'), RunConfig(dataset_id='fixture'))
    source_text = 'Retain this factual qualifier exactly: may help under stable conditions.'
    result = {'role':'reflection','page_id':'page-id','queries':['What may help?'],
        'original_document':{'blocks':[{'block_id':'b1','type':'paragraph','text':source_text,'raw_html':'x'*500000}],
                            'chunks':[{'chunk_id':'c1','block_ids':['b1']}]},
        'rewrite':{'changes':[{'source_id':'b1','chunk_id':'c1','before':source_text,'after':'This may help under stable conditions.',
                              'evidence':[{'block_id':'b1','quote':source_text}]}],'summary':'Validated.'},
        'original':{'mean_score':.2},'after':{'mean_score':.3},'delta':.1,'status':'applied'}
    dataset = adapter.make_reflective_dataset({},EvaluationBatch(outputs=[result],scores=[.3],trajectories=[result]),['editorial_strategy'])
    serialized = json.dumps(dataset)
    assert serialized.count(source_text) == 1 and 'raw_html' not in serialized
    assert dataset['editorial_strategy'][0]['Inputs']['source_scope'] == 'changed_chunks'
    adapter.propose_new_texts({'editorial_strategy':registry.editorial},dataset,['editorial_strategy'])
    assert client.schema['properties']['editorial_strategy']['maxLength'] == int(len(registry.editorial)*1.5)
