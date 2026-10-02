# GEPA implementation handoff

Implemented from the reviewed [plan](gepa-plan.md) and [spec](gepa-spec.md). The documentation review found no actionable defects.

## Current live handoff — 2026-10-02

The [experiment log](gepa-live-experiment.md) supersedes the initial wiring checks below. Current backend verification is **162 passed, 2 opt-in checks skipped**; the latest frontend build/typecheck and three API-error checks passed. No current candidate has demonstrated guarded held-out superiority. Baseline v7 remains selected. Historical numerical recommendations and the failed paired held-out comparison are preserved; their qualification is superseded by later guardrail corrections. The full reviewer caught a source-confirmed invented audit-trail feature but also made false positives on explicitly supported content; both are recorded in the experiment log.

The current edit boundary is `body-content-v4`: source DOM/ARIA and conservative class/ID navigation and footer protections leave core upstream parser/scorer fields unchanged. The current semantic gate is `fidelity-slots-v4` using `gpt-5` with low reasoning effort (see the dated decision in spec §5): batches of at most eight edits are reviewed against their original chunks, and labels/topic plausibility cannot support new factual guarantees. A passed LLM judge is still fallible. Promotion compares the frozen full fidelity profile and edit boundary, so incompatible historical recommendations stay inspectable but cannot promote.

Research currently keeps P2 on `gpt-4.1-mini` and experiments with `gpt-5-mini` reflection (explicit low effort, 8,192-token output budget); application defaults remain unchanged. Reflection receives counts/types of mechanically validated edits. Missing traces report null rather than zero. Sparse policy wording has not reliably constrained the rewriter’s actual scope; counts make that failure visible without changing the fixed harness. Frozen manifests identify each trial’s model, instruction hashes, source roles, gate and limits.

The [scope-profile trial](../verification/gepa-run-a445fda1.json) failed during baseline on connection errors before reflection. A read-only authenticated provider check subsequently succeeded; a [separate recovery trial](../verification/gepa-provider-recovery-trial-v1.json) uses the same configuration/profile. The recovery candidate was superseded by the source audit; the full-reviewer trial `2ac71e74c52d4d3ba643de45fa2b3e3f` now uses otherwise identical frozen fields. [Restart checks](../verification/gepa-fidelity-model-restart-v1.json) confirm promotion of the old mini-reviewed recommendation is blocked. Inspect `GET /api/gepa/runs` for the latest status. Failed runs are not resumed or overwritten. The 100-attempt cap includes baseline/reflection P2 calls; extra judge/reflection/embedding calls remain separately counted. No new held-out data has entered search.

The backend uses the actual GEPA 0.1.4 optimizer with a custom adapter, instance-level Pareto selection, seeded rotating reflection batches and strict reflection-score admission. Source data, fixed prompt instructions, P1 and fidelity rules remain outside the mutable component. The first paragraph of baseline v7 is editable; composition reproduces the original baseline bytes. All six server-supported model families have explicit baseline registrations; registration is not evidence of optimized quality.

Initial search disables merge: one editorial component is mutated sequentially within the 100-attempt default. Complementary candidates remain visible on the page-level frontier. Merge exploration is deferred, rather than implied by a mutation lineage. Both proposal and iteration ceilings prevent cached/no-op search from spinning indefinitely.

Dataset preparation deterministically stratifies by chunk-count buckets (five-chunk increments, capped at four) and usable-query-count buckets (three-query increments, capped at three), then hashes seed/snapshot identities for selection and 60/30 roles. Sources are verified against completed Markdownify/v7/raw artifacts. Ten original observations per host remain in provenance; duplicate usable query text is evaluated once. Live scoring retains the explicitly deferred Markdownify context contract mismatch from upstream issue #15.

Implemented proposed defaults: only supported fidelity verdicts pass; uncertainty rejects the whole proposal. Semantic rejection affects candidate failure rate, but only technical failures trip the circuit. The same gate protects ordinary real drafts, adding separately reported sequential review calls. Missing original/proposed scores stop evaluation rather than fabricate a reward. Complete selection vectors are required for recommendation/promotion.

Prompt candidates and promoted `selected.json` pointers are versioned in `prompt-registry/`; commit the selected artifact and pointer together. Run data remains local and ignored. Promotion writes registry files without automatically committing or pushing them. One process owns one active coordinator; no restart/resume or queue is implemented. Stop is checked before each rewrite, judge, reflection and embedding batch. Already dispatched results are saved. Technical completion counters and their event records share one ordering lock. Cache hits are free within the frozen run. Full-selection batches reserve all remaining uncached attempts before dispatch.

