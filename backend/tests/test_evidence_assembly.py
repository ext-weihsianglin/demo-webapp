"""Regression coverage for model-generated immutable source reference failures."""
from copy import deepcopy
import pytest
from app.extraction import extract_document
from app.rewriting import ProviderProposal, assemble_proposal, validate_edits, RewriteFailure


def fixture():
    document,chunks=extract_document('<main><h2>First</h2><p>Exact source text, with qualifiers.</p><h2>Second</h2><p>Different source evidence.</p></main>','html','https://example.com','example.com')
    block=next(b for b in document['blocks'] if b['type']=='paragraph')
    proposal=ProviderProposal.model_validate({'status':'proposed','summary':'A proposal','review_flags':[], 'edits':[{'block_id':block['block_id'],'after':'Source text preserves its qualifiers.','reason':'Clarify supported wording.','evidence':[{'block_id':block['block_id']}],'review_flags':[],'heading_level':None}]})
    assembled=assemble_proposal(proposal,document,chunks)
    chunk=next(c for c in chunks if block['block_id'] in c['block_ids'])
    return document,chunks,proposal,assembled,chunk,block


def test_source_fields_are_copied_exactly_without_changing_original():
    document,chunks,proposal,assembled,chunk,block=fixture();original=deepcopy(document)
    validate_edits(assembled,document,chunk,False)
    edit=assembled.edits[0]
    assert edit.before==block['text'] and edit.snapshot_id==document['snapshot_id']
    assert edit.chunk_id==chunk['chunk_id']
    assert edit.evidence[0].quote==block['text']
    assert document==original
    proposal.edits[0].evidence[0].block_id='missing'
    with pytest.raises(RewriteFailure) as error:assemble_proposal(proposal,document,chunks)
    assert error.value.details['checks_failed']==['unknown_block']


@pytest.mark.parametrize('failure',['snapshot_mismatch','unknown_block','cross_chunk_evidence','empty_quote','quote_mismatch'])
def test_evidence_failures_have_specific_diagnostics(failure):
    document,chunks,proposal,assembled,chunk,block=fixture()
    evidence=assembled.edits[0].evidence[0]
    if failure=='snapshot_mismatch':evidence.snapshot_id='wrong'
    elif failure=='unknown_block':evidence.block_id='missing'
    elif failure=='empty_quote':evidence.quote=' '
    elif failure=='quote_mismatch':evidence.quote='Exact source...with invented ellipsis'
    else:
        other=next(b for b in document['blocks'] if b['block_id'] not in chunk['block_ids'])
        evidence.block_id=other['block_id'];evidence.quote=other['text']
    with pytest.raises(RewriteFailure) as error:validate_edits(assembled,document,chunk,False)
    assert failure in error.value.details['checks_failed']


def test_schema_binds_each_edit_to_same_chunk_evidence():
    from app.rewriting import response_schema, editable
    document,chunks,_,_,_,_=fixture()
    blocks={b['block_id']:b for b in document['blocks']}
    schema=response_schema(document,chunks)
    for target, declaration in schema['properties']['blocks']['properties'].items():
        name=declaration['anyOf'][0]['$ref'].split('/')[-1]
        allowed=schema['$defs'][name]['properties']['evidence']['items']['properties']['block_id']['enum']
        chunk=next(c for c in chunks if target in c['block_ids'])
        assert editable(blocks[target], document)
        assert set(allowed)=={i for i in chunk['block_ids'] if blocks[i]['text'].strip()}
