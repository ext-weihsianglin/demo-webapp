# Upstream P1 v7 and embedding parity investigation

Read-only source/artifact audit, 2026-10-01 local / 2026-10-02 UTC. No provider calls, model deserialization, training, or code changes.

## Delivery status

Update after the original trace: PR #13 merged at `864e6634a54ad80ac1657129e994b18c3a1f7eff`, making v7 available on main. The webapp now pins that revision. The user explicitly deferred the legacy-context mismatch for webapp serving; [issue #15](https://github.com/ext-weihsianglin/content-optimization-system/issues/15) records it. The initial observations below are historical and explain the serving adaptation.

GitHub PR metadata checked with `gh pr list`: [PR #14](https://github.com/ext-weihsianglin/content-optimization-system/pull/14) merged into **feat/lr-evidence-v5-v6**, not main, at 2026-10-02T01:35:43Z. Its source HEAD is `5db69cc19a0ab0a3131be141e2f919464f6211c5`. [PR #13](https://github.com/ext-weihsianglin/content-optimization-system/pull/13), from that base branch to main, remains open. Inspected main snapshot `f971b14` includes the embedding/markdownify work but does not contain v7. Importing main alone will not supply v7.

Local scorer source: `/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/.worktrees/deck-prototype-trad-ml-scorers`. Main source snapshot: `/tmp/gepa-upstream-20261001`. Shared data root: `/Users/ext-weihsiang.lin/Documents/profound/data/content-optimization-system`.

## Frozen model contract

Selected experimental model is `trad_ml_scorer/v7/semantic_context.joblib` under shared data. SHA-256 independently checked without loading it: `2ff334173b83364fb49685fcdca7339f71b1c88bcef154d71e0a21d595587d6b`, matching `v7/shared-cache-sha256.json`.

It consumes **55 ordered numeric features**: ten original-space semantic similarities followed by 45 selected v5 prompt-only/document-only context columns. The fitted bundle contains `pipeline`, `feature_names`, `version`, `variant`, selection, embedding identity, serializer identity and source hashes. Inference is `pipeline.predict_proba(matrix)[:, 1]` with matrix columns exactly in `feature_names` order; use the fitted imputation/scaling pipeline, never refit it for a GEPA run. The 45 columns are selected by `feature_dependencies.feature_group` from the frozen v5 model names. Exact names are also recorded as the semantic_context finalist in `trad_ml_scorer/v7/results.json`.

Sources: [semantic_experiment.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/semantic_experiment.py), [adoption decision](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/v7/decision.md), [plan](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/v7/plan.md).

V7 is adopted as a development direction, not established superior on validation: CV AUC .67440 versus v5 .66185, validation AUC .66443 versus .67435, paired validation delta -.00992 (95% host-bootstrap interval -.03369 to +.01348). No v7 test predictions were performed. Preserve classifier-score language; these are not citation probabilities or causal rewrite gains.

## Mixed parser contract: integration issue to resolve explicitly

V7 semantic features come from **markdownify** documents, but its 45 context columns are copied unchanged from the **retention-parser v5 cache**. `prepare_evidence.py` reads saved `data/trad_ml_scorer/v2/documents/<snapshot_id>.json.gz`; semantic_experiment copies v5 context columns rather than recomputing them using markdownify. `robust_features.robust_features(prompt, doc)` combines retention features and richer features after `scoring_view` suppresses repeated/unsupported headings. `evidence_features` supplies v5 additions. The exact subset must follow frozen names.

Therefore replacing the app parser with markdownify and computing every context feature from the resulting document is **not exact v7 inference parity**. Existing fitted retention features also enforce `downstream-document-v1` and retention policy. For original corpus rows, reuse verified context cache values; for future pages/rewrites, preserve a versioned retention-scoring view alongside the new markdownify representation or explicitly establish/retrain a new all-markdownify scorer version. This is a model-contract decision, not an arbitrary adapter implementation detail.

Sources: [prepare_evidence.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/prepare_evidence.py), [robust_features.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/robust_features.py), [retention_features.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/retention_features.py).

## Embedding identity and original-space alignment

Shared run `representations/runs/markdownify-openai-v1` and feature entry `features/openai-v1.json` are the authoritative prepared data. V7 manifest binds:

- OpenAI `text-embedding-3-large`, **3072 dimensions**, config ID `fc28538b81c52b5c18bca73f5ec7e7fa163bfc4a3a630e79c18a957d472a5e8a`, embedding identity `e8f0823f296ef4653dc4c01ed9a2e7c507f727193135c847728322e4ca8245ea`.
- Serializer `blocks-v3-markdownify`, path normalizer identity from upstream config; 4096-byte section chunks and 7000-byte page/field input ceilings, conservative UTF-8 byte counting. Provider capacity 8192 bytes. Empty OpenAI query instruction; no query/document prefix added for OpenAI.
- Ten features: title, best H1, outline, page and path cosine; section maximum, top-three mean, median, Q25, Q75. Missing views remain missing and use training-fitted imputation/indicators.
- Seven independent training-only 32D PCA projections exist for exploration but **are not used by v7**. Cross-field PCA-coordinate cosine would be invalid; no whole-training PCA transforms belong in GEPA scoring.

Importable representation primitives are `representations.inputs.document_units(document, config)`, `text_units`, `serialize`, `render_block`; `representations.url_path.normalize_path`; `representations.providers.HTTPProvider`; `representations.cache.VectorStore`, `request_key`; `representations.runner.load_vectors`, `normalized`; `representations.alignment.align(run, model_name)`. These are currently run/artifact-oriented building blocks, not a supplied request-level scorer API. `trad_ml_scorer.semantic_features.original_cosines`, `section_summary`, `validate_join` are small importable contract helpers; `prepare_semantic.main` is offline preparation only. A new upstream inference facade is needed to compose these without copying formulas into the app.

Serialization preserves v3 inline Markdown, code whitespace, structured table cell/header/span JSON, heading ancestry and original chunk membership. Long non-section fields get a derived unit: normalize member vectors, sum weighted by member UTF-8 content bytes, normalize total, cast float32. Section chunks are scored individually rather than pooled. Alignment excludes `:chunk` units for whole-field similarities and selects maximum across eligible field candidates. Runner normalizes vectors; align computes dot products in original space.

Sources: [inputs.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/inputs.py), [config.json](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/config.json), [runner.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/runner.py), [alignment.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/alignment.py), [semantic_features.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/semantic_features.py).

## Cache and live-call requirements

Corpus run is complete: 409,730 logical units, 408,746 exported vectors, 354,112 unique requests, zero failed requests; unavailable units remain explicit. Shared cache is `representations/shared-store`, SQLite catalog plus immutable vector shards. Cache keys bind semantic model config, query/document role and serialized text hash. Serialization/path version is intentionally excluded from provider-cache identity, while exact text and model identity remain bound; the run separately binds serializer/config identity.

Existing source/query vectors can reuse this cache without API calls. Future/custom queries and rewritten field/chunk texts require new embeddings unless their exact keys already exist. A complete source corpus does **not** eliminate per-candidate GEPA embedding costs. Reuse unchanged title/path/query/section units but never reuse old body vectors for changed prose. Explicitly enabled live scoring is necessary for new content; offline-only mode must fail visibly on cache miss. The same OpenAI model and dimensions are necessary but insufficient: exact serializer, chunking, pooling, normalization and context contract must match too.

Sources: [cache.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/cache.py), [providers.py](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/representations/providers.py), [completed-run context](https://github.com/ext-weihsianglin/content-optimization-system/blob/f971b14/PROJECT_CONTEXT.md).

## Frozen split identity and GEPA readiness

`v7/manifest.json` documents 9,432 eligible rows with **no additional exclusions**, inherited host assignments and zero host overlap: train 7,540 rows / 771 hosts; validation 945 / 97; test 947 / 97. `joined_records.jsonl` carries record ID, raw file SHA/source row, snapshot/extraction/query identity and split. `prepare_semantic.validate_join` enforces original hash/row, snapshot, prompt, URL, host, split, payload and label parity. Source split reference remains v2 records/host assignments; use joined row identity rather than the extraction benchmark's development/heldout designation.

User direction is strict P1-test-only examples in webapp and frozen P1 train/validation for GEPA. Build new bundles from these audited split identities, preserve full original per-host query records, and detect host and duplicate-payload overlap. Do not call the existing 40 extraction-heldout examples P1 test without reclassification.

Before GEPA: pin/import combined upstream code and trusted model; resolve mixed-parser context inference; create original-record feature/score parity fixtures from cached matrices; verify same serializer units, pooled vectors and ten semantic fields; add stubbed/cache-only new-page and proposed-page parity tests; expose cache misses/provider failures; record new live-call limits. For proposals, immutable source evidence must remain separate from regenerated scoring text/outline/chunks. Updating text while retaining stale `inline_markdown` would make the v3 serializer silently embed old content. Chunk boundaries and ancestry must be recomputed under the same recipe for changed content, with proposed identities/provenance distinct from original-source matches.

Verification limits: checked text source, manifests, GitHub metadata and chosen model checksum only; did not unpickle models, recompute numerical features, inspect all vector shards, or perform live embedding/rewrite calls. Numerical corpus audit evidence cited in upstream manifest is upstream evidence, not newly reproduced here.

## Exact original inference versus proposed-content policy

The scorer branch exposes a legacy path: `trad_ml_scorer.retention_features.parse_snapshot(payload, href, hostname, source)` directly invokes `preprocessing.adapters.local.extract_conservative` for HTML, then `preprocessing.downstream.document`, preserving source inventory and computing `scorer_source_word_count`. This can reproduce original context features only when its **legacy dependency fingerprints** are pinned too. Importing its Python function against the newly changed markdownify/downstream modules is not proof of parity; old and new modules share namespace names. The currently bundled webapp v2 wheel already contains the old modules and verifies their fingerprints, but combining these with a newer same-namespace wheel needs a deliberate versioned facade/vendor namespace or a separately isolated legacy scoring component.

For proposed content, there is no supplied exact mapping from markdownify `dom-blocks-v3` edits onto old conservative-parser blocks. Their segmentation, nesting, inline representation and identities differ. Computing v5 contexts on edited markdownify blocks is a **new serving policy**; leaving old contexts unchanged is also a new policy and prevents the model seeing document-length/structure changes. Reparse of exported Markdown differs from original HTML and loses metadata/format diagnostics; it cannot claim frozen training parity. Patching original HTML with edits would need an explicit HTML patching implementation and user-visible scope beyond this workflow.

Recommended gate: reproduce original corpus rows exactly first with both parser views; then choose and version proposed-content scoring deliberately. One option is recalibrating/refitting a new scorer whose semantic and context features both come from markdownify, so original and rewritten blocks share one feature contract. Another is maintaining an explicit mapping/edit projection into the legacy scoring document, with deterministic fixtures and unsupported mappings surfaced. Neither is an existing turnkey v7 capability. The app should not ship a v7 badge or GEPA reward claiming exact v7 rewrite parity until this decision is made and checked.

Model-bundle source metadata covers semantic artifact/run hashes; it does not itself include the old parser fingerprints for all 45 context columns. Their full provenance must also come from frozen v5 cache/model manifests and v2/v4 selection hashes, as retained by `prepare_evidence.py`. This prevents a model hash check alone from certifying the complete inference pipeline.
