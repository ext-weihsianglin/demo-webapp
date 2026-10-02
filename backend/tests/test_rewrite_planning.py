"""Protect atomic source context, complete queries and a single budgeted page call."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import tiktoken
from app.extraction import extract_document
from app.rewriting import plan_requests, rewrite, Settings, response_schema, PROMPT
from test_rewriting import StubClient

QUERIES = [f'How should I choose road running shoes for condition {i}?' for i in range(10)]


def many_chunks():
    source = '<main>'+''.join(f'<h2>Road running {i}</h2><p>For everyday road runs {i}, choose a comfortable fit. No single shoe is best for every runner.</p>' for i in range(33))+'</main>'
    document,chunks=extract_document(source,'html','https://example.com/shoes','example.com')
    # Noneditable diagnostics should not consume a request's editorial budget.
    document['source_metadata']['jsonld'] = [{'articleBody':'extra structured data '*10000}]
    document['source_metadata']['visibility'] = {'diagnostics':'nested DOM diagnostic '*10000}
    return document,chunks


def test_pack_whole_chunks_and_keep_every_query_and_block_text_once():
    document,chunks=many_chunks();original=deepcopy(document)
    settings=Settings();encoding=tiktoken.encoding_for_model(settings.model)
    requests=plan_requests(document,chunks,QUERIES,'Preserve original',False,settings,encoding)
    assert len(chunks)>1 and len(requests)==1
    assert [c['chunk_id'] for batch,_,_,_ in requests for c in batch]==[c['chunk_id'] for c in chunks]
    received=[]
    for batch,data,count,estimate in requests:
        payload=json.loads(data)
        assert count+settings.output_tokens<=settings.context_tokens
        assert count==len(encoding.encode(PROMPT+data+json.dumps(response_schema(document,batch))))+256
        assert payload['target_queries']==QUERIES
        assert payload['scope']=='whole_page'
        assert 'jsonld' not in payload['source_metadata'] and 'visibility' not in payload['source_metadata']
        assert all('text' not in c and 'markdown' not in c for c in payload['chunks'])
        assert all('source_locator' not in b for b in sorted(payload['editable_blocks'] + payload['read_only_context'], key=lambda b: b['order']))
        received.extend((b['block_id'],b['text']) for b in sorted(payload['editable_blocks'] + payload['read_only_context'], key=lambda b: b['order']))
    assert received==[(b['block_id'],b['text']) for b in document['blocks']]
    assert document==original
    stub=StubClient();result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=stub)
    assert result['status']=='succeeded' and result['telemetry']['original_chunks']==len(chunks)
    assert result['telemetry']['calls']==len(stub.requests)==1
    assert result['document']['source_metadata']==original['source_metadata'] and document==original


def test_batched_edits_cannot_use_evidence_from_another_original_chunk():
    document,chunks=many_chunks()
    def cross_chunk(proposal,response,data):
        edit=proposal['edits'][0]
        own=next(c for c in data['chunks'] if edit['block_id'] in c['block_ids'])
        other=next(c for c in data['chunks'] if c['chunk_id']!=own['chunk_id'])
        block=next(b for b in data['editable_blocks'] + data['read_only_context'] if b['block_id'] in other['block_ids'] and b['text'])
        edit['evidence']=[{'block_id':block['block_id']}]
    result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=StubClient(cross_chunk))
    assert result['status']=='invalid_output' and 'document' not in result


def test_whole_page_uses_one_call_and_oversized_page_fails_before_provider():
    document,chunks=many_chunks();stub=StubClient()
    result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=stub,settings=Settings())
    assert result['status']=='succeeded' and len(stub.requests)==1
    source='<main><p>Choose a comfortable fit for road runs.</p><pre>'+('retained atomic code '*20000)+'</pre></main>'
    document,chunks=extract_document(source,'html','https://example.com/shoes','example.com')
    stub=StubClient();result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=stub,settings=Settings(context_tokens=16000,output_tokens=4000))
    assert result['status']=='context_limit' and not stub.requests
    assert document['blocks'][-1]['text']=='retained atomic code '*20000


def test_real_qa_snapshot_fits_default_budget_without_truncation():
    folder=Path(__file__).resolve().parents[1]/'data/examples-multiquery-dedup-v1'
    if not folder.exists():
        pytest.skip('Install held-out examples for the Asanify QA reproduction')
    catalog=json.loads((folder/'catalog.json').read_text())
    example=next(e for e in catalog['examples'] if e['hostname']=='asanify.com')
    content=(folder/(example['snapshot_id']+'.txt')).read_text()
    document,chunks=extract_document(content,example['format'],example['href'],example['hostname'])
    settings=Settings(model='gpt-4.1');requests=plan_requests(document,chunks,example['queries'],'Preserve original',False,settings,tiktoken.encoding_for_model(settings.model))
    assert len(chunks)==33 and len(requests)==1
    assert sum(len(batch) for batch,_,_,_ in requests)==33
    assert all(count+settings.output_tokens<=settings.context_tokens for _,_,count,_ in requests)
    assert all(json.loads(data)['target_queries']==example['queries'] for _,data,_,_ in requests)


def test_unchanged_edit_is_validated_but_does_not_count_as_a_body_rewrite():
    document,chunks=many_chunks()
    def unchanged(proposal,response,data):
        proposal['edits'][0]['after']=next(b['text'] for b in data['editable_blocks'] if b['block_id']==proposal['edits'][0]['block_id'])
    result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=StubClient(unchanged))
    assert result['status']=='abstained' and result['telemetry']['ignored_unchanged_edits']>0
    assert 'document' not in result
    def bad_quote(proposal,response,data):
        unchanged(proposal,response,data)
        proposal['edits'][0]['evidence'][0]['quote']='fabricated evidence'
    result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=StubClient(bad_quote))
    assert result['status']=='invalid_output' and 'document' not in result


def test_protected_edit_rejected_with_bounded_provider_schema():
    document,chunks=many_chunks()
    protected=document['blocks'][1]
    protected['links']=[{'href':'https://example.com/original','text':protected['text']}]
    def protected_edit(proposal,response,data):
        edit=proposal['edits'][0]
        edit['block_id']=protected['block_id']
    stub=StubClient(protected_edit)
    result=rewrite(document,chunks,QUERIES,'Preserve original',False,client=stub)
    assert result['status']=='invalid_output' and 'document' not in result
    schema=stub.requests[0]['text']['format']['schema']
    for branch in schema['$defs']['ProviderEdit']['anyOf']:
        assert protected['block_id'] not in branch['properties']['block_id']['enum']
        assert branch['properties']['heading_level']=={'type':'null'}
    assert set(schema['$defs']['EvidenceReference']['properties'])=={'block_id'}
