from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.extraction import extract_document
from app.url_proposals import candidates, replace_suffix, experiment, body_view
from app.embeddings import prepare_units
from representations.cache import request_key
from representations.url_path import normalize_path


def parsed(href='https://example.com/journal/123.html?x=%2F#intro', heading='Road shoe fit'):
    return extract_document(f'<head><link rel="canonical" href="https://example.com/canonical" /></head><main><h1>{heading}</h1><p>Choose road shoes with comfortable fit and traction for everyday running.</p></main>', 'html', href, 'example.com')[0]


@pytest.mark.parametrize('href,expected', [
 ('https://example.com/a%20b/old.html?q=1#x','https://example.com/a%20b/road-shoe-fit.html?q=1#x'),
 ('HTTP://EXAMPLE.com:8080/a/old/','HTTP://EXAMPLE.com:8080/a/road-shoe-fit/'),
 ('https://example.com/a/caf%C3%A9.md?#','https://example.com/a/road-shoe-fit.md?#'),
])
def test_preserve_parent_and_url_bytes(href, expected):
    assert replace_suffix(href,'road-shoe-fit') == expected


def test_encoding_and_canonical_normalization():
    href=replace_suffix('https://example.com/a/old.htm','café-chaussures')
    assert href == 'https://example.com/a/caf%C3%A9-chaussures.htm'
    assert normalize_path(href)['text'] == 'a / café chaussures.htm'


@pytest.mark.parametrize('href',['https://example.com/','https://example.com/a/x.php','https://example.com/a/x%2Fy','https://example.com/a/..','https://example.com/a/x;id=1','https://example.com/a/%zz'])
def test_ambiguous_routes_abstain(href):
    with pytest.raises(ValueError): replace_suffix(href,'road-shoe-fit')
    assert len(candidates(parsed(href),['Road shoes?'])) == 1


def test_grounding_bounds_already_descriptive_and_unrelated_queries():
    doc=parsed(); rows=candidates(doc,['Road shoes?', 'Hotels in Paris?'])
    assert 1 < len(rows) <= 4 and rows[0]['keep_current']
    assert 'paris' not in rows[1]['proposed_href']
    assert rows[1]['query_coverage'][1]['status']=='no_lexical_evidence'
    assert rows[1]['evidence'][0]['snapshot_id']==doc['snapshot_id']
    assert len(candidates(parsed('https://example.com/journal/road-shoe-fit.html'),['Road shoes?']))==1


def test_canonical_cache_keys_changed_only_for_path():
    original=parsed(); changed=deepcopy(original); changed['source']['href']=replace_suffix(original['source']['href'],'road-shoe-fit')
    config,before,q=prepare_units(original,['Road shoes?'])
    _,after,q2=prepare_units(changed,['Road shoes?'])
    keys=lambda units: {u['subview']:request_key(u,config['models']['openai-large']) for u in units if u['status']=='ready'}
    b,a=keys(before),keys(after)
    assert b['url_path'] != a['url_path']
    assert {k:v for k,v in b.items() if k!='url_path'} == {k:v for k,v in a.items() if k!='url_path'}
    assert keys(q)==keys(q2)
    _,same,_=prepare_units(deepcopy(original),['Road shoes?'])
    assert keys(same)==b


def test_full_queries_four_scenarios_provenance_and_negative_selection():
    doc=parsed(); saved=deepcopy(doc); body=deepcopy(doc); body['artifact_kind']='proposed_content_based_on_source_snapshot'
    calls=[]
    def scorer(document,content,format,queries,**kwargs):
        calls.append((document,queries,kwargs))
        value=.5 if kwargs['proposed_href'] in (None,doc['source']['href']) else .4
        return {'status':'scored','per_query':[{'query_index':i,'query':q,'score':value} for i,q in enumerate(queries)],'mean_score':value}
    report=experiment(doc,'Original payload','html',['Road shoes?','Hotels?','Road shoes?'],body=body,scorer=scorer)
    assert len(calls)==2+2*len(report['candidates'])
    assert all(c[1]==['Road shoes?','Hotels?'] for c in calls)
    assert doc==saved and report['source_metadata']==saved['source_metadata']
    assert report['selected_href']==doc['source']['href']
    assert report['candidates'][1]['comparisons']['path_vs_original']['mean_delta']<0


def test_missing_scores_explicit(monkeypatch):
    monkeypatch.setenv('P1_MODEL_PATH','/nonexistent/issue14-model.joblib')
    doc=parsed(); before=deepcopy(doc)
    report=experiment(doc,'Original payload','html',['Road shoes?'])
    assert report['original']['status']=='unavailable'
    assert all(c['path_only']['status']=='unavailable' for c in report['candidates'])
    assert doc==before


