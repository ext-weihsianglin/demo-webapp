"""The reviewed QA artifact must reach the existing selector and draft request."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.gepa import routes
from app.prompt_registry import ROOT, PromptRegistry
from test_api import SOURCE


CANDIDATE = 'gpt-4.1-mini--procedure--4dc3c4a39237157a3b1a3b02'
PROMPT_HASH = 'f2ef0597491c588bd90b30a971498c4d286ec0f7624d5b608e78d3330801554c'


def test_shipped_qa_prompt_is_selectable_and_sent_to_rewriter(monkeypatch, draft_stub):
    registry = PromptRegistry(ROOT)
    monkeypatch.setenv('PROMPT_REGISTRY_ROOT', str(ROOT))
    monkeypatch.setattr(routes, 'manager', SimpleNamespace(registry=registry))
    client = TestClient(main.app)
    catalog = client.get('/api/prompts', params={'model': 'gpt-4.1-mini'})
    assert catalog.status_code == 200
    assert catalog.json()['selected_id'] == 'gpt-4.1-mini--rewrite-page-v7'
    entry = next(p for p in catalog.json()['prompts'] if p['id'] == CANDIDATE)
    assert entry['kind'] == 'experimental' and not entry['selected']
    assert entry['prompt_hash'] == PROMPT_HASH
    for model in registry.models:
        if model != 'gpt-4.1-mini':
            assert CANDIDATE not in [p['id'] for p in registry.catalog(model)['prompts']]

    candidate = registry.resolve(CANDIDATE, 'gpt-4.1-mini')
    assert candidate['contract_hash'] == registry.baseline('gpt-4.1-mini')['contract_hash']
    captured = []
    stubbed_rewrite = main.rewrite

    def capture(*args, **kwargs):
        captured.append(kwargs)
        return stubbed_rewrite(*args, **kwargs)

    monkeypatch.setattr(main, 'rewrite', capture)
    response = client.post('/api/draft', json={**SOURCE, 'model': 'gpt-4.1-mini', 'prompt_id': CANDIDATE})
    assert response.status_code == 200, response.text
    assert captured[0]['prompt'] == candidate['effective_prompt']
    assert captured[0]['prompt_id'] == CANDIDATE
    assert response.json()['telemetry']['prompt_hash'] == PROMPT_HASH
    assert registry.resolve(None, 'gpt-4.1-mini')['id'] == 'gpt-4.1-mini--rewrite-page-v7'
