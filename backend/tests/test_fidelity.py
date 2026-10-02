from types import SimpleNamespace as NS
import pytest
from app.fidelity import check_fidelity


class Judge:
    def __init__(self, verdict, block='b1', source_ids=None):
        self.verdict, self.block = verdict, block
        self.source_ids = ['b1'] if source_ids is None else source_ids
        self.responses = self
    def create(self, **request):
        import json
        return NS(status='completed', output=[], usage=NS(input_tokens=20, output_tokens=10),
                  output_text=json.dumps({'edits':{self.block:{'verdict':self.verdict,
                  'category':'qualifier_loss','reason':'The source says may, not will.', 'source_ids':self.source_ids}}}))


def document():
    return {'snapshot_id':'s1','blocks':[{'block_id':'b1','text':'The treatment may help.'}],
            'chunks':[{'chunk_id':'c1','block_ids':['b1']}]}


def changes():
    return [{'source_id':'b1','chunk_id':'c1','before':'The treatment may help.',
             'after':'The treatment will help.','evidence':[{'block_id':'b1','quote':'The treatment may help.'}]}]


@pytest.mark.parametrize('verdict,status',[('supported','passed'),('unsupported','rejected'),('uncertain','rejected')])
def test_gate_returns_explicit_outcome_without_partial_acceptance(verdict,status):
    assert check_fidelity(document(),changes(),client=Judge(verdict))['status']==status


def test_unknown_judge_identity_cannot_approve_edit():
    assert check_fidelity(document(),changes(),client=Judge('supported','invented'))['status']=='unavailable'


@pytest.mark.parametrize('verdict', ['unsupported', 'uncertain'])
def test_no_supporting_source_is_semantic_rejection(verdict):
    result = check_fidelity(document(),changes(),client=Judge(verdict,source_ids=[]))
    assert result['status'] == 'rejected'
    assert result['findings'][0]['source_ids'] == []


def test_supported_verdict_still_requires_known_source_references():
    assert check_fidelity(document(),changes(),client=Judge('supported',source_ids=[]))['status']=='unavailable'
    assert check_fidelity(document(),changes(),client=Judge('unsupported',source_ids=['invented']))['status']=='unavailable'


def test_judge_schema_requires_every_edit_and_reserves_large_output():
    import json
    doc = {'snapshot_id':'large','blocks':[{'block_id':f'b{i}','text':'The treatment may help.'} for i in range(120)],
           'chunks':[{'chunk_id':'c1','block_ids':[f'b{i}' for i in range(120)]}]}
    edits = [{**changes()[0],'source_id':f'b{i}'} for i in range(120)]
    class CompleteJudge:
        responses = property(lambda self:self)
        def create(self, **request):
            self.request = request
            return NS(status='completed',output=[],usage=NS(input_tokens=20,output_tokens=10),
                      output_text=json.dumps({'edits':{e['source_id']:{'verdict':'supported','category':'same_meaning',
                          'reason':'Meaning preserved.','source_ids':[e['source_id']]} for e in edits}}))
    judge = CompleteJudge()
    result = check_fidelity(doc,edits,client=judge)
    assert result['status']=='passed' and len(result['findings'])==120
    slots = judge.request['text']['format']['schema']['properties']['edits']
    assert set(slots['required']) == {e['source_id'] for e in edits}
    assert slots['additionalProperties'] is False
    assert judge.request['max_output_tokens'] >= 120*100


def test_incomplete_coverage_remains_unavailable():
    doc = document()
    doc['blocks'].append({'block_id':'b2','text':'The treatment may help.'})
    doc['chunks'][0]['block_ids'].append('b2')
    assert check_fidelity(doc,changes()+[{**changes()[0],'source_id':'b2'}],client=Judge('supported'))['status']=='unavailable'