Numeric UI/server bounds: 1–50 proposals, 1–20 reflection pages, 30–2,000 attempts, 1–20 workers, 1–3× mutable length, 1–20 consecutive failures, failure fraction (0,1], minimum 1–100 completions. Defaults remain 10 / 2 / 100 / 10 / 1.5× / 3 / 0.2 / 10. These are pre-run controls; increasing a cap is an explicit configuration choice.

Initial verification: locked dependency sync passed; 117 backend tests passed, 2 opt-in checks skipped; frontend production build and typecheck passed; diff whitespace check passed. A stubbed integration executes the actual GEPA optimizer end to end: one improved mutation uses 64 rewrite attempts, excludes selection pages from reflection, evaluates all 30 selection pages, exports traces and promotes explicitly. A separate real-provider smoke on one reflection page measured original v7 scores from cached original-space embeddings, made one P2 call that abstained and made one reflection mutation. It did not exercise the fidelity/rescore branch or make a quality claim. A second bounded live check produced six edits; the source-relative gate rejected the whole proposal, and reflection received those findings. Both bounded checks retained original scores. A later user-started baseline run saved 30 selection outcomes, including six applied, fidelity-approved proposals that were rescored with real v7/embeddings; optimization was interrupted before reflection. No candidate was promoted. See [live wiring evidence](../verification/gepa-live-smoke.json). No optimized prompt is automatically promoted, and classifier improvements do not establish citation uplift or factual truth.


Review fixes: prompt registry initialization is lazy, preserving source analysis when research configuration is invalid; candidate polling returns a locked deep snapshot; repeated/no-op mutations preserve full selection metrics; interrupted embedding phases save already dispatched call/token counts. Regression tests cover each operational boundary. The reviewed original design remains in Git history at `6c1788c`.


## Standards review

Two documented issues (eager registry startup dependency and stale README status) and one shared-state concern were identified and resolved. Focused follow-up found no remaining actionable standards defects.

## Spec review

Two preservation defects were identified and resolved: repeated candidates could lose selection metrics, and interrupted embeddings could lose usage counts. Follow-up identified one related overwrite after post-embedding scorer failure; that is fixed and covered by a regression. No remaining actionable spec defects are known.

Review axes remain separate: Standards 2 documented findings + 1 heuristic concern, all resolved; Spec 2 findings + 1 related follow-up edge, all resolved.


## Proxy error and interrupted-run recovery — 2026-10-02

A backend restart during user polling made the Next proxy return plain-text HTTP 500. The GEPA client attempted JSON parsing and displayed `Unexpected token I`. The shared API response reader now detects non-JSON proxy errors, preserves structured backend diagnostics and clears transient polling errors after recovery. Three frontend regression checks reproduce the exact parser symptom and verify the corrected behavior (`node --test frontend/app/api-client.test.mjs`). Production build/typecheck pass.

Graceful shutdown now signals the research budget, preventing further rewrite/judge/reflection/embedding phases after already dispatched work. Restarted coordinators restore saved candidate artifacts and attempt counters from page events without resuming or recommending partial runs. A shutdown/recovery regression passes. Unique atomic temporary paths protect artifacts during overlapping shutdown/recovery writes.

The user's interrupted `d0df3554` run retained all 30 baseline outcomes: 6 applied/rescored and 24 retained original, 30 P2 calls, 28 fidelity calls and 8 embedding batches. These are operational outcomes, not uplift evidence. The browser and API are available; no full optimized live run is claimed.

