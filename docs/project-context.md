# Project context and session handoff

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
