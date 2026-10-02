# GEPA optimization design interview

Status: interview stopped at the user's request. The consolidated [plan](gepa-plan.md) and [implementation spec](gepa-spec.md) are the current review documents. This file preserves interview provenance; proposed and superseded ideas below are not new requirements. Optimizer implementation remains pending.

## Current priority

The user paused GEPA design to establish upstream parity first: P1 v7, its exact OpenAI embedding inputs and pooling, and the Markdownify corpus preprocessing path for future HTML. Webapp held-out examples must strictly belong to the scorer's test split. GEPA will subsequently use train/validation data. The historical extraction-held-out bundle does not satisfy the new test-only requirement; do not treat its label as proof of test membership.

The user subsequently directed the webapp to defer the mixed-parser context mismatch and file an upstream issue. The implementation uses current Markdownify contexts under `markdownify-context-v1`, with that limitation visible. [Issue #15](https://github.com/ext-weihsianglin/content-optimization-system/issues/15) tracks the canonical inference contract. No retraining was performed. After the foundation PR, an interactive smoke check completed a P2 v7 draft and v7 rescoring with fresh OpenAI embeddings; this confirms live wiring, not rewrite quality or generalization.

## Settled scope

- Learn a reusable P2 prompt on a frozen set of snapshots and complete target query sets, aiming to generalize to future HTML pages.
- Freeze 90 eligible pages from distinct P1-validation hosts: 60 GEPA reflection pages and 30 GEPA candidate-selection pages. Evaluate baseline rewrites on the 30 selection pages upfront; evaluate reflection pages on demand. Mutations receive reflection examples from the 60 and candidates are compared on the fixed 30. P1 test stays outside optimization.
- P1 is the initial score component; allow additional components later. Aggregation is the mean P1 over each page's distinct queries, followed by an equal-weight mean over pages. Record deltas against original-page scores and baseline-prompt rewrites. Selection mean P1 takes priority over individual-query regressions, which remain visible. Recommend candidates only when selection mean exceeds baseline and failure rate is no worse; explicit promotion changes the model default, otherwise baseline remains.
- Evolve editorial strategy while preserving fixed source handling, protected-content rules, evidence requirements and output contracts. Limit the mutable editorial component to a configurable 1.5 times its initial text length. The user also approved designing a separate gpt-4.1-mini factual-fidelity gate before applying/scoring rewrites, checking changed blocks against original text and supporting passages. Gate outcomes, uncertainty handling and circuit-breaker integration remain unresolved; model-assisted checks do not establish factual truth.
- The user originally identified `rewrite-page-v6.txt`; the requested latest PR #3 refresh at `cf84c33` superseded this with `rewrite-page-v7.txt`. Preserve its keyed-edit contract when adding prompt candidates.
- Deliver a functioning GEPA loop wired into a GEPA Optimization tab, with prompt changes and P1 score traces. Expose candidate limit, reflection batch size, evaluation budget and prompt-growth limit as editable run settings. Defaults: ten proposed candidates, two reflection pages per mutation, full 30-page selection evaluation for admitted candidates, and a hard cap of 100 page-rewrite attempts. Count baseline attempts within the cap; reflection calls and embedding calls have separate usage counters. Cache repeated candidate/page results. Q19 accepted baseline-on-selection plus on-demand reflection and the two-page default: 30 baseline selection attempts + 60 for two full challengers + up to eight parent/challenger reflection attempts gives an illustrative total of 98. The proposal limit is a ceiling; the attempt budget may terminate earlier.
- Default page-evaluation concurrency is ten, adjustable in the UI. Mutation decisions remain sequential. Page evaluations are independent; no measured account throughput limit has been established. Provider 429 responses must remain visible and concurrency must respect stop semantics.
- Start optimization with gpt-4.1-mini for both rewriter and reflection, configured separately and frozen per run; support separately identified gpt-5-mini optimized prompts later. The registry must distinguish model-specific baselines and candidates.
- Use a simple browser-open research workflow: Start, live progress, Stop and inspect/export, saving traces as operations complete. No pause/resume, job queue or automatic restart initially. Stop prevents subsequent calls; an in-flight operation finishes and is recorded.
- Preflight source-insufficient pages before freezing the dataset. Isolated invalid proposals retain the original page and its measured score, with no rewrite applied; they remain explicit failures. Stop the run after three consecutive failures, or a failure rate greater than 20% after at least ten attempts. Distinguish validation/schema failures from provider failures.
- Model-specific prompt registry entries record parent, run, prompt hash and fixed-contract version. Prompt promotion is explicit per model. Content Studio must support choosing both the rewriter model and a compatible registered prompt; no implicit cross-model prompt reuse.

## Repository facts

The checkout reuses a frozen P1 scorer and whole-page P2 rewriter. Prompt injection must affect both token preflight and provider instructions. P2 validates edits and resolves evidence passages from source block IDs; these checks establish provenance, not factual entailment. Current language checks remain part of validation.

The app currently has synchronous drafting and ephemeral browser state, without research jobs or run persistence. The assigned checkout now has the pinned local v7 model and 97-host test-only example bundle. GEPA still requires its own train/validation manifests and run controls.

Existing extraction-held-out examples are exploratory for rewrite optimization. Using them in search makes them optimization data; they cannot also serve as an untouched final rewrite evaluation set.

## Open decisions

Factual-fidelity gate outcomes, uncertainty handling and circuit-breaker integration; deterministic dataset sampling and eligibility details; detailed trace schema.

## Historical dataset discussion (superseded by Q14)

The user clarified that webapp held-out examples must strictly come from the test split; GEPA will use train/validation after upstream parity is established. P1 fitting splits and P2 prompt-search roles are distinct: GEPA validation participates in candidate selection and is therefore exposed to optimization. Preserve an independent final test role if generalization is the intended claim.

Historical proposal, superseded: reuse eligible P1 training pages for GEPA reflection and eligible P1 validation pages for candidate selection, with frozen P1 weights and host/payload isolation. If P1 in-sample scoring materially changes candidate ranking, a new pool unseen by P1 or out-of-fold scoring is a stronger follow-up. Higher frozen-P1 scores alone do not establish real citation gains.

The historical example-preparation path used an extraction manifest's `dev`/`heldout` roles, not proof of P1 train/validation/test membership. The merged preparation path now verifies v7 assignments and serves test only. Verify membership before assigning P2 roles. Prior rewrite QA also exposed some held-out pages to prompt development; distinguish these from untouched final examples.

Read-only membership audit: the extraction manifest at `/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/evaluation/extraction/manifest.json` contains 60 development and 40 held-out snapshots. Joining hostnames to `/Users/ext-weihsiang.lin/Documents/profound/data/content-optimization-system/trad_ml_scorer/v2/host_splits.json` places the 40 extraction-held-out snapshots in 29 P1 training, 5 P1 validation and 6 P1 test hosts. The 60 development snapshots fall in 54 P1 training, 1 P1 validation and 5 P1 test hosts. Extraction and P1 holdouts are different partitions.

## Integration references

- [GEPA adapters](https://gepa-ai.github.io/gepa/guides/adapters/) describe evaluation batches and reflective feedback for custom systems.
- [GEPA callbacks](https://gepa-ai.github.io/gepa/guides/callbacks/) describe optimization lifecycle events for trace capture.

## Resumed interview evidence and preferences

The frozen v7/corpus audit found 771 eligible train hosts, 97 validation hosts and 97 test hosts, with 7,478 / 944 / 943 distinct selected-or-needs-review snapshots respectively. These broad counts require final usable-query/preflight filtering; selected HTML alone supports 30 train plus 30 validation hosts. Sampling can stratify chunk counts and host query counts with seeded identity ordering. GEPA must not sample test hosts.

Q10/Q11/Q13 accepted the explicit failure, circuit-breaker, minimal lifecycle and model-specific registry proposals above, including Content Studio model-plus-prompt selection. Existing strict schema plus backend validation can still report invalid/unsupported/incomplete outputs; source-insufficient eligibility is a separate preflight condition.

Q12: the user asked why GEPA needs pages from both P1 train and validation, proposing a validation-only pool of roughly 90 pages. This is compatible with the agreed test exclusion. P1 split membership and GEPA reflection/selection roles are separate; a validation-only pool can be partitioned into GEPA train and GEPA validation. Q14 subsequently settled 90 eligible pages, partitioned into 60 reflection and 30 selection pages. Q15 confirmed gpt-4.1-mini as the reflection default. Q16 lowered the hard page-rewrite cap from 600 to 100 and requires editable UI knobs. Q17 accepted mean-first selection and explicit promotion. Q18 accepted the prompt-length guardrail and raised semantic fidelity as a required concern.

Q20: the user requested ten concurrent page evaluations rather than the proposed conservative default of two. Q21 accepted designing the source-relative semantic gate, with its extra inference and separate usage accounting. This is still design work, not authorization to claim a completed guardrail.