The full-reviewer trial was agent-stopped after retained `MainFoot` edits. [Actual-source replay and fresh boundary trial](gepa-live-experiment.md#retained-footer-containers) record the footer correction, unchanged core parser fields and otherwise identical evaluation configuration.

The [bounded fidelity batch handoff](gepa-live-experiment.md#bounded-fidelity-batches) records complete coverage, whole-proposal rejection, interruption usage accounting, provider replay/control and a new frozen trial. The original gate prompt is unchanged; only the batch protocol/profile changes.


## Persisted source rejection

Candidate detail now supports recording an operator source rejection after a run finishes. An immutable local record retains the candidate identity, prompt hash, reason and timestamp; exports include the record and event. Status preserves the numerical recommendation but marks its promotion blocked. Promotion and rejection share the coordinator lock, and a fresh coordinator reads the same rejection. This does not certify candidates without a rejection or alter the run's frozen reward vectors. The regression first failed on the missing interface, then passed through saved records, restart and blocked promotion. API checks cover malformed requests and the actual promotion endpoint. Current checks: 162 backend tests passed, two opt-in skipped; frontend build/typecheck and three error checks passed.

## Fidelity v4 and score sensitivity — 2026-10-02

The judge now constrains source references to known block IDs in each edit’s original chunk, distinguishes natural-language changes from faithful paraphrases, and reserves at least 8,192 output tokens. Frozen profiles include reasoning effort and schema limits; oversized schemas fail before dispatch. This changes ordinary drafts as well as research evaluation. All-or-nothing application remains. Six saved live checks reject three known unsafe edits and accept their faithful controls; they do not establish universal judge accuracy. An actual idle restart preserved the source rejection, 88-attempt history and baseline registry selection; unsafe promotion still returns HTTP 400. Fresh run c536094b now uses v4 with otherwise identical frozen evaluation configuration; no held-out comparison has used it yet.

Backend validation: 162 passed, two opt-in checks skipped. Model-selection API tests now also stub the external judge; they previously left that provider boundary live. See the [dated diagnostic evidence](gepa-live-experiment.md#fidelity-v4-and-score-sensitivity).


## Query-driven procedure monitoring — 2026-10-02

Issue #9 supersedes the narrow paragraph mutation policy for new runs. The `query-procedure-v1` component permits a full rewrite procedure before the unchanged v7 fixed contract, with a UI-configurable 1,000–16,000 character bound (6,000 default). Historical registry records remain readable; runs freeze the new component profile and request-budget policy, and older profiles cannot promote without reevaluation.

Reflection receives the trusted fixed P2 contract separately from complete untrusted source blocks, original chunk membership, all target queries, edits, before/after P1 scores and fidelity findings. Saved `reflection-input-N` artifacts expose the actual instructions, payload and schema. Candidates retain the proposed procedure, bounded reflection rationale, model/instruction hash and originating trace reference. P2 receives that rationale as untrusted user JSON plus the current page's full query set and original P1 feedback; it does not receive other reflection pages as evidence. The registry preserves this configuration across ordinary draft selection and restart.

Rewriting, reflection and fidelity preflight the complete input, schema, output reserve and a 2,048-token overhead allowance against the conservative 128,000-token budget. Oversized inputs fail before provider dispatch without truncation. Stub tests exercise each boundary. Grounded few-shot selection/provenance remains unfinished and disabled; this is the procedure/context slice of issue #9, not its completion.

Validation: 166 backend tests passed, 2 opt-in live checks skipped; frontend production build/typecheck and diff checks passed. A fresh live monitoring run `06880b29841e4dd69c589b7095e00663` uses gpt-4.1-mini P2, gpt-5-mini reflection, two proposed candidates, two reflection pages, concurrency 10 and a hard 100-attempt cap. It retains the frozen 60/30 validation roles and GPT-5 fidelity v4 policy. The preceding run `6082eccf` was stopped and archived at 81 attempts before this idle backend restart. No prompt promotion or held-out calls were made for the new trial. Live quality remains unproven.


### GPT-5-mini comparison and explicit procedure limit — 2026-10-02

The user requested a stronger P2 model after the two-proposal procedure trial produced zero accepted edits across 38 attempts. Run `06880b29` is archived with its plateau audit; both candidates tied their parents on reflection pages and were rejected before full selection evaluation. No P1 uplift claim follows from scores that retained original pages.

The GEPA tab now defaults to GPT-5-mini for rewriting and reflection. Fresh run `b918675d60c2495b878cafc067e18094` uses its model-specific baseline v7, the same frozen roles/seed, two proposals, 100 maximum attempts, concurrency 10 and the unchanged fidelity policy. Trusted reflection instructions explicitly state the configurable character maximum (6,000 for this run), suggest a 70% target to leave room, require complete sentences/steps and distinguish procedure steps from the fixed single-line plain-text rewrite contract. The manifest hashes these actual configured instructions. This guidance does not establish that future procedures will always be complete.

Fidelity rejection discards the complete page proposal and retains the original score, but does not trigger the technical circuit breaker or halt search. A tied candidate is rejected; the next proposal may proceed until the configured proposal/attempt limit, operator stop or technical circuit breaker. These semantics remain unchanged; no unsafe partial edits are applied.

Validation: 19 targeted GEPA coordinator/API tests passed, including the configured limit in actual reflection instructions and a custom-limit regression; frontend production build/typecheck and diff checks passed. No live held-out evaluation or promotion was made.


### Procedure repair and fidelity calibration — 2026-10-02

The user requested procedure validation and a source audit before further optimization. New procedures are checked for length, unfinished endings and known fixed-output conflicts; one explicitly logged, fully budgeted repair is allowed before registration. Raw returned text and validation errors are inspectable beside reflection requests. A failed repair preserves the parent. The versioned component profile freezes these rules for promotion compatibility. A live diagnostic produced a complete 5,226-character procedure; raw and registered text matched exactly.

The 12 saved-edit fidelity replay produced 11 verdicts and one timeout. Three disputes with the initial assistant assessments involved omitted details; three newly authored controls preserving those details all passed. An explicit retry of the unavailable case was rejected for omissions. The judge showed variability and one flawed rationale, but this audit did not establish a reason to weaken its policy. The original prompt/policy remains in service. These are assistant source assessments, not independent human labels or a measured false-positive rate. See [the complete audit and reproducible fixtures](gepa-fidelity-calibration.md).

Checks: 175 backend tests passed with two opt-in checks skipped; 27 targeted coordinator/API/procedure tests passed again after refining a validator false-positive edge case; diff checks passed. The backend was reloaded only after all runs were terminal. No full GEPA run, held-out comparison, P1 rescoring or promotion was started.


### Shared branch reconciliation with P1 v7.1

While publishing this work, the shared PR branch received PR #12 (canonical P1 v7.1 and 0.3.0 library). The procedure/calibration change was rebased onto that merge. Frozen audit inputs and historical v7 scores were preserved; fidelity calibration does not use P1 and was not rerun to change its results.

Installed the verified v7.1 artifact at the fresh ignored path `backend/data/scoring/model-v7.1.joblib`, preserving the old model. Local backend configuration now selects that path. Two installed-model tests now honor `P1_MODEL_PATH`, matching production, so both old artifacts and the new model can coexist. Combined verification: **177 backend tests passed, two opt-in checks skipped; frontend build/typecheck and diff checks passed**. The backend was restarted with the pinned v7.1 artifact successfully loaded.

The old `validation-90-v2` manifest binds v7/0.2.0 and is intentionally incompatible with the merged scorer/parser profile. A fresh compatible dataset must be prepared before the next full GEPA run. Historical experiment scores must not be compared as if measured by v7.1. No new optimization run was launched.


### Soft fidelity penalties for GEPA research — 2026-10-02

User requested penalties instead of the binary factual gate during optimization. Mechanically valid proposals now receive raw proposed P1 minus per-block factual deductions (default unsupported .05, uncertain .02, UI-configurable). Reflection receives exact rationales, evidence/block IDs and reward decomposition. Admission/Pareto/numerical ranking use reward; raw P1 and per-query deltas remain distinct. Ordinary drafting keeps its factual checks, and technical/mechanical failures keep their existing accounting. No proposal is partially applied or automatically promoted. See [the reward contract](gepa-fidelity-penalty.md). Historical binary-gate decisions above remain dated evidence.

Verification: **181 backend tests passed, two opt-in checks skipped; frontend production build/typecheck and diff checks passed**. Stubbed integration checks exercise negative rewards, penalty-based candidate ranking, reflection rationales and unchanged ordinary drafting checks. The local backend was reloaded with v7.1 and the browser shows the new penalty controls. No live optimization/provider call or promotion was made; a compatible frozen v7.1 dataset remains required.

### Readable experiment and prompt names — 2026-10-02

New experiments accept an optional UI name and receive a sanitized semantic slug with UTC timestamp and short unique suffix. Without a custom name, the model and fidelity-search purpose provide the prefix. Existing UUID run URLs/artifacts remain unchanged and receive readable display labels. Prompt-picker and candidate labels derive from reflection rationale (or editorial text for older candidates), with model and short prompt hash to distinguish variants; immutable prompt IDs and promotion pointers remain unchanged. Labels are escaped display metadata, never added to LLM instructions. Full backend suite (181 tests) and frontend build/typecheck passed; five focused tests then passed including two new naming checks and slug-based API/export/promotion coverage.

### PR #18 reconciliation and versioned registry checkpoint — 2026-10-02

Integrated PR #18 (registry ignore-rule removal) and its current-main ancestry, including the query-aware QA prompt and PR #17 Studio fidelity-review behavior. Checked in all 117 validated candidate artifacts present at the checkpoint plus selected pointers: GPT-4.1-mini baseline v7 and GPT-5-mini procedure `6b91e526e2c5940d0d11774d` (prompt hash `59288bcd…`). Historical and rejected candidates remain experimental; presence in the registry is not an endorsement. Full research traces, evaluations and source snapshots stay in ignored local storage. Prompt trace references require those local run artifacts. Candidates generated after this checkpoint require a subsequent commit.

Updated current research guidance and the HTML guide to match ordinary Studio behavior: retain drafts with fidelity findings for human review. Mechanical/self-reported-factual checks remain distinct. PR #17 bumps the edit boundary to v5; pre-v5 experiments cannot be newly promoted through a coordinator running the merged code. Previously selected registry pointers remain selected. The active experiment continues under its already-loaded v4 process; no restart or historical profile rewriting was performed.

Combined validation: 189 backend tests passed, two opt-in checks skipped; frontend production build/typecheck, both fidelity UI tests and diff checks passed. All candidate hashes/contracts and selected pointers resolved successfully.
