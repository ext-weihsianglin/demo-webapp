# PR #3 reconciliation and production verification

Verified on 2026-10-01 against `origin/main` at `020d2d6`, after PR #2 (real OpenAI rewriting) and PR #4 (guidance) merged. The nine source-verification/rewrite conflicts are resolved in this PR branch; the prior isolated-preview review is historical evidence.

## Deployment

Local production frontend: **http://127.0.0.1:3005**. FastAPI: **http://127.0.0.1:8011**. No hosting target was configured or supplied, so verification used a production build on the user's machine, not a hosted/public deployment. Other sessions' services on ports 3000/8000 were left untouched.

From the repository root, with server credentials in the process environment:

```sh
uv sync --project backend --locked --dev
uv run --project backend --locked uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

From `frontend/`:

```sh
API_URL=http://127.0.0.1:8011 npm run build
API_URL=http://127.0.0.1:8011 npm run start -- --port 3005
```

The proxy destination must be set during the production build. Credentials remain backend-only and were not written to reports or frontend configuration.

## Verified behavior

- Original-source analysis remains independent of OpenAI credentials, model catalog loading and rewrite configuration. Source comparisons, mapping filters, chunks, metadata groups, source statements and report exports remain available.
- Draft tools load the server model catalog on demand. Real generation replaces the old deterministic mock; no mock/provider/model fallback is introduced.
- Proposals have an explicit renderer variant, original-source reference labels, supporting quotes and telemetry. They have **zero source-match badges and zero Compare with source buttons**. Original-source verification is not a certificate for rewritten text.
- Browser interaction on a public custom HTML snapshot generated one actual body edit with `gpt-4.1-mini`, prompt `rewrite-baseline-v1`: 2,075 input tokens, 333 output tokens, 6,218 ms. Cost was unavailable because no pricing was configured. The title and other body passages stayed unchanged. The changed paragraph, before/after, snapshot/chunk/block references, supporting quote and Markdown preview were visibly rendered.
- Returning to analysis retained the original body. Selecting another model cleared the prior draft and disabled the stale Review your draft step.
- A real `gpt-5.6-sol` attempt displayed `model_unavailable`: the server credentials cannot access it. No draft was applied and no fallback occurred. This does not establish live support for GPT-5.6/GPT-6 models.
- Held-out Asanify snapshot: 481 blocks, 33 chunks, 239 copied source passages, 24 ambiguous mappings and 222 heuristic boilerplate hints. The mapping filter showed 24 blocks; comparison of `Recent Posts` stayed unresolved and offered possible matches without certifying a location. Chunk context caveats and separate source/computed metadata groups remained visible.
- Clicking Export extraction report created a 739,898-byte JSON download. Its snapshot identity, 481 blocks, 24 ambiguous mappings and passing consistency checks were checked from the downloaded artifact. The browser automation download event did not surface, so the downloaded file was inspected directly.
- A custom Markdown fixture retained nested lists, original code indentation (`  keep indentation\n`) and table header cells (`Type`, `Advice`). Its source comparison returned the exact original Markdown line containing `**comfortable fit**` and honestly labeled the formatting difference. One fenced-code source mapping was unavailable in the pinned parser and remained flagged.

## Validation

- Locked dependency sync: passed.
- Backend suite: **55 passed, 1 explicitly opt-in live smoke skipped**. Live generation/access checks above were performed through the production UI, separately from ordinary tests.
- Frontend production build and typecheck: passed.
- The 40-snapshot source audit exactly matches the committed frozen diagnostic report.
- No conflict markers remain; `git diff --check` passes.

## Quality limits observed

The successful body rewrite added: “This ensures better comfort and support during your runs.” Its quoted source recommends comfortable fit and natural cushioning but does not establish that guarantee/support claim. The mechanical evidence validator accepted the source quote; it is not an entailment validator. The displayed human-review warning is therefore necessary. This interaction confirms real generation/rendering and the source/proposal separation, not that generated content is factually verified or citation-optimized. No prompt/GEPA optimization or upstream parser change was introduced while resolving the merge.

Source completeness, factual truth and rendered webpage visibility remain outside the mechanical source audit. The original HTML/CSS is not patched or rendered as the final page.

## Screenshots

- [Original-source verification](reconciled-source-preview.jpg)
- [Real proposal and evidence](reconciled-draft-preview.jpg)
- [Unavailable-model failure](reconciled-model-error.jpg)
