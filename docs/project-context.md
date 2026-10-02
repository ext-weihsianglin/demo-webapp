# Project context and session handoff

## Selectable query-aware QA prompt — 2026-10-02

The shipped GPT-4.1 mini catalog now includes **Experimental f2ef0597**, preserving
Baseline v7 as the default and all fixed guards. [QA instructions and evidence](query-aware-prompt-qa.md)
record the exact tested prompt, three-page comparison and unsupported edits.
The earlier live experiment used unmerged body-content-v5/advisory-fidelity work;
this registry addition does not include those changes or establish quality uplift.
Catalog-to-draft wiring is verified with stub providers; no new live run or deployment.

## V7.1 scoring and explanation integration — 2026-10-02 UTC

The checkout retains its keyed `rewrite-page-v7` proposal contract and verified model catalog. It imports research revision `6a9606d3febaf62f76c8448c44f91a120107e5a6` through package 0.3.0. Historical wheels and reports are preserved. Packaging and explicit-format/tuple API adaptations are recorded in `backend/packages/provenance-v3.json` and `content-optimization-library-v3.patch`; `build_upstream_package.py` reproduces the build.

HTML uses the completed corpus's source-owned Markdownify hotfix flow. Definition/thematic-break blocks are supported in compatibility sections. P1 loads trusted frozen v7.1 semantic_context bytes, ten OpenAI text-embedding-3-large original-3072D cosine summaries and 45 Markdownify context inputs. The app imports upstream serialization, splitting, vector cache/provider validation, normalized pooling and semantic helpers; PCA is excluded. Original source inventory remains fixed while proposals regenerate text, outline, chunks and changed embedding inputs.

