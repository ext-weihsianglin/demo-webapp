"""Request-level orchestration over the upstream representation recipe/cache.

No PCA. No provider calls on cache misses unless P1_ENABLE_LIVE_EMBEDDINGS=1.
The upstream exporter owns normalization and byte-weighted pooling.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from preprocessing.downstream import structure_chunks
from representations import SERIALIZER_VERSION
from representations.cache import VectorCache, embedding_config, request_key
from representations.config import load_config
from representations.inputs import document_units, make_unit
from representations.providers import HTTPProvider, ProviderError, validated_vectors
from representations.runner import export_vectors, SavedVectors
from representations.storage import digest
from trad_ml_scorer.semantic_features import original_cosines, section_summary

EMBEDDING_IDENTITY = 'e8f0823f296ef4653dc4c01ed9a2e7c507f727193135c847728322e4ca8245ea'


class EmbeddingUnavailable(ValueError):
    def __init__(self, status, telemetry):
        super().__init__(status)
        self.status, self.telemetry = status, telemetry


def prepare_units(document, queries):
    """Adapt a structured document to the same inputs used by the corpus run."""
    config = load_config()
    if digest(embedding_config(config['models']['openai-large'])) != EMBEDDING_IDENTITY:
        raise ValueError('Embedding configuration differs from frozen v7')
    doc = deepcopy(document)
    # Never reuse source chunks/text for a changed proposal.
    if doc.get('artifact_kind') == 'proposed_content_based_on_source_snapshot':
        doc['outline'], doc['chunks'] = structure_chunks(doc['snapshot_id'], doc['selection']['method'], doc['blocks'], 6000)
        doc['chunk_ids'] = [c['chunk_id'] for c in doc['chunks']]
    units = document_units({'snapshot': {**doc['source'], 'snapshot_id': doc['snapshot_id']},
        'extraction_id': digest([doc['snapshot_id'], doc['blocks'], doc['chunks']]),
        'selection': doc['selection'], 'inventory': doc['source_metadata'],
        'blocks': doc['blocks'], 'chunks': doc['chunks'], 'retention_first': True}, config)
    query_units = []
    for query in queries:
        unit = make_unit(None, None, 'query', 'query', query,
            status='ready' if query.strip() and len(query.encode()) <= config['page_bytes'] else 'unavailable',
            reason=None if query.strip() and len(query.encode()) <= config['page_bytes'] else 'invalid_query')
        unit['unit_id'] = digest([SERIALIZER_VERSION, 'query', query])
        query_units.append(unit)
    return config, units, query_units


def semantic_features(document, queries, *, provider=None, cache_root=None):
    config, doc_units, query_units = prepare_units(document, queries)
    cfg = config['models']['openai-large']
    units = doc_units + list({u['unit_id']: u for u in query_units}.values())
    telemetry = {'model': cfg['model'], 'dimensions': cfg['dimensions'],
        'embedding_identity': EMBEDDING_IDENTITY, 'serializer_version': SERIALIZER_VERSION,
        'calls': 0, 'input_tokens': 0, 'cached_requests': 0, 'missing_requests': 0}
    cache_root = cache_root or os.getenv('EMBEDDING_CACHE_ROOT', str(Path(__file__).resolve().parents[1] / 'data/embedding-cache'))
    store = VectorCache(cache_root, cfg)
    try:
        requests = {request_key(u, cfg): u for u in units if u['status'] == 'ready'}
        locations = store.locations()
        missing = [(key, unit) for key, unit in requests.items() if key not in locations]
        telemetry.update(cached_requests=len(requests) - len(missing), missing_requests=len(missing))
        if missing and provider is None and os.getenv('P1_ENABLE_LIVE_EMBEDDINGS') != '1':
            raise EmbeddingUnavailable('embedding_cache_miss', telemetry)
        limit = int(os.getenv('P1_MAX_EMBEDDING_REQUESTS', '512'))
        if len(missing) > limit:
            raise EmbeddingUnavailable('embedding_request_limit', telemetry)
        if missing:
            provider = provider or HTTPProvider(cfg)
            with store.writer(cache_root):
                # Recheck after locking; another request might have completed.
                locations = store.locations()
                for role in ('query', 'document'):
                    pending = [(key, unit) for key, unit in missing if key not in locations and unit['role'] == role]
                    while pending:
                        batch, size = [], 0
                        while pending and len(batch) < cfg['batch_size']:
                            key, unit = pending[0]
                            byte_size = len(unit['text'].encode())
                            if batch and size + byte_size > cfg['batch_bytes']:
                                break
                            batch.append(pending.pop(0)); size += byte_size
                        telemetry['calls'] += 1
                        vectors, usage = provider.embed([u['text'] for _, u in batch], role)
                        vectors = validated_vectors([{'index': i, 'embedding': v} for i, v in enumerate(vectors)], len(batch), cfg['dimensions'])
                        telemetry['input_tokens'] += usage.get('total_tokens', usage.get('prompt_tokens', 0))
                        locations.update(store.save([(key, v) for (key, _), v in zip(batch, vectors)], usage=usage))
        # Reuse the upstream exporter verbatim, including all-or-nothing pooling.
        with tempfile.TemporaryDirectory(prefix='p1-vectors-') as temporary:
            run = Path(temporary)
            index = export_vectors(run, 'request', cfg, units, store, locations, {})
            vectors = SavedVectors(np.load(run / 'vectors/request/vectors.npy', allow_pickle=False), index)
            rows = []
            for unit in query_units:
                query = vectors.get(unit['unit_id'])
                if query is None:
                    raise EmbeddingUnavailable('embedding_query_unavailable', telemetry)
                row = {}
                for name, view, prefix in (('title', 'title', 'document_title'), ('h1', 'title', 'h1'),
                    ('outline', 'outline', 'outline'), ('page', 'page', 'page'), ('path', 'path', 'url_path')):
                    selected = [u for u in doc_units if u['view'] == view and u['subview'].startswith(prefix)
                        and not u['subview'].endswith(':chunk') and u['unit_id'] in vectors]
                    values = original_cosines(query, np.stack([vectors[u['unit_id']] for u in selected])) if selected else []
                    row[name + '_similarity'] = float(max(values)) if len(values) else np.nan
                sections = [vectors[u['unit_id']] for u in doc_units if u['view'] == 'section' and u['unit_id'] in vectors]
                if not sections or not np.isfinite(row['page_similarity']):
                    raise EmbeddingUnavailable('embedding_content_unavailable', telemetry)
                row.update(section_summary(original_cosines(query, np.stack(sections))))
                rows.append(row)
        return rows, telemetry
    except ProviderError as error:
        raise EmbeddingUnavailable('embedding_provider_error', {**telemetry, 'provider_error': error.reason}) from None
    finally:
        store.close()
