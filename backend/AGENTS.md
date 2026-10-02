# Backend guidance

Inherit the root [AGENTS.md](../AGENTS.md). Use FastAPI and uv-managed dependencies with `uv.lock`. The current main scaffold requires Python 3.11+ and keeps local extraction/mock rewriting in `app/main.py`. PR #2 requires Python 3.12+ and adds the bundled extraction wheel. Check the current `pyproject.toml` before setup.

## Proposed integration boundaries and contracts

The following files/contracts are implemented in [PR #2](https://github.com/ext-weihsianglin/demo-webapp/pull/2), which was still open at the dated handoff. Apply them where present; do not assume this documentation PR installs that implementation. For the current scaffold, preserve its query-independent extraction and clearly labeled mock behavior until the real integration is merged.

- `app/extraction.py` calls the pinned upstream retention parser. Keep extraction independent of the target query and citation labels. Do not duplicate the upstream parser or replace the wheel with an unpublished Git dependency.
- `app/examples.py` serves explicitly prepared, hash-verified extraction-held-out snapshots. Saved payloads are read-only; their target queries are editable. Version-2 bundles retain all ten host records and default to the distinct usable prompt set; never silently pick the first prompt. `scripts/prepare_examples.py` prepares the ignored local bundle. Missing bundles must not prevent custom snapshots.
- `app/rewriting.py` owns token budgeting, OpenAI requests, edit validation and rendering. `app/main.py` owns request validation and HTTP errors. Keep the fixed baseline prompt separate from untrusted source inputs.
- `GET /api/rewrite-models` is the server-owned model catalog. `OPENAI_REWRITE_MODEL` is the default; `OPENAI_REWRITE_MODELS` narrows the supported catalog; it cannot add untested IDs. An unsupported default is a configuration error. Clients may choose only listed IDs, and omitted selections retain the default. Model inclusion does not prove account access. Preserve `model_unavailable` errors; never fall back silently. Global configured price estimates apply only to the default model.
- Editable blocks currently comprise plain top-level paragraphs/headings. Preserve linked/formatted blocks, tables, nested lists, code and source metadata. Structural permission only permits level changes to existing headings. Do not broaden this contract without matching validation, rendering, tests and documentation.
- Validate snapshot/chunk/block references, exact `before` text and evidence quotes. Exact quote validation is not semantic entailment. Carry extraction warnings/review flags, abstain when source is insufficient, and require a body edit for successful generation.
- Budget the full input/schema/instructions and output reserve in model tokens. Extraction chunks use a soft character target. Oversized groups must fail visibly rather than be silently truncated. Incomplete/refused/invalid output cannot become a partial successful draft.

## Checks and evidence

Ordinary scaffold tests exercise the deterministic mock. PR #2 adds stubbed OpenAI clients and explicit live/evaluation commands below; these commands require that implementation to be present. Run `uv run pytest -q` from this directory. Credentials in `.env` must be loaded explicitly for CLI checks, for example:

```sh
RUN_OPENAI_LIVE=1 RUN_OPENAI_LIVE_MODELS=gpt-4.1,gpt-5 \
  uv run --env-file .env pytest -q tests/test_live_rewriting.py
uv run --env-file .env python scripts/evaluate_rewriting.py --live --output evaluation/new-report.json
```

The flags above explicitly enable provider calls; do not enable them in ordinary tests. Keep secrets and raw provider error bodies out of test/report output. New reports can contain full source data.

Read the [project-context evidence links](../docs/project-context.md#models-and-live-verification-limits) (or `evaluation/baseline-review.md` and `evaluation/model-support-verification.md` when present) before claiming quality or live model support. Existing interactive extraction-held-out data is exploratory, not a reserved P2 final test set. Preserve frozen reports; reserve separate rewrite data before GEPA/memory optimization.

## Current reconciliation

PR #2 is merged into main. The checkout combines real OpenAI draft orchestration with source verification; historical scaffold/open-PR descriptions above are dated context. Source analysis/evidence must remain independent of rewrite configuration. Keep proposed content distinct from the original snapshot and never attach original-source match badges to rewritten text.

## Multi-query P1/P2

`app/scoring.py` reuses the installed frozen upstream P1 v2 features and verifies the pinned model bytes before deserialization plus parser/feature fingerprints. Do not retrain, silently substitute models or fabricate scores when the local model is absent. Source inspection remains available without P1/OpenAI configuration. Requests accept a deduplicated `queries` array, with legacy `query` supported separately. Score original and proposed structured documents for the identical full query set, retaining original source inventory and metadata. Report the equal-weight mean and every per-query regression; P1 changes are not citation probabilities or causal uplift.

Keep historical `rewrite-baseline-v1.txt` and frozen reports intact. Current generation uses `rewrite-page-v7.txt`, all target queries and whole-document P1 feedback per page. Make one whole-page provider attempt per draft request with no SDK retry. Preflight the complete page plus output reserve; fail visibly rather than split or drop source/query context. Keep full metadata in the source/scored document, while editorial payloads use minimal metadata and one copy of block text. Keep the provider schema bounded; the provider returns a required nullable slot per editable block, containing replacement text and evidence block IDs. Reject missing/unknown keys and conflicting duplicate JSON keys; normalize only identical duplicates. Resolve immutable before text, snapshot/chunk identities and full evidence passages from the original source in the backend. Enforce editable targets and same-chunk evidence; never claim copied evidence establishes semantic support. Validate references/evidence even for unchanged edits; ignore validated no-ops without counting them as body changes. Never add unsupported answers to satisfy host prompts for other pages. The evaluation script requires a fresh output and explicit `--live`; repeated `--example-query` flags override the complete query set.

Language preservation follows each original block, not target queries or metadata. Preserve explicit uncertainty from `app/language_guard.py`; do not claim heuristic language detection is complete or add provider calls to validate language.
