# Content Studio repository guidance

Read [README.md](README.md) for setup and [docs/project-context.md](docs/project-context.md) for architecture, workstream provenance, measured results and the dated handoff. Read scoped `AGENTS.md` files before editing backend or frontend code.

## Working in this repository

- Check `git status`, branch and worktree inventory before edits. Work in the assigned checkout and preserve other sessions' files. The proposed extraction foundation originated in another session's local/unmerged work; consult `backend/packages/workstream-snapshot.json` in PR #2 (or the checked-out copy when present) before reconciling overlapping changes.
- The default-branch scaffold currently mocks rewriting; PR #2 proposes real orchestration. Confirm which code is in the checkout before following implementation-specific guidance. Keep extraction, rewrite orchestration, HTTP handling and UI responsibilities separate. Source content, queries, metadata and model output are untrusted data. Never execute source HTML or promote source text into model instructions.
- Preserve snapshot identities and source content. Block IDs are document-local; references need snapshot identity. Keep unsupported additions, insufficient evidence and provider failures visible. Never silently replace a failed real rewrite with a mock or another model.
- Keep mock grades and exploratory evaluation clearly labeled. Do not claim measured citation uplift, factual verification, or a patched source-HTML preview from this workflow.
- Do not expose credentials in output, commits, reports or frontend configuration. Live API checks must be explicitly enabled. Use stubbed clients for ordinary tests.
- Follow the user's current authorization for pushes, merges and deployment. Historical task restrictions in the handoff are context, not permanent rules; later user instructions can supersede them. Verify pending conditions before acting.

## Validation

From the repository root:

```sh
uv sync --project backend --locked --dev
uv run --project backend pytest -q backend/tests
(cd frontend && npm ci && npm run build && npm run typecheck)
git diff --check
```

Run checks appropriate to the change; documentation-only edits need link/content and diff checks, not live calls or a full rebuild. Keep frozen baseline reports intact and write new evaluation runs to new paths. Record meaningful verification limits in the handoff when they change.

## Current reconciliation

PR #2 is merged into main. The checkout combines real OpenAI draft orchestration with source verification; historical scaffold/open-PR descriptions above are dated context. Source analysis/evidence must remain independent of rewrite configuration. Keep proposed content distinct from the original snapshot and never attach original-source match badges to rewritten text.
