# Research fidelity penalty — 2026-10-02

GEPA now evaluates mechanically valid proposals even when the fidelity judge finds unsupported or uncertain content. The research objective is:

```text
reward = raw proposed-page mean P1
       − unsupported edit count × unsupported penalty
       − uncertain edit count × uncertain penalty
```

Defaults are **0.05 per unsupported edited block** and **0.02 per uncertain edited block**: 5 and 2 points on the UI's /100 display. Both are tunable between 0 and 1 before a run. They are exploratory weights, not calibrated probabilities or a demonstrated optimal trade-off.

Each edited block receives at most one deduction. A rewriter self-flag of `unsupported_addition` or `missing_evidence` remains a concern even if the judge misses it; unsupported takes precedence over uncertain. Judge reasons and evidence IDs remain in the complete fidelity result, and the reward decomposition lists the deductions. Adding supported edits does not dilute existing deductions. The sum and reward are not clipped; sufficiently poor proposals can have negative rewards. Native GEPA accepts numeric rewards and the integration tests exercise negative baseline rewards.

## Reflection and selection

Reflection receives the complete original source/query/edit/score traces, every judge finding and a `reward_components` object containing raw P1, total penalty, final reward, verdict counts and the rationale/block IDs/deduction for each factual violation. Its trusted instructions explicitly ask it to address those errors while preserving source facts. Repair requests retain the same feedback and complete context budgeting.

GEPA admission, Pareto comparisons and numerical recommendation use the **penalized reward**. Candidate `selection_mean` remains raw mean P1; `selection_reward`, `selection_penalty` and `fidelity_violation_rate` are separately saved and displayed. Per-query score changes remain raw P1. A candidate can therefore rank higher by improving factual fidelity even if raw P1 is lower. Execution-failure rate still cannot worsen for a recommendation; semantic concerns are now tracked separately from execution failures. Numerical recommendation does not certify factual correctness, and promotion remains explicit with existing recorded source-rejection blocks.

A completed proposal with concerns has status `evaluated_with_penalty`. Its complete proposed document is scored; no edits are selectively dropped and the result is not replaced by the original solely because of a factual verdict. All pages remain in their fixed denominators. Abstention keeps the original score and zero factual deduction. Technical/mechanical failures and unavailable fidelity judgments retain their existing original-score fallback and execution-failure accounting; missing judgments do not become successful evaluations.

The run manifest freezes the reward version, exact weights and aggregation policy. Runs without a compatible policy cannot promote through the new coordinator. Existing historical scores are not reinterpreted as penalized rewards, and registry caching remains scoped to a run.

## Scope and review

This change applies to **GEPA research evaluation**. Ordinary Content Studio drafting retains its factual gate. Mechanical output/schema, snapshot/block/evidence identities, protected content and language checks still apply in research. The research-only switch for self-reported factual flags is server-owned and is not an ordinary draft request field. Source-relative fidelity remains a fallible judgment.

The dashboard exposes both weights, raw P1, mean deduction, mean reward and pages with factual concerns. Page details and reflection traces expose the reasons. No full optimization or live provider call was required for this implementation. The v7.1-compatible frozen dataset still needs preparation before another full run.
