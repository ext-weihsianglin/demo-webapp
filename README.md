# Content Studio

A Next.js + FastAPI demo with baseline OpenAI rewriting and mock grading for source-grounded content optimization.

## Run

Requires Node.js 20.9+ and Python 3.12+. Install `uv` for Python dependency management.

Terminal 1:

```sh
cd backend
uv sync --dev
cp .env.example .env  # Set OPENAI_API_KEY here for drafting.
uv run uvicorn app.main:app --env-file .env --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. API documentation: http://127.0.0.1:8000/docs.
Next.js proxies `/api/*` to FastAPI; set `API_URL` in `frontend/.env.local` to override the backend address. Analysis requires no API key. Draft generation requires server-side `OPENAI_API_KEY`.

## UX

1. Choose **Your own page** to enter a target query, page URL (`href`), hostname, and HTML, Markdown, or text snapshot. Or choose **Held-out examples**, select a host and saved page, and use its original query or write your own. “Host” is represented by page URL + hostname, matching the adjacent research schema.
2. Inspect sections, source statements (“factoids”), metadata, and mock diagnostics. Select a rewrite model and editorial tone; structural suggestions require opt-in.
3. Review the draft and attributed changes. Copy or export Markdown. Source changes invalidate previous analysis and drafts.

The running-shoes example is illustrative, with no invented product rankings or performance claims. Submitted content is processed in memory and never fetched or executed. Draft generation sends retained source blocks/chunks and metadata to OpenAI with `store=False`; do not submit source data you cannot send to that provider. Page HTML is displayed only as escaped text. The draft preview uses the app's editorial styling; it does **not** reproduce arbitrary source CSS. Original files and styles are never modified.

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
identities. Both modes invoke the installed research retention parser. Grades remain mocked; rewriting uses the versioned OpenAI baseline.

Custom input remains usable without a bundle. Its limit is 200,000 characters;
saved examples support up to 8,000,000 characters without truncation. Switching
back to **Your own page** restores the previous custom inputs. User edits to a
query or source invalidate previous analysis and drafts.

These examples are held out for the extraction benchmark. Interactive prompt
experimentation is exploratory; it does not establish an untouched P2 rewrite
test set. Reserve separate examples when measuring GEPA or memory improvements.

## What is real vs. mocked

- **Real:** API validation, installed retention-first extraction/selection for HTML/Markdown/text, typed blocks, metadata/JSON-LD, source mappings, quality flags, structured chunks, frontend/API round trips, review/export.
- **Mock:** query alignment and answer clarity scores; structural score uses only heading count. No predicted score gain or citation uplift. There is no automatic demo rewrite fallback.
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

Validated draft generation uses the library's `blocks_to_markdown` so nested lists,
code whitespace and table spans survive export. Source metadata and JSON-LD remain
separate from generated body content.

Replace `/api/analyze` mock grades with query-aware graders after extraction. Preserve disagreements/abstention and structural diagnostics; do not treat relative within-host citation labels as absolute probabilities.

`backend/app/rewriting.py` owns generation, token budgeting, source validation and rendering, independently of extraction and the endpoint. Its hand-written prompt is `backend/app/prompts/rewrite-baseline-v1.txt`. No GEPA or retrieval memory is included. All source/query/metadata content is untrusted data in the user message; the fixed editorial/security instructions are separate.

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

## OpenAI rewrite setup and limits

Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY` there, or export it into the backend process. Start uvicorn with `--env-file .env` as above. The key is server-only; never put it in frontend variables. `OPENAI_REWRITE_MODEL` defaults to `gpt-4.1-mini` and must support Responses structured outputs. `OPENAI_REWRITE_MODELS` configures the dropdown allowlist (comma-separated; defaults to `gpt-4.1-mini,gpt-4.1,gpt-4.1-nano,gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna,gpt-6-sol,gpt-6.1-sol,gpt-6-luna,gpt-6-astra`). The configured default is always included. `GET /api/rewrite-models` exposes the choices without credentials. Draft requests may supply `model`; omitted values use the server default, and unlisted values are rejected before generation. The GPT-5.6 family choices use their API IDs: `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` (see [official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)). Newer choices include `gpt-6-sol`, `gpt-6.1-sol`, `gpt-6-luna`, and `gpt-6-astra` (see the [official model catalog](https://developers.openai.com/api/docs/models)). These reasoning models use the provider’s default reasoning effort; their reasoning tokens count toward the output cap, so increase `REWRITE_OUTPUT_TOKENS` within the context budget if a run reports incomplete output. Account/model access errors remain visible. See [GPT-5.6+ verification limits](backend/evaluation/model-support-verification.md): current credentials lack access to the new model IDs, so live support is not yet confirmed. Changing the model clears the previous draft. Configuration is read per request. The client uses bounded timeout (45 seconds per attempt), one retry (maximum two), no external tools, and `store=False`. See [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

`REWRITE_CONTEXT_TOKENS` (16,000) includes instructions, JSON source payload, output schema, a 256-token overhead allowance and `REWRITE_OUTPUT_TOKENS` (4,000). This is an application cap; set it within the selected model's verified capacity. Tokenization uses tiktoken's model encoding, with an explicitly reported `o200k_base` fallback for unknown aliases. Whole extraction chunks are processed sequentially, at most `REWRITE_MAX_CALLS` (12). Oversized tables, code and nested-list groups cause a visible context-limit failure if they do not fit; no source is silently truncated or omitted. Calls made before a later failure may incur charges; no partial draft is applied.

Only plain top-level paragraphs and headings can be rewritten. Linked or inline-formatted blocks, tables, code, lists and metadata stay unchanged. Structural permission permits changing levels of existing headings; block insertion/deletion/reordering is intentionally outside this baseline. Every edit includes exact before text, snapshot/chunk/block identities, source evidence quotes, a reason and review flags. Validation proves references/quotes match source, **not** factual entailment. Human reviewers must check support, qualifiers and omissions before applying a proposal. Model-flagged unsupported additions or missing evidence prevent draft application. Extraction review flags remain visible.

Missing credentials, API errors/timeouts, refusals, incomplete/invalid output, unsupported output, context limits and insufficient evidence return explicit failure status and telemetry in the HTTP error's `detail`. There is no silent mock fallback. Successful drafts require a body edit. The UI renders escaped structured blocks and provides Markdown export; it does not patch HTML or reproduce source CSS. Model/prompt version, aggregate input/output usage, elapsed time and failure status are returned. Cost is unavailable unless both `REWRITE_INPUT_USD_PER_MILLION` and `REWRITE_OUTPUT_USD_PER_MILLION` are configured; these prices apply only to the configured default model, and other model choices report cost unavailable. Estimates exclude discounts/cached-token pricing and are not billing records.

## Frozen exploratory rewrite baseline

From the backend directory:

```sh
uv run pytest -q
# Explicitly enables a credentialed smoke test:
RUN_OPENAI_LIVE=1 uv run pytest -q tests/test_live_rewriting.py
# Verify explicit dropdown models (optional comma-separated list):
RUN_OPENAI_LIVE=1 RUN_OPENAI_LIVE_MODELS=gpt-5.6-sol,gpt-6.1-sol uv run pytest -q tests/test_live_rewriting.py
# Explicitly enables real calls and writes full sources, proposals, telemetry and checks:
uv run --env-file .env python scripts/evaluate_rewriting.py --live --output evaluation/new-report.json
# Add an extraction held-out example; its original query is editable interactively:
uv run --env-file .env python scripts/evaluate_rewriting.py --live --example-id SNAPSHOT_ID --example-query "A source-supported query" --output evaluation/new-report.json
```

Without `--live`, evaluation makes no API calls and records `not_run`. `evaluation/samples.json` freezes the custom source. `evaluation/baseline-report.json` records the custom success and original held-out-query abstention. `evaluation/heldout-supported-query-report.json` records the held-out success with an edited supported query, including source identity; `evaluation/baseline-review.md` records human review and limitations. Reports contain source data, so choose export destinations appropriately. Exact evidence validity, unchanged blocks, metadata, structure, body changes, qualifier-term omissions and query-term presence are repeatable checks. Lexical proxies are not semantic quality scores. Factual support, omissions and query usefulness require human review. Mock grades and relative citation labels never enter generation or evaluation and are not measured uplift. Interactive extraction-held-out examples are exploratory; reserve separate rewrite final test data before any GEPA/memory optimization.