The v7.1 migration pins merged upstream revision `6a9606d3` through package 0.3.0 and serves its canonical Markdownify adapter under `markdownify-v7.1`. Draft comparisons expose exact per-query `β(z_after-z_before)` rewrite effects, raw values and secondary absolute `βz` contributions. Explanation details remain outside P2 and GEPA prompts; [issue #11](https://github.com/ext-weihsianglin/demo-webapp/issues/11) tracks that separate audit.

Webapp example preparation now joins v7 row assignments to the completed corpus and preserves ten host queries, original bytes and provenance. Only P1 test hosts are served; legacy bundles without that proof are rejected. The local ignored bundle contains 97 hosts, and the trusted model is installed under `backend/data/scoring/model.joblib`. GEPA now uses an independent frozen P1-validation manifest and the actual 0.1.4 optimizer. See the [implementation handoff](gepa-implementation.md) for the tab, model-specific registry, run budgets, traces and verification limits.

`P1_ENABLE_LIVE_EMBEDDINGS=1` explicitly enables cache-miss requests; default scoring is cache-only. Configure `EMBEDDING_CACHE_ROOT` to reuse the existing shared store. Live embedding requests are preflighted against `P1_MAX_EMBEDDING_REQUESTS` (default 512 per scoring operation), batched with a 60-second provider timeout and no retry. Failed/missing embeddings remain unavailable without substitution. New candidate text may incur embedding calls in addition to rewriting/reflection costs. Source inspection remains available when scoring is unavailable.

Verification: the historical [v7 parity audit](../verification/upstream-v7-parity.json) remains frozen. The [v7.1 parity audit](../verification/upstream-v7-1-parity.json) matches saved parser output, all 55 feature values and canonical predictions for five validation records with zero provider calls. These are bounded parity/integration evidence, not factual verification, citation uplift or untouched P2 final-test evidence.

## Current integration — 2026-10-01

PR #2 has merged into `main`. PR #3 reconciles the source-verification workspace with that real OpenAI rewrite implementation. The default view inspects the original snapshot with typed blocks, chunks, source passages, metadata groups and source comparisons. Opening optional draft tools loads the server model catalog; extraction inspection works without OpenAI credentials or rewrite configuration. Proposed blocks are separately labeled and never receive original-source match certificates. Local production verification and current validation results are recorded in `verification/pr3-deployment-verification.md`.

The remainder of this document preserves the earlier dated handoff; its open-PR/scaffold/merge-condition statements describe that historical state, not the current checkout.


This document separates the current default-branch scaffold from the proposed implementation in PR #2 and records a dated session handoff. This standalone documentation PR contains no extraction, API-client or UI feature code. [README.md](../README.md) is the runnable setup reference. [AGENTS.md](../AGENTS.md) and the scoped backend/frontend guidance describe editing practices.

## Current default branch

At the handoff, `main` was scaffold commit `6423dcf`: Python 3.11+ FastAPI, Next.js/React, lightweight local extraction and deterministic title/optional-heading mock rewriting in `backend/app/main.py`. Grades are mock. Saved examples, the research wheel, real OpenAI orchestration, model selection and live/evaluation artifacts are implemented in unmerged PR #2, not installed by these documentation changes. Use the checked-out README and dependency manifests for setup; verify main/PR state before assuming this snapshot is current.

## Proposed product and architecture — PR #2

The architecture below describes [PR #2](https://github.com/ext-weihsianglin/demo-webapp/pull/2). Listed new paths may be absent on main until that feature PR is merged.

Content Studio is a Next.js/React frontend and FastAPI backend for source-grounded editorial proposals. Users submit an HTML/Markdown/text snapshot or select a prepared extraction-held-out example, edit a target query, inspect retained source data, select model/tone/structural permission, and review attributed edits. State is ephemeral. URLs identify snapshots; the app does not fetch live pages.

| Area | Files | Responsibility |
| --- | --- | --- |
| HTTP contracts | `backend/app/main.py` | Source/example validation; analyze/draft/model-catalog endpoints; visible failures |
| Extraction | `backend/app/extraction.py`, `backend/packages/` | Installed retention-first upstream parser, typed blocks, source mappings, metadata/JSON-LD, warnings, outlines and chunks |
| Saved examples | `backend/app/examples.py`, `backend/scripts/prepare_examples.py` | Local hash-verified held-out bundle, immutable payloads and editable queries |
| Rewriting | `backend/app/rewriting.py`, `backend/app/prompts/rewrite-baseline-v1.txt` | OpenAI Responses structured proposals, model-token budgeting, validation, rendering and telemetry |
| UI | `frontend/app/page.tsx`, `extraction-view.tsx`, `source-picker.tsx` | Editing controls, structured source/proposal display, evidence/reasons and Markdown export |
| Evidence | `backend/tests/`, `backend/evaluation/`, `backend/scripts/evaluate_rewriting.py` | Stubbed tests, explicit live smoke, frozen exploratory samples/reports and qualitative review |

Real generation uses the selected OpenAI model with server-only credentials, bounded timeouts/retries/call count, and `store=False`. Grades remain mock; there is no measured citation uplift. The preview renders escaped structured content and exports Markdown, not source HTML patched with the original layout/CSS.

Only plain top-level prose/headings can change. Tables, nested lists, code whitespace, links, inline formatting and metadata remain unchanged. Structural permission permits existing heading-level changes, not insertion/deletion/reordering. Edits require valid snapshot/chunk/block identities, exact before text, supporting source quotes, reasons and review flags. Mechanical validation does not prove factual entailment; human review must assess qualifiers, support and omissions. No unsupported or incomplete output is silently applied.

## Proposed extraction foundation and reconciliation

The issue #1 branch began from app scaffold commit `6423dcf`. The required integration existed locally/unmerged in `deck/web-app-workstream` and its separate worktree. It was read and copied into the isolated `deck/openai-draft-rewriting` branch without modifying the other session's checkout.

[workstream-snapshot.json](https://github.com/ext-weihsianglin/demo-webapp/blob/dbc53398c7eeca1c810a24dc76757027b1b9ae6d/backend/packages/workstream-snapshot.json) records hashes of the copied foundation files. This includes extraction/examples, their tests, UI components and the bundled upstream wheel. When reconciling branches, inspect current workstream/main contents and overlapping changes; do not overwrite newer work using this historical snapshot or blindly replay the whole foundation.

The library derives from `content-optimization-system` revision `3d4d35d3c32ac5b8c14983f99f92c2f633669417`. [provenance.json](https://github.com/ext-weihsianglin/demo-webapp/blob/dbc53398c7eeca1c810a24dc76757027b1b9ae6d/backend/packages/provenance.json) records the wheel identity; [content-optimization-library.patch](https://github.com/ext-weihsianglin/demo-webapp/blob/dbc53398c7eeca1c810a24dc76757027b1b9ae6d/backend/packages/content-optimization-library.patch) records the packaging/API patch. Packaging was unpublished at this handoff. The wheel allows installation without a sibling research checkout. A published, pinned dependency is a future option, not an available foundation assumption.

Example preparation requires the research manifest, saved evaluation snapshots and original parquet sources. The generated `backend/data/examples/` bundle is ignored by Git; a fresh checkout may have no bundle. `CONTENT_EXAMPLES_DIR` can point to a prepared bundle. Custom input still works. Paths are relative to the backend process directory unless absolute.

## Models and live verification limits

In PR #2, the dropdown reads `GET /api/rewrite-models`. Default: `gpt-4.1-mini`. Built-in choices comprise GPT-4.1 mini/full/nano, GPT-5.6 Sol/Terra/Luna, GPT-6 Sol/Luna/Astra and GPT-6.1 Sol. Server environment can override the catalog; the configured default is always included. Selection is validated before generation and recorded in telemetry. Changing selection clears the previous draft.

On 2026-10-01, real `gpt-4.1-mini` rewriting succeeded for a custom snapshot and a saved Sainsbury's held-out article with an edited supported query. The article appropriately abstained for its original Aldi comparison query. Frozen reports plus [baseline-review.md](https://github.com/ext-weihsianglin/demo-webapp/blob/dbc53398c7eeca1c810a24dc76757027b1b9ae6d/backend/evaluation/baseline-review.md) record actual outputs, token use, latency and qualitative limitations. No price configuration was available. These are exploratory data, not an untouched P2 final set. Reports predate a documented correction to recompute proposed-document text/outline and carry abstention flags; retain their historical outputs.

Explicit live smoke checks for all seven added GPT-5.6/GPT-6 IDs failed with API access errors. A minimal `gpt-5.6-sol` diagnostic returned HTTP 403 `model_not_found`; none of the seven IDs appeared in the current account model list. Stubbed routing support is confirmed, but live GPT-5.6+ rewriting is **not verified with those credentials**. See [model-support-verification.md](https://github.com/ext-weihsianglin/demo-webapp/blob/dbc53398c7eeca1c810a24dc76757027b1b9ae6d/backend/evaluation/model-support-verification.md) for the repeatable check. Do not conflate official model documentation, dropdown inclusion, and actual account access.

In this session, workspace-shell credentials were available while a shell launched directly in the backend directory lacked them. This is an observed environment difference, not a guarantee about future shells. Load `.env` explicitly for commands that need it, verify availability with a boolean, and never print the key. Provider `model_not_found` errors surface as `model_unavailable`, with no automatic model fallback.

## Dated handoff — 2026-10-01

Issue: [#1](https://github.com/ext-weihsianglin/demo-webapp/issues/1). PR: [#2](https://github.com/ext-weihsianglin/demo-webapp/pull/2), targeting `main`. At the handoff check the PR was open, mergeable, with no configured GitHub status checks. Verify its live state before acting.

Implementation commits on the feature branch:

- `c2f1603`: extraction foundation plus OpenAI baseline orchestration, UI, evaluation and docs.
- `005fa9a`: server-configured model dropdown and request routing.
- `dbc5339`: GPT-5.6/GPT-6 catalog additions and clear model-access failures.

Last ordinary backend suite: **48 passed, 1 explicitly opt-in live test skipped**, with one upstream Starlette/httpx deprecation warning. Frontend build/typecheck passed after the dropdown change; the later catalog changes were backend-only. Locked dependency sync and diff checks passed. The initial GPT-4.1-mini live smoke passed; the seven newer-model attempts failed as described above. Do not label failed live checks as passing validation.

The user initially prohibited merges, then explicitly authorized merging **after confirming 5.6+ support**. The live account-access condition remains unmet. A decision was requested between retaining the open PR until live verification passes and merging with the documented access limitation; no answer had arrived at this handoff. The request to document context does not resolve that condition. No merge, deployment, force-push, or worktree deletion has occurred. The implementation is in PR #2; this documentation is submitted separately against main. Separating the guidance does not merge or install the feature.

For a future session: inspect current instructions, branch/worktrees, PR state and any new user authorization; use credentials with access to repeat the explicit smoke checks. If those pass, or the user explicitly accepts the documented limit, complete the authorized merge without requiring duplicate permission. Preserve other worktrees and do not deploy unless requested.

## Follow-up boundaries

GEPA/prompt optimization and retrieval memory should follow the measured baseline behind the rewriting interface. Reserve separate rewrite final test data first. Relevance selection may reduce navigation-heavy token cost, but must assess omissions explicitly. Broader structural edits, HTML patching/source-layout preview, calibrated graders and prospective citation-frequency/rank experiments are separate workstreams. Generate shared frontend types from OpenAPI when the contract stabilizes.


## Multi-query flow (2026-10-01)

Current branch adds the complete host prompt set to the existing source-verification/real-rewrite integration. The new example bundle joins all ten frozen records per host across hash-verified shards, keeps their provenance, excludes unusable prompts explicitly and deduplicates exact trimmed text. The selected immutable snapshot does not change. Custom requests/UI also support multiple queries.

`app/scoring.py` reuses the bundled upstream `lr-retention-v2` feature implementation and the trusted frozen v2 model (SHA-256 recorded in README). It scores every distinct query, reports the equal-weight mean/minimum, and rescoring compares the original and proposed structured documents with unchanged source inventory/metadata. The model is local ignored data; unavailable/invalid models return visible unavailability. These are sampled within-host top-class predictions among already-cited pages, not actual citation probabilities or causal rewrite gains; extraction-held-out is not a P1 final-test claim.

`rewrite-multiquery-v1.txt` and every user JSON payload include the entire target-query set plus whole-document P1 feedback. One coordinated proposal aims to improve the mean while avoiding individual regressions, followed by per-query rescoring and explicit regression reporting. No iterative optimization, GEPA or memory is installed. The frozen baseline prompt/reports remain unchanged. Queries for other pages on a host require missing-evidence review rather than fabricated answers.


## Asanify draft QA correction (2026-10-02 UTC)

The 33-chunk Asanify held-out snapshot initially returned HTTP 422 `context_limit`: an input needed 16,782 tokens plus 4,000 output reserve under the 16,000-token backend budget. Full source metadata contributed roughly 13,000 tokens to every request; after removing that duplication, one-call-per-chunk planning would still exceed the 12-call cap.

Current `rewrite-multiquery-v2` batches whole original chunks, budgets the actual per-batch schema/input plus output reserve, and retains all target queries and block text. The original document (including JSON-LD, visibility, source locators and rich structures) remains intact for extraction review/P1; those noneditable diagnostics and duplicate text/Markdown are omitted from editorial inputs. Dynamic provider schemas constrain editable block IDs and exact original before strings; server validation still enforces snapshot/chunk/block/evidence consistency. Fully validated no-op edits are omitted and cannot create a successful draft without a real paragraph change. Historical prompts/reports remain unchanged. Next.js now allows five minutes for the multi-batch response instead of its default 30-second proxy timeout.

The user subsequently requested a 128,000-token rewrite context budget. The default and local backend now use that cap, including the unchanged 4,000-token output reserve. This configuration change does not resolve the separately observed provider `invalid_json_schema` error; successful live drafting remains unverified.

## Whole-page rewrite — supersedes batching above

User requested one OpenAI call per page. Current `rewrite-page-v3.txt` plans over all retained blocks and distinct target queries with whole-page P1 feedback. The user JSON declares `scope: whole_page`, includes source order/heading context, editable flags and original chunk memberships. All evidence still uses the original same-chunk validation contract. The planner emits exactly one request or rejects the full-page budget before any provider call; automatic SDK retries are disabled. Defaults are 128,000 total tokens, 16,000 output tokens and a 120-second timeout. The model returns one complete edit proposal, then P1 rescoring runs across all queries.

Removed source-sized before/quote enums from the provider schema; editable block IDs use a bounded enum when within the schema size allowance; exact source identity/text/evidence and protected-block checks remain server-side. Heading levels use a null-only schema when structural permission is off. Historical batching reports are not evidence of the current flow.

Validation: 69 backend tests passed, one opt-in live suite test skipped. A separate explicit live schema check completed. Final Asanify request through the frontend proxy made exactly one gpt-4.1 call (55,207 input / 7,689 output tokens), but returned HTTP 502 because a proposed evidence quote/reference failed same-chunk exact-source validation. No draft was applied. This remains a generation reliability limitation, not a context or schema error. See `verification/whole-page-rewrite.json`.

## Explicit edit boundary

`rewrite-page-v4` separates the user payload into `editable_blocks` and `read_only_context`. System instructions and the user edit boundary prohibit read-only edit targets; source order/chunk IDs remain available across the partition. All source text is retained once. The existing bounded editable-ID schema and server enforcement remain active; read-only blocks may support exact same-chunk evidence but cannot be changed. Tests check disjoint/exhaustive partitioning, schema IDs and protected-content preservation. This prompt change does not establish that every live model response will validate.

## Evidence-reference debugging

User QA snapshot `0cbc8a5e12709367e63cdd9579bfee14bdabd85e758cf0b1e3ed29a2f61481aa` is blog.blazingcdn.com. A captured v4 reproduction using gpt-4.1-mini found an incorrect edit chunk ID plus evidence strings attached to heading IDs rather than their source paragraphs; one string also introduced an ellipsis. This reproduces the failure class, not the exact nondeterministic response from the user's earlier QA. It does not justify accepting arbitrary cross-chunk references or approximate quotes.

`rewrite-page-v5` uses a separate provider proposal contract: block_id, after, reason, selected evidence block IDs, review_flags and heading_level. The server resolves immutable before text, snapshot/chunk references and full evidence text from the original source; output API fields remain compatible. Same-chunk evidence and protected-content checks remain strict. Evidence passages are explicitly labeled server-copied from model-selected IDs, not model-authored quotes or semantic entailment. Failure telemetry identifies the edit/evidence IDs and individual failed checks without logging raw source or provider error bodies. Regression tests cover immutable assembly, unknown IDs and all five evidence failure categories.

The final v5 provider schema uses bounded per-chunk alternatives to restrict both editable target IDs and evidence IDs to the same original chunk. Large pages exceeding the schema bounds retain server checks. Request-local short chunk aliases reduce repeated hash tokens; original identities remain unchanged in the returned API document. Three consecutive requests through `http://127.0.0.1:3005/api/draft` for the user's example with gpt-4.1-mini succeeded in 18.514s, 12.729s and 16.332s (one call each; 17, 12 and 16 edits). All nine distinct host queries were scored before/after. Protected blocks, source metadata, source order and exact evidence provenance passed checks in all three runs. Per-query regressions were 1, 0 and 2 respectively; this is reliability evidence, not guaranteed quality or uplift. See `verification/evidence-rewrite-three-successes.json`. Final backend suite: 76 passed, one opt-in live suite test skipped; the three explicit live endpoint checks are separate. Browser-button interaction was not part of this streak.

## Language guardrails

A deterministic injected-response test demonstrated that the previous pipeline accepted an English-to-Spanish body rewrite. `rewrite-page-v6` now specifies per-block language preservation and supplies local source-language hints; multilingual queries are not a translation request. Local Lingua validation rejects confidently detected language changes and labels inconclusive short/mixed/ambiguous edits for review. Tests reject Spanish/French/Japanese/Russian translations of English prose and accept Spanish-source rewriting despite English queries and conflicting metadata. The reported Gemini deployment is unconfirmed: this checkout currently has the OpenAI provider path only. These checks do not establish a live Gemini reproduction. Backend suite: 82 passed, one opt-in live test skipped.

A live check exposed false English→Esperanto classifications in Lingua low-accuracy mode. The guard now uses lazily loaded high-accuracy models. Replaying all 45 edits from the three saved successful drafts found zero language-change false positives (41 preserved, 4 inconclusive); a technical-English regression test captures the observed issue.

Final language-guard validation: 83 tests pass, one opt-in live suite test skipped. The high-accuracy v6 live request for the saved blog.blazingcdn.com example returned HTTP 200 in 19.229 seconds with 18 edits and one inconclusive language check flagged for review. See `verification/language-guard-live-high-accuracy.json`; the low-accuracy failed run is retained and explicitly labeled superseded.

## Verified P2 model catalog

Current credential catalog listed GPT-4.1/full/mini/nano and GPT-5/full/mini/nano only. Explicit live v6 checks on the user's saved QA page passed for gpt-4.1 (34.6s), gpt-4.1-nano (28.9s), gpt-5 (74.5s), and gpt-5-mini (57.3s). gpt-4.1-mini abstained on this run but has a successful v6 live run recorded in `verification/language-guard-live-high-accuracy.json`; keep it as default. gpt-5-nano returned duplicate edits and failed validation, so it is excluded alongside unavailable GPT-5.6/GPT-6 entries. The five enabled IDs are enforced in server catalog/request validation; environment configuration may narrow the list but cannot expand it. Unsupported configured defaults fail visibly. See `verification/p2-model-catalog-verification.json`. Compatibility checks do not guarantee every future draft succeeds or improves content.

## Keyed P2 harness and held-out matrix

Current `rewrite-page-v7` requests one required nullable slot per editable block, with identity supplied by the object key. Null leaves the original intact. Duplicate keys with identical values are normalized once; conflicting duplicate keys, missing slots, unknown/protected targets and malformed replacements reject the complete proposal. Evidence/source identities remain backend-resolved, with the existing same-chunk, structure and language checks. Nonblank single-line replacements are schema-constrained. Oversized keyed schemas fail visibly before any provider call. This retains one generation call, no repair loop or model fallback. GPT-5 mini/nano use low reasoning effort to reduce latency; GPT-5 nano is re-enabled because output reliability is distinct from API compatibility. Partial supported body improvements are sufficient; the prompt does not require answering unsupported host queries or rewriting every block.

`backend/scripts/verify_rewrite_matrix.py` requires `--live`, repeated `--example-id`/`--model` selectors and a fresh `--output`. It loads hash-verified local persisted snapshots through `load_example`; hostname fields are identities, not URLs to fetch. It sends saved content to OpenAI only. Optional `--artifacts-dir` retains full model/source output locally for diagnosis.

Final verification: 93 backend tests passed; one opt-in live suite test skipped. Separate real API matrix passed 8/8 drafts across blog.blazingcdn.com and asanify.com, each with GPT-4.1 mini/nano and GPT-5 mini/nano. Each used one model call and all recorded source/evidence/structure checks passed. The complete distinct query sets (9 and 10) were retained and rescored. Final latencies ranged from 7.219s to 33.915s. See `verification/keyed-rewrite-final-matrix.json` (includes prompt hash). Earlier matrix/format/low-reasoning reports retain the formatting rejection, timeout and abstentions encountered while refining the harness. The final matrix is API-level, not browser-button verification, semantic entailment certification or guaranteed P1/citation uplift. Short-language uncertainty and per-query regressions remain visible.


## GEPA local research implementation — 2026-10-01

The reviewed plan/spec are implemented: model-specific prompt selection, a GEPA Optimization tab, one local coordinator, fixed validation-only 60/30 data, atomic attempt reservations, technical circuit breakers, source-relative fidelity checks, saved outcomes and explicit promotion. Baseline v7 bytes and frozen P1/parser contracts remain unchanged. Ordinary real drafts also use the fidelity gate; it is an LLM judgment, not factual verification.

The local ignored `validation-90-v2` dataset contains 90 hash-verified validation hosts, ten original query records per host and deterministic source/role selection. The webapp continues serving test-only examples. No candidate has been promoted, no complete optimized live experiment has been run, and no quality or citation uplift claim follows from wiring checks. [Implementation details and checks](gepa-implementation.md) record the actual GEPA stub integration and two bounded provider checks, including abstention and whole-proposal fidelity rejection. Frozen older reports remain intact.


A 2026-10-02 backend restart interrupted a user-started run after its 30 baseline selection rewrites. All page outcomes were retained, including six fidelity-approved/rescored proposals. Progress was recovered from saved events. The frontend now handles plain-text proxy failures, and graceful shutdown stops later provider phases. Final verification: 117 backend tests passed, 2 opt-in checks skipped; 3 frontend API-error regression checks passed; production build/typecheck and diff checks passed. See [the handoff](gepa-implementation.md#proxy-error-and-interrupted-run-recovery--2026-10-02).

## Advisory studio validation and prompt inspection — 2026-10-02

The interactive `/api/draft` flow retains readable model responses, including self-reported unsupported/missing-evidence flags, language warnings, schema errors and incomplete output. Mechanically valid edits enter the proposed page; invalid/protected/ambiguous edits remain inspectable without being applied. Raw provider text is escaped in the UI. No-applied-edit responses explicitly show the original page preview and are marked `review_required`. Research acceptance still uses its existing strict orchestration path.

The selected-prompt viewer posts to `/api/prompt-preview`, which reuses the request builder with the displayed P1 feedback without provider or scoring calls. Draft responses record the exact system instructions and user message actually sent; these may differ from a preview if scoring availability changes. Source content remains untrusted data, and prompt registry contracts are unchanged.

QA must check `p1.status == scored`, not just HTTP 200. This machine's v7.1 artifact is `model-v7.1.joblib`; the older `model.joblib` does not match the pinned v7.1 hash. Provider generation was exercised with stubs for this change, not live quality evaluation.
