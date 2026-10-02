from copy import deepcopy

from fastapi.testclient import TestClient
from app.main import app, Source, analyze
from app.verification import SourceInspector, verify_document

HTML = '<html><head><title>Original title</title><script type="application/ld+json">{"name":"Original"}</script></head><body><main><h1>Original heading</h1><p>First line<br>Second line</p><p hidden>Hidden original sentence.</p><footer><p>Privacy policy</p></footer></main></body></html>'


def payload(content=HTML, format='html'):
    return dict(query='What is on this page?', href='https://example.com/page', hostname='example.com', content=content, format=format)


def test_breaks_hidden_and_boilerplate_are_retained():
    result = analyze(Source(**payload()))
    checks = result['verification']['blocks']
    blocks = result['document']['blocks']
    broken = next(block for block in blocks if 'First line' in block['text'])
    assert checks[broken['block_id']]['status'] == 'source_representation_match'
    hidden = next(block for block in blocks if block['text'] == 'Hidden original sentence.')
    assert any(hint.startswith('Hidden-source') for hint in checks[hidden['block_id']]['review_hints'])
    footer = next(block for block in blocks if block['text'] == 'Privacy policy')
    assert any('boilerplate' in hint.lower() for hint in checks[footer['block_id']]['review_hints'])
    assert all(check['passed'] for check in result['verification']['checks'])


def test_tampering_is_detected():
    result = analyze(Source(**payload()))
    document = deepcopy(result['document'])
    paragraph = next(block for block in document['blocks'] if block['type'] == 'paragraph')
    paragraph['text'] = 'An invented statement absent from the source.'
    assert SourceInspector(HTML, 'html').inspect(paragraph)['status'] == 'text_mismatch'
    document['source_metadata']['title'] = 'Invented title'
    document['source_metadata']['jsonld'] = []
    chunks = deepcopy(result['chunks'])
    chunks[0]['block_ids'].append(chunks[0]['block_ids'][0])
    chunks[0]['characters'] += 1
    facts = deepcopy(result['factoids'])
    facts[0]['text'] = 'Invented passage'
    audit = verify_document(HTML, 'html', document, chunks, facts)
    failed = [check['name'] for check in audit['checks'] if not check['passed']]
    assert len(failed) >= 5
    assert any('JSON-LD' in name for name in failed)


def test_duplicate_text_does_not_certify_unique_mapping():
    content = '<main><p>Repeated original sentence.</p><p>Repeated original sentence.</p></main>'
    result = analyze(Source(**payload(content)))
    block = next(block for block in result['document']['blocks'] if block['type'] == 'paragraph')
    block = {**block, 'source_locator': None, 'mapping_status': 'ambiguous'}
    evidence = SourceInspector(content, 'html').inspect(block, include_preview=True)
    assert evidence['status'] == 'unresolved'
    assert not evidence['locator_resolved']
    assert len(evidence['possible_source_matches']) == 2


def test_page_wide_sidebar_class_does_not_flag_article_as_boilerplate():
    content = '<html><body class="has-sidebar content-right-sidebar"><main><p>Original article sentence.</p></main><aside><p>Sidebar sentence.</p></aside></body></html>'
    result = analyze(Source(**payload(content)))
    blocks = result['document']['blocks']
    article = next(block for block in blocks if block['text'] == 'Original article sentence.')
    sidebar = next(block for block in blocks if block['text'] == 'Sidebar sentence.')
    checks = result['verification']['blocks']
    assert not any('boilerplate' in hint.lower() for hint in checks[article['block_id']]['review_hints'])
    assert any('boilerplate' in hint.lower() for hint in checks[sidebar['block_id']]['review_hints'])


def test_evidence_endpoint_and_native_source_ranges():
    client = TestClient(app)
    source = payload()
    result = client.post('/api/analyze', json=source).json()
    block = next(block for block in result['document']['blocks'] if 'First line' in block['text'])
    evidence = client.post('/api/evidence', json={**source, 'block_id': block['block_id']}).json()
    assert evidence['snapshot_id'] == result['snapshot_id']
    assert '<br/>' in evidence['source_fragment']
    assert client.post('/api/evidence', json={**source, 'block_id': 'absent'}).status_code == 404
    for format, content in [('text', 'First source sentence.\n\nSecond source sentence.'), ('markdown', '# Original heading\n\nSource with **bold words** and a [link](./help).')]:
        result = analyze(Source(**payload(content, format)))
        inspector = SourceInspector(content, format)
        for block in result['document']['blocks']:
            evidence = inspector.inspect(block, include_preview=True)
            assert evidence['locator_resolved']
            assert evidence['source_fragment'] in content
            assert evidence['status'] in ('text_match', 'normalized_text_match', 'source_range_only', 'structure_only')
