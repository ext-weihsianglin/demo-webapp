# GEPA implementation plan

Status: implemented for local research; see [implementation handoff](gepa-implementation.md). The agreed requirements and proposed defaults below preserve the reviewed design record; the handoff identifies the implementation choices.

Read the [implementation spec](gepa-spec.md) for contracts and acceptance criteria, [interview record](gepa-design.md) for provenance, and [glossary](../GLOSSARY.md) for terminology.

## Outcome

Add a GEPA Optimization tab that runs a bounded, real GEPA search for a reusable P2 editorial prompt. Users can configure a run, inspect every prompt change and rewrite/P1 trace, compare candidates, and explicitly select a model-specific prompt for Content Studio.

The first experiment uses frozen P1 v7 as a reward proxy and `gpt-4.1-mini` for rewriting and reflection. A source-relative factual-fidelity gate will check proposed edits before they are applied and scored. Improving P1 does not establish citation uplift or factual truth.

## Foundation already merged

[Demo PR #5](https://github.com/ext-weihsianglin/demo-webapp/pull/5) imports pinned upstream revision `864e663` through the 0.2.0 package:

- HTML uses the completed corpus's upstream Markdownify flow and hotfixes.
- Frozen P1 v7 consumes ten original-space OpenAI cosine features and 45 context features. Embeddings use `text-embedding-3-large`, 3,072 dimensions, upstream serialization/splitting/cache identity/normalized pooling. PCA is excluded.
- The webapp serves 97 verified P1-test hosts. GEPA needs a separate dataset loader; it must not use this test catalog.
- Current P2 baseline is `rewrite-page-v7.txt`, with keyed edits, protected blocks, language preservation and source-evidence validation.
- Existing backend tests and frontend build/typecheck passed. Bounded parser/semantic parity audits and a later live draft/rescore smoke check succeeded.

Frozen v7 trained its 45 context columns on older-parser documents. Current serving recomputes them from Markdownify documents under `markdownify-context-v1`, as authorized by the user. Keep this limitation in every run manifest; [upstream issue #15](https://github.com/ext-weihsianglin/content-optimization-system/issues/15) tracks it. No retraining or exact legacy-context score parity is part of this work.

## Agreed experiment

| Setting | Initial value / behavior |
|---|---|
| Dataset | 90 eligible pages from distinct P1-validation hosts |
| Reflection split | 60 pages; rewrite diagnostics guide mutations |
| Selection split | 30 fixed pages; compare candidates |
| Test split | Excluded from search and reflection |
| Baseline evaluation | All 30 selection pages upfront; reflection pages on demand |
| Rewriter / reflection model | `gpt-4.1-mini`, separate settings frozen per run |
| Proposed-candidate ceiling | 10, excluding baseline |
| Reflection batch | 2 pages per mutation, rotating through the 60 |
| Rewrite-attempt ceiling | 100, including baseline and reflection evaluation |
| Page-evaluation concurrency | 10; mutations remain sequential |
| Primary score | Mean over queries within each page, then equal-weight mean over pages |
| Recommendation | Selection mean exceeds baseline, failure rate no worse |
| Regressions | Visible; individual-query regression does not automatically disqualify |
| Prompt growth | Mutable editorial text at most 1.5× its initial length |
| Run controls | Start, live progress, Stop, inspect/export |
| Persistence | Save traces as work completes; no pause/resume or automatic restart |
| Promotion | Explicit, per rewriter model; no automatic default replacement |

Run limits are editable in the UI before Start and immutable during a run. Reflection, fidelity and embedding calls have separate counters from rewrite attempts. A proposed-candidate ceiling does not guarantee that many fully evaluated candidates.

### Budget implication

With a fresh cache, 30 baseline selection rewrites, two 30-page challenger evaluations and two parent/challenger reflection batches of two pages consume at most 98 rewrite attempts. GEPA can reject a mutation before full selection evaluation, so actual allocation can differ. Do not start a full selection evaluation without capacity for its uncached pages. Report partial/unadmitted candidates rather than declaring them winners.

Ten workers can reduce elapsed time for independent pages; this is not a promise of account throughput. Extra gate calls, embedding cache misses, rate limits and existing cache write locks still affect latency. No inference-latency optimization is required to ship the initial loop.

## Failure policy

**Agreed:** exclude insufficient-content pages before freezing the dataset. An isolated invalid rewrite keeps the original page and its measured P1 score, with an explicit failure trace. Do not remove failed pages from a candidate's score denominator.

**Agreed:** stop the run after three consecutive failures, or a failure rate greater than 20% after at least ten attempts. Keep provider failures separate from schema/validation failures.

**Proposed detail:** calculate the rate cumulatively over completed uncached rewrite evaluations; record completion order for the consecutive counter. A valid abstention is not a failure. Missing original P1 scores or incompatible model/parser inputs stop preflight rather than fabricate rewards.

## Factual-fidelity gate

**Agreed direction:** add a separate `gpt-4.1-mini` check comparing changed blocks with original text and supporting passages. Identify invented claims, contradictions, material qualifier loss and unsupported promotional claims. The optimizer cannot alter or disable this gate.

**Proposed first version:** structured per-edit findings and `supported / unsupported / uncertain` outcomes. Apply the whole proposal only when all edits pass; preserve the original page otherwise. Gate rejections are feedback for prompt search; distinguish them from infrastructure errors. Use the same gate for baseline and candidates. The spec records remaining uncertainty and circuit-breaker choices explicitly.

## Prompt registry and Content Studio

**Agreed:** registry entries distinguish rewriter models. Start with `gpt-4.1-mini`; support an independently optimized `gpt-5-mini` family later. Do not silently reuse an optimized prompt across models.

Content Studio gets both Model and Prompt selectors. Model selection filters compatible prompts. Prompt changes invalidate stale drafts; every request/result records the exact prompt identity and hash.

**Storage:** commit baseline references, fixed contracts, candidate artifacts and model-default pointers in `prompt-registry/`. Run directories containing traces remain ignored. Keep baseline v7 intact. Promotion updates the model-default pointer; commit it together with its referenced candidate. Promotion itself does not generate a Git commit or deployment.

## Delivery sequence

1. **Freeze data and prompt contracts.** Prepare the 90-page manifest with source/query/split provenance, deterministic selection, eligibility exclusions and 60/30 roles. Introduce a registry/resolver and compose fixed instructions with an editable component without changing baseline behavior.
2. **Build page evaluation and fidelity checks.** Reuse extraction, rewrite validation, embeddings and P1 scoring. Add source-relative gate outcomes, original-score fallback, immutable result identities and separate usage accounting.
3. **Wire the real GEPA engine.** Pin the dependency, implement a custom adapter, reflect only from the 60-page split, evaluate admitted candidates on the fixed 30, preserve the Pareto frontier, and enforce atomic budgets and stop conditions.
4. **Expose a minimal run service.** One active run, bounded page workers, saved manifests/events/artifacts, live status polling, Stop and export. No distributed queue or restart/resume machinery.
5. **Build the UI.** GEPA tab with editable configuration, attempt usage, progress, stop reasons, candidate lineage/diffs, mean and per-query P1 comparisons, fidelity findings and export. Add model-compatible prompt selection to Content Studio.
6. **Verify and hand off.** Meaningful stubbed integration tests, frontend checks and an explicitly enabled small live smoke run. Do not automatically consume the full 100-attempt budget during verification.

## Review points still open

These are design defaults to refine during implementation review, not unanswered interview questions:

- Exact deterministic page-selection algorithm and eligibility handling if fewer than 90 hosts remain.
- Fidelity gate treatment of uncertainty, whole-proposal rejection, relationship to the circuit breaker, and whether to enforce it on ordinary Content Studio drafts immediately.
- Reflection evidence/context/token bounds and the treatment of missing P1 or judge outputs.
- GEPA merge settings, exact prompt segmentation and limits, and final candidate tie-breaking/recheck behavior.
- UI numeric bounds, rate-limit behavior, trace artifact schema and retention details.

Keep proposed choices visible in the implementation spec; do not represent them as already agreed.
