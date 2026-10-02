# Content Studio

A Next.js + FastAPI demo with multi-query OpenAI rewriting, frozen P1 scoring and mock editorial grading for source-grounded content optimization.

## Project context for future sessions

Read [project context and dated handoff](docs/project-context.md) for current architecture, workstream provenance, model verification limits and the historical handoff. Repository editing guidance lives in [AGENTS.md](AGENTS.md), with scoped instructions in [backend/AGENTS.md](backend/AGENTS.md) and [frontend/AGENTS.md](frontend/AGENTS.md).

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
Next.js proxies `/api/*` to FastAPI with a five-minute timeout for whole-page drafting; set `API_URL` in `frontend/.env.local` to override the backend address. Analysis requires no API key. Draft generation requires server-side `OPENAI_API_KEY`.

## UX

1. Choose **Your own page** to enter target queries (one per line), page URL (`href`), hostname, and HTML, Markdown, or text snapshot. Or choose **Held-out examples**, select a host and saved page, and load all distinct usable prompts from its ten host records or write your own query set. “Host” is represented by page URL + hostname, matching the adjacent research schema.
2. Inspect sections, chunks, source statements (“factoids”), and metadata. Review P1 scores for every target query. Compare blocks with the saved source, filter review hints, and export the extraction report or original snapshot.
3. Optionally open draft tools, select a model and editorial tone, then review attributed OpenAI edits, every query’s before/after P1 scores and any regressions, or export Markdown. Source changes invalidate previous analysis and drafts.

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
preserves all ten original host prompt records and their source URLs/shard rows. Usable prompts are trimmed and deduplicated by exact text; blank/invalid prompts are explicitly counted and excluded. No citation labels enter scoring or generation. It does not resample or fetch live pages. The
current manifest provides 40 hosts/pages. The generated bundle lives in
`backend/data/examples/`, is excluded from Git, and is not overwritten on reruns.
Use `--output /new/path` to prepare another bundle and set
`CONTENT_EXAMPLES_DIR=/new/path` when starting the API to serve it. Paths set in
the environment are resolved relative to the backend process working directory.

`GET /api/examples` lists host/page/query metadata without payloads or citation
labels; `GET /api/examples/{snapshot_id}` loads a hash-verified saved snapshot.
Analysis and draft requests can supply `{example_id}` to use the prepared host query set, or `{example_id, queries: ["Query one?", "Query two?"]}` to override it. Custom snapshots use `queries` alongside the source fields. The legacy single `query` remains supported, but cannot accompany `queries`. The API accepts 1–20 distinct usable queries, each 3–1,000 characters. Saved content is read-only; custom queries are allowed. Responses
carry `source_origin` with the original snapshot, split, manifest and payload
identities. Both modes invoke the installed research retention parser. P1 scores use the pinned upstream model when installed; editorial grades remain mocked. Rewriting uses the versioned multi-query OpenAI baseline.

Custom input remains usable without a bundle. Its limit is 200,000 characters;
saved examples support up to 8,000,000 characters without truncation. Switching
back to **Your own page** restores the previous custom inputs. User edits to a
query or source invalidate previous analysis and drafts.

These examples are held out for the extraction benchmark. Interactive prompt
experimentation is exploratory; it does not establish an untouched P2 rewrite
test set. Reserve separate examples when measuring GEPA or memory improvements.

## Frozen P1 model

Install the trusted v2 artifact locally (raw research data and models remain outside Git):

```sh
cd backend
uv run python scripts/prepare_p1.py --model /path/to/content-optimization-system/data/trad_ml_scorer/v2/model.joblib
```

The pinned SHA-256 is `f78ca1f8e51f147a5b52a16cafed6819d165f18eff8bf6e0f5ed61cf5c918b92`. The default installed path is `backend/data/scoring/model.joblib`; `P1_MODEL_PATH` can point elsewhere but must contain those same trusted bytes. The installer refuses an existing output. No model is retrained or substituted. Source inspection and custom snapshots still work without the model.

P1 predicts the sampled within-host top class among already-cited pages. Scores are shown on a 0–100 scale for comparison, not as citation probabilities. Extraction-held-out hosts are not necessarily P1-test-held-out. All ten host records stay visible in provenance; distinct usable queries receive equal weight. Some prompts refer to other URLs on the host. No new snapshot is sampled and the selected original payload stays unchanged.

## What is real vs. mocked

