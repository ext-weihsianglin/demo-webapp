# GEPA live experiment — 2026-10-02

This record tracks the live gpt-4.1-mini experiment and remaining acceptance work. P1 is a classifier proxy; a better score does not certify factual truth or citation uplift.

## Frozen protocol

- Dataset `validation-90-v2`: 60 reflection / 30 selection pages from distinct P1-validation hosts. P1 test is excluded from optimization.
- Baseline `gpt-4.1-mini--rewrite-page-v7`; immutable fixed instructions, parser, P1 and source-relative gate.
- Rewriter/reflection `gpt-4.1-mini`, 100 rewrite attempts, 10 workers, two reflection pages per mutation, ten proposal ceiling, 1.5× mutable-text bound.
- Predeclared dogfood: blog.blazingcdn.com and erp.compare, two repeats each for baseline and selected candidate, identical full query sets. [Protocol](../verification/gepa-dogfood-protocol-v1.json) records selection before any mutation exists. No test feedback enters further prompt optimization.

## Failures and corrections

Run `d6a254c540dd47db9abcdd3fc4134dfc` stopped after 27 rewrite attempts when a fidelity-approved rewrite needed fresh embeddings and scoring became unavailable. The proposed embedding trace recorded 31 misses and zero provider calls. The pre-fix upstream cache writer rejects overlapping writers immediately; an isolated replay using the committed pre-fix module reproduced `CacheBusyError` with two cold scores and stub embeddings. Local writes now serialize under one backend lock. External-process cache contention still fails visibly; there is no hidden provider retry or fabricated score.

Every score previously loaded all 588,411 cache locations. A measured request needed only 41 keys: full lookup 0.901s versus parameterized bounded lookup 0.090s under the measured conditions. This is a lookup measurement, not a total latency promise. Vector identity, upstream reads/writes, shard checksums, normalization, pooling, original-space cosines and frozen P1 are unchanged. Grouped lookups stay below SQLite parameter limits.

The UI now displays a remotely started run's frozen settings, updates saved-run status as progress arrives, refreshes open candidate details after saved completions, and distinguishes reserved, dispatched and completed work. Usage totals explicitly reflect saved phases, so in-flight tokens may appear later.

## Verification completed

- Concurrent-miss regression: the second cold score waits for the local writer and both complete.
- Lookup regression: bounded queries match upstream catalog locations, including more keys than one SQLite group.
- [Parser/semantic parity](../verification/gepa-cache-parity-v1.json): five validation records pass without provider calls.
- [Live fidelity probes](../verification/gepa-guardrails-v1.json): four unsupported rewrites rejected and faithful control accepted. This is bounded guardrail evidence, not a claim that an LLM judge cannot be fooled.
- A fresh-process registry test resolves a promoted candidate and its exact prompt bytes/hash after restart.

## Live optimization status

Retry `37f8e094ccee4fbf8a0502a87a2a39b3` uses the same frozen experiment after the cache corrections. Its result, persistence checks and paired held-out comparison will be added when terminal. No optimized superiority is claimed while these checks remain pending.

## Remaining limits

Whole-proposal rejection can retain the original page when only one edit fails fidelity, reducing accepted sample yield. The frozen v7 context-feature training/serving mismatch remains deliberately deferred under upstream issue #15. Model stochasticity and two already exposed P1-test hosts limit dogfood conclusions. The agreed 100-attempt cap may permit fewer than two fully evaluated challengers; incomplete selection vectors cannot be ranked or promoted.
