<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Content Studio UI guidance

Inherit the root [AGENTS.md](../AGENTS.md) and read [project context](../docs/project-context.md). Keep this project-specific section outside the generated Next.js block above.

The current scaffold uses `app/page.tsx` and deterministic mock generation. The following additional components and real-generation contracts are implemented in [PR #2](https://github.com/ext-weihsianglin/demo-webapp/pull/2); apply them where present and preserve honest mock labeling in the scaffold.

- `app/page.tsx` manages the source/analyze/review flow; `source-picker.tsx` handles saved examples; `extraction-view.tsx` renders escaped structured data.
- Read model options from `/api/rewrite-models`; do not hardcode another frontend catalog or put credentials in frontend configuration. Send the selected ID in draft requests and show the returned model in telemetry.
- Clear stale drafts when the source/query/model changes. Disable model selection during generation. Saved example payloads are read-only while their query remains editable.
- Preserve source warnings and distinguish OpenAI proposals, mock grades and provider failures. A listed model is not evidence of account access. Do not present a failed generation or substituted model as success.
- Render source/model text as escaped content; avoid injecting arbitrary HTML. Preserve structured table spans, code whitespace, nested list relationships and visible source links. Markdown export is a content proposal, not patched source HTML.
- Keep snapshot/chunk/block references, evidence quotes and edit reasons reviewable. Do not claim that exact source quotes establish factual verification or citation uplift.

For UI changes run `npm run build` and `npm run typecheck`. The root README documents the backend proxy and setup. Do not overwrite other sessions' generated files or modify the Next.js instruction block to remove its requirements.

## Current reconciliation

PR #2 is merged into main. The checkout combines real OpenAI draft orchestration with source verification; historical scaffold/open-PR descriptions above are dated context. Source analysis/evidence must remain independent of rewrite configuration. Keep proposed content distinct from the original snapshot and never attach original-source match badges to rewritten text.
