# Content Studio

A mock-first Next.js + FastAPI demo for source-grounded content optimization.

## Run

Requires Node.js 20.9+ and Python 3.12+. Install `uv` for Python dependency management.

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

1. Choose **Your own page** to enter a target query, page URL (`href`), hostname, and HTML, Markdown, or text snapshot. Or choose **Held-out examples**, select a host and saved page, and use its original query or write your own. “Host” is represented by page URL + hostname, matching the adjacent research schema.
2. Inspect sections, chunks, source statements (“factoids”), and metadata. Compare blocks with the saved source, filter review hints, and export the extraction report or original snapshot.
3. Optionally open the mock draft tools, choose editorial tone and structural permission, then review or export the Markdown proposal. Source changes invalidate previous analysis and drafts.

The running-shoes example is illustrative, with no invented product rankings or performance claims. Submitted content is processed in memory and not fetched, persisted, executed, or sent to an LLM. Page HTML is displayed only as escaped text. The draft preview uses the app's editorial styling; it does **not** reproduce arbitrary source CSS. Original files and styles are never modified.

## Held-out examples

Prepare the local bundle from the research repository's existing frozen manifest,
materialized `data/evaluation/` snapshots, and original `data/raw/` parquet files:

```sh
cd backend
uv sync --dev
uv run python scripts/prepare_examples.py --research-root /path/to/content-optimization-system
```

This packages only the designated `heldout` split, checks development/held-out
host and payload isolation, verifies source hashes and original parquet rows, and
preserves the original queries. It does not resample or fetch live pages. The
current manifest provides 40 hosts/pages. The generated bundle lives in
`backend/data/examples/`, is excluded from Git, and is not overwritten on reruns.
Use `--output /new/path` to prepare another bundle and set
`CONTENT_EXAMPLES_DIR=/new/path` when starting the API to serve it. Paths set in
the environment are resolved relative to the backend process working directory.

`GET /api/examples` lists host/page/query metadata without payloads or citation
labels; `GET /api/examples/{snapshot_id}` loads a hash-verified saved snapshot.
Analysis and draft requests can supply `{example_id, query}` instead of custom
source fields. Saved content is read-only; custom queries are allowed. Responses
carry `source_origin` with the original snapshot, split, manifest and payload
identities. Both modes invoke the installed research retention parser. Grades and
rewriting remain mocked.

Custom input remains usable without a bundle. Its limit is 200,000 characters;
saved examples support up to 8,000,000 characters without truncation. Switching
back to **Your own page** restores the previous custom inputs. User edits to a
query or source invalidate previous analysis and drafts.

These examples are held out for the extraction benchmark. Interactive prompt
experimentation is exploratory; it does not establish an untouched P2 rewrite
test set. Reserve separate examples when measuring GEPA or memory improvements.

## What is real vs. mocked

- **Real:** API validation, installed retention-first extraction/selection for HTML/Markdown/text, typed blocks, metadata/JSON-LD, source mappings, quality flags, structured chunks, frontend/API round trips, review/export.
- **Mock:** query alignment and answer clarity scores; structural score uses only heading count. Draft generation deterministically changes the title (with simple tone variants) and optionally adds a heading for low-structure pages. Body text is retained, not substantively rewritten. No predicted score gain or citation uplift.
- **Not connected:** optional clean extraction candidates, calibrated graders, phase 2 GEPA or prompt-optimized model, persistent runs, live URL fetching, source-style rendering, HTML patching.

## Integration boundaries

`backend/app/extraction.py` invokes `preprocessing.api.parse_snapshot` from the
installed `content-optimization-exploration` library. Extraction is query-independent:
the target query and citation labels never enter the parser. HTML uses conservative
DOM; Markdown/text use the native adapter. Inventory, retention selection,
`downstream-document-v1`, heading outlines, source locators and chunks come from
the research implementation. API responses retain the full `document` and `chunks`,
with compatibility `sections`/`factoids` views for the demo. Flags remain visible;
insufficient source content prevents draft generation. Block IDs are document-local,
so use `(snapshot_id, block_id)` for references. Chunks use a soft character target,
not a model token budget.

The library is installed by `uv sync` from the local wheel declared in
`backend/pyproject.toml`. It was built from `origin/main` at
`3d4d35d3c32ac5b8c14983f99f92c2f633669417` plus packaging metadata and an importable
snapshot API; the existing parser files are unchanged. Wheel identity and the
reviewable upstream patch are in `backend/packages/provenance.json` and
`backend/packages/content-optimization-library.patch`. Packaging changes are local
and not yet published upstream. This keeps the app runnable without a sibling
checkout or temporary path; a pinned Git dependency can replace the wheel after
the packaging changes are published. No extraction code is copied into the app.

Mock draft generation uses the library's `blocks_to_markdown` so nested lists,
code whitespace and table spans survive export. Source metadata and JSON-LD remain
separate from generated body content.

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

### Extraction verification

The default analysis view compares extraction with the saved snapshot. Sections expose typed blocks, parent relationships, mapping status and lazy **Compare with source** previews. Filters highlight ambiguous mappings, hidden-source attributes and possible boilerplate without removing content. Chunks preserve block order and show inferred heading context and oversized groups. **Source statements** is the display name for the compatibility `factoids` field: these are copied passages, not atomic or independently verified facts. Metadata separates copied source fields from computed inventory and heuristics. Source previews are escaped text; HTML fragments are DOM serializations, with that normalization explicitly labeled.

Mechanical checks cover chunk partition/order, nested groups, chunk text/counts, passage copies, exact snapshot identity, source title/meta tags and raw JSON-LD mappings. These checks do not prove completeness, factual truth, relevance or rendered visibility. A matching substring also does not certify semantic grouping. Unresolved mappings remain unresolved even when candidate matching text is found. Mock grading and draft controls are available separately through **Open mock draft tools**.

Reproduce the 40-example diagnostics from an installed example bundle:

```sh
cd backend
.venv/bin/python scripts/audit_examples.py > ../verification/heldout-source-audit.json
```

The checked-in report is a development diagnostic on the extraction held-out slice, not a human gold evaluation. All mechanical checks passed across 7,538 blocks; 1,290 ambiguous mappings and one unavailable mapping remain unverified. No text mismatch was found at resolved locations. Nine chunks exceed the soft character limit. Boilerplate (1,240 blocks) and hidden-source (228 blocks) hints require human review and can overlap.

Priorities for improving the research parser: establish more precise source ranges for ambiguous paragraphs; distinguish article content from navigation/sidebar/footer without losing source content; make chunk heading context respect DOM regions; and introduce atomic claim extraction only with explicit source references and separate factual verification. Measure omissions against human annotations before claiming extraction coverage improvements. Keep this pinned parser and frozen examples unchanged while collecting review findings.

Upstream follow-ups: [source mappings #7](https://github.com/ext-weihsianglin/content-optimization-system/issues/7), [chunk heading context #8](https://github.com/ext-weihsianglin/content-optimization-system/issues/8), [oversized chunk consumption #9](https://github.com/ext-weihsianglin/content-optimization-system/issues/9), and [inline semantics #10](https://github.com/ext-weihsianglin/content-optimization-system/issues/10). Real P2 OpenAI orchestration remains deferred in [demo-webapp #1](https://github.com/ext-weihsianglin/demo-webapp/issues/1). No Markdownify substitution is included in this workstream.
