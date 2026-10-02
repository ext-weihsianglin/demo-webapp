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

The UI now displays a remotely started run's frozen settings, updates saved-run status as progress arrives, refreshes open candidate details after saved completions, and distinguishes reserved, dispatched and completed work. Usage totals explicitly reflect saved phases, so in-flight tokens may appear later. “Refresh runs” lets an already open tab discover a remotely started run without leaving the workspace. A browser check adopted the fourth run, disabled its frozen settings and Start, and retained Stop while live progress advanced.

## Verification completed

- Concurrent-miss regression: the second cold score waits for the local writer and both complete.
- Lookup regression: bounded queries match upstream catalog locations, including more keys than one SQLite group.
- [Parser/semantic parity](../verification/gepa-cache-parity-v1.json): five validation records pass without provider calls.
- [Live fidelity probes](../verification/gepa-guardrails-v1.json): four unsupported rewrites rejected and faithful control accepted. This is bounded guardrail evidence, not a claim that an LLM judge cannot be fooled.
- A fresh-process registry test resolves a promoted candidate and its exact prompt bytes/hash after restart.
- [Live candidate registry check](../verification/gepa-registry-live-v1.json): a fresh Python process resolves the same catalog as the running API, validating actual generated candidate prompt bytes/hashes. No live candidate has qualified for promotion yet, so the selected-winner backend restart remains pending.

## Live optimization status

Retry `37f8e094ccee4fbf8a0502a87a2a39b3` stopped at the ten-proposal ceiling after 42 rewrite attempts, with no admissible mutation. Its baseline selection mean was 0.407489 and failure fraction 0.866667. Reflection exceeded the mutable-text limit, and duplicate raw DOM/source fields overflowed some reflection requests. Context-preflight failures incorrectly consumed the proposal counter.

Reflection now presents original source text once, with changes and evidence referenced by ID, and excludes raw DOM diagnostics. When edits exist it includes their complete source chunks; otherwise it includes the entire page. The response schema enforces the mutable-text character bound, and preflight failures are logged without counting a provider proposal. No source text is truncated and fixed rewriter/gate instructions remain unchanged.

Third run `062a765eb15343ba8d96ba282f12abdb` used those corrections with the same frozen configuration. Its baseline selection mean is 0.409264 and failure fraction 0.833333. It stopped at 96/100 attempts with nine proposals and 15 technical failures, without a recommendation. The next admitted challenger required an uncached 30-page selection batch, so atomic reservation refused to dispatch it with only four attempts left. [Terminal result and every mutable strategy](../verification/gepa-run-062a765e.json) preserve the outcome; full page traces remain in the local run export.

Its first full challenger, `gpt-4.1-mini--885bc0d8059b6913d10c2554`, scores 0.407539 with the same failure fraction, below baseline; it cannot be recommended. That strategy named its two reflection pages' topic (cat food), exposing a generalization pitfall before any test-page evaluation. Subsequent reflection instructions explicitly request a generic editing method, prohibit example-specific names/topics, prioritize fidelity-approved focused edits, and ask for complete sentences below the length bound. This change is for a new frozen run; it does not alter the recorded run or its manifest. After all runs became terminal, the backend was restarted: saved terminal status/budget and all actual candidate prompt hashes survived. Fourth run `5f1536b7bf72467386a6da16ce453cc6` uses the same configuration with the revised reflection-prompt hash. The selected-winner restart check and paired held-out comparison still require a qualifying candidate. No optimized superiority is claimed while these checks remain pending.

All UI API consumers now handle non-JSON proxy failures, including evidence inspection and example loading. The proxy error regression, frontend build and typecheck pass. A plain-text HTTP 500 is presented as an availability error; it does not become a draft or a fabricated score.

[Fourth terminal result](../verification/gepa-run-5f1536b7.json): stopped at 80/100 attempts, five proposals and six technical failures. Its complete general challenger scored 0.409092 versus baseline 0.409105; failures improved from 0.8 to 0.766667. The lower mean still disqualifies promotion. A subsequent admitted candidate could not reserve 30 uncached selection pages with only 20 attempts left. No held-out comparison was performed.

Several fourth-run strategies ended mid-sentence at the 501-character hard bound. Reflection now has an explicit advisory target of 250 characters and asks for one or two complete sentences; the configurable hard bound is unchanged. Fifth run `c8439bf1e8c141ef9228bc5370dfa015` records this new reflection-prompt hash and seed 1 with the same frozen page roles, baseline, models, gate, P1 and 100-attempt cap. Changing the reflection seed explores another optimization batch; it is not independent generalization evidence. The successful optimization, actual winner promotion/restart and predeclared held-out comparison remain pending.

## Remaining limits

Whole-proposal rejection can retain the original page when only one edit fails fidelity, reducing accepted sample yield. The frozen v7 context-feature training/serving mismatch remains deliberately deferred under upstream issue #15. Model stochasticity and two already exposed P1-test hosts limit dogfood conclusions. The agreed 100-attempt cap may permit fewer than two fully evaluated challengers; incomplete selection vectors cannot be ranked or promoted.
