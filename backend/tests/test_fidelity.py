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


def test_reasoning_judge_dispatch_and_saved_profile_match():
    from app.gepa.runs import fidelity_profile
    class Capture(Judge):
        def create(self, **request):
            self.request = request
            return super().create(**request)
    client = Capture('supported')
    result = check_fidelity(document(), changes(), client=client)
    profile = fidelity_profile()
    assert client.request['model'] == profile['model'] == 'gpt-5'
    assert client.request['reasoning'] == {'effort':'low'}
    assert profile['reasoning_effort'] == result['telemetry']['reasoning_effort'] == 'low'
    assert client.request['max_output_tokens'] == profile['output_budget']['minimum'] == 8192
    assert result['telemetry']['batches'][0]['output_limit'] == client.request['max_output_tokens']


def test_provider_schema_cannot_emit_chunk_hashes_or_cross_chunk_sources():
    import json
    from jsonschema import Draft202012Validator, ValidationError
    doc=document()
    doc['blocks'].append({'block_id':'b2','text':'A different treatment may help.'})
    doc['chunks'].append({'chunk_id':'c2','block_ids':['b2']})
    edits=changes()+[{**changes()[0],'source_id':'b2','chunk_id':'c2'}]
    class Capture:
        responses=property(lambda self:self)
        def create(self, **request):
            self.schema=request['text']['format']['schema']
            return NS(status='completed',output=[],usage=None,output_text=json.dumps({'edits':{
                identity:{'verdict':'supported','category':'paraphrase','reason':'Meaning preserved.',
                          'source_ids':[identity]} for identity in ('b1','b2')}}))
    client=Capture()
    assert check_fidelity(doc,edits,client=client)['status']=='passed'
    validator=Draft202012Validator(client.schema)
    body={'edits':{identity:{'verdict':'supported','category':'paraphrase','reason':'Meaning preserved.',
                           'source_ids':[identity]} for identity in ('b1','b2')}}
    validator.validate(body)
    for refs in (['c1'],['b2'],[],['invented']):
        body['edits']['b1']['source_ids']=refs
        with pytest.raises(ValidationError):
            validator.validate(body)
    body['edits']['b1'].update(verdict='unsupported',source_ids=[])
    validator.validate(body)


def test_oversized_fidelity_reference_schema_fails_before_dispatch():
    doc={'snapshot_id':'huge','blocks':[{'block_id':f'b{i}','text':'May help.'} for i in range(1000)],
         'chunks':[{'chunk_id':'c1','block_ids':[f'b{i}' for i in range(1000)]}]}
    class NoCall:
        responses=property(lambda self:self)
        def create(self, **request):
            raise AssertionError('An oversized source-reference schema reached the provider')
    edit={**changes()[0],'source_id':'b0'}
    result=check_fidelity(doc,[edit],client=NoCall())
    assert result['status']=='unavailable' and result['reason']=='fidelity_schema_limit'
    assert result['telemetry']['calls']==0


def test_bounded_judge_batches_cover_every_edit_and_aggregate_usage():
    import json
    doc = {'snapshot_id':'large','blocks':[{'block_id':f'b{i}','text':'The treatment may help.'} for i in range(120)],
           'chunks':[{'chunk_id':'c1','block_ids':[f'b{i}' for i in range(120)]}]}
    edits = [{**changes()[0],'source_id':f'b{i}'} for i in range(120)]
    class CompleteJudge:
        requests = []
        responses = property(lambda self:self)
        def create(self, **request):
            self.requests.append(request)
            requested = json.loads(request['input'][0]['content'])['changes']
            return NS(status='completed',output=[],usage=NS(input_tokens=20,output_tokens=10),
                      output_text=json.dumps({'edits':{e['source_id']:{'verdict':'supported','category':'same_meaning',
                          'reason':'Meaning preserved.','source_ids':[e['source_id']]} for e in requested}}))
    judge = CompleteJudge()
    result = check_fidelity(doc,edits,client=judge)
    assert result['status']=='passed' and len(result['findings'])==120
    assert len(judge.requests) == 15
    covered = []
    for request in judge.requests:
        slots = request['text']['format']['schema']['properties']['edits']
        assert len(slots['required']) <= 8 and slots['additionalProperties'] is False
        covered.extend(slots['required'])
    assert len(covered) == len(set(covered)) == 120
    assert set(covered) == {e['source_id'] for e in edits}
    assert result['telemetry']['calls'] == 15
    assert result['telemetry']['input_tokens'] == 300
    assert result['telemetry']['output_tokens'] == 150


