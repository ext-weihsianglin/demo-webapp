# Content Studio

A Next.js + FastAPI demo with multi-query OpenAI rewriting, frozen P1 scoring and mock editorial grading for source-grounded content optimization.

## Project context for future sessions

Read [project context and dated handoff](docs/project-context.md) for current architecture, workstream provenance, model verification limits and the historical handoff. Repository editing guidance lives in [AGENTS.md](AGENTS.md), with scoped instructions in [backend/AGENTS.md](backend/AGENTS.md) and [frontend/AGENTS.md](frontend/AGENTS.md).

GEPA planning: [implementation plan](docs/gepa-plan.md) and [specification](docs/gepa-spec.md). The optimizer and research tab are implemented for bounded local experiments.

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

Prepare a version-3 local bundle from the completed Markdownify corpus, original Parquet snapshots, and frozen P1 v7 row assignments:

```sh
cd backend
uv sync --dev
uv run python scripts/prepare_examples.py \
  --corpus /path/to/processed/markdownify-corpus-v1-complete \
  --split-root /path/to/trad_ml_scorer/v7 \
  --raw-root /path/to/raw
```

Only **P1 test hosts** enter the webapp. The current bundle contains 97 hosts, one deterministic saved page per host, with all ten original host prompt records. Preparation checks split/corpus/raw hashes and host/payload separation from train/validation. Queries are trimmed and deduplicated; unusable prompts remain counted in provenance. Labels never enter generation or scoring.

The generated bundle lives in ignored `backend/data/examples/`; it is never overwritten. Use `--output /new/path` and `CONTENT_EXAMPLES_DIR=/new/path` for another bundle. Old extraction-held-out bundles are rejected because that designation does not establish P1 test membership. Paths in environment variables are relative to the backend process working directory.

`GET /api/examples` lists host/page/query metadata without payloads or citation
labels; `GET /api/examples/{snapshot_id}` loads a hash-verified saved snapshot.
Analysis and draft requests can supply `{example_id}` to use the prepared host query set, or `{example_id, queries: ["Query one?", "Query two?"]}` to override it. Custom snapshots use `queries` alongside the source fields. The legacy single `query` remains supported, but cannot accompany `queries`. The API accepts 1–20 distinct usable queries, each 3–1,000 characters. Saved content is read-only; custom queries are allowed. Responses
carry `source_origin` with the original snapshot, split, manifest and payload
identities. Both modes invoke the installed research retention parser. P1 scores use the pinned upstream model when installed; editorial grades remain mocked. Rewriting uses the versioned multi-query OpenAI baseline.

Custom input remains usable without a bundle. Its limit is 200,000 characters;
saved examples support up to 8,000,000 characters without truncation. Switching
back to **Your own page** restores the previous custom inputs. User edits to a
query or source invalidate previous analysis and drafts.

These examples are P1 test data. GEPA must use separately frozen train/validation data. Interactive test-page inspection and baseline debugging are recorded exposure; test membership alone does not establish an untouched final P2 evaluation.

## Frozen P1 model

Install the trusted v7 `semantic_context` artifact locally:

```sh
cd backend
uv run python scripts/prepare_p1.py --model /path/to/trad_ml_scorer/v7/semantic_context.joblib
```

Pinned SHA-256: `2ff334173b83364fb49685fcdca7339f71b1c88bcef154d71e0a21d595587d6b`. Default installed path: `backend/data/scoring/model.joblib`; override with `P1_MODEL_PATH`. The installer refuses an existing destination; use a fresh path when replacing v2. No retraining or fallback model is included.

V7 uses ten original-space cosine summaries from OpenAI `text-embedding-3-large` (3,072 dimensions), plus 45 context features and the frozen fitted pipeline. PCA coordinates are not scorer inputs. `app/embeddings.py` imports the upstream serialization, byte splitting, cache identity, vector validation, normalized byte-weighted pooling and cosine helpers. Query/title/H1/outline/page/path/section inputs match `blocks-v3-markdownify`.

Set `EMBEDDING_CACHE_ROOT` to the prepared shared store to reuse existing vectors. Cache-only scoring is the default. New queries/pages/rewrites need fresh embeddings on cache misses; explicitly enable `P1_ENABLE_LIVE_EMBEDDINGS=1` in the backend configuration for those calls. `P1_MAX_EMBEDDING_REQUESTS` caps new unique requests per scoring operation (default 512); all misses are preflighted before provider calls. Calls have the upstream 60-second timeout and no automatic retry. Failed/missing embeddings remain visible; no lexical-only substitute is used. Responses include embedding calls, cache counts and reported token usage. Extraction inspection remains available without credentials or P1 inputs.

