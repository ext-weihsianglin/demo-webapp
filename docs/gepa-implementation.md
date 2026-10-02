# GEPA implementation handoff

Implemented from the reviewed [plan](gepa-plan.md) and [spec](gepa-spec.md). The documentation review found no actionable defects.

## Current live handoff — 2026-10-02

The [experiment log](gepa-live-experiment.md) supersedes the initial wiring checks below. Current backend verification is **145 passed, 2 opt-in checks skipped**; the latest frontend build/typecheck and three API-error checks passed. No current candidate has demonstrated guarded held-out superiority. Baseline v7 remains selected. Historical numerical recommendations and the failed paired held-out comparison are preserved; their qualification is superseded by later guardrail corrections. The full reviewer caught a source-confirmed invented audit-trail feature but also made false positives on explicitly supported content; both are recorded in the experiment log.

The current edit boundary is `body-content-v3`: source DOM/ARIA and conservative class/ID navigation protections leave core upstream parser/scorer fields unchanged. The current semantic gate is `fidelity-slots-v2` using `gpt-4.1` (see the dated decision in spec §5): each edit is reviewed against its original chunk, and labels/topic plausibility cannot support new factual guarantees. A passed LLM judge is still fallible. Promotion compares the frozen full fidelity profile and edit boundary, so incompatible historical recommendations stay inspectable but cannot promote.

Research currently keeps P2 on `gpt-4.1-mini` and experiments with `gpt-4.1` reflection; application defaults remain unchanged. Reflection receives counts/types of mechanically validated edits. Missing traces report null rather than zero. Sparse policy wording has not reliably constrained the rewriter’s actual scope; counts make that failure visible without changing the fixed harness. Frozen manifests identify each trial’s model, instruction hashes, source roles, gate and limits.

The [scope-profile trial](../verification/gepa-run-a445fda1.json) failed during baseline on connection errors before reflection. A read-only authenticated provider check subsequently succeeded; a [separate recovery trial](../verification/gepa-provider-recovery-trial-v1.json) uses the same configuration/profile. The recovery candidate was superseded by the source audit; the full-reviewer trial `2ac71e74c52d4d3ba643de45fa2b3e3f` now uses otherwise identical frozen fields. [Restart checks](../verification/gepa-fidelity-model-restart-v1.json) confirm promotion of the old mini-reviewed recommendation is blocked. Inspect `GET /api/gepa/runs` for the latest status. Failed runs are not resumed or overwritten. The 100-attempt cap includes baseline/reflection P2 calls; extra judge/reflection/embedding calls remain separately counted. No new held-out data has entered search.

The backend uses the actual GEPA 0.1.4 optimizer with a custom adapter, instance-level Pareto selection, seeded rotating reflection batches and strict reflection-score admission. Source data, fixed prompt instructions, P1 and fidelity rules remain outside the mutable component. The first paragraph of baseline v7 is editable; composition reproduces the original baseline bytes. All six server-supported model families have explicit baseline registrations; registration is not evidence of optimized quality.

Initial search disables merge: one editorial component is mutated sequentially within the 100-attempt default. Complementary candidates remain visible on the page-level frontier. Merge exploration is deferred, rather than implied by a mutation lineage. Both proposal and iteration ceilings prevent cached/no-op search from spinning indefinitely.

Dataset preparation deterministically stratifies by chunk-count buckets (five-chunk increments, capped at four) and usable-query-count buckets (three-query increments, capped at three), then hashes seed/snapshot identities for selection and 60/30 roles. Sources are verified against completed Markdownify/v7/raw artifacts. Ten original observations per host remain in provenance; duplicate usable query text is evaluated once. Live scoring retains the explicitly deferred Markdownify context contract mismatch from upstream issue #15.

Implemented proposed defaults: only supported fidelity verdicts pass; uncertainty rejects the whole proposal. Semantic rejection affects candidate failure rate, but only technical failures trip the circuit. The same gate protects ordinary real drafts, adding one separately reported call. Missing original/proposed scores stop evaluation rather than fabricate a reward. Complete selection vectors are required for recommendation/promotion.

Run data and registry candidates are local ignored JSON artifacts. One process owns one active coordinator; no restart/resume or queue is implemented. Stop is checked before each rewrite, judge, reflection and embedding batch. Already dispatched results are saved. Technical completion counters and their event records share one ordering lock. Cache hits are free within the frozen run. Full-selection batches reserve all remaining uncached attempts before dispatch.

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
