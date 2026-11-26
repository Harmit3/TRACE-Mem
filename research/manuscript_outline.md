# Provisional manuscript outline

Scope is the independent TRACE-Mem research manuscript. The CS9548 assessed report and presentation follow their separate instructor rules.

## Candidate titles

1. When Verification Helps Temporal Memory: A Budget-Matched Replay Study
2. The Cost of Checking Memory Writes: Target Staleness and Horizon Error in LLM Agents
3. From Fixed Streams to Live State: Limits of Learned Verification for Long-Horizon Memory

## Outline

1. **Abstract.** State the proposed question, the same-budget reversal, planning sensitivity, and external completion limit.
2. **Introduction.** Explain why a correct decision on one memory write can change a later candidate and why scoring a fixed stream is insufficient to characterize online allocation.
3. **Related work.** Compare temporal memory and lifecycle work with budgeted inference and verification. Position trajectory evaluation as the contribution, with no priority claim.
4. **Methodology.** Specify observed and effective times, the exact conflict guard, B3 and H-paced, logistic T1 and adaptive T2, call accounting, and separate authorization and reading paths.
5. **Experimental design.** Audit synthetic help labels, training and calibration split boundaries, fixed and live replay, matched calls, family bootstrap, and the post-hoc reuse of the 100 histories. Define external completion and adapted judging.
6. **Results.** Show the budget reversal and horizon sensitivity. Report B3 and H-paced with confidence intervals, the NLI diagnostics, QA failures, negative promotion gates and human-assisted access separately.
7. **Discussion.** Trace target staleness, arrival timing, horizon underspend and state-to-answer attrition. State which counterfactuals the design cannot isolate.
8. **Limitations.** Shared synthetic update archetypes, underestimated clustering, adaptation to the examined cohort, sparse helpfulness positives, missing external paired support and judge disagreement.
9. **Ethics and reproducibility.** Disclose AI assistance, human-approved annotation provenance and access controls. Describe the sanitized synthetic reproduction package and separate local restricted artifacts.
10. **Conclusion.** Characterize when pacing helped and when the simple baseline was preferable. Avoid claims that the current evidence does not support.

[Results and sources](tables/results.md) · [Publication feasibility](../docs/publication_readiness.md)
