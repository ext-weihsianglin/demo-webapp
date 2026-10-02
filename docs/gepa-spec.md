# GEPA implementation specification

Status: implemented for local research; see [implementation handoff](gepa-implementation.md). The agreed requirements and proposed defaults below preserve the reviewed design record; the handoff identifies the implementation choices.

## 1. Scope and invariants

Implement the actual GEPA optimizer, a GEPA Optimization tab, saved research traces, and model-compatible prompt selection in Content Studio. Reuse the current P2 harness and frozen P1 scorer. Do not substitute a custom hill-climbing loop and label it GEPA.

Source content, target queries, metadata, judge inputs and model outputs remain untrusted. Preserve original snapshots, protected blocks, document-local identity boundaries and versioned baseline files. Neither reflection nor a candidate can change extraction, P1 weights/features, the output schema, evidence validation, the fidelity gate, fixed security/language instructions or the evaluation dataset.

P1 outputs remain classifier-score comparisons. Original source passages prove provenance; neither copied evidence nor an LLM gate proves factual truth.

## 2. Frozen dataset

**Agreed:** use 90 pages from distinct P1-validation hosts, with 60 reflection and 30 selection pages. P1 test hosts and payloads are outside both roles. Do not load the webapp test catalog as GEPA data.

**Proposed preparation:** join completed Markdownify corpus records to hash-verified v7 assignments; verify original source bytes and saved document identities using the existing preparation primitives. Select HTML pages with usable retained editable paragraphs and nonempty usable host query sets. Preflight source sufficiency, keyed-schema size and token budget with the fixed baseline. Record exclusions before selecting/finalizing the manifest. Unsupported host queries remain present; they are not a reason to invent answers or cherry-pick favorable queries.

Choose one eligible snapshot per host deterministically, stratified by page/chunk size and distinct host query count. Seed ordering and the partition; validate host, snapshot and payload isolation. If fewer than 90 hosts pass, fail preparation with an exclusion report rather than silently shrink or substitute test pages. Exact bucket boundaries are an implementation-review detail.

Manifest contents:

| Field group | Required identity |
|---|---|
| Dataset | ID, schema version, seed, preparation version, manifest hash |
| Upstream | Corpus manifest/records hashes, v7 split hash, package revision/module identity |
| Scorer | P1 version/model SHA, serving policy, context mismatch issue |
| Page | Host, snapshot/payload hash, href, source file hash/row, source format, saved document reference |
| Queries | Ordered distinct usable queries, original host records, query-set hash, exclusions |
| Role | `reflection` or `selection`; original P1 assignment must be `validation` |
| Eligibility | Baseline preflight result and deterministic exclusion reasons |

Source files and generated data remain ignored local artifacts. Run startup validates the frozen manifest rather than regenerating or resampling it.

## 3. Prompt contracts and registry

**Agreed:** evolve editorial strategy only; use model-specific baselines/candidates and explicit promotion. Preserve `backend/app/prompts/rewrite-page-v7.txt` as the baseline source.

**Proposed layout:**

```text
prompt-registry/
  contracts/
    rewrite-page-v7/                 # fixed security, preservation and output instructions
  p2/
    gpt-4.1-mini/
      baseline/                     # committed reference/metadata for baseline v7
      candidates/<candidate-id>/    # ignored generated prompt + metadata
      selected.json                 # ignored local default pointer
    gpt-5-mini/
      baseline/                     # explicitly registered model-specific baseline
      candidates/<candidate-id>/
      selected.json
backend/data/gepa/
  datasets/<dataset-id>/
  runs/<run-id>/
```

Run artifacts are separate from registry entries. A candidate's full effective prompt can be reconstructed and hashed without its run directory. A future model family must be explicitly registered; an existing model-specific optimized prompt is not silently copied or selected.

Candidate metadata includes ID, model, parent IDs, run ID, baseline ID, mutable-text hash, effective-prompt hash, fixed-contract version/hash, character count, creation time and evaluation status. Baseline entries distinguish registered support from measured performance on that model.

