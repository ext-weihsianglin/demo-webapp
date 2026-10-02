from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.rewriting import Settings, rewrite
from test_rewriting import StubClient, SOURCE

client = TestClient(app)
PAYLOAD = {'query':'How should I choose road shoes?', 'href':'https://example.com/shoes',
           'hostname':'example.com', 'format':'html', 'content':SOURCE}

@pytest.fixture(autouse=True)
def model_config(monkeypatch):
    monkeypatch.setenv('OPENAI_REWRITE_MODEL','gpt-4.1-mini')
    monkeypatch.delenv('OPENAI_REWRITE_MODELS', raising=False)

@pytest.mark.parametrize('selected', ['gpt-4.1-mini','gpt-4.1','gpt-4.1-nano','gpt-5','gpt-5-mini',None])
def test_dropdown_model_routes_to_client_and_telemetry(selected, monkeypatch):
    from app import main
    stub=StubClient()
    monkeypatch.setattr(main,'rewrite',lambda *args,**kwargs:rewrite(*args,client=stub,**kwargs))
    response=client.post('/api/draft',json={**PAYLOAD,**({'model':selected} if selected else {})})
    assert response.status_code==200
    expected=selected or 'gpt-4.1-mini'
    assert all(request['model']==expected for request in stub.requests)
    assert response.json()['telemetry']['model']==expected


def test_server_allowlist_and_configured_default(monkeypatch):
    monkeypatch.setenv('OPENAI_REWRITE_MODEL','gpt-5-mini')
    monkeypatch.setenv('OPENAI_REWRITE_MODELS','gpt-4.1, gpt-4.1,gpt-4.1-mini')
    options=client.get('/api/rewrite-models').json()
    assert options=={'default_model':'gpt-5-mini','models':['gpt-5-mini','gpt-4.1','gpt-4.1-mini']}
    assert Settings.from_env().model==options['default_model']

@pytest.mark.parametrize('model',['arbitrary-model','', ' gpt-4.1-mini', 'gpt-4.1-nano'])
def test_unlisted_models_rejected_before_generation(model,monkeypatch):
    from app import main
    monkeypatch.setenv('OPENAI_REWRITE_MODELS','gpt-4.1')
    def forbid(*args,**kwargs):
        raise AssertionError('Unlisted model reached generation')
    monkeypatch.setattr(main,'rewrite',forbid)
    assert client.post('/api/draft',json={**PAYLOAD,'model':model}).status_code==422


def test_default_price_estimate_does_not_apply_to_other_models(monkeypatch):
    monkeypatch.setenv('REWRITE_INPUT_USD_PER_MILLION','1')
    monkeypatch.setenv('REWRITE_OUTPUT_USD_PER_MILLION','2')
    assert Settings.from_env('gpt-4.1-mini').input_price==1
    alternate=Settings.from_env('gpt-4.1')
    assert alternate.input_price is alternate.output_price is None


def test_default_catalog_only_contains_tested_families():
    options=client.get('/api/rewrite-models').json()
    assert options['default_model']=='gpt-4.1-mini'
    assert options['models']==['gpt-4.1-mini','gpt-4.1','gpt-4.1-nano','gpt-5','gpt-5-mini']


def test_unavailable_model_reports_access_failure_without_provider_body(monkeypatch):
    from types import SimpleNamespace
    import httpx
    from openai import PermissionDeniedError
    from app import main
    class Unavailable:
        def __init__(self): self.responses=self
        def create(self,**kwargs):
            response=httpx.Response(403,request=httpx.Request('POST','https://api.openai.com/v1/responses'))
            raise PermissionDeniedError('sensitive provider detail',response=response,
                body={'code':'model_not_found','type':'invalid_request_error'})
    monkeypatch.setattr(main,'rewrite',lambda *args,**kwargs:rewrite(*args,client=Unavailable(),**kwargs))
    response=client.post('/api/draft',json={**PAYLOAD,'model':'gpt-5'})
    assert response.status_code==502
    assert response.json()['detail']['status']=='model_unavailable'
    assert 'cannot access gpt-5' in response.json()['detail']['summary']
    assert 'sensitive provider detail' not in response.text


@pytest.mark.parametrize('model',['gpt-5-nano','gpt-5.6-sol','gpt-6-sol','gemini-pro','gpt-5-custom'])
def test_environment_cannot_expand_supported_catalog(model,monkeypatch):
    monkeypatch.setenv('OPENAI_REWRITE_MODELS',f'gpt-4.1,{model}')
    assert model not in client.get('/api/rewrite-models').json()['models']
    assert client.post('/api/draft',json={**PAYLOAD,'model':model}).status_code==422


def test_unsupported_configured_default_reports_configuration_error(monkeypatch):
    monkeypatch.setenv('OPENAI_REWRITE_MODEL','gpt-6-sol')
    response=client.get('/api/rewrite-models')
    assert response.status_code==503
    assert 'supported P2 model catalog' in response.json()['detail']
