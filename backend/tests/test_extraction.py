import socket

from fastapi.testclient import TestClient
from preprocessing.api import parse_snapshot

from app.extraction import extract_document
from app.main import app

client = TestClient(app)


def source(content, format="html"):
    return {"query": "What does this page explain?", "href": "https://example.com/docs", "hostname": "example.com", "format": format, "content": content}


def test_api_uses_installed_parser_and_preserves_structure_in_drafts():
    payload = source('<html><head><title>Plans</title><script type="application/ld+json">{"@type":"Product","name":"Source metadata"}</script></head><body><main><h1>Plans</h1><ul><li>Parent<ul><li>Child</li></ul></li></ul><pre>  first\n    second\n</pre><table><tr><th colspan="2">Limits</th></tr><tr><td>10</td><td>20</td></tr></table></main></body></html>')
    expected, chunks = parse_snapshot(payload['content'], payload['href'], payload['hostname'], source_format='html')
    response = client.post('/api/analyze', json=payload).json()
    assert response['document'] == expected
    assert response['chunks'] == chunks
    changed_query = client.post('/api/analyze', json={**payload, 'query': 'A different target question?'}).json()
    assert changed_query['document'] == response['document']
    assert changed_query['chunks'] == response['chunks']
    assert response['snapshot_id'] == expected['snapshot_id']
    assert response['document']['source_metadata']['jsonld'][0]['types'] == ['Product']
    assert 'Source metadata' not in response['document']['text']
    table = next(block for block in expected['blocks'] if block['type'] == 'table')
    assert table['table']['cells'][0]['colspan'] == 2
    assert [identity for chunk in chunks for identity in chunk['block_ids']] == [block['block_id'] for block in expected['blocks']]
    draft = client.post('/api/draft', json=payload).json()
    assert '  - Child' in draft['markdown']
    assert '  first\n    second\n' in draft['markdown']
    assert 'colspan="2"' in draft['markdown']
    assert draft['snapshot_id'] == response['snapshot_id']
    assert draft['changes'][0]['source_id'] in {block['block_id'] for block in expected['blocks']}


def test_flagged_source_stays_available_and_empty_source_abstains():
    flagged = client.post('/api/analyze', json=source('<main><p>Access denied but retain this source caveat.</p></main>')).json()
    assert flagged['extraction']['status'] == 'needs_review'
    assert 'possible_error_response' in flagged['extraction']['quality_flags']
    assert 'retain this source caveat' in flagged['document']['text']
    shell = source('<html><head><title>Metadata title</title></head><body><script>run()</script></body></html>')
    empty = client.post('/api/analyze', json=shell).json()
    assert empty['extraction']['status'] == 'source_insufficient'
    assert empty['sections'] == empty['document']['blocks'] == empty['chunks'] == []
    assert client.post('/api/draft', json=shell).status_code == 422


def test_library_invocation_does_not_fetch_resources(monkeypatch):
    def forbid_network(*args, **kwargs):
        raise AssertionError('Extraction attempted network access')
    monkeypatch.setattr(socket, 'socket', forbid_network)
    parsed, _ = extract_document('<main><p><a href="../help">Help</a></p><script src="https://example.com/script.js">run()</script></main>', 'html', 'https://example.com/docs', 'example.com')
    assert parsed['blocks'][0]['links'][0]['resolved_target'] == 'https://example.com/help'
    assert 'run()' not in parsed['text']
