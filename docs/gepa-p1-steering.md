# P1-aware GEPA steering — 2026-10-02

The user supplied three local reports: `trad_ml_scorer/interpretation/fixed_prompt/report.html`, `trad_ml_scorer/v6/report.html` and `trad_ml_scorer/v7/report.html` in the `deck-prototype-trad-ml-scorers` research worktree. [Evidence](../verification/gepa-v7-steering-evidence-v1.json) preserves their absolute paths, content hashes and coefficients from the hash-verified model actually served by this webapp.

The fixed-prompt and v6 reports describe v5, retained by v6 after all new feature variants failed the predeclared development gates. Their lexical query–document features are absent from the served v7 model. V7 uses ten original-space embedding similarities plus 45 context features. Its report describes a prototype, not a validated improvement over v5: validation AUC is 0.6644 versus v5's 0.6744. The webapp uses v7 at the user's direction; neither these reports nor P1 scores establish citation uplift.

## What can change under the current harness

These are fitted coefficients per training standard deviation, not permutation importance, causal effects or guarantees that an edit increases score. All correlated inputs and missing indicators must be recomputed together.

| Served v7 signal | Coefficient | Permitted editorial use |
| --- | ---: | --- |
| Path similarity | +0.12867 | URL is fixed; no optimization action. |
| Title similarity | +0.10358 | Source title metadata is fixed; no optimization action. |
| H1 similarity | +0.04768 | Clarify an existing editable body H1's supported subject, preserving its level and scope. |
| Page similarity | +0.04329 | Make source-supported answers and relationships explicit in relevant body paragraphs. |
| Outline similarity | +0.03311 | Clarify existing editable body headings to accurately describe their sections. |
| Section upper quartile / maximum / top-three mean | +0.03045 / +0.02860 / +0.02149 | Improve coherent, already relevant paragraphs within their original evidence chunks. |
| Heading/list counts | +0.06863 / +0.04865 | Counts and structure are fixed; do not insert headings or lists. |

Many larger coefficients concern fixed query or URL properties. Negative fitted weights, including lower-quartile section similarity and vocabulary ratios, are not instructions to remove relevance, facts or vocabulary. Do not target parser warnings, sparse-body flags, source format, metadata or length ratios. H1 editing is available only when the source block passes the existing editable-body protections. Ordinary generation still requires at least one useful paragraph edit; headings alone cannot pass.

## Reflection instruction change

`backend/app/gepa/adapter.py` now tells the reflection model which served-v7 signals are plausible editing hypotheses. It encourages policies that clarify up to two existing body headings and one to three related paragraphs, with limits across the entire page. Policies should make existing subjects, relationships and answers explicit, rather than merely swap synonyms. It removes the previous blanket advice to leave all headings unchanged. The model must preserve attribution, qualifications, language, heading levels and block order, and use only original-chunk factual support. It must judge hypotheses by actual mean P1 and every query regression.

Only reflection guidance changes. Baseline v7 bytes, the mutable-component size limit, fixed rewriter instructions, parser/scorer, fidelity profile, test separation and promotion rules remain unchanged. The c536094b trial kept its original frozen reflection instructions and was cooperatively stopped at the user’s request. After an idle backend reload, fresh run 6082eccf binds the new reflection hash; all other evaluation fields remain unchanged. See the [startup evidence](../verification/gepa-v7-steering-trial-v1.json).

## Why the reports do not justify easy large gains

The fixed-query report's coherent edits had small and variable average effects: moving a relevant paragraph earlier averaged +0.11 percentage points; splitting a paragraph averaged +0.02; replacing a title with its existing H1 averaged −0.93. Those edits are not all permitted here. V6's title manipulation stress inflated scores by +0.2300 on average for v5, but that is a robustness failure, not a legitimate editorial target. Repeated query prose also defeated the corroboration variant. These findings support keeping title/URL identity and anti-stuffing controls intact.

Our [three fixed answer-first controls](../verification/gepa-answer-first-benchmark-v1.json) passed the v4 judge but averaged only +0.000023 P1. The [offline feature explanation](../verification/gepa-answer-first-feature-explanation-v1.json) reproduces all query predictions within 1e-12 using cached vectors and independently verifies that feature contributions sum to each logit change. Between 38 and 42 of 55 raw inputs remained unchanged. The small scores are reproduced by the actual model; this check does not prove an achievable ceiling.

Validation after the guidance edit: 162 backend tests passed, two opt-in checks skipped. A [live reflection-only smoke](../verification/gepa-v7-steering-reflection-smoke-v1.json) uses saved reflection outcomes, no rewrite or held-out calls, and a separate diagnostic registry; it verifies request composition without claiming improved drafts. Stronger P1 gains, adherence to the generated strategy, safe promotion and fixed-pair held-out superiority still require a fresh real GEPA trial and source review.
