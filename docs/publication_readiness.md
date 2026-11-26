# Publication feasibility

**A bounded negative-results or methods manuscript is plausible. A general superiority submission is premature.** TRACE-Mem is an executable prototype with informative counterexamples for matched-budget evaluation. It has no replicated end-to-end verification advantage on an external benchmark.

## Proposed primary question

Under a fixed ceiling on extra verifier calls, when does learned allocation improve exact temporal state under chronological replay, relative to early-call and heuristic allocation, and how do target staleness and planning error change that comparison?

This is the proposed framing for a future manuscript and independent study. Step 30 predeclared its own primary comparisons. Step 31 froze a robustness protocol for already examined histories. This synthesis assigns neither a retrospective preregistration nor confirmatory status.

## Literature and plausible contribution

| Primary work | Relevant relationship |
| --- | --- |
| Memora | FAMA evaluates remembering while penalizing retrieval or reliance on invalidated information. TRACE-Mem used pinned arithmetic with a smaller local judge on a development persona, which cannot support a leaderboard comparison. [Paper](https://aclanthology.org/2026.findings-acl.1337/) · [Code](https://github.com/geniesinc/Memora) |
| LongMemEval | The indexing–retrieval–reading decomposition explains why a verifier-only claim needs evidence that both upstream extraction and downstream reading function. [Paper](https://arxiv.org/abs/2410.10813) · [Code](https://github.com/xiaowu0162/LongMemEval) |
| Mem0 | Dynamic extraction, consolidation, updates and retrieval, with a graph variant. TRACE-Mem's scientific contrast is explicit allocation of extra checks at competing writes. An external head-to-head comparison has not been run. [Paper](https://arxiv.org/abs/2504.19413) · [Code](https://github.com/mem0ai/mem0) |
| A-MEM | Structured notes and evolving links emphasize organization. TRACE-Mem tests temporal state transitions under verification budgets rather than learning a linking scheme. [Paper](https://arxiv.org/abs/2502.12110) · [Code](https://github.com/WujiangXu/A-mem) |
| Zep / Graphiti | Temporal graph validity and invalidation anticipate storing competing facts and letting users query their histories. Temporal representation is established prior work. [Paper](https://arxiv.org/abs/2501.13956) · [Code](https://github.com/getzep/graphiti) |
| MemFSM / ValidMem | Closest lifecycle comparison. Distinguishes validity from visibility and evaluates supersession, expiry, and current versus historical intent. TRACE-Mem cannot claim that separation as novelty. Test a policy layer with the same inputs and budgets before alleging a comparative advantage. [Paper](https://aclanthology.org/2026.emnlp-main.260/) |
| AgeMem | Learns memory operations, including controlled forgetting, with reinforcement learning. TRACE-Mem leaves the lifecycle rules fixed and fits an escalation score, then paces calls online. [Paper](https://aclanthology.org/2026.acl-long.981/) |
| Chain-of-Verification | Adds checks to drafted answers. TRACE-Mem spends an explicit allowance checking competing writes to persistent state, where an early change can affect later targets. [Paper](https://aclanthology.org/2024.findings-acl.212/) |
| FrugalGPT and Adaptive-Consistency | Adapt model or sample expenditure to predicted utility or agreement. These establish cost-aware and uncertainty-aware allocation. A shift from per-question cost to sequential, state-dependent candidate arrivals is the empirical distinction of interest. [FrugalGPT](https://arxiv.org/abs/2305.05176) · [Adaptive-Consistency](https://arxiv.org/abs/2305.11860) |
| FlexA-Mem | Recent budget-adaptive memory allocates tokens to timeline detail at read time. TRACE-Mem allocates additional verifier calls during writes. The word budget alone is not a distinction. [Paper](https://arxiv.org/abs/2610.33274) · [Code](https://github.com/WujiangXu/Flex-Amem) |
| STALE / CUPMem and TOKI | STALE targets implicit conflict and CUPMem includes write-time state revision. TOKI formalizes contradictions as bitemporal writes with provenance and keyed adjudication for replay. The former motivates an independent conflict suite and the latter makes general claims of novel replay or write-time verification too broad. [STALE](https://arxiv.org/abs/2605.06527) · [TOKI](https://arxiv.org/abs/2606.06240) |

The defensible contribution is an empirical comparison that exposes rank reversals and underspending when the same learned scores are evaluated under different target semantics or horizon assumptions. It combines frozen state transitions, measured budget use, paired family-level analysis, and a documented failure path from memory to QA. This targeted primary-source review is neither exhaustive nor a priority claim. Citation sources and identifiers are in [references.bib](../research/references.bib).

## Priorities before submission

1. Give the [sanitized Step 30/31 package](../reproducibility/README.md) to a researcher outside the implementation team for independent offline verification. Internal isolated reproduction is complete. No external reviewer has signed off.
2. Review and approve the [Step 36 protocol and analysis plan](../research/validation_protocol_v2.md) using the [Step 37 onboarding packet](../research/reviewer_onboarding.md). The executable bindings and causal estimator have engineering coverage. Independent researchers still need to verify disjoint mechanisms and gold. The actual cohort, model-adapter freeze and selected stage require approval before execution.
3. Have independent reviewers adjudicate the existing six LongMemEval worksheet cases and an explicitly sampled set of deletion/resolution and helpfulness edge cases if making claims about those capabilities. Report disagreement and adjudication, and preserve original labels.
4. If claiming external or end-to-end benefit, first establish ingestion and reader completion on a predeclared, answer-blind evaluation population. Then test publicly documented comparators under equal access and cost controls. Preserve failure-inclusive results and compare with the closest temporal lifecycle system. No such run was performed here.

## Authorship, permission, and scope

The outline and abstract are for independent research. The CS9548 authorization is student-confirmed verbal permission for coding and development. It does not authorize generation of assessed report prose or slides. Record AI assistance in implementation, authored fixtures, analysis, figure generation and drafting, and have the research authors verify every claim and reference before submitting. Step 29 decisions were explicitly human-approved with AI assistance. Neither proposed annotations nor the pending LongMemEval worksheet constitute independently authored human ground truth. [Authorization and contribution record](ethics_and_permissions.md)
