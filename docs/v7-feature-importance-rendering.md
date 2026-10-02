# P1 v7.1 feature values, model weights, and rewrite effects

Research date: 2026-10-02. This note traces the upstream implementation and proposes a display contract for Content Studio. It uses source code, frozen artifacts, generated reports, and GitHub PR metadata as primary sources.

## Agreed delivery scope

The explanation work will ship on the Markdownify-consistent v7.1 scorer requested in [demo-webapp issue #10](https://github.com/ext-weihsianglin/demo-webapp/issues/10), not on the mixed-parser v7 serving adaptation. V7.1 is the foundation; explanation arithmetic and UI follow only after original/proposed scoring uses its canonical adapter and verified artifact.

The primary product job is post-rewrite visibility. For every target query, Content Studio will lead with the exact paired rewrite effect `β(z_after - z_before)`, then offer clean secondary disclosures for the original and rewritten pages' absolute `βz` contributions. Raw values remain visible as `x`; `z` always means the fitted imputed and standardized value, and `β` means the learned coefficient applied to `z`.

Per-query explanations are authoritative. A cross-query view may summarize signed mean delta log odds, maximum absolute effect and positive/negative query counts, but it must retain the individual query cells and must not present mean probability as one additive decomposition.

GEPA traces and reflection feedback are outside this delivery. [Issue #11](https://github.com/ext-weihsianglin/demo-webapp/issues/11) records the staged follow-up: persist versioned explanations first, audit proxy-gaming risk on reflection-only data, then explicitly decide whether a conservative family-level projection may enter reflection. Raw model weights must not become prompt-optimization instructions.

### Implementation sequence

1. Pin the merged upstream v7.1 revision and package its canonical `markdownify_context` and `predict_markdownify` modules with provenance.
2. Install and checksum the v7.1 artifact; reject legacy v7, wrong feature order and feature-code drift without fallback.
3. Route original and proposed scoring through the canonical adapter, preserving source inventory and rebuilding changed document derivatives and semantic inputs.
4. Version score/run identities with `lr-semantic-v7.1` and remove the legacy-context warning only after parity and invalidation checks pass. Historical v7 artifacts retain their labels.
5. Capture raw and transformed feature rows at the scoring seam and verify exact logit/probability accounting.
6. Add the query-level paired waterfall, raw-value table, absolute before/after disclosures and cross-query summary.

The migration remains a preprocessing-consistency correction. V7.1 validation AUC 0.66501 versus v7 0.66443 is a small, uncertain development difference; it is not citation-uplift evidence or a reason to retune the scorer.

## The key correction

The supplied [`fixed_prompt/report.html`](/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/.worktrees/deck-prototype-trad-ml-scorers/trad_ml_scorer/interpretation/fixed_prompt/report.html) is **not a v7 feature-importance report**. Its source report identifies the model as frozen v5 retained by v6, and says it performed no refit or test evaluation ([local source, lines 1–15](/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/.worktrees/deck-prototype-trad-ml-scorers/trad_ml_scorer/interpretation/fixed_prompt/report.md)). The project handoff repeats that distinction at `PROJECT_CONTEXT.md:380-399`.

V7 deliberately put page-edit interpretation on hold. It compared predictive performance for four logistic-regression designs, selected `semantic_context` using training host-grouped cross-validation, and generated only model-comparison and paired-validation charts. The chosen model has ten original-space embedding-similarity inputs plus 45 prompt/document context inputs ([PR #14](https://github.com/ext-weihsianglin/content-optimization-system/pull/14), [training implementation](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/semantic_experiment.py#L29-L105), [report builder](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/build_semantic_report.py#L13-L35)). The v7 report explicitly says the work measured predictive performance and withheld page-edit recommendations ([report](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/v7/report.md#L1-L7)).

V7 was merged through [PR #14](https://github.com/ext-weihsianglin/content-optimization-system/pull/14) into the scorer integration branch and then through [PR #13](https://github.com/ext-weihsianglin/content-optimization-system/pull/13) into `main`. Its validation AUC was 0.66443 versus 0.67435 for v5, with paired delta -0.00992 and a 95% host-bootstrap interval spanning zero. It was adopted as a development direction, not demonstrated as superior and not evaluated on test in that round ([PR #14](https://github.com/ext-weihsianglin/content-optimization-system/pull/14), [v7 decision](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/v7/decision.md)).

## What the earlier analysis actually computed

The upstream pipeline is median imputation with missing-value indicators, followed by `StandardScaler`, followed by logistic regression ([`train_lr.py:29-31`](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/train_lr.py#L29-L31)). That makes three different ideas easy to confuse:

Use `x` for the raw feature value, `z` for that value after the fitted imputer and standardizer, and `β` for the learned logistic-regression coefficient applied to `z`. Thus `βz` is a feature's contribution to one example's logit, while `β(z_after - z_before)` is its exact contribution to a rewrite's logit change. Missingness indicators are additional transformed terms with their own `z` and `β`.

| Quantity | Scope | Meaning | Suitable rewrite display? |
| --- | --- | --- | --- |
| Standardized coefficient `βⱼ` | Global model | Change in log odds for one training standard deviation of transformed feature `j`, holding the other model inputs fixed | Secondary context only |
| Validation permutation AUC drop | Dataset/global | Loss of validation ranking performance after shuffling a feature | Separate audit view only |
| Row contribution `βⱼzⱼ` | One query/page pair | A transformed feature's additive term in that row's logit | Useful for explaining one score, with baseline caveats |
| Paired delta contribution `βⱼ(zⱼ,after − zⱼ,before)` | One fixed-query rewrite | Exact additive share of the rewrite's logit change | Primary rewrite explanation |
| Raw feature delta `xⱼ,after − xⱼ,before` | One fixed-query rewrite | Change in an understandable input unit, such as cosine similarity or `log1p` count | Primary companion to delta contribution |

### Global importance in v5/v6

The v5 report extracted transformed feature names from the fitted imputer, zipped them to the logistic-regression coefficients, and sorted by absolute coefficient. Because the names come after imputation, missingness indicators appear as their own terms ([`build_evidence_report.py:18-22`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/build_evidence_report.py#L18-L22)). The report labeled this as log odds per training standard deviation, not an edit effect ([same file, lines 30–36](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/build_evidence_report.py#L30-L36)).

The separate permutation audit shuffled each selected raw feature on validation data 20 times with seed 137 and measured the ROC-AUC drop. It also shuffled all members of a feature family together, preserving their row alignment within the family ([`audit_frontier.py:27-53`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/audit_frontier.py#L27-L53)). The report warns that correlation can dilute individual permutation importance and that one-feature response curves can create impossible combinations ([`build_evidence_report.py:61-64`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/build_evidence_report.py#L61-L64)).

V7 did **not** produce an equivalent coefficient JSON, permutation audit, or feature-importance section. Its checked-in artifacts contain candidate results and validation predictions, while the fitted model and matrices remained ignored local artifacts ([v7 report, lines 95–106](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/v7/report.md#L95-L106)). Content Studio later extracted standardized v7 coefficients from the hash-verified served model for a diagnostic steering note; it labels them as slopes rather than permutation importance, causal effects, or editing guarantees ([`docs/gepa-p1-steering.md:3-21`](gepa-p1-steering.md), [`verification/gepa-v7-steering-evidence-v1.json`](../verification/gepa-v7-steering-evidence-v1.json)).

### Exact paired attribution in the fixed-prompt report

The reusable part is much stronger than a global importance chart. For a fixed query and URL, the earlier analysis reparsed the edited HTML, recomputed the complete feature vector, transformed both vectors with the fitted imputer and scaler, and calculated:

```text
logit(x) = intercept + Σ βⱼ zⱼ(x)

Δlogit = logit(after) − logit(before)
         = Σ βⱼ [zⱼ(after) − zⱼ(before)]
```

The implementation asserts that the feature delta contributions sum to the model's `decision_function` difference, then returns the before/after probabilities and every transformed term ([`fixed_prompt_edits.py:10-26`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/fixed_prompt_edits.py#L10-L26)). The analysis also checked original raw features against the frozen cache before applying edits, retained missing-indicator effects, and stored changed contributions plus grouped logit deltas ([`analyze_fixed_prompt.py:61-103`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/analyze_fixed_prompt.py#L61-L103)).

The local report renders the changed terms in descending absolute delta-logit magnitude, shows the top 12, and combines the rest into “Other changed features” ([`build_fixed_prompt_report.py:46-55`](https://github.com/ext-weihsianglin/content-optimization-system/blob/864e6634a54ad80ac1657129e994b18c3a1f7eff/trad_ml_scorer/build_fixed_prompt_report.py#L46-L55)). Its example moves the score from 0.7779 to 0.7054 and attributes the exact -0.38034 logit change across six changed measurements ([local report, lines 31–41](/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/.worktrees/deck-prototype-trad-ml-scorers/trad_ml_scorer/interpretation/fixed_prompt/report.md)). The report is explicit that coefficients describe slopes, permutation describes across-record predictive reliance, and neither is an edit's causal effect ([local report, lines 43–65](/Users/ext-weihsiang.lin/Documents/profound/content-optimization-system/.worktrees/deck-prototype-trad-ml-scorers/trad_ml_scorer/interpretation/fixed_prompt/report.md)).

This exact contrast transfers directly to v7.1 because v7.1 keeps the same fitted pipeline structure and feature order while retraining the context inputs from Markdownify documents. Its 55 raw inputs expand to 62 transformed terms because the imputer adds seven missingness indicators. The contrast must include all 62 terms even when the UI groups an indicator with its parent feature.

## V7.1 feature values

The ten semantic inputs are original-space cosine similarities for title, best H1, outline, pooled page, normalized path, and five summaries over section-chunk similarities. Empty section sets remain missing; no PCA coordinates enter the scorer ([`semantic_features.py:1-39`](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/semantic_features.py#L1-L39)). A larger cosine means greater embedding similarity; it does not by itself mean better content or a higher real citation likelihood.

The remaining 45 raw inputs are prompt-only or document-only context features inherited from v5. The selection was originally made by filtering the v5 model's feature names to the `prompt` and `doc` dependency groups ([`semantic_experiment.py:44-53`](https://github.com/ext-weihsianglin/content-optimization-system/blob/5db69cc19a0ab0a3131be141e2f919464f6211c5/trad_ml_scorer/semantic_experiment.py#L44-L53)). V7.1 retrains those context inputs from Markdownify documents and exposes the canonical `trad_ml_scorer.predict_markdownify` adapter. Content Studio must serve that adapter under `markdownify-v7.1`, so the former mixed-parser warning and upstream issue #15 no longer belong in current score or explanation responses.

For the current rewrite boundary, several terms should normally have exactly zero paired delta:

- prompt-only inputs, because the ordered query is fixed;
- path and path similarity, because the source URL is fixed;
- source title and title similarity, because source metadata is immutable in the current proposal flow;
- source/parser diagnostics that the rewrite is not allowed to manipulate.

H1, outline, page, section, length, and composition features can change when an editable body block changes. The display should derive this from the two actual vectors and show unexpected changes as diagnostics; it should not hard-code them away.

## Current Content Studio seam

The backend already does nearly all expensive work. `score_document` creates one raw 55-feature row per query, builds the ordered matrix, and calls the frozen pipeline, but returns only probabilities and aggregates ([`backend/app/scoring.py:58-83`](../backend/app/scoring.py)). `compare_scores` verifies query order and emits before, after, and probability delta, but has no access to either feature matrix ([`backend/app/scoring.py:91-102`](../backend/app/scoring.py)). The frontend therefore has only score-level fields and renders the current four-column query table ([`frontend/app/p1-scores.tsx:3-42`](../frontend/app/p1-scores.tsx)).

An existing offline diagnostic already proves the linear attribution calculation against v7. It transforms the before/after matrices with `pipeline[:-1]`, multiplies their difference by `pipeline[-1].coef_[0]`, and asserts the result sums to the decision-function delta within `1e-12` ([`backend/scripts/explain_gepa_benchmark.py:44-98`](../backend/scripts/explain_gepa_benchmark.py)). Reuse that arithmetic against the hash-verified v7.1 bundle and its canonical feature rows.

## Recommended product design

### Primary view: “Why this rewrite changed P1”

Keep the current per-query score table. Make each query row expandable after a rewrite. Its first expanded view should be a horizontal waterfall or diverging bar chart of paired delta-logit contributions:

- sort by `abs(delta_log_odds)`;
- show positive and negative effects around zero;
- show the top 10–12 transformed terms and aggregate the rest into “Other changed features”;
- label missing-state transitions explicitly;
- show `Σ feature effects = Δ log odds` and, separately, the observed probability change;
- keep zero-delta fixed features collapsed under “Unchanged inputs.”

Probability is nonlinear, so individual features should not be assigned additive “probability point contributions.” Only the total logit delta should be converted through the sigmoid to reproduce the before/after score. This preserves the exact accounting used upstream.

The paired rewrite view is primary. Two secondary disclosures, “Explain original score” and “Explain rewritten score,” show the absolute `βz` contributions for each side. Their reference point is the fitted model's standardized baseline, so they explain model arithmetic rather than causal importance. Keep these absolute views visually subordinate to the rewrite effect.

Below the chart, a feature table should expose both values and model behavior:

| Feature | Raw before | Raw after | Raw delta | Standardized coefficient | Before logit contribution | After logit contribution | Delta log odds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

Use human labels and units, while retaining the canonical feature name in a tooltip or details row. Represent a missing raw input as `null` plus a missing flag; never serialize `NaN`. Pair each generated `missingindicator_*` term with its parent raw feature in the UI, while keeping it as a separate term in the additive check.

### Multiple target queries

Do not decompose the mean probability as though it were a linear model output. It is a mean of nonlinear sigmoid outputs and has no single exact additive feature breakdown.

For multiple queries:

1. Default to the query with the largest regression, or the largest absolute score change when there is no regression.
2. Add a feature-by-query heatmap of delta-logit contributions. Rows are features; columns are queries; color shows direction and magnitude.
3. Offer compact summaries such as mean delta log odds, maximum absolute delta, and positive/negative query counts. Preserve the individual cells so cancellation remains visible.
4. Keep the existing mean-score and regression counts above the explanation.

This is more faithful than a single averaged waterfall and directly supports the app's equal-weight objective plus per-query regression review.

### Secondary view: “How the model is weighted”

Put global coefficients in a separate, clearly labeled disclosure. Use diverging bars sorted by absolute standardized coefficient and group them into:

- semantic query–document similarity;
- prompt context;
- document structure/content context;
- fixed URL/metadata;
- parser/source diagnostics;
- missingness indicators.

Call these **standardized model weights**, not rewrite importance. Mark whether each input is editable, fixed, or diagnostic under the current rewrite boundary. This prevents a large path, prompt, or diagnostic coefficient from looking like an optimization instruction.

Do not label a coefficient chart “permutation importance.” Neither v7 nor the v7.1 migration supplies a frozen permutation artifact. If dataset-level permutation is desired later, compute it as a separate upstream development audit on the fixed validation split, pin the model/data hashes, include repeated-shuffle spread, and keep it visually separate from the per-rewrite receipt. A family-level permutation is preferable as a companion because many page and section similarities are correlated.

## Suggested response contract

Avoid duplicating model-global metadata inside every row. One possible shape is:

```json
{
  "explanation": {
    "version": "p1-linear-explanation-v1",
    "model_sha256": "d1c4b25480a1579239b8fd9c8bfa7d3beac11bfa2ec591d8540941b6f89493cc",
    "feature_version": "lr-semantic-v7.1",
    "serving_policy": "markdownify-v7.1",
    "space": "log_odds",
    "global_terms": [
      {
        "term": "page_similarity",
        "raw_feature": "page_similarity",
        "coefficient": 0.043287,
        "family": "semantic",
        "rewrite_role": "editable"
      }
    ],
    "per_query": [
      {
        "query_index": 0,
        "before_logit": 0.12,
        "after_logit": 0.15,
        "delta_logit": 0.03,
        "terms": [
          {
            "term": "page_similarity",
            "raw_before": 0.62,
            "raw_after": 0.64,
            "raw_delta": 0.02,
            "standardized_before": 0.31,
            "standardized_after": 0.37,
            "contribution_before": 0.013,
            "contribution_after": 0.016,
            "delta_log_odds": 0.003
          }
        ]
      }
    ]
  }
}
```

The actual numbers above are illustrative. The contract should also carry imputed values and `raw_missing_before` / `raw_missing_after` when either side is missing. The intercept belongs once in global metadata and is unchanged in a paired comparison.

The clean backend design is to factor matrix construction and explanation out of `score_document` into a private result object used by both scoring and comparison. Public analysis responses can omit row-level details until a draft comparison exists, reducing payload size. Draft scoring can then pass both internal results to `compare_scores`, which emits the paired explanation. The frozen model, feature order, source inventory, and embedding calls remain unchanged.

## Verification requirements

The implementation should fail closed if any of these invariants do not hold:

1. Raw rows have the frozen 55 names in exact bundle order.
2. Transformed term names and coefficient length match; currently this is 62 terms.
3. For each side, `intercept + Σ contribution` equals `decision_function` within a tight numerical tolerance.
4. For each query, `Σ delta_log_odds` equals `after_logit − before_logit`.
5. `sigmoid(before_logit)` and `sigmoid(after_logit)` reproduce the returned probabilities.
6. Before and after explanations have the same model hash, feature version, serving policy, ordered queries, and transformed term names.
7. Missing-value transitions include their indicator contribution and never become an implicit zero.
8. Source inventory and immutable metadata retain their existing identities; explanations use the proposed document only for fields the scorer already recomputes.
9. Cache misses, provider failures, or model validation failures keep the explanation unavailable alongside the score. No partial explanation or mock fallback is returned.

## Recommended first slice

Migrate scoring to the canonical v7.1 adapter first, then implement exact paired attribution in the draft response and an expandable per-query waterfall plus raw-value table. Include clean secondary disclosures for the original and rewritten pages' absolute `βz` contributions. This needs no new model calls beyond the before/after scoring already performed. Treat the global coefficient chart as a secondary follow-up using the same hash-verified bundle. Defer dataset-level permutation importance until it exists as a separately versioned development artifact.

Persisting these explanations in GEPA traces and selectively exposing family-level summaries to reflection is intentionally deferred. It needs an explicit versioned feedback contract and an audit for proxy gaming before reflection consumes it; raw model weights should not be supplied as optimization instructions.

That first slice answers the user's practical question—what measurements changed and how the frozen LR converted those changes into this score movement—while preserving the boundary between model behavior, dataset-level reliance, and real-world editorial value.
