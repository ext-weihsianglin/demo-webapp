import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from preprocessing.schema import snapshot_identity

client = TestClient(app)


def write_catalog(path, example, records=None):
    records = records or [{'query': example['query'], 'href': example['href'], 'usable': True} for _ in range(10)]
    example.update(queries=list(dict.fromkeys(r['query'].strip() for r in records if r['usable'])),
        query_records=records, query_scope='host', query_record_count=len(records),
        unusable_query_count=sum(not r['usable'] for r in records),
        query_set_hash=hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    (path/'catalog.json').write_text(json.dumps({'bundle_version': 3, 'p1_version': 'lr-semantic-v7',
        'p1_split_hash': 'd'*64, 'examples': [example], 'manifest_hash': 'b'*64}))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_EXAMPLES_DIR", str(tmp_path))
    content = "# Saved source\n\nKeep this original qualified claim.\n"
    _, identity = snapshot_identity(content, "https://example.com/page")
    example = {"snapshot_id": identity, "payload_hash": hashlib.sha256(content.encode()).hexdigest(), "href": "https://example.com/page", "hostname": "example.com", "format": "markdown", "split": "test", 'p1_split': 'test', "title": "Saved source", "query": "Original target query?", "characters": len(content)}
    write_catalog(tmp_path, example)
    (tmp_path / f"{identity}.txt").write_text(content)
    return tmp_path, example, content


def test_examples_support_custom_queries_and_keep_original_identity(bundle, draft_stub):
    _, example, content = bundle
    listing = client.get("/api/examples").json()
    assert listing["examples"] == [example]
    assert "content" not in listing["examples"][0]
    assert client.get(f"/api/examples/{example['snapshot_id']}").json()["content"] == content
    payload = {"example_id": example["snapshot_id"], "query": "A freely chosen different query?"}
    analysis = client.post("/api/analyze", json=payload)
    assert analysis.status_code == 200
    assert analysis.json()["source_origin"]["snapshot_id"] == example["snapshot_id"]
    assert analysis.json()["source_origin"]["split"] == "test"
    original = client.post("/api/analyze", json={**payload, "query": example["query"]}).json()
    assert original["sections"] == analysis.json()["sections"]
    draft = client.post("/api/draft", json=payload).json()
    assert draft["changes"][0]["before"] == "Keep this original qualified claim."
    assert draft["source_origin"] == analysis.json()["source_origin"]
    assert client.post("/api/analyze", json={**payload, "content": "Changed source content must detach."}).status_code == 422


def test_unlisted_and_changed_sources_are_rejected(bundle):
    path, example, _ = bundle
    assert client.get("/api/examples/not-a-snapshot").status_code == 404
    assert client.post("/api/analyze", json={"example_id": "c" * 64, "query": "Some query?"}).status_code == 404
    (path / f"{example['snapshot_id']}.txt").write_text("Tampered source snapshot")
    assert client.get(f"/api/examples/{example['snapshot_id']}").status_code == 503
    assert client.post("/api/analyze", json={"example_id": example["snapshot_id"], "query": "Some query?"}).status_code == 503


def test_development_catalog_is_not_served(bundle):
    path, example, _ = bundle
    for split in ('train', 'validation', 'heldout'):
        write_catalog(path, {**example, 'split': split, 'p1_split': split})
        assert client.get("/api/examples").status_code == 503


def test_empty_catalog_keeps_custom_flow_available(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTENT_EXAMPLES_DIR", str(tmp_path))
    assert client.get("/api/examples").json()["examples"] == []
    payload = {"query": "Free target query?", "href": "https://example.com/page", "hostname": "example.com", "format": "text", "content": "# This is literal plain text, not a heading."}
    result = client.post("/api/analyze", json=payload)
    assert result.status_code == 200
    assert result.json()["source_origin"] == {"kind": "custom"}
    assert result.json()["sections"][0]["kind"] == "p"
    assert result.json()["sections"][0]["text"].startswith("# ")


def test_large_examples_keep_full_source_but_custom_input_is_bounded(bundle):
    path, example, _ = bundle
    content = "Long saved source statement. " * 8000
    _, identity = snapshot_identity(content, example['href'])
    example = {**example, "snapshot_id": identity}
    (path / f"{example['snapshot_id']}.txt").write_text(content)
    write_catalog(path, {**example, 'payload_hash': hashlib.sha256(content.encode()).hexdigest()})
    result = client.post("/api/analyze", json={"example_id": example["snapshot_id"], "query": "Target query?"})
    assert result.status_code == 200
    assert result.json()["sections"][0]["text"] == content.strip()
    assert client.post("/api/analyze", json={"query": "Target query?", "href": example["href"], "hostname": example["hostname"], "content": content}).status_code == 422
