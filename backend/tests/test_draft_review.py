import json
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from fastapi.testclient import TestClient
from app.extraction import extract_document
from app.rewriting import rewrite
from app.draft_review import review_response
from test_rewriting import SOURCE, StubClient


def source():
    return extract_document(SOURCE, 'html', 'https://example.com/shoes', 'example.com')


def test_flagged_and_language_changed_edits_remain_in_preview():
    doc, chunks = source()
    client = StubClient(lambda p,r,d:p['edits'][0].update(review_flags=['unsupported_addition','missing_evidence'],
        after='Para correr por carretera, elige zapatos cómodos. Ningún zapato es el mejor para todos los corredores.'))
    result = rewrite(doc,chunks,'Road shoes?', 'Preserve original',False,client=client,review_mode=True)
    assert result['status']=='review_required'
    assert len(result['changes'])==1
    codes={w['code'] for w in result['validation_warnings']}
    assert {'unsupported_addition','missing_evidence','language_changed'} <= codes
    assert 'Para correr' in result['markdown']
    assert result['prompt_messages']['system']==client.requests[0]['instructions']
    assert result['prompt_messages']['user']==client.requests[0]['input'][0]['content']


def test_mixed_valid_protected_unknown_and_bad_evidence_proposals():
    doc,chunks=source(); original=deepcopy(doc)
    paragraphs=[b for b in doc['blocks'] if b['type']=='paragraph' and not b['links']]
    code=next(b for b in doc['blocks'] if b['type']=='code')
    def edit(identity, evidence=None):
        return {'after':'A proposed revision for review.','reason':'Review this.',
                'review_flags':[],'heading_level':None,'evidence':[{'block_id':evidence or identity}]}
    values={paragraphs[0]['block_id']:edit(paragraphs[0]['block_id']),
            paragraphs[1]['block_id']:edit(paragraphs[1]['block_id'],'missing'),
            code['block_id']:edit(code['block_id']), 'unknown':edit('unknown')}
    raw=json.dumps({'status':'proposed','summary':'Mixed proposals','review_flags':[],'blocks':values})
    result=review_response(raw,doc,chunks,False)
    assert len(result['changes'])==1 and len(result['unapplied_edits'])==3
    assert result['raw_model_output']==raw and doc==original
    assert next(b for b in result['document']['blocks'] if b['block_id']==code['block_id'])==code


@pytest.mark.parametrize('raw', ['A readable but unstructured proposed paragraph.', '{"blocks": {"b000001": {"after": "unfinished'])
def test_malformed_output_is_visible_without_claiming_applied_edits(raw):
    doc,chunks=source(); result=review_response(raw,doc,chunks,False,completed=False)
    assert result['raw_model_output']==raw and not result['changes']
    assert result['document']['text']==doc['text']
    assert 'incomplete_output' in {w['code'] for w in result['validation_warnings']}


def test_conflicting_duplicate_never_silently_selects_one_edit():
    doc,chunks=source(); identity=next(b['block_id'] for b in doc['blocks'] if b['type']=='paragraph')
    raw='{"status":"proposed","summary":"x","review_flags":[],"blocks":{"'+identity+'":{"after":"one"},"'+identity+'":{"after":"two"}}}'
    result=review_response(raw,doc,chunks,False)
    assert not result['changes'] and result['unapplied_edits']
    assert result['raw_model_output']==raw


def test_http_draft_retained_and_preview_matches_sent_messages(monkeypatch):
    import app.main as main
    client=StubClient(lambda p,r,d:p['edits'][0].update(review_flags=['unsupported_addition']))
    monkeypatch.setattr(main,'rewrite',lambda *a,**k:rewrite(*a,**k,client=client))
    score={'status':'unavailable','per_query':[]}
    monkeypatch.setattr(main,'score_document',lambda *a,**k:score.copy())
    monkeypatch.setattr(main,'check_fidelity',lambda *a,**k:{'status':'rejected','reason':'source_relative_check','findings':[]})
    body={'queries':['Road shoes?', 'Trail shoes?'],'href':'https://example.com/shoes',
          'hostname':'example.com','content':SOURCE,'model':'gpt-4.1-mini'}
    http=TestClient(main.app)
    preview=http.post('/api/prompt-preview',json={**body,'p1_feedback':score})
    assert preview.status_code==200 and not client.requests
    response=http.post('/api/draft',json=body)
    assert response.status_code==200
    result=response.json()
    assert result['status']=='review_required' and result['changes']
    assert result['fidelity']['status']=='rejected'
    assert preview.json()['system']==result['prompt_messages']['system']
    assert preview.json()['user']==result['prompt_messages']['user']
