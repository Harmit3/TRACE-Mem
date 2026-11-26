# External reviewer guide

**Research question.** Under a common verifier-call cap, when does an adaptive learned policy improve temporal memory accuracy relative to early-call or heuristic allocation, and how sensitive is the comparison to the replay mode and forecast horizon?

The saved experiments have one cohort of 100 histories, ten per synthetic scenario family. Six exact slot checks per history measure five retrospective as-of states and the final state. Historical accuracy uses five checks. Checks, seeds, policies and repeated deletion checks do not add independent families. Step 31 reused Step 30 histories. Cross-domain authored update patterns still overlap.

- **B0/B1/B2** use no verifier and represent no memory, append-only memory and temporal rules, respectively. **B3** spends on the earliest eligible conflicts in chronological replay. **B4** is seeded random verification. **B5** prioritizes uncertainty. **T1** uses a frozen logistic threshold. **T2** allocates progressively using the frozen learned score. **H-paced** applies the same pacing mechanism to a heuristic. No-NLI arms omit contradiction features and use the frozen ablation artifact.
- **Budgets** are 0%, 10%, 25%, 50% and 100% of five nominal reference opportunities per history. Fractional caps are rotated across histories. The fixed stream matches calls against B2 targets even when those targets become stale. Closed loop checks the policy's own live state and can underspend. Step 31 supplied horizons of two, three, five, seven and ten opportunities in advance.
- **Intervals** average Step 30 B4 seeds within history, take paired within-history differences, average them within family, and sample the ten family means with replacement 2,000 times with seed 9001. Percentile intervals are descriptive and unadjusted. Conditions at unequal realized spending compare fixed ceilings rather than equal calls.

## Verification steps

1. Use a clean directory containing only this release and a CPython runtime. Follow the [README](README.md) to verify checksums, derive the results, and optionally render the plots.
2. In `reproduced.json`, check the Step 30 50% T2 minus H-paced interval in each mode. Expected differences are about -11.3 points on the fixed stream and +6.7 points in closed loop. In Step 31 check T2 against B3 at the nominal and doubled horizons. Under the 50% cap the latter contrast is about -9.7 points, with T2 spending 211 and B3 250.
3. Check the recorded historical, harmful adoption, staleness and deletion counts as diagnostics. Inspect the comparison curves and spending separately. Save the environment and any discrepancy in the [review record](independent-review-checklist.md).

Offline verification establishes numerical consistency, grouping, call accounting and chart provenance. It cannot establish label validity, fresh-inference reproducibility, autonomous deletion, QA transfer, or external superiority. A separately recruited reviewer and genuinely new families are still needed for independent scientific validation. The release does not contain transcripts or any human-review labels.
