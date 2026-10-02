import time
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
