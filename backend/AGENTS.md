# Backend guidance

Inherit the root [AGENTS.md](../AGENTS.md). Python 3.12+, FastAPI, uv-managed dependencies; use `uv.lock` and the bundled extraction wheel.

## Boundaries and contracts

- `app/extraction.py` calls the pinned upstream retention parser. Keep extraction independent of the target query and citation labels. Do not duplicate the upstream parser or replace the wheel with an unpublished Git dependency.
- `app/examples.py` serves explicitly prepared, hash-verified extraction-held-out snapshots. Saved payloads are read-only; their target query is editable. `scripts/prepare_examples.py` prepares the ignored local bundle. Missing bundles must not prevent custom snapshots.
- `app/rewriting.py` owns token budgeting, OpenAI requests, edit validation and rendering. `app/main.py` owns request validation and HTTP errors. Keep the fixed baseline prompt separate from untrusted source inputs.
- `GET /api/rewrite-models` is the server-owned model catalog. `OPENAI_REWRITE_MODEL` is the default; `OPENAI_REWRITE_MODELS` is the allowlist. Clients may choose only listed IDs, and omitted selections retain the default. Model inclusion does not prove account access. Preserve `model_unavailable` errors; never fall back silently. Global configured price estimates apply only to the default model.
- Editable blocks currently comprise plain top-level paragraphs/headings. Preserve linked/formatted blocks, tables, nested lists, code and source metadata. Structural permission only permits level changes to existing headings. Do not broaden this contract without matching validation, rendering, tests and documentation.
- Validate snapshot/chunk/block references, exact `before` text and evidence quotes. Exact quote validation is not semantic entailment. Carry extraction warnings/review flags, abstain when source is insufficient, and require a body edit for successful generation.
- Budget the full input/schema/instructions and output reserve in model tokens. Extraction chunks use a soft character target. Oversized groups must fail visibly rather than be silently truncated. Incomplete/refused/invalid output cannot become a partial successful draft.

## Checks and evidence

Ordinary tests use stubbed OpenAI clients. Run `uv run pytest -q` from this directory. Credentials in `.env` must be loaded explicitly for CLI checks, for example:

```sh
RUN_OPENAI_LIVE=1 RUN_OPENAI_LIVE_MODELS=gpt-5.6-sol,gpt-6.1-sol \
  uv run --env-file .env pytest -q tests/test_live_rewriting.py
uv run --env-file .env python scripts/evaluate_rewriting.py --live --output evaluation/new-report.json
```

The flags above explicitly enable provider calls; do not enable them in ordinary tests. Keep secrets and raw provider error bodies out of test/report output. New reports can contain full source data.

Read `evaluation/baseline-review.md` and `evaluation/model-support-verification.md` before claiming quality or live model support. Existing interactive extraction-held-out data is exploratory, not a reserved P2 final test set. Preserve frozen reports; reserve separate rewrite data before GEPA/memory optimization.