- **Real:** frozen upstream P1 v2 scoring when the trusted model is installed, complete query-set feedback in rewriting, before/after per-query comparisons, API validation, installed retention-first extraction/selection for HTML/Markdown/text, typed blocks, metadata/JSON-LD, source mappings, quality flags, structured chunks, frontend/API round trips, review/export.
- **Mock:** query alignment and answer clarity scores; structural score uses only heading count. P1 changes are classifier-score changes, not measured citation uplift. There is no automatic demo rewrite fallback.
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

`app/scoring.py` invokes the installed upstream P1 v2 feature implementation for each distinct target query. It verifies the trusted model SHA-256 and fitted parser/feature fingerprints before use. Both source and proposal are scored as structured documents with the same original source inventory and metadata, without reparsing exported Markdown. Missing/incompatible models produce explicit unavailability, never mock P1 values. Preserve disagreements/abstention and structural diagnostics; do not treat relative within-host labels as citation probabilities.

`backend/app/rewriting.py` owns generation, token budgeting, source validation and rendering, independently of extraction and the endpoint. Its current hand-written prompt is `backend/app/prompts/rewrite-page-v6.txt`; `rewrite-baseline-v1.txt` and `rewrite-multiquery-v1.txt` remain historical baselines. Every request includes all distinct target queries and whole-page P1 feedback. Each draft request makes one whole-page OpenAI call with all retained blocks and target queries. Extraction chunks remain evidence/provenance boundaries, not generation batches. The user payload separates `editable_blocks` (the only valid edit targets) from `read_only_context` (context/evidence only), preserving original order fields and chunk membership through short request-local chunk aliases. Block text appears once; raw DOM locators, JSON-LD, visibility diagnostics and duplicate chunk text/Markdown stay in the original document for review and scoring. A bounded response schema defines the proposal shape and, within its size allowance, binds editable targets to evidence IDs in the same original chunk; the server validates editable IDs, exact before text and same-chunk evidence. Fully validated unchanged edits are ignored and cannot satisfy the body-edit requirement. The objective is their equal-weight mean while avoiding individual regressions. This is one proposal followed by rescoring, not an iterative optimizer or a guarantee of improvement on every query. Unsupported host queries remain missing-evidence review items; they do not justify invented content. No GEPA or retrieval memory is included. All source/query/metadata content is untrusted data in the user message; the fixed editorial/security instructions are separate.

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

Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY` there, or export it into the backend process. Start uvicorn with `--env-file .env` as above. The key is server-only; never put it in frontend variables. `OPENAI_REWRITE_MODEL` defaults to `gpt-4.1-mini` and must support Responses structured outputs. `OPENAI_REWRITE_MODELS` configures the dropdown allowlist (comma-separated; defaults to `gpt-4.1-mini,gpt-4.1,gpt-4.1-nano,gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna,gpt-6-sol,gpt-6.1-sol,gpt-6-luna,gpt-6-astra`). The configured default is always included. `GET /api/rewrite-models` exposes the choices without credentials. Draft requests may supply `model`; omitted values use the server default, and unlisted values are rejected before generation. The GPT-5.6 family choices use their API IDs: `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` (see [official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)). Newer choices include `gpt-6-sol`, `gpt-6.1-sol`, `gpt-6-luna`, and `gpt-6-astra` (see the [official model catalog](https://developers.openai.com/api/docs/models)). These reasoning models use the provider’s default reasoning effort; their reasoning tokens count toward the output cap, so increase `REWRITE_OUTPUT_TOKENS` within the context budget if a run reports incomplete output. Account/model access errors remain visible. See [GPT-5.6+ verification limits](backend/evaluation/model-support-verification.md): current credentials lack access to the new model IDs, so live support is not yet confirmed. Changing the model clears the previous draft. Configuration is read per request. The client uses a 120-second timeout and no automatic retries, no external tools, and `store=False`. See [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

`REWRITE_CONTEXT_TOKENS` (128,000) includes instructions, JSON source payload, output schema, a 256-token overhead allowance and `REWRITE_OUTPUT_TOKENS` (16,000). This is an application cap; set it within the selected model's verified capacity. Tokenization uses tiktoken's model encoding, with an explicitly reported `o200k_base` fallback for unknown aliases. The complete retained page is submitted once. If the full input plus output reserve exceeds the context budget, the request fails before contacting OpenAI; it never silently splits or truncates source/query context. Legacy call-count/retry configuration does not enable additional provider attempts. Incomplete output fails without applying a partial draft.

Only plain top-level paragraphs and headings can be rewritten. Linked or inline-formatted blocks, tables, code, lists and metadata stay unchanged. Structural permission permits changing levels of existing headings; block insertion/deletion/reordering is intentionally outside this baseline. The model returns an editable block ID, replacement text, a reason, evidence block IDs and review flags. The backend supplies exact before text, snapshot/chunk identities and complete evidence passages from the selected source blocks. It rejects unknown IDs, protected targets and evidence outside the original chunk. The API response includes these assembled references and passages; they are server-copied evidence, not model-authored quotations. Validation proves references/quotes match source, **not** factual entailment. Human reviewers must check support, qualifiers and omissions before applying a proposal. Model-flagged unsupported additions or missing evidence prevent draft application. Extraction review flags remain visible.

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

Without `--live`, evaluation makes no API calls and records `not_run`. `evaluation/samples.json` freezes the custom source. `evaluation/baseline-report.json` records the custom success and original held-out-query abstention. `evaluation/heldout-supported-query-report.json` records the held-out success with an edited supported query, including source identity; `evaluation/baseline-review.md` records human review and limitations. Reports contain source data, so choose export destinations appropriately. Exact evidence validity, unchanged blocks, metadata, structure, body changes, qualifier-term omissions and query-term presence are repeatable checks. Lexical proxies are not semantic quality scores. Factual support, omissions and query usefulness require human review. Mock editorial grades and raw citation labels never enter generation or evaluation; frozen P1 predictions now enter the multi-query rewrite feedback and are not measured uplift. Interactive extraction-held-out examples are exploratory; reserve separate rewrite final test data before any GEPA/memory optimization.

### Extraction verification

The default analysis view compares extraction with the saved snapshot. Sections expose typed blocks, parent relationships, mapping status and lazy **Compare with source** previews. Filters highlight ambiguous mappings, hidden-source attributes and possible boilerplate without removing content. Chunks preserve block order and show inferred heading context and oversized groups. **Source statements** is the display name for the compatibility `factoids` field: these are copied passages, not atomic or independently verified facts. Metadata separates copied source fields from computed inventory and heuristics. Source previews are escaped text; HTML fragments are DOM serializations, with that normalization explicitly labeled.

Mechanical checks cover chunk partition/order, nested groups, chunk text/counts, passage copies, exact snapshot identity, source title/meta tags and raw JSON-LD mappings. These checks do not prove completeness, factual truth, relevance or rendered visibility. A matching substring also does not certify semantic grouping. Unresolved mappings remain unresolved even when candidate matching text is found. Mock grades and real OpenAI draft controls are available separately through **Open draft tools**. Source inspection does not require rewrite-model configuration or an API key. Proposed draft blocks retain references to the original snapshot but do not receive source-match badges.

Reproduce the 40-example diagnostics from an installed example bundle:

```sh
cd backend
.venv/bin/python scripts/audit_examples.py > ../verification/heldout-source-audit.json
```

The checked-in report is a development diagnostic on the extraction held-out slice, not a human gold evaluation. All mechanical checks passed across 7,538 blocks; 1,290 ambiguous mappings and one unavailable mapping remain unverified. No text mismatch was found at resolved locations. Nine chunks exceed the soft character limit. Boilerplate (1,240 blocks) and hidden-source (228 blocks) hints require human review and can overlap.

Priorities for improving the research parser: establish more precise source ranges for ambiguous paragraphs; distinguish article content from navigation/sidebar/footer without losing source content; make chunk heading context respect DOM regions; and introduce atomic claim extraction only with explicit source references and separate factual verification. Measure omissions against human annotations before claiming extraction coverage improvements. Keep this pinned parser and frozen examples unchanged while collecting review findings.

Upstream follow-ups: [source mappings #7](https://github.com/ext-weihsianglin/content-optimization-system/issues/7), [chunk heading context #8](https://github.com/ext-weihsianglin/content-optimization-system/issues/8), [oversized chunk consumption #9](https://github.com/ext-weihsianglin/content-optimization-system/issues/9), and [inline semantics #10](https://github.com/ext-weihsianglin/content-optimization-system/issues/10). Real P2 OpenAI orchestration was merged in [demo-webapp PR #2](https://github.com/ext-weihsianglin/demo-webapp/pull/2). No Markdownify substitution is included in this workstream.

### Rewrite language preservation

Rewrites preserve each source block's language, independently of target-query language or page metadata. The prompt and user payload state this policy. A local Lingua check rejects confidently detected source/output language changes before a draft can be applied, with `language_changed` diagnostics. It makes no additional LLM call. Short, unsupported, mixed or ambiguous text may be inconclusive and is labeled `language_preservation_unverified` for review; this is a heuristic guardrail, not a universal translation detector. Detection uses the [Lingua library](https://github.com/pemistahl/lingua-py), with lazily loaded high-accuracy models and conservative confidence thresholds; its model package adds approximately 165 MiB to installation downloads. The frozen P1 model/parser remain unchanged.
