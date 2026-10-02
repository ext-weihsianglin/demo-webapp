# Issue #14: opt-in URL suffix spike

The separate `POST /api/url-proposals` endpoint requires `opt_in: true`. Analysis and body drafting retain their existing behavior. The source/draft review screen offers a disabled-by-default experiment and exports a JSON recommendation report. URLs are displayed as text; this workflow contains no URL fetch, publishing, redirect or migration operation.

`app/url_proposals.py` owns candidate generation and scenario comparison. `app/scoring.py` accepts a request-local `proposed_href` intervention **after** computing the source inventory from the original URL. The original document, snapshot identity, source references, canonical metadata and source word count remain unchanged. The intervention changes the scoring copy's URL only. The existing canonical feature adapter recomputes every context feature and the canonical representation adapter regenerates path inputs; cache identity decides which unaffected vectors can be reused. No title substitution or local path normalization approximation is used.

Candidate generation is intentionally conservative: keep current plus at most three alternatives copied from retained original H1s, in source order. H1s must contain 2–12 Unicode words and fit a 120-byte stem. Host/query text never supplies new candidate words. Parent path, scheme/authority, port, original extension, trailing slash, query bytes and fragment bytes stay intact. Root paths, encoded slashes, dot segments, matrix parameters, malformed escapes, credentials and extensions other than `.html`, `.htm` and `.md` abstain. This cannot infer undocumented application route constraints. All alternatives require route/topic review before any separately authorized migration.

Every candidate, including keep current, is scored over the same ordered distinct query set. Reports compare original, body-only, path-only and combined scenarios, showing all per-query and equal-weight mean deltas and canonical exact feature effects where available. Combined-vs-body isolates the path effect after a body proposal. Body scenarios require an imported proposal; without one, their absence is explicit. The frontend can import the current successful draft; the server validates immutable identities, exact before text, edit boundaries, same-chunk evidence and structural permission, reconstructing the body from original blocks. Client-supplied documents or metadata are never accepted. Imported proposals are **not re-certified** for semantic/language fidelity or authenticated as prior successful drafts.

URL explanation terms are labeled editable only within the path experiment. The default body explanation panel continues marking them fixed. `path_similarity` is query-to-path cosine, distinct from query-to-title similarity. Missing model/embeddings/provider failures remain unavailable. An imputed missing feature is not semantic evidence. Exported migrations are hypothetical review recommendations and list route existence/collisions, permanent redirects, canonical/internal-link/sitemap updates and monitoring as separate work.

## Predeclared evaluation

[predeclared.json](../backend/evaluation/url-suffix/predeclared.json) defines all synthetic examples, partitions, body edits and selection rules before scoring. Development has an opaque suffix with an unsupported host query. Validation covers already-descriptive, mixed-query, Unicode/trailing-slash and unsupported-route examples. Final examples remain reserved and unscored; tune only development/validation and freeze policy before the explicit `--final` command. These are diagnostic fixtures, not research population data or an untouched P2 quality benchmark.

Keep current unless path-only mean delta exceeds `1e-9` and no individual delta is below `-1e-9`. Select the largest eligible mean delta, resolving ties by original H1 order. Missing scores disqualify change. This conservative rule can reject a positive mean with any regression. It does not optimize combined effects, establish semantic relevance, or authorize migration. Neutral and negative candidates remain in the report.

Run cache-only evaluation from the root; output must be a fresh path:

```sh
uv run --project backend python backend/scripts/evaluate_url_suffix.py \
  --split validation --output verification/url-suffix-validation-new.json
```

The harness disables live embeddings regardless of shell settings. It does not generate body drafts or call providers. Final evaluation additionally requires `--split final --final` after freezing policy.

## Observed results and limits (2026-10-02)

[Development report](../verification/url-suffix-development-v1.json) and [validation report](../verification/url-suffix-validation-v1.json): 1 development and 4 validation fixtures, **zero scored examples**. The concrete dependency missing from this isolated checkout is `backend/data/scoring/model.joblib`, the pinned v7.1 `semantic_context` artifact with SHA-256 `d1c4b25480a1579239b8fd9c8bfa7d3beac11bfa2ec591d8540941b6f89493cc`. The canonical pipeline is installed from the locked 0.3.0 wheel. Install the trusted artifact with `backend/scripts/prepare_p1.py`; then fresh path embeddings must already exist in the canonical cache for this cache-only harness. No unrelated model or fabricated scores were substituted.

All examples retained keep current because scores were unavailable. The already-descriptive fixture produces no new alternative; the `.php` fixture abstains due to its route extension. These are proposal-policy outcomes, **not measured neutral P1 effects**. No positive, neutral or negative model effect can be concluded from these runs. Focused tests exercise neutral, negative, mixed-regression and missing-score selection with explicitly stubbed values; those values are not evaluation evidence.

The conservative H1 strategy can miss better suffixes, overstate a page's topic, carry claims already unsupported in the source, or abstain on valid application routes. Lexical query overlap is exposed as a hint only; it cannot establish supported answers, locations or promises. Model gains cannot establish factual fidelity, citation uplift, route safety or search/traffic benefits. A real final scoring run remains blocked on the pinned model and appropriate canonical embeddings; final examples were not used for tuning.

## Handoff

Changed backend files: `app/url_proposals.py`, `app/scoring.py`, `app/main.py`, `tests/test_url_proposals.py`, `scripts/evaluate_url_suffix.py`, `evaluation/url-suffix/predeclared.json`. Changed frontend files: `app/url-proposals.tsx`, `app/page.tsx`. Documentation/report files: this document, README/project-context links, and the two new verification reports.

Validation: locked backend sync and frontend dependency install; focused URL tests; full backend suite; frontend production build and typecheck; `git diff --check`. Full backend result: **195 passed, 4 skipped** (optional live/model-dependent checks); one existing Starlette/httpx deprecation warning. Build/typecheck and diff checks passed. Browser-button interaction was not tested. No live provider calls, final evaluation, merge, push, deployment, external comment or migration was performed. Remaining decisions: provide the pinned model/cache, review route constraints and topic fidelity, freeze policy and authorize final scoring; actual migration requires separate authorization.