**Serving adaptation:** the webapp computes v7's context features from current Markdownify documents. Frozen training used legacy cached context columns. This intentionally deferred mismatch is disclosed as `markdownify-context-v1` and tracked in [upstream issue #15](https://github.com/ext-weihsianglin/content-optimization-system/issues/15); the webapp does not claim exact frozen-context parity. Original source inventory/metadata remain fixed for proposals, while changed text, outline, chunks and embeddings are rebuilt.

P1 estimates sampled within-host top class among already-cited pages. Scores are comparative classifier outputs, not citation probabilities or causal uplift. V7 is an experimental development choice; its semantic features alone do not establish superior quality.

## What is real vs. mocked

- **Real:** bounded GEPA optimization and persistent local research traces, model-specific prompt selection, source-relative fidelity checks, frozen upstream P1 v7 scoring when the trusted model is installed, complete query-set feedback in rewriting, before/after per-query comparisons, API validation, installed retention-first extraction/selection for HTML/Markdown/text, typed blocks, metadata/JSON-LD, source mappings, quality flags, structured chunks, frontend/API round trips, review/export.
- **Mock:** query alignment and answer clarity scores; structural score uses only heading count. P1 changes are classifier-score changes, not measured citation uplift. There is no automatic demo rewrite fallback.
- **Not connected:** optional clean extraction candidates, calibrated graders, live URL fetching, source-style rendering, HTML patching.

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

The library is installed by `uv sync` from the pinned local 0.2.0 wheel declared in `backend/pyproject.toml`. It bundles merged upstream revision `864e6634a54ad80ac1657129e994b18c3a1f7eff`, including Markdownify hotfixes, v7 and representations. [provenance-v2.json](backend/packages/provenance-v2.json) records wheel/module hashes; [content-optimization-library-v2.patch](backend/packages/content-optimization-library-v2.patch) records packaging, the tuple facade and explicit source-format override. Extraction logic stays upstream. Rebuild with `uv run python scripts/build_upstream_package.py`. Historical wheel/provenance remain intact.

HTML uses the same source-owned `dom-blocks-v3` and pinned `markdownify==1.2.3` path as the completed corpus, preserving inline syntax, tables, code and definitions. This is not a bare Markdownify call over arbitrary HTML. Native Markdown/text keep their adapter and explicit format. The source remains untrusted and is never executed.

Validated draft generation uses the library's `blocks_to_markdown` so nested lists,
code whitespace and table spans survive export. Source metadata and JSON-LD remain
separate from generated body content.

The webapp adds query-independent `source_role_context` metadata for HTML controls whose ARIA ancestry is omitted from upstream blocks. This overlay leaves core parser/scorer fields unchanged. The `body-content-v2` rewrite boundary protects site chrome, forms and controls using source DOM paths and normalized roles; article headers inside `main`/`article` remain editable.

`app/scoring.py` verifies the trusted v7 model before deserialization, the ordered 55-feature contract and packaged module fingerprints. Original and proposed structured documents are scored over the same query set and immutable source inventory. Scoring is separate from extraction and HTTP handling. Missing/incompatible models or embeddings produce explicit unavailability.

Reproduce the bounded cache-only parser/semantic parity audit:

```sh
cd backend
uv run python scripts/verify_upstream_parity.py \
  --corpus /path/to/processed/markdownify-corpus-v1-complete \
  --split-root /path/to/trad_ml_scorer/v7 \
  --raw-root /path/to/raw \
  --cache-root /path/to/representations/shared-store \
  --output ../verification/new-parity.json
```

[Recorded audit](verification/upstream-v7-parity.json): five validation records matched saved parser fields exactly; all ten semantic features differed by at most `1.19e-7`. No provider calls. This establishes bounded parser/semantic parity, not legacy-context parity or quality uplift.

