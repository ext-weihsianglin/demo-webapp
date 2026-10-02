from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import scoring
from app.extraction import extract_document
from app.rewriting import rewrite
from trad_ml_scorer.retention_features import features_from_document, parse_snapshot, predict_retention
from preprocessing.quality import source_inventory
from scripts.analyze_content import words
from test_rewriting import SOURCE, StubClient
from test_examples import bundle, write_catalog

client = TestClient(app)
PAYLOAD = dict(href='https://example.com/shoes', hostname='example.com', content=SOURCE, format='html')
QUERIES = ['How should I choose road shoes?', 'What grip should trail shoes have?']


def test_queries_deduplicated_without_changing_extraction(draft_stub):
    a = client.post('/api/analyze', json={**PAYLOAD, 'queries': [QUERIES[0], ' '+QUERIES[0]+' ', QUERIES[1]]}).json()
    b = client.post('/api/analyze', json={**PAYLOAD, 'query': 'A different query?'}).json()
    assert a['target_queries'] == QUERIES
    assert a['document'] == b['document']
    assert a['chunks'] == b['chunks']
    result = client.post('/api/draft', json={**PAYLOAD, 'queries': QUERIES}).json()
    assert result['target_queries'] == QUERIES
    assert result['p1_before']['query_count'] == result['p1_after']['query_count'] == 2
    for queries in ([], ['ab'], [' '*4], ['q'*1001], ['valid']*21):
        assert client.post('/api/analyze', json={**PAYLOAD, 'queries': queries}).status_code == 422
    assert client.post('/api/analyze', json=PAYLOAD).status_code == 422
    assert client.post('/api/analyze', json={**PAYLOAD, 'queries': QUERIES, 'query':'Legacy conflict?'}).status_code == 422


def test_every_rewrite_chunk_gets_complete_deduplicated_queries_and_p1():
    document, chunks = extract_document(SOURCE, 'html', PAYLOAD['href'], PAYLOAD['hostname'])
    before = {'status':'scored', 'per_query':[{'query':q, 'score':0.6} for q in QUERIES], 'mean_score':0.6}
    stub = StubClient()
    result = rewrite(document, chunks, [*QUERIES, QUERIES[0]], 'Preserve original', False, client=stub, p1_feedback=before)
    assert result['status'] == 'succeeded'
    for request in stub.requests:
        data = json.loads(request['input'][0]['content'])
        assert data['target_queries'] == QUERIES
        assert data['p1_feedback'] == before
        assert 'target_query' not in data
        assert 'distinct' in data['optimization_objective']
        assert 'untrusted data' in request['instructions']
        assert 'regressions' in request['instructions']


def test_example_defaults_to_all_host_queries_and_allows_override(bundle):
    path, example, _ = bundle
    records = [{'query':f'Target query number {i}?', 'href':f'https://example.com/{i}', 'usable':True} for i in range(10)]
    write_catalog(path, example, records)
    result = client.post('/api/analyze', json={'example_id':example['snapshot_id']}).json()
    assert result['target_queries'] == [r['query'] for r in records]
    override = client.post('/api/analyze', json={'example_id':example['snapshot_id'], 'queries':QUERIES}).json()
    assert result['document'] == override['document']


def test_unavailable_scoring_never_substitutes_mock(tmp_path, monkeypatch):
    monkeypatch.setenv('P1_MODEL_PATH', str(tmp_path/'missing.joblib'))
    document, _ = extract_document(SOURCE, 'html', PAYLOAD['href'], PAYLOAD['hostname'])
    result = scoring.score_document(document, SOURCE, 'html', QUERIES)
    assert result['status'] == 'unavailable' and result['per_query'] == [] and 'mean_score' not in result
    path = tmp_path/'untrusted.joblib';path.write_bytes(b'not the pinned model')
    monkeypatch.setenv('P1_MODEL_PATH',str(path))
    monkeypatch.setattr(scoring, 'load_model', lambda *a: pytest.fail('Untrusted model must never be deserialized'))
    assert scoring.score_document(document, SOURCE, 'html', QUERIES)['status'] == 'unavailable'


def test_comparison_surfaces_regression_even_when_mean_improves():
    def scores(values):
        return {'status':'scored','mean_score':sum(values)/len(values),'per_query':[{'query_index':i,'query':q,'score':v} for i,(q,v) in enumerate(zip(QUERIES,values))]}
    result = scoring.compare_scores(scores([0.2,0.8]), scores([0.4,0.7]))
    assert result['mean_delta'] > 0 and result['regression_count'] == 1
    assert result['per_query'][1]['delta'] < 0
    with pytest.raises(ValueError):
        other = scores([0.2,0.8]);other['per_query'].reverse()
        scoring.compare_scores(scores([0.2,0.8]),other)


