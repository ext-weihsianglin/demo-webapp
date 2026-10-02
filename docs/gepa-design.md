# GEPA optimization design interview

Status: GEPA design in progress; upstream foundation integrated locally.

## Current priority

The user paused GEPA design to establish upstream parity first: P1 v7, its exact OpenAI embedding inputs and pooling, and the Markdownify corpus preprocessing path for future HTML. Webapp held-out examples must strictly belong to the scorer's test split. GEPA will subsequently use train/validation data. The historical extraction-held-out bundle does not satisfy the new test-only requirement; do not treat its label as proof of test membership.

The user subsequently directed the webapp to defer the mixed-parser context mismatch and file an upstream issue. The implementation uses current Markdownify contexts under `markdownify-context-v1`, with that limitation visible. [Issue #15](https://github.com/ext-weihsianglin/content-optimization-system/issues/15) tracks the canonical inference contract. No retraining or live provider checks were performed.

## Settled scope

- Learn a reusable P2 prompt on a frozen set of snapshots and complete target query sets, aiming to generalize to future HTML pages.
- P1 is the initial score component; allow additional components later. Improving component means is the initial direction, with aggregation and acceptance rules still unresolved.
- Evolve editorial strategy while preserving fixed source handling, protected-content rules, evidence requirements and output contracts.
- The user originally identified `rewrite-page-v6.txt`; the requested latest PR #3 refresh at `cf84c33` superseded this with `rewrite-page-v7.txt`. Preserve its keyed-edit contract when adding prompt candidates.
- Deliver a functioning GEPA loop wired into a GEPA Optimization tab, with prompt changes and P1 score traces.

## Repository facts

The checkout reuses a frozen P1 scorer and whole-page P2 rewriter. Prompt injection must affect both token preflight and provider instructions. P2 validates edits and resolves evidence passages from source block IDs; these checks establish provenance, not factual entailment. Current language checks remain part of validation.

The app currently has synchronous drafting and ephemeral browser state, without research jobs or run persistence. The assigned checkout now has the pinned local v7 model and 97-host test-only example bundle. GEPA still requires its own train/validation manifests and run controls.

Existing extraction-held-out examples are exploratory for rewrite optimization. Using them in search makes them optimization data; they cannot also serve as an untouched final rewrite evaluation set.

## Open decisions

Dataset split and identities; score aggregation and failure treatment; model configuration; run budgets and controls; persistent traces and restart behavior; candidate comparison and promotion.

## Dataset discussion (Q5, unresolved)

The user clarified that webapp held-out examples must strictly come from the test split; GEPA will use train/validation after upstream parity is established. P1 fitting splits and P2 prompt-search roles are distinct: GEPA validation participates in candidate selection and is therefore exposed to optimization. Preserve an independent final test role if generalization is the intended claim.

Proposed direction, not yet agreed: reuse eligible P1 training pages for GEPA reflection and eligible P1 validation pages for candidate selection, with frozen P1 weights and host/payload isolation. If P1 in-sample scoring materially changes candidate ranking, a new pool unseen by P1 or out-of-fold scoring is a stronger follow-up. Higher frozen-P1 scores alone do not establish real citation gains.

The shipped example-preparation path uses an extraction manifest's `dev`/`heldout` roles, not proof of P1 train/validation/test membership. Verify membership before assigning P2 roles. Prior rewrite QA also exposed some held-out pages to prompt development; distinguish these from untouched final examples.

Read-only membership audit: the extraction manifest at `/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/evaluation/extraction/manifest.json` contains 60 development and 40 held-out snapshots. Joining hostnames to `/Users/ext-weihsiang.lin/Documents/profound/data/content-optimization-system/trad_ml_scorer/v2/host_splits.json` places the 40 extraction-held-out snapshots in 29 P1 training, 5 P1 validation and 6 P1 test hosts. The 60 development snapshots fall in 54 P1 training, 1 P1 validation and 5 P1 test hosts. Extraction and P1 holdouts are different partitions.

## Integration references

- [GEPA adapters](https://gepa-ai.github.io/gepa/guides/adapters/) describe evaluation batches and reflective feedback for custom systems.
- [GEPA callbacks](https://gepa-ai.github.io/gepa/guides/callbacks/) describe optimization lifecycle events for trace capture.