`backend/app/rewriting.py` owns generation, token budgeting, source validation and rendering, independently of extraction and the endpoint. Its current hand-written prompt is `backend/app/prompts/rewrite-page-v7.txt`; `rewrite-baseline-v1.txt` and `rewrite-multiquery-v1.txt` remain historical baselines. Every request includes all distinct target queries and whole-page P1 feedback. Each draft request makes one whole-page OpenAI call with all retained blocks and target queries. Extraction chunks remain evidence/provenance boundaries, not generation batches. The user payload separates `editable_blocks` (the only valid edit targets) from `read_only_context` (context/evidence only), preserving original order fields and chunk membership through short request-local chunk aliases. Block text appears once; raw DOM locators, JSON-LD, visibility diagnostics and duplicate chunk text/Markdown stay in the original document for review and scoring. A bounded response schema defines the proposal shape and, within its size allowance, binds editable targets to evidence IDs in the same original chunk; the server validates editable IDs, exact before text and same-chunk evidence. Fully validated unchanged edits are ignored and cannot satisfy the body-edit requirement. The objective is their equal-weight mean while avoiding individual regressions. This is one proposal followed by rescoring, not an iterative optimizer or a guarantee of improvement on every query. Unsupported host queries remain missing-evidence review items; they do not justify invented content. No GEPA or retrieval memory is included. All source/query/metadata content is untrusted data in the user message; the fixed editorial/security instructions are separate.

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

Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY` there, or export it into the backend process. Start uvicorn with `--env-file .env` as above. The key is server-only. The supported P2 catalog is `gpt-4.1-mini,gpt-4.1,gpt-4.1-nano,gpt-5,gpt-5-mini,gpt-5-nano`. These IDs are available to the current credentials and have been checked with this rewrite pipeline; access can differ for other credentials. The default remains `gpt-4.1-mini`. `OPENAI_REWRITE_MODELS` can narrow this catalog, but cannot add untested IDs; a supported configured default is always included. An unsupported `OPENAI_REWRITE_MODEL` produces a configuration error, never a silent fallback. The old GPT-5.6/GPT-6 entries are excluded.

`GET /api/rewrite-models` exposes the permitted choices. Draft requests reject unlisted models before generation. GPT-5 mini/nano use low reasoning effort to bound latency; GPT-5 uses the provider default. Reasoning tokens share the output cap. Account failures, abstention, incomplete responses and validation failures remain visible; catalog inclusion does not guarantee every request succeeds or improves scores. Model changes clear the previous draft. The client uses a 120-second timeout, no automatic retries, no external tools and `store=False`. See [initial model checks](verification/p2-model-catalog-verification.json) and [current mini/nano harness verification](verification/keyed-rewrite-final-matrix.json) and [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

`REWRITE_CONTEXT_TOKENS` (128,000) includes instructions, JSON source payload, output schema, a 256-token overhead allowance and `REWRITE_OUTPUT_TOKENS` (16,000). This is an application cap; set it within the selected model's verified capacity. Tokenization uses tiktoken's model encoding, with an explicitly reported `o200k_base` fallback for unknown aliases. The complete retained page is submitted once. If the full input plus output reserve exceeds the context budget, the request fails before contacting OpenAI; it never silently splits or truncates source/query context. Legacy call-count/retry configuration does not enable additional provider attempts. Incomplete output fails without applying a partial draft.

Only plain top-level paragraphs and headings can be rewritten. Linked or inline-formatted blocks, tables, code, lists and metadata stay unchanged. Structural permission permits changing levels of existing headings; block insertion/deletion/reordering is intentionally outside this baseline. The provider returns a required object keyed by every editable block ID: null means unchanged; a replacement includes text, a reason, evidence block IDs and review flags. Identical duplicate JSON keys are normalized once; conflicting duplicates, missing slots and unexpected IDs reject the entire proposal. Replacement text is constrained to a nonblank single line. No repair call or model fallback is used. The backend supplies exact before text, snapshot/chunk identities and complete evidence passages from the selected source blocks. It rejects unknown IDs, protected targets and evidence outside the original chunk. The API response includes these assembled references and passages; they are server-copied evidence, not model-authored quotations. Validation proves references/quotes match source, **not** factual entailment. Human reviewers must check support, qualifiers and omissions before applying a proposal. Model-flagged unsupported additions or missing evidence prevent draft application. Extraction review flags remain visible.

Missing credentials, API errors/timeouts, refusals, incomplete/invalid output, unsupported output, context limits and insufficient evidence return explicit failure status and telemetry in the HTTP error's `detail`. There is no silent mock fallback. Successful drafts require a body edit. The UI renders escaped structured blocks and provides Markdown export; it does not patch HTML or reproduce source CSS. Model/prompt version, aggregate input/output usage, elapsed time and failure status are returned. Cost is unavailable unless both `REWRITE_INPUT_USD_PER_MILLION` and `REWRITE_OUTPUT_USD_PER_MILLION` are configured; these prices apply only to the configured default model, and other model choices report cost unavailable. Estimates exclude discounts/cached-token pricing and are not billing records.

## Frozen exploratory rewrite baseline

From the backend directory:

```sh
uv run pytest -q
# Explicitly enables a credentialed smoke test:
RUN_OPENAI_LIVE=1 uv run pytest -q tests/test_live_rewriting.py
# Verify explicit dropdown models (optional comma-separated list):
RUN_OPENAI_LIVE=1 RUN_OPENAI_LIVE_MODELS=gpt-4.1,gpt-5 uv run pytest -q tests/test_live_rewriting.py
# Explicitly enables real calls and writes full sources, proposals, telemetry and checks:
uv run --env-file .env python scripts/evaluate_rewriting.py --live --output evaluation/new-report.json
# Add a P1-test example; its original query is editable interactively:
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