def test_incomplete_coverage_remains_unavailable():
    doc = document()
    doc['blocks'].append({'block_id':'b2','text':'The treatment may help.'})
    doc['chunks'][0]['block_ids'].append('b2')
    assert check_fidelity(doc,changes()+[{**changes()[0],'source_id':'b2'}],client=Judge('supported'))['status']=='unavailable'


def test_another_edited_chunk_cannot_support_a_claim():
    import json
    doc = document()
    doc['blocks'].append({'block_id':'b2','text':'A different treatment will help.'})
    doc['chunks'].append({'chunk_id':'c2','block_ids':['b2']})
    edits = changes()+[{'source_id':'b2','chunk_id':'c2','before':'A different treatment will help.',
        'after':'A different treatment helps.','evidence':[{'block_id':'b2','quote':'A different treatment will help.'}]}]
    class CrossChunkJudge:
        responses = property(lambda self:self)
        def create(self, **request):
            return NS(status='completed',output=[],usage=None,output_text=json.dumps({'edits':{
                identity:{'verdict':'supported','category':'claim','reason':'The treatment will help.',
                    'source_ids':['b2']} for identity in ('b1','b2')}}))
    result = check_fidelity(doc,edits,client=CrossChunkJudge())
    assert result['status']=='unavailable'
    assert result['reason']=='invalid_judge_output'

@pytest.mark.parametrize('later_verdict,expected', [('unsupported','rejected'), ('uncertain','rejected'), ('malformed','unavailable')])
def test_later_batch_failure_never_accepts_supported_prefix(later_verdict, expected):
    import json
    doc = {'snapshot_id':'s1', 'blocks':[{'block_id':f'b{i}','text':'May help.'} for i in range(9)],
           'chunks':[{'chunk_id':'c1','block_ids':[f'b{i}' for i in range(9)]}]}
    edits = [{**changes()[0], 'source_id':f'b{i}'} for i in range(9)]
    class LaterFailure:
        calls = 0
        responses = property(lambda self:self)
        def create(self, **request):
            self.calls += 1
            rows = json.loads(request['input'][0]['content'])['changes']
            verdict = 'supported' if self.calls == 1 else later_verdict
            body = {'edits':{c['source_id']:{'verdict':verdict,'category':'scope',
                'reason':'Qualifier was changed.','source_ids':[c['source_id']]} for c in rows}}
            return NS(status='completed',output=[],usage=NS(input_tokens=20,output_tokens=10),
                      output_text=json.dumps(body))
    progress = []
    result = check_fidelity(doc, edits, client=LaterFailure(), on_progress=progress.append)
    assert result['status'] == expected
    assert result['telemetry']['calls'] == 2
    assert result['telemetry']['input_tokens'] == 40
    assert len(result['findings']) == (8 if expected == 'unavailable' else 9)
    assert all(p['status'] == 'unavailable' for p in progress)
    assert progress[0]['telemetry']['calls'] == 1
    assert len(progress[0]['findings']) == 8


def test_interrupted_later_batch_preserves_completed_usage_in_progress():
    import json
    doc = {'snapshot_id':'s1', 'blocks':[{'block_id':f'b{i}','text':'May help.'} for i in range(9)],
           'chunks':[{'chunk_id':'c1','block_ids':[f'b{i}' for i in range(9)]}]}
    edits = [{**changes()[0], 'source_id':f'b{i}'} for i in range(9)]
    class Interrupted:
        calls = 0
        responses = property(lambda self:self)
        def create(self, **request):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('stopped before dispatch')
            rows = json.loads(request['input'][0]['content'])['changes']
            return NS(status='completed',output=[],usage=NS(input_tokens=20,output_tokens=10),
                output_text=json.dumps({'edits':{c['source_id']:{'verdict':'supported','category':'same',
                    'reason':'Meaning preserved.','source_ids':[c['source_id']]} for c in rows}}))
    progress = []
    with pytest.raises(RuntimeError, match='stopped before dispatch'):
        check_fidelity(doc, edits, client=Interrupted(), on_progress=progress.append)
    assert progress[-1]['status'] == 'unavailable'
    assert progress[-1]['telemetry']['calls'] == 1
    assert progress[-1]['telemetry']['input_tokens'] == 20
    assert progress[-1]['telemetry']['reviewed_edits'] == 8