Resolve opaque prompt IDs server-side; never accept a client filesystem path. Verify hashes and model/contract compatibility before use. Candidate artifacts are immutable; promotion changes only a model's local selected pointer.

Compose the baseline from fixed and mutable regions while reproducing its original instruction bytes and behavior. Both `plan_requests` token accounting and the provider call must receive the exact resolved prompt. Current module-global `PROMPT` is not sufficient for candidate injection. Cache keys and telemetry use the effective hash, not just a display name.

**Agreed:** cap mutable text at 1.5 times the initial mutable character count, configurable before a run. Proposed counting is Unicode code points. Empty, oversized or malformed candidates are rejected before page calls, with rejection reasons retained. Fixed instructions are not counted in the evolving component and cannot be edited by reflection.

## 4. Page evaluation and reward

```text
resolve immutable candidate + page/query identities
  → score original document using frozen P1
  → validate budget and reserve rewrite attempt
  → P2 whole-page call and existing mechanical validation
  → source-relative fidelity gate for changed valid proposals
  → apply accepted edits to a proposed document
  → refresh chunks, outline, serialization and affected embeddings
  → score proposed document with the same P1/query set
  → save outcome, evidence, scores, findings and usage
```

Do not execute source HTML. Preserve source metadata/inventory for proposal scoring. Reuse upstream Markdownify and original-space embedding orchestration; no PCA or lexical-only replacement.

For page `p` with `Qp` distinct usable queries:

```text
page_score(p, candidate) = mean(P1(proposed_or_retained_original_p, q) for q in Qp)
selection_score(candidate) = mean(page_score(p, candidate) for p in fixed_30_selection_pages)
```

Report each query's original, baseline and candidate scores plus deltas; report page means and aggregate means. Query regressions are visible but mean P1 has priority. A fixed original-page score is a measured fallback, not an invented penalty.

**Agreed:** valid abstention/no useful change retains original content and scores. Invalid proposals retain original content/scores and count as failures. Never exclude a failed page from the candidate's denominator.

A missing original P1 score, unavailable required embedding or incompatible frozen inputs cannot produce a fabricated score. **Proposed:** fail preflight when known in advance; otherwise record evaluation unavailability and stop the run. An incomplete selection vector is not rankable or promotable.

## 5. Factual-fidelity gate

**Agreed direction:** a separate `gpt-4.1-mini` call checks proposed edits against original source and copied supporting passages before acceptance/scoring. This is source-relative verification, not verification against external facts.