### Keyed rewrite verification

Run a fresh explicit live matrix against hash-verified held-out snapshots (repeat both selectors):

```sh
CONTENT_EXAMPLES_DIR=/absolute/path/to/examples uv run --project backend python backend/scripts/verify_rewrite_matrix.py --live --example-id SNAPSHOT_ID --model gpt-4.1-mini --model gpt-5-nano --output verification/new-matrix.json
```

The command refuses existing output files. `--artifacts-dir /fresh/path` optionally records full provider output and proposed source data for debugging. Reports distinguish successful body drafts, valid abstentions, timeouts and validation failures; they do not establish factual entailment or citation uplift. Null entries keep original blocks intact. The keyed schema has its own size guard and fails before generation when too large, without dropping source content.

## GEPA research

The GEPA Optimization tab runs `gepa==0.1.4` against a separate frozen **P1 validation** dataset. Prepare it once, using a fresh output path:

```sh
cd backend
uv run python scripts/prepare_gepa.py \
  --corpus /path/to/processed/markdownify-corpus-v1-complete \
  --split-root /path/to/trad_ml_scorer/v7 \
  --raw-root /path/to/raw \
  --output data/gepa/datasets/validation-90-v1
```

Preparation verifies source/split hashes and eligibility without provider calls, then freezes 60 reflection and 30 selection pages from distinct hosts. The webapp test catalog is excluded. Configure the trusted P1 model, backend `OPENAI_API_KEY`, embedding cache and explicit `P1_ENABLE_LIVE_EMBEDDINGS=1` before research. Dataset/run storage defaults to `backend/data/gepa`; `GEPA_DATA_ROOT` overrides it.

Choose the rewriter, reflection model and seed prompt; edit limits before Start. Defaults are 100 total page rewrite attempts, concurrency 10, two reflection pages per mutation and ten proposed mutations. Baseline selection consumes 30 attempts. Reflection, fidelity and embedding calls are additional and counted separately. Enable live research calls explicitly. Start/Stop, saved outcomes, prompt diffs, per-query original/baseline/candidate comparisons and JSON export are available. Stop saves in-flight results; restart leaves interrupted runs inspectable without resuming them. One backend process owns one active run.

Only the baseline's first editorial paragraph evolves; its remaining instructions and mechanical harness stay fixed. Prompt registry entries are model-specific and content-addressed. Baselines reproduce v7 bytes. Experimental entries are selectable in Content Studio; promotion updates a local model default only when a complete 30-page candidate improves baseline mean without increasing failure rate. Generated prompts/defaults and run data are ignored local files. `PROMPT_REGISTRY_ROOT` overrides generated registry storage.

Both research and ordinary real drafts use the same source-relative `gpt-4.1-mini` fidelity gate. Unsupported or uncertain edits reject the whole proposal. Research retains the original page and measured score; semantic rejection is feedback, while judge/provider failures count toward the technical breaker. A passed gate is an LLM judgment, not factual verification. This adds a provider call for changed drafts.

For a bounded live wiring check, explicitly run:

```sh
uv run python scripts/smoke_gepa.py --live --dataset validation-90-v1 \
  --output data/gepa/smoke-report-v1.json
```

It uses one reflection-page rewrite and one reflection mutation, with no selection evaluation or promotion. Ordinary tests use stub clients. See [implementation spec](docs/gepa-spec.md) for invariants and [implementation handoff](docs/gepa-implementation.md) for choices and verification limits.
