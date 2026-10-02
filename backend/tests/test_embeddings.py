from copy import deepcopy
import hashlib

import numpy as np
import pytest
from app.embeddings import EmbeddingUnavailable, prepare_units, semantic_features
from app.extraction import extract_document
from representations.providers import ProviderError


class StubEmbeddings:
    def __init__(self):
        self.calls = []

    def embed(self, texts, role):
        self.calls.append((texts, role))
        return [np.random.default_rng(int(hashlib.sha256(t.encode()).hexdigest()[:8], 16)).normal(size=3072).astype(np.float32) for t in texts], {'total_tokens': len(texts)}


def parsed():
    return extract_document('<main><h1>Road shoes</h1><p>Choose road shoes that fit comfortably and retain traction.</p></main>', 'html', 'https://example.com/shoes', 'example.com')[0]


def test_cache_only_misses_do_not_contact_provider(tmp_path, monkeypatch):
    monkeypatch.delenv('P1_ENABLE_LIVE_EMBEDDINGS', raising=False)
    with pytest.raises(EmbeddingUnavailable) as failure:
        semantic_features(parsed(), ['How to choose shoes?'], cache_root=tmp_path)
    assert failure.value.status == 'embedding_cache_miss'
    assert failure.value.telemetry['calls'] == 0


def test_original_space_cache_reuse_and_changed_proposal_invalidation(tmp_path):
    doc = parsed(); original = deepcopy(doc); provider = StubEmbeddings()
    before, info = semantic_features(doc, ['How to choose shoes?'], provider=provider, cache_root=tmp_path)
    assert len(before[0]) == 10 and info['dimensions'] == 3072 and info['calls'] > 0
    again, cached = semantic_features(doc, ['How to choose shoes?'], cache_root=tmp_path)
    assert cached['calls'] == 0
    for name in before[0]:
        np.testing.assert_equal(before[0][name], again[0][name])
    proposal = deepcopy(doc)
    block = next(b for b in proposal['blocks'] if b['type'] == 'paragraph')
    block['text'] = 'Select comfortable road shoes with appropriate traction.'
    block.pop('inline_markdown', None)
    proposal['artifact_kind'] = 'proposed_content_based_on_source_snapshot'
    _, units, _ = prepare_units(proposal, ['How to choose shoes?'])
    assert any(block['text'] in u['text'] for u in units if u['view'] == 'page')
    after, changed = semantic_features(proposal, ['How to choose shoes?'], provider=provider, cache_root=tmp_path)
    assert changed['cached_requests'] > 0 and changed['missing_requests'] > 0
    assert after[0]['page_similarity'] != before[0]['page_similarity']
    assert doc == original


def test_preflight_limit_and_provider_errors_visible(tmp_path, monkeypatch):
    provider = StubEmbeddings()
    monkeypatch.setenv('P1_MAX_EMBEDDING_REQUESTS', '0')
    with pytest.raises(EmbeddingUnavailable, match='embedding_request_limit'):
        semantic_features(parsed(), ['How to choose shoes?'], provider=provider, cache_root=tmp_path)
    assert provider.calls == []
    monkeypatch.setenv('P1_MAX_EMBEDDING_REQUESTS', '512')
    class Failed:
        def embed(self, *args):
            raise ProviderError('http_429')
    with pytest.raises(EmbeddingUnavailable) as failure:
        semantic_features(parsed(), ['How to choose shoes?'], provider=Failed(), cache_root=tmp_path)
    assert failure.value.status == 'embedding_provider_error'
    assert failure.value.telemetry['provider_error'] == 'http_429'


def test_stop_between_embedding_batches_prevents_next_provider_call(tmp_path):
    from app.gepa.evaluation import AttemptBudget, RunStopped
    budget = AttemptBudget(100)
    class StoppingProvider(StubEmbeddings):
        def embed(self, texts, role):
            result = super().embed(texts, role)
            budget.stop()
            return result
    provider = StoppingProvider()
    with pytest.raises(RunStopped):
        semantic_features(parsed(), ['How to choose shoes?'], provider=provider,
                          cache_root=tmp_path, before_call=budget.check)
    assert len(provider.calls) == 1