def test_api_requires_opt_in_and_default_analyze_unchanged(monkeypatch):
    monkeypatch.setenv('P1_MODEL_PATH','/nonexistent/issue14-model.joblib')
    payload={'href':'https://example.com/a/123','hostname':'example.com','queries':['Road shoes?'], 'format':'html','content':'<main><h1>Road shoe fit</h1><p>Comfortable fit and traction help choose road shoes for everyday running.</p></main>'}
    client=TestClient(app)
    assert client.post('/api/url-proposals',json=payload).status_code==422
    result=client.post('/api/url-proposals',json={**payload,'opt_in':True})
    assert result.status_code==200
    analysis=client.post('/api/analyze',json=payload).json()
    assert analysis['document']['source']['href']==payload['href']
    assert 'candidates' not in analysis
    assert result.json()['snapshot_id']==analysis['snapshot_id']


def test_path_intervention_recomputes_context_features_without_metadata_change():
    from trad_ml_scorer.retention_features import features_from_document
    doc=parsed('https://example.com/a/42'); saved=deepcopy(doc)
    changed=deepcopy(doc); changed['source']['href']=replace_suffix(doc['source']['href'],'support')
    before=features_from_document('Road shoes?',doc); after=features_from_document('Road shoes?',changed)
    assert before['path_support_docs'] != after['path_support_docs']
    assert before['path_depth']==after['path_depth']
    assert doc==saved and changed['source_metadata']==saved['source_metadata']


def test_imported_body_proposal_preserves_provenance_and_rejects_forgery():
    from app.rewriting import Proposal, RewriteFailure
    doc=parsed(); saved=deepcopy(doc)
    block=next(b for b in doc['blocks'] if b['type']=='paragraph')
    chunk=next(c for c in doc['chunks'] if block['block_id'] in c['block_ids'])
    edit={'snapshot_id':doc['snapshot_id'],'chunk_id':chunk['chunk_id'],'block_id':block['block_id'], 'before':block['text'], 'after':'For everyday running, choose road shoes with comfortable fit and traction.', 'reason':'Clarify existing advice.', 'heading_level':None,'review_flags':[], 'evidence':[{'snapshot_id':doc['snapshot_id'],'block_id':block['block_id'],'quote':block['text']}]}
    proposal=Proposal(status='proposed',summary='Diagnostic',review_flags=[],edits=[edit])
    body=body_view(doc,proposal)
    assert doc==saved
    for key in ('snapshot_id','source','source_metadata','raw_payload_reference'):
        assert body[key]==doc[key]
    proposal.edits[0].snapshot_id='forged'
    with pytest.raises(RewriteFailure): body_view(doc,proposal)


@pytest.mark.parametrize('changed_values',[(.5,.5),(.8,.4)])
def test_neutral_and_regressing_candidates_keep_current(changed_values):
    doc=parsed()
    def scorer(document,content,format,queries,**kwargs):
        vals=(.5,.5) if kwargs['proposed_href'] in (None,doc['source']['href']) else changed_values
        return {'status':'scored','mean_score':sum(vals)/2,'per_query':[{'query_index':i,'query':q,'score':v} for i,(q,v) in enumerate(zip(queries,vals))]}
    result=experiment(doc,'Original payload','html',['Road shoes?','Hotels?'],scorer=scorer)
    assert result['selected_href']==doc['source']['href']


def test_scoring_intervention_is_request_local_and_inventory_stays_original(tmp_path, monkeypatch):
    from app import scoring
    from trad_ml_scorer.semantic_features import NAMES
    doc=parsed(); before=deepcopy(doc); observations=[]
    model=tmp_path/'stub-test-only';model.write_text('test-only')
    monkeypatch.setenv('P1_MODEL_PATH',str(model))
    monkeypatch.setattr(scoring,'_load_model',lambda *a: {})
    inventory=scoring.source_inventory
    def capture(content,href,format):
        assert href==doc['source']['href']
        return inventory(content,href,format)
    monkeypatch.setattr(scoring,'source_inventory',capture)
    def semantic(view,queries,**kwargs):
        observations.append(deepcopy(view))
        return [dict.fromkeys(NAMES,.4) for q in queries], {'calls':0,'test_stub':True}
    monkeypatch.setattr(scoring,'semantic_features',semantic)
    monkeypatch.setattr(scoring,'predict_document',lambda *a: .5)
    href=replace_suffix(doc['source']['href'],'support-guide')
    result=scoring.score_document(doc,'<main><p>Original source content for scoring.</p></main>','html',['Road shoes?'],proposed_href=href)
    assert result['status']=='scored'
    assert observations[0]['source']['href']==href
    assert observations[0]['source_metadata']==doc['source_metadata']
    assert observations[0]['snapshot_id']==doc['snapshot_id']
    assert doc==before
