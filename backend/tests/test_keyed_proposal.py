import json
import pytest
from app.rewriting import parse_provider_proposal, RewriteFailure, editable
from test_evidence_assembly import fixture
from test_rewriting import StubClient,run


def keyed_fixture():
    document,_,proposal,_,_,_=fixture()
    item=proposal.edits[0].model_dump()
    key=item.pop('block_id')
    payload={'status':'proposed','summary':'A supported edit','review_flags':[], 'blocks':{b['block_id']:None for b in document['blocks'] if editable(b, document)}}
    payload['blocks'][key]=item
    return document,payload,key


def test_identical_duplicate_edit_is_normalized_once():
    result=run(StubClient(lambda p,r,d:p['edits'].append(dict(p['edits'][0]))))
    assert result['status']=='succeeded'
    assert len(result['changes'])==1
    assert result['telemetry']['normalized_duplicate_keys']==1


def test_conflicting_duplicate_edit_rejects_entire_draft():
    result=run(StubClient(lambda p,r,d:p['edits'].append({**p['edits'][0],'after':'Conflicting replacement'})))
    assert result['status']=='invalid_output' and 'document' not in result
    assert result['telemetry']['validation_error']['checks_failed']==['conflicting_duplicate_key']


@pytest.mark.parametrize('mutation',['missing','unknown','wrong_identity','invalid_null'])
def test_exact_key_set_and_value_shape(mutation):
    document,payload,key=keyed_fixture()
    if mutation=='missing':payload['blocks'].pop(key)
    elif mutation=='unknown':payload['blocks']['invented']=None
    elif mutation=='wrong_identity':payload['blocks'][key]['block_id']=key
    else:payload['blocks'][key]=[]
    with pytest.raises(RewriteFailure):parse_provider_proposal(json.dumps(payload),document)


def test_null_means_unchanged_and_all_null_can_abstain():
    document,payload,key=keyed_fixture()
    result,count=parse_provider_proposal(json.dumps(payload),document)
    assert len(result.edits)==1 and result.edits[0].block_id==key and count==0
    payload['status']='abstained';payload['blocks'][key]=None
    result,_=parse_provider_proposal(json.dumps(payload),document)
    assert result.status=='abstained' and result.edits==[]


def test_missing_or_conflicting_identity_never_silently_wins():
    document,payload,key=keyed_fixture()
    # Conflicting duplicates are caught even in fields nested inside one edit.
    raw=json.dumps(payload)
    raw=raw.replace('"heading_level": null','"heading_level": null, "heading_level": 2')
    with pytest.raises(RewriteFailure) as error:parse_provider_proposal(raw,document)
    assert error.value.details['checks_failed']==['conflicting_duplicate_key']


def test_oversized_keyed_schema_fails_before_provider():
    from copy import deepcopy
    from app.rewriting import response_schema
    document,_,key=keyed_fixture()
    block=next(b for b in document['blocks'] if b['block_id']==key)
    document=deepcopy(document)
    document['blocks']=[{**block,'block_id':f'b{i:06d}'} for i in range(5000)]
    chunks=[{'chunk_id':'large','block_ids':[b['block_id'] for b in document['blocks']]}]
    with pytest.raises(RewriteFailure) as error:response_schema(document,chunks)
    assert error.value.status=='context_limit'
