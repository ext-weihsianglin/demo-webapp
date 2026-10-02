import pytest
from fastapi.testclient import TestClient
from app import main


@pytest.mark.parametrize('status', ['rejected', 'unavailable'])
def test_fidelity_assessment_preserves_draft_and_scores(monkeypatch, draft_stub, status):
    assessment = {'status': status, 'reason': 'source_relative_check', 'findings': [
        {'block_id': 'b000001', 'verdict': 'unsupported', 'category': 'qualifier',
         'reason': 'The source says may, not will.', 'source_ids': []}]}
    monkeypatch.setattr(main, 'check_fidelity', lambda *a: assessment)
    scored = []
    def score(document, *a, **kw):
        scored.append(document)
        return {'status': 'unavailable', 'per_query': []}
    monkeypatch.setattr(main, 'score_document', score)
    response = TestClient(main.app).post('/api/draft', json={
        'queries': ['How should I choose road shoes?'], 'href': 'https://example.com/shoes',
        'hostname': 'example.com', 'format': 'html',
        'content': '<h1>Road shoes</h1><p>For everyday road runs, choose a comfortable fit and cushioning that feels natural.</p>'})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'succeeded'
    assert result['fidelity'] == assessment
    assert result['changes'] and result['markdown'] and result['document']
    assert len(scored) == 2 and 'p1_comparison' in result
