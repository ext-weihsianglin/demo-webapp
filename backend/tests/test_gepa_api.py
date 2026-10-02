import time
import json
from fastapi.testclient import TestClient
from app.main import app
from app.gepa import routes
from app.gepa.runs import RunManager
from app.prompt_registry import PromptRegistry
from test_gepa_runs import make_dataset, ResearchClient, scorer


def test_http_research_requires_explicit_live_flag_and_exports_promotable_result(tmp_path,monkeypatch):
    make_dataset(tmp_path,monkeypatch)
    manager=RunManager(registry=PromptRegistry(tmp_path/'registry'),client=ResearchClient(),scorer=scorer,directory=tmp_path/'runs')
    monkeypatch.setattr(routes,'manager',manager)
    client=TestClient(app)
    assert client.post('/api/gepa/runs',json={'dataset_id':'fixture'}).status_code==400
    assert client.post('/api/gepa/runs',json={'dataset_id':'fixture','concurrency':1000}).status_code==422
    assert client.get('/api/gepa/datasets').json()['datasets'][0]['selection']==30
    prompts=client.get('/api/prompts',params={'model':'gpt-4.1-mini'}).json()
    assert prompts['prompts'][0]['kind']=='baseline'
    started=client.post('/api/gepa/runs',json={'dataset_id':'fixture','candidates':1,'enable_live_calls':True})
    assert started.status_code==202
    identity=started.json()['id']
    assert identity.startswith('gpt-4-1-mini-fidelity-search-')
    assert started.json()['display_name'] == identity
    for _ in range(300):
        result=client.get('/api/gepa/runs/'+identity).json()
        if result['status'] not in ('running','preflighting','stopping'):
            break
        time.sleep(.01)
    assert result['recommendation'],result
    assert result['usage']['fidelity']['calls']==64
    assert result['usage']['reflection']['calls']==1
    exported=client.get('/api/gepa/runs/'+identity+'/export').json()
    assert exported['manifest']['gepa_version']=='0.1.4'
    assert exported['summary']['usage']['rewrite']['calls']==64
    traces=client.get('/api/gepa/runs/'+identity+'/reflection-traces')
    assert traces.status_code==200
    trace=traces.json()['traces'][0]
    assert trace['input']['examples']['editorial_strategy'][0]['Inputs']['source_scope']=='whole_page'
    assert trace['response']['validation_errors']==[]
    assert json.loads(trace['response']['output_text'])['editorial_strategy'].startswith('Clarify')
    assert manager.registry.fixed in trace['instructions']
    assert trace['input']['examples']['editorial_strategy'][0]['Inputs']['queries']==['How should I choose road shoes?']
    proposals=[json.loads(request['input'][0]['content']) for request in manager.client.requests]
    evolved=[p for p in proposals if p['optimization_context']]
    assert evolved and evolved[0]['optimization_context']['rationale']=='Clarify answer wording.'
    assert evolved[0]['target_queries']==['How should I choose road shoes?']
    assert evolved[0]['p1_feedback']['mean_score']==.2
    assert 'examples' not in evolved[0]['optimization_context']
    assert client.post('/api/prompts/'+result['recommendation']+'/promote',json={'run_id':identity}).status_code==200
    assert client.post('/api/gepa/runs/'+identity+'/stop').status_code==200


def test_broken_research_registry_does_not_disable_source_analysis(tmp_path, monkeypatch):
    from test_api import SOURCE
    import app.gepa.runs as run_module
    def unavailable():
        raise ValueError('Prompt fixed contract changed')
    monkeypatch.setattr(run_module, 'PromptRegistry', unavailable)
    manager = run_module.RunManager()
    monkeypatch.setattr(routes, 'manager', manager)
    client = TestClient(app)
    assert client.post('/api/analyze', json=SOURCE).status_code == 200
    assert client.get('/api/prompts', params={'model':'gpt-4.1-mini'}).status_code == 400


def test_http_source_rejection_is_validated_and_blocks_promotion(tmp_path, monkeypatch):
    from app.gepa.runs import RunConfig
    from test_gepa_runs import wait
    make_dataset(tmp_path, monkeypatch)
    manager=RunManager(registry=PromptRegistry(tmp_path/'registry'),client=ResearchClient(),scorer=scorer,directory=tmp_path/'runs')
    monkeypatch.setattr(routes,'manager',manager)
    final=wait(manager,manager.start(RunConfig(dataset_id='fixture',candidates=1,enable_live_calls=True))['id'])
    candidate=final['recommendation']
    path=f'/api/gepa/runs/{final["id"]}/candidates/{candidate}/reject'
    client=TestClient(app)
    assert client.post(path,json={'reason':''}).status_code == 422
    assert client.post(path,json={'reason':'  '}).status_code == 400
    assert client.post(path,json={'reason':'Unstated guarantee in b1.','approved':True}).status_code == 422
    rejected=client.post(path,json={'reason':'Unstated guarantee in b1.'})
    assert rejected.status_code == 200
    assert not rejected.json()['promotion_compatible']
    assert client.post(f'/api/prompts/{candidate}/promote',json={'run_id':final['id']}).status_code == 400
    assert client.get(f'/api/gepa/runs/{final["id"]}/export').json()['summary']['source_rejections'][candidate]['reason'] == 'Unstated guarantee in b1.'
