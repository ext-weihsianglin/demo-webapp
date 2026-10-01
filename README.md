# Content Studio

A mock-first Next.js + FastAPI demo for source-grounded content optimization.

## Project context for future sessions

Read [project context and dated handoff](docs/project-context.md) for the current scaffold, proposed extraction/rewrite integration, model verification limits and the pending PR merge condition. Repository editing guidance lives in [AGENTS.md](AGENTS.md), with scoped instructions in [backend/AGENTS.md](backend/AGENTS.md) and [frontend/AGENTS.md](frontend/AGENTS.md).

## Run

Requires Node.js 20.9+ and Python 3.11+. Install `uv` for Python dependency management.

Terminal 1:

```sh
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. API documentation: http://127.0.0.1:8000/docs.
Next.js proxies `/api/*` to FastAPI; set `API_URL` in `frontend/.env.local` to override the backend address. No API keys required.

## UX

1. Enter target query, page URL (`href`), hostname, and HTML or Markdown snapshot. “Host” is represented by page URL + hostname, matching the adjacent research schema.
2. Inspect sections, source statements (“factoids”), metadata, and mock diagnostics. Choose editorial tone; structural suggestions require opt-in.
3. Review the draft and attributed changes. Copy or export Markdown. Source changes invalidate previous analysis and drafts.

The running-shoes example is illustrative, with no invented product rankings or performance claims. Submitted content is processed in memory and not fetched, persisted, executed, or sent to an LLM. Page HTML is displayed only as escaped text. The draft preview uses the app's editorial styling; it does **not** reproduce arbitrary source CSS. Original files and styles are never modified.

## What is real vs. mocked

- **Real:** API validation, local HTML/Markdown extraction, source block IDs, metadata, source statement provenance, frontend/API round trips, review/export.
- **Mock:** query alignment and answer clarity scores; structural score uses only heading count. Draft generation deterministically changes the title (with simple tone variants) and optionally adds a heading for low-structure pages. Body text is retained, not substantively rewritten. No predicted score gain or citation uplift.
- **Not connected:** phase 1 candidate extraction/selection, calibrated graders, phase 2 GEPA or prompt-optimized model, persistent runs, live URL fetching, source-style rendering, HTML patching.

## Integration boundaries

`backend/app/main.py` keeps `extract(content, format)` query-independent. Replace this lightweight adapter with the adjacent `content-optimization-system/preprocessing` snapshot/candidate/block workflow. Its source-only metadata and source mappings should survive candidate selection. Current block IDs are local sequential IDs, not full DOM selectors or durable mappings.

Replace `/api/analyze` mock grades with query-aware graders after extraction. Preserve disagreements/abstention and structural diagnostics; do not treat relative within-host citation labels as absolute probabilities.

Replace `/api/draft` with an optimizer adapter consuming extracted blocks, approved facts, query, grades, tone, and structural permission. Return proposed patches plus source evidence and change reasons. Add factual consistency checks and explicit review for unsupported additions. A future HTML patch adapter should target text nodes and preserve CSS/classes/assets; restructuring should remain opt-in.

For now request and response types live beside the API and frontend. Generate TypeScript types from FastAPI OpenAPI when the contracts stabilize. All state is ephemeral and refresh resets the demo.

## Checks

```sh
cd frontend
npm run build
npm run typecheck
```

```sh
cd backend
uv run pytest -q
```

Tests cover query-independent extraction, boilerplate removal, source traceability, source-claim retention, structural opt-in, untrusted text, Markdown, and invalid inputs.
