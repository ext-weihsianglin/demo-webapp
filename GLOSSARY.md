# Content Studio

Content Studio creates source-grounded rewrite proposals and supports research into improving the prompts that produce them.

## Language

**P1 score**:
A frozen classifier's estimate of the sampled within-host top class among already-cited pages for a target query. It is a reward proxy, not a citation probability or a measure of factual correctness.
_Avoid_: Citation uplift, quality score

**Rewrite explanation**:
A query-specific account of how a completed rewrite proposal changed P1 measurements and the resulting P1 score.
_Avoid_: Optimization recommendation

**Raw P1 feature value**:
A human-readable measurement supplied to P1 for one page and target query, before the model's fitted preprocessing.

**Standardized P1 feature value**:
A raw P1 feature value after the frozen model's fitted imputation and scaling. This is the value multiplied by a standardized model weight.

**Standardized model weight**:
The frozen logistic-regression coefficient applied to a standardized P1 feature value.
_Avoid_: Rewrite importance, causal effect

**Rewrite effect**:
A P1 feature's exact additive contribution to the change in log odds between the original page and a rewrite proposal for one target query.
_Avoid_: Citation uplift, probability-point contribution

**P2 rewriter**:
The system that proposes edits to a source snapshot for its target queries while preserving source evidence and protected content.

**Baseline prompt**:
The versioned, hand-written P2 prompt used as the starting point and comparison reference for prompt optimization. Its existence alone does not establish a measured quality floor.

**Prompt candidate**:
A version of the P2 editorial instructions evaluated during prompt optimization.

**Research run**:
A bounded experiment that evaluates prompt candidates and records their prompt changes, rewrite outcomes, and P1 scores.

**Score component**:
A named measure of a rewrite outcome that contributes feedback to prompt optimization. P1 is the initial component; components describe separate aspects of performance.

**Optimization dataset**:
A frozen collection of source snapshots and their target query sets used to learn a reusable P2 prompt. Its examples are exposed to prompt search, even when originally held out for extraction evaluation.

**Final evaluation set**:
A separate collection of examples kept outside prompt search to assess the selected prompt's generalization.

**Prompt registry**:
A collection of versioned prompts that distinguishes each rewriter model's baseline, experimental candidates and selected prompts.

**Reflection split**:
Optimization examples whose rewrite outcomes and diagnostics guide proposed prompt changes.

**Selection split**:
A fixed set of optimization examples used to compare prompt candidates and choose which to retain. It participates in prompt search and is distinct from the final evaluation set.