**Implementation decision — 2026-10-02:** the fixed reviewer becomes `gpt-4.1` after a validation source audit confirmed that mini approved an invented full-audit-trail feature. A full-model audit rejected that edit, but also falsely flagged explicitly supported Google Drive steps; its findings remain fallible and conservative rejection can reduce yield. The [audit and source comparison](gepa-live-experiment.md#reviewer-capacity-and-audit-fallibility) record both errors. P2 remains `gpt-4.1-mini`; instructions, schema, scope and output budgets stay fixed. Fresh baseline/challenger evaluation is required and old reviewer profiles cannot promote. Ordinary drafts also use this separate judge and require access to its model.

**Proposed input:** validated edit IDs, immutable before/after text, relevant original chunk context, selected evidence IDs/full copied passages and language hints. Bind everything to snapshot/chunk/block identities. Source/query content is data; the judge is forbidden from following embedded instructions or using external knowledge. No hidden chain-of-thought is requested or logged.

Check every changed block for:

- New unsupported factual assertions, numbers, comparisons, guarantees or causal claims.
- Contradiction, altered negation, lost uncertainty/conditions/exceptions or material factual omission.
- Unsupported superlatives, urgency or sensational claims added to chase query scores.
- Language changes or protected-content deviation missed by mechanical checks.

Useful clearer wording and stronger organization are allowed when the supported meaning remains intact. Do not reject a rewrite merely because its style changes.

**Proposed output schema:** per-edit `supported / unsupported / uncertain`, categorized findings, a brief rationale and source block references. Validate envelope completeness, known IDs and any quoted passages mechanically. Unchanged blocks need no gate call. Missing/refused/malformed judge output is a gate infrastructure error, not a fabricated supported verdict.

**Proposed disposition:** accept only when every edit is supported. Unsupported or uncertain findings reject the whole proposal; retain original content and its score and expose the findings to reflection. No silent partial application. Apply identical gate settings to baseline and candidates.

**Open circuit detail:** count semantic rejections in candidate failure statistics and promotion checks, but treat them as normal optimization feedback rather than run-level infrastructure circuit-breaker failures. Judge/provider errors count toward that breaker. This distinction is proposed and must remain visible until reviewed.

Gate calls/tokens/latency are separately recorded; the 100 cap counts P2 rewrite attempts, not all provider calls. Proposed additional ceilings are at most one judge call per changed validated rewrite, no automatic retries, and at most one reflection proposal call per permitted mutation. Keep these phases visible in the UI.

**Open serving detail:** initial research must use the gate. Applying it to all ordinary Content Studio drafts is proposed, with a clear gate status in the result; it has not been explicitly settled. Promoted candidates must not appear to inherit fidelity assurances when the ordinary draft path bypasses the gate.

## 6. GEPA adapter and search

Pin an appropriate GEPA release and lock transitive dependencies during implementation. Use its [custom adapter protocol](https://gepa-ai.github.io/gepa/guides/adapters/) to integrate existing rewrite/evaluation behavior and structured reflective feedback. Use the [core optimizer](https://gepa-ai.github.io/gepa/api/core/optimize/) for the real search, budget/stop integration and Pareto candidate history.

Map `candidate = {editorial_strategy: mutable_text}` to a resolved effective prompt. Each data instance is a frozen page with its complete query set. The adapter returns page scores, proposed/retained outcomes and captured trajectories.

Reflection receives only examples from the 60-page reflection split: original/source evidence, applied or rejected edits, per-query and page P1 deltas, fidelity findings, validation failures and concise diagnostics. It never receives selection-page content or test-page traces as mutation examples. Candidate selection may use the fixed selection scores, as intended.

Preserve candidates that help different selection pages on the instance-level Pareto frontier; aggregate mean determines the final recommendation. **Proposed:** standard Pareto parent selection, rotating seeded reflection batches, strict improvement for admitting reflective mutations, and merging complementary candidates within the same proposal/attempt ceilings. Explicitly disable assumptions that a saturated classifier score proves a page is perfect. Exact GEPA options and merge counts are implementation-review details.

The baseline is immutable. Every mutation or merge records its parent IDs, prompt diff, reasoning summary, component bounds and admission/rejection outcome. Rejected prompt proposals consume proposal/reflection budgets when those calls occurred, but do not consume rewrite attempts if no page was attempted.

## 7. Budgets, concurrency and stopping

**Agreed initial defaults:**

| Knob | Default |
|---|---:|
| Proposed candidates | 10 |
| Reflection pages per mutation | 2 |
| Rewrite attempts | 100 |
| Concurrent page evaluations | 10 |
| Mutable-text length multiplier | 1.5 |
| Consecutive-failure breaker | 3 |
| Failure-rate breaker | >20%, after at least 10 attempts |

Expose these before Start; validate finite positive bounds and sensible minimum budgets. Numeric upper bounds are proposed implementation details. Freeze all settings in the run manifest. The 30-page selection set is not changed mid-run to fit a budget.

Use an atomic attempt reservation before scheduling each uncached P2 page evaluation. Concurrent workers must never exceed the cap. Return unused reservations for failures before any P2 request; dispatched failed requests still consume an attempt. Never let hidden SDK retries evade accounting.

Before admitting a candidate to full selection evaluation, reserve capacity for all uncached selection pages. Release unused reservations if work stops. A GEPA metric-call counter is not sufficient on its own: track actual uncached rewrite attempts through the adapter/harness. Cache hits do not consume attempts.

**Proposed breaker accounting:** cumulative run-level technical failures divided by completed uncached P2 evaluations, starting after ten completions; consecutive failures follow saved completion-event order. Valid abstentions and cache hits do not count as technical failures. Include baseline evaluations. Separately show semantic rejection rate. Do not hide 429 responses or silently retry them; expose rate-limit stop/failure reasons and let the user lower concurrency for a new run.

Stop reasons distinguish user stop, proposal limit, attempt budget, circuit breaker, input/scorer incompatibility and fatal infrastructure failure. On Stop, schedule no further pages or provider calls. Already dispatched calls may complete and are saved; an evaluation needing another call remains interrupted/unscored. Partial candidate evaluations cannot become a recommendation. This precise behavior is a proposed clarification of the agreed in-flight-call semantics.

## 8. Caching and comparability

**Agreed:** reuse repeated candidate/page evaluation results within a run. Freeze both generation-model and reflection-model settings. Changing model/settings/dataset starts a new run.

Cache identity includes dataset/page/source/query hashes, candidate effective-prompt hash, fixed contract, generation settings/tone/structure permission, parser package identity, P1 model/features/serving policy, embedding recipe and fidelity-gate prompt/model/settings. Do not reuse a result after any affecting identity changes.

**Proposed:** start with per-run immutable evaluation reuse rather than cross-run rollout reuse. Reuse upstream embedding vectors across runs by their existing exact cache keys. Candidate evaluations represent recorded stochastic samples, not statistically certain expected scores; repeated winner confirmation can be added later without changing historical traces.

## 9. Run service and local storage

**Agreed:** simple browser-open operation, saved traces, no pause/resume or automatic restart.

**Proposed:** one active run per backend process, an in-process coordinator and bounded page-worker pool. The frontend polls status/events; no distributed task queue. Reject a second active run with an explicit conflict. A browser reload can inspect existing status without starting duplicate work.

Run state:

```text
created → preflighting → running → completed
                         └→ stopping → stopped
created/preflighting/running → failed
server restart with unfinished work → interrupted (read-only)
```

Save an immutable config/identity manifest, append-only ordered events, atomic summary snapshots, candidate metadata and per-page evaluation artifacts. Completed artifacts remain inspectable/exportable after stop or restart; automatic continuation is out of scope.

## 10. Trace contract

| Artifact | Required content |
|---|---|
| Run manifest | Dataset roles/hashes, baseline/contract, model settings, P1/embedding identities, gate identity, limits, seed, timestamps |
| Candidate record | Parent IDs, full mutable/effective prompt and hashes, diff, proposal summary, bounds, admission and frontier status |
| Page evaluation | Candidate/page/query identities, role, original and applied proposed blocks, evidence, validation and gate findings, outcome |
| Score record | Ordered original/baseline/candidate per-query values, page mean, deltas and full-selection aggregate when complete |
| Usage record | Phase, provider/model, calls, token counts, cache hits, latency, attempt reservations/consumption, nullable cost |
| Event | Monotonic event ID, time, run/candidate/page IDs, phase, state change, counts and safe reason codes |
| Export | Config, candidates/diffs, score tables, findings, usage and final stop/recommendation summary |

Record prompt changes even when rejected and score changes even when negative. Partial results are labeled partial. Costs are null unless model-specific prices are configured; do not invent a dollar cap from missing prices. Never save credentials, authentication headers or raw provider error bodies. Local exports can contain source/proposed content; do not publish them automatically.

## 11. Proposed HTTP interfaces

These routes are design proposals, not existing endpoints.

| Route | Responsibility |
|---|---|
| `GET /api/prompts?model=...` | Compatible baseline/candidates, selected default, identities and status |
| Existing `POST /api/draft` + `prompt_id` | Resolve model-compatible prompt; record effective identity |
| `GET /api/gepa/datasets` | Prepared optimization manifests and role counts |
| `POST /api/gepa/runs` | Validate/freeze config, create run, return run ID without blocking for completion |
| `GET /api/gepa/runs/{id}` | Settings, phase, usage, baseline, candidates and stop reason |
| `GET /api/gepa/runs/{id}/events?after=...` | Incremental saved progress events |
| `POST /api/gepa/runs/{id}/stop` | Idempotent stop request |
| `GET /api/gepa/runs/{id}/candidates/{candidate_id}` | Prompt diff, lineage and score/fidelity detail |
| `GET /api/gepa/runs/{id}/export` | Local review/download artifact |
| `POST /api/prompts/{id}/promote` | Explicit compatible model-default selection |

Unknown IDs, incompatible model/prompt pairs, changed artifacts, overlapping active runs and unavailable frozen inputs return explicit errors. Prompt selection must affect token budgeting and actual provider instructions identically. No arbitrary model IDs, file paths or source instructions become server configuration.

## 12. UI behavior

**Agreed:** add a GEPA Optimization tab and Model + Prompt selectors in Content Studio.

The GEPA tab shows dataset roles, model/prompt settings, editable limits, the fixed-contract and P1 interpretation disclosures, and Start. During execution it shows phase, rewrite attempts remaining, concurrent work, separate reflection/gate/embedding usage, candidate lineage and mean P1 changes. Stop stays available without disrupting source inspection.

Candidate detail shows full prompt/diff, page/query comparisons, rejected edits and evidence/gate findings. A leaderboard distinguishes baseline, partial, rejected, frontier, fully evaluated and recommended candidates. Export includes the review data. Promotion is explicit and never automatic.

Content Studio filters prompts by selected model, visibly labels experimental candidates and selected defaults, clears stale drafts after a model/prompt change, and records both identities in draft telemetry. **Proposed:** allow explicit inspection/testing of structurally valid experimental candidates without making them defaults. Candidates with incompatible contracts or missing artifacts are disabled.

## 13. Acceptance criteria and verification

Use stubbed provider clients for ordinary verification. Live runs require an explicit flag and a small configured budget.

- Manifest preparation excludes all P1-test hosts/payloads, produces 60/30 roles and preserves complete usable host queries and immutable source identities.
- Baseline prompt composition reproduces v7; choosing a registered candidate changes both preflight tokens and provider instructions. Model mismatch and fixed-contract modification are rejected.
- A real GEPA integration with deterministic stub feedback produces mutations, parent/child traces and selection results; selection/test source examples never enter reflection inputs.
- Per-query/page/aggregate math uses the fixed denominator. Invalid/abstained/rejected outcomes retain original scores; unavailable originals are never fabricated.
- Gate fixtures catch unsupported numbers, changed negation, lost qualifiers, invented superlatives and judge-output injection; supported paraphrases pass. Uncertainty behavior follows the reviewed policy.
- Ten-worker tests prove attempt reservations cannot exceed 100, full-selection admission respects remaining capacity, cache hits are free, and stopped/interrupted partial candidates cannot be promoted.
- Breaker fixtures cover isolated failures, three consecutive failures, >20% after ten completions, provider failures and the reviewed semantic-rejection distinction.
- Saved artifacts reconstruct every candidate and comparison; stop/restart preserves inspection without automatic resume. Exports contain no credentials.
- UI supports run configuration/progress/stop/detail/export and model-compatible prompt selection. Existing extraction/drafting flows remain usable.
- Run locked backend sync/tests, frontend build/typecheck and diff checks. An explicitly enabled small live smoke confirms rewrite, gate, embeddings, scoring and traces; it does not establish generalization or citation uplift.

## 14. Suggested module boundaries

**Proposed:** `app/prompt_registry.py` owns lookup/composition/promotion; `app/fidelity.py` owns the immutable source-relative judge; `app/gepa/adapter.py` bridges GEPA to evaluation; `app/gepa/evaluation.py` owns page outcomes/caching/accounting; `app/gepa/runs.py` owns lifecycle/workers/stop; `app/gepa/storage.py` owns artifacts/events; preparation scripts own frozen dataset construction. Existing extraction, scoring and rewriting remain independent services. HTTP handlers only validate requests and invoke these interfaces.

Frontend run controls, candidate detail and model-compatible prompt selection should be separate components. No GEPA execution belongs in browser code, and provider keys stay server-side.

Implementation decision — 2026-10-02: fidelity-slots-v3 uses sequential batches of at most eight edits, with original-chunk-only evidence, complete coverage and whole-proposal rejection. This supersedes the single-review-call implementation after a saved bulk review missed commercial-scope drift that bounded replay rejected. The instruction hash and gpt-4.1 reviewer remain unchanged. Calls/latency increase and are separately accounted; the frozen profile includes batch size. See [bounded fidelity batch evidence](gepa-live-experiment.md#bounded-fidelity-batches).


Implementation decision — 2026-10-02: candidate source review can record an immutable rejection through `POST /api/gepa/runs/{id}/candidates/{candidate_id}/reject` with a nonblank reason (maximum 2,000 characters). This is an operator assessment, not a factual-verification certificate. The record binds the candidate prompt hash and is included in exports. Numerical recommendations, scores and frozen search traces remain intact, but promotion of a source-rejected recommendation is blocked. Rejections remain effective after coordinator restart. Candidate review in the UI shows the reason and offers a rejection control after the run finishes. This closes the gap between a documented source finding and enforceable promotion behavior.

Implementation decision — 2026-10-02: `fidelity-slots-v4` replaces the full 4.1 reviewer with GPT-5, low reasoning effort and an 8,192-token minimum output reserve. Provider schemas restrict source IDs to original-chunk block IDs and require nonempty support for supported verdicts. Reasoning and conservative schema-size limits are frozen in compatibility profiles. Whole-proposal rejection and original-score retention remain unchanged. This follows saved unsafe/faithful controls, not held-out feedback. Judge fallibility, additional latency and small observed P1 sensitivity remain open limitations; see [evidence](gepa-live-experiment.md#fidelity-v4-and-score-sensitivity).


## Query-driven procedure monitoring — 2026-10-02

Issue #9 supersedes the narrow paragraph mutation policy for new runs. The `query-procedure-v1` component permits a full rewrite procedure before the unchanged v7 fixed contract, with a UI-configurable 1,000–16,000 character bound (6,000 default). Historical registry records remain readable; runs freeze the new component profile and request-budget policy, and older profiles cannot promote without reevaluation.

Reflection receives the trusted fixed P2 contract separately from complete untrusted source blocks, original chunk membership, all target queries, edits, before/after P1 scores and fidelity findings. Saved `reflection-input-N` artifacts expose the actual instructions, payload and schema. Candidates retain the proposed procedure, bounded reflection rationale, model/instruction hash and originating trace reference. P2 receives that rationale as untrusted user JSON plus the current page's full query set and original P1 feedback; it does not receive other reflection pages as evidence. The registry preserves this configuration across ordinary draft selection and restart.

Rewriting, reflection and fidelity preflight the complete input, schema, output reserve and a 2,048-token overhead allowance against the conservative 128,000-token budget. Oversized inputs fail before provider dispatch without truncation. Stub tests exercise each boundary. Grounded few-shot selection/provenance remains unfinished and disabled; this is the procedure/context slice of issue #9, not its completion.

Validation: 166 backend tests passed, 2 opt-in live checks skipped; frontend production build/typecheck and diff checks passed. A fresh live monitoring run `06880b29841e4dd69c589b7095e00663` uses gpt-4.1-mini P2, gpt-5-mini reflection, two proposed candidates, two reflection pages, concurrency 10 and a hard 100-attempt cap. It retains the frozen 60/30 validation roles and GPT-5 fidelity v4 policy. The preceding run `6082eccf` was stopped and archived at 81 attempts before this idle backend restart. No prompt promotion or held-out calls were made for the new trial. Live quality remains unproven.


### Soft fidelity penalties for GEPA research — 2026-10-02

User requested penalties instead of the binary factual gate during optimization. Mechanically valid proposals now receive raw proposed P1 minus per-block factual deductions (default unsupported .05, uncertain .02, UI-configurable). Reflection receives exact rationales, evidence/block IDs and reward decomposition. Admission/Pareto/numerical ranking use reward; raw P1 and per-query deltas remain distinct. Ordinary drafting keeps its factual checks, and technical/mechanical failures keep their existing accounting. No proposal is partially applied or automatically promoted. See [the reward contract](gepa-fidelity-penalty.md). Historical binary-gate decisions above remain dated evidence.
