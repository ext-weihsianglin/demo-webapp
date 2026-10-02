# Content Studio

Content Studio creates source-grounded rewrite proposals and supports research into improving the prompts that produce them.

## Language

**P1 score**:
A frozen classifier's estimate of the sampled within-host top class among already-cited pages for a target query. It is a reward proxy, not a citation probability or a measure of factual correctness.
_Avoid_: Citation uplift, quality score

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