def test_invalid_explanation_is_unavailable_without_hiding_scores(monkeypatch):
    def scores(values):
        return {'status':'scored','mean_score':sum(values)/len(values),
                'per_query':[{'query_index':i,'query':q,'score':v} for i,(q,v) in enumerate(zip(QUERIES,values))],
                '_explanation_basis': {'invalid': True}}
    monkeypatch.setattr(scoring, 'compare_basis', lambda *args: (_ for _ in ()).throw(ValueError('drift')))
    result = scoring.compare_scores(scores([.2,.8]), scores([.3,.7]))
    assert result['status'] == 'scored' and result['explanation_status'] == 'unavailable'
    assert 'explanation' not in result


def test_feature_parity_with_frozen_upstream_for_html():
    document, _ = extract_document(SOURCE, 'html', PAYLOAD['href'], PAYLOAD['hostname'])
    document['scorer_source_word_count'] = len(words(source_inventory(SOURCE, PAYLOAD['href'], 'html')['body_text']))
    upstream = parse_snapshot(SOURCE, PAYLOAD['href'], PAYLOAD['hostname'])
    for query in QUERIES:
        assert features_from_document(query, document) == features_from_document(query, upstream)


def test_installed_frozen_model_parity_and_proposed_document_scoring(monkeypatch, tmp_path):
    path = Path(os.getenv('P1_MODEL_PATH', Path(__file__).resolve().parents[1]/'data/scoring/model.joblib'))
    if not path.exists():
        pytest.skip('Install the pinned model to run real P1 parity validation')
    monkeypatch.setenv('P1_MODEL_PATH', str(path))
    from trad_ml_scorer.semantic_features import NAMES
    from trad_ml_scorer.markdownify_context import feature_row
    semantics = [dict.fromkeys(NAMES, .4), dict.fromkeys(NAMES, .6)]
    monkeypatch.setattr(scoring, 'semantic_features', lambda *a, **kw: (semantics, {'calls': 0, 'test_stub': True}))
    document, chunks = extract_document(SOURCE, 'html', PAYLOAD['href'], PAYLOAD['hostname'])
    original = deepcopy(document)
    before = scoring.score_document(document, SOURCE, 'html', QUERIES)
    assert before['status'] == 'scored'
    stat = path.stat();bundle = scoring._load_model(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
    for row in before['per_query']:
        inputs = feature_row(row['query'], document, semantics[row['query_index']])
        expected = bundle['pipeline'].predict_proba(inputs.reshape(1, -1))[0, 1]
        assert row['score'] == pytest.approx(expected)
    draft = rewrite(document,chunks,QUERIES,'Preserve original',False,client=StubClient(),p1_feedback=before)
    after = scoring.score_document(draft['document'], SOURCE, 'html', QUERIES)
    assert after['status'] == 'scored'
    assert scoring.compare_scores(before,after)['status'] == 'scored'
    assert document == original and draft['document']['source_metadata'] == original['source_metadata']


def test_draft_returns_exact_query_level_rewrite_explanation_without_prompt_leakage(
        monkeypatch, draft_stub):
    path = Path(os.getenv('P1_MODEL_PATH', Path(__file__).resolve().parents[1] / 'data/scoring/model.joblib'))
    if not path.exists():
        pytest.skip('Install the pinned model to run real P1 explanation validation')
    monkeypatch.setenv('P1_MODEL_PATH', str(path))
    from trad_ml_scorer.semantic_features import NAMES
    semantics = [dict.fromkeys(NAMES, .4), dict.fromkeys(NAMES, .6)]
    monkeypatch.setattr(scoring, 'semantic_features',
                        lambda *a, **kw: (semantics, {'calls': 0, 'test_stub': True}))

    result = client.post('/api/draft', json={**PAYLOAD, 'queries': QUERIES}).json()

    assert result['status'] == 'succeeded'
    assert '_explanation_basis' not in result['p1_before']
    assert '_explanation_basis' not in result['p1_after']
    explanation = result['p1_comparison']['explanation']
    assert explanation['version'] == 'p1-linear-explanation-v1'
    assert explanation['feature_version'] == 'lr-semantic-v7.1'
    assert explanation['serving_policy'] == 'markdownify-v7.1'
    assert len(explanation['global_terms']) == 62
    metadata = {term['term']: term for term in explanation['global_terms']}
    assert metadata['title_similarity']['family'] == 'fixed_metadata'
    assert metadata['title_similarity']['rewrite_role'] == 'fixed'
    assert metadata['needs_review']['rewrite_role'] == 'diagnostic'
    assert len(explanation['per_query']) == len(QUERIES)
    for query in explanation['per_query']:
        assert len(query['terms']) == 62
        assert all('imputed_before' in term and 'imputed_after' in term for term in query['terms'])
        assert sum(term['delta_log_odds'] for term in query['terms']) == pytest.approx(
            query['delta_logit'], abs=1e-10)
        before = result['p1_comparison']['per_query'][query['query_index']]['before']
        after = result['p1_comparison']['per_query'][query['query_index']]['after']
        import math
        assert 1 / (1 + math.exp(-query['before_logit'])) == pytest.approx(before, abs=1e-12)
        assert 1 / (1 + math.exp(-query['after_logit'])) == pytest.approx(after, abs=1e-12)
