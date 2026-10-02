from types import SimpleNamespace as NS
import pytest
from app.fidelity import check_fidelity


class Judge:
    def __init__(self, verdict, block='b1'):
        self.verdict, self.block = verdict, block
        self.responses = self
    def create(self, **request):
        import json
        return NS(status='completed', output=[], usage=NS(input_tokens=20, output_tokens=10),
                  output_text=json.dumps({'edits':[{'block_id':self.block,'verdict':self.verdict,
                  'category':'qualifier_loss','reason':'The source says may, not will.', 'source_ids':['b1']}]}))


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
