"""Cross-workstream regressions for PR #2 plus the source verification PR."""
from copy import deepcopy
from fastapi.testclient import TestClient
from app.main import app

SOURCE = {'query':'How should I choose road shoes?', 'href':'https://example.com/shoes', 'hostname':'example.com', 'format':'html', 'content':'<main><h1>Road shoes</h1><p>For road runs, choose a comfortable fit. No single shoe is best for every runner.</p></main>'}


def test_analysis_and_source_evidence_need_no_rewrite_configuration(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setenv('REWRITE_CONTEXT_TOKENS','invalid')
    client=TestClient(app)
    response=client.post('/api/analyze',json=SOURCE)
    assert response.status_code==200
    analysis=response.json()
    assert all(check['passed'] for check in analysis['verification']['checks'])
    block=next(b for b in analysis['document']['blocks'] if b['type']=='paragraph')
    evidence=client.post('/api/evidence',json={**SOURCE,'block_id':block['block_id']})
    assert evidence.status_code==200 and evidence.json()['parsed_text']==block['text']
    assert evidence.json()['status']=='text_match'


def test_real_proposal_does_not_replace_original_verification(draft_stub):
    client=TestClient(app)
    original=client.post('/api/analyze',json=SOURCE).json()
    saved=deepcopy(original)
    draft=client.post('/api/draft',json=SOURCE)
    assert draft.status_code==200
    proposal=draft.json()
    assert proposal['mode']=='openai' and proposal['document']['artifact_kind']=='proposed_content_based_on_source_snapshot'
    assert proposal['document']['text']!=original['document']['text']
    assert proposal['document']['source_metadata']==original['document']['source_metadata']
    assert 'verification' not in proposal
    edit=proposal['changes'][0]
    evidence=client.post('/api/evidence',json={**SOURCE,'block_id':edit['block_id']}).json()
    assert evidence['parsed_text']==edit['before'] and evidence['parsed_text']!=edit['after']
    assert client.post('/api/analyze',json=SOURCE).json()==saved
