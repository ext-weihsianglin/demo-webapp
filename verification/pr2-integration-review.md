# PR #2 / PR #3 semantic integration review

Reviewed on 2026-10-01. Latest default branch is `main`, not `master`. At review time it points to `6423dcf`; `git merge origin/main` on the PR #3 branch reports **Already up to date**. No PR was merged into the default branch.

Inputs:

- PR #3 source-verification workstream: `4306a5b13e256670630d52b3ea0d719e7ce20faa`.
- PR #2 OpenAI rewrite workstream: `dbc53398c7eeca1c810a24dc76757027b1b9ae6d`.
- PR #2 remains open. It copied the shared extraction foundation before the source-verification UI/API was added.

## Finding

**The PRs are not conflict-free as submitted.** An isolated merge preview found nine conflicted files: `README.md`, `backend/.env.example`, `backend/app/main.py`, `backend/pyproject.toml`, `backend/tests/test_examples.py`, `backend/tests/test_extraction.py`, `backend/uv.lock`, `frontend/app/extraction-view.tsx`, and `frontend/app/page.tsx`.

The parser, example adapter/importer, package wheel/patch/provenance and source picker are byte-identical across the two PRs. No divergence was found in that shared extraction foundation.

The conflicts have semantic consequences; choosing one side wholesale is incorrect:

| Boundary | Required resolution |
|---|---|
| Analysis API | Keep PR #3's `verification` response and `/api/evidence`, alongside PR #2's `/api/rewrite-models` and model-validated draft request. |
| Draft API | Keep PR #2's real `rewrite(...)` handler and explicit error/abstention responses. PR #3's deterministic title-only draft handler is superseded. |
| Source review | Keep PR #3's default verification mode, original-source comparisons, filters, source statements labeling, metadata groups, and exports. |
| Proposed draft display | Keep PR #2's structured proposed blocks, evidence and telemetry. Render proposals without source-match badges or the original analysis's verification result. Their block IDs/locators reference the original source, not proof that new text matches it. |
| Model configuration | Load model options when opening optional draft tools, rather than making extraction analysis depend on the rewrite-model endpoint. Missing credentials or invalid rewrite settings must not block source inspection. |
| Dependency/config files | Keep the shared wheel path and Python 3.12 requirement; add PR #2's OpenAI/tiktoken dependencies, lock entries and server configuration. |
| Tests | Retain verification tests. Use PR #2's draft stubs and updated body-rewrite expectations rather than obsolete mock-title assertions. |
| Documentation/UI language | Preserve verification limits and source workflow. Replace superseded mock-draft wording with explicit optional real rewriting, configuration and model-access limitations. |

## Tested combined resolution

A local integration preview is available at `/tmp/demo-webapp-pr2-pr3-review` on branch `deck/pr2-pr3-integration-review`. It contains a merge-in-progress with the nine conflicts resolved using the decisions above. This preview was not pushed or incorporated into either PR; it does not broaden PR #3 to include the entire P2 workstream.

Validation of the combined code:

- Locked dependency installation succeeds.
- Backend suite: **55 passed, 1 skipped**. The skipped test is the explicit opt-in live OpenAI test. No live OpenAI generation was performed for this review.
- Frontend typecheck and production build pass. Proposed-content explanatory copy was subsequently added and typechecked.
- The 40-example source audit reproduces PR #3's committed JSON report exactly: 7,538 blocks, no comparison mismatches at resolved source locations, unchanged unresolved mapping and oversized chunk counts.
- Seven shared foundation files were compared byte-for-byte: example adapter, extraction adapter, importer, source picker, wheel, packaging patch and package provenance.

Two additional combined regression tests prove:

1. With no OpenAI key and an invalid rewrite context configuration, `/api/analyze` and `/api/evidence` still work and all original source consistency checks pass.
2. A stubbed real rewrite changes proposed body text, while original metadata remains retained, evidence resolves to `before` rather than `after`, the proposal receives no source-verification result, and reanalysis returns the unchanged original document and verification.

This is evidence that the workflows can coexist **after deliberate reconciliation**, not a claim that the current PR branches merge cleanly. Live model access, factual entailment and completeness are outside this integration check. PR #2's previously documented model-access limitations still apply.

## Merge guidance

Choose a merge order, then reconcile the remaining PR against the newly updated `main` using the table above and rerun the combined checks. Keep extraction verification on the original document and OpenAI drafting on the separate proposal. Do not resolve all overlapping files with `--ours` or `--theirs`.
