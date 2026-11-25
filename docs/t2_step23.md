# Step 23 · T1 failure analysis and adaptive verification

This development experiment starts from PR #31 at `8b76872`. Commit `1abd2e6` freezes the new policy, two previously uninspected fictional histories, five random seeds, and the budget grid before verification inference. The original T1 coefficients, normalization and thresholds remain pinned. Prior synthetic evaluation and Step 22 results are diagnostic references and are excluded from policy selection. No Memora data or benchmark answers are used in this milestone. The extractor is unchanged.

## Policies

T2 v1 holds the budget coordinate of the existing T1 score at 1.0, so the ranking component is comparable across an episode. The score acts as a relative verification-utility signal. T2 compares it with an empirical upper-tail quantile from the V3 training vectors, without using helpfulness labels. The fraction of training scores accepted depends on remaining calls divided by the estimated number of opportunities left, which is the predeclared planning horizon minus observed eligible arrivals. The pacing rule uses only the current candidate, elapsed eligible count, and remaining calls. It accepts all opportunities if remaining calls cover the estimated rest and always honors the hard cap. Ties above or on the cutoff are processed in arrival order. A poorly specified horizon can lead to premature spend or underspend.

The nonlearned **H-paced** comparator shares the same pacing rule and training-only reference distribution. Its utility is .55 for an asserted change, .25 for uncertainty, or zero for an explicit correction, plus .15 for temporal conflict and .10 times attributable provenance. It needs no NLI score or learned probabilities. Implicit assertions receive priority because the B2 baseline ordinarily defers them, while explicit corrections can succeed without verification. This is a heuristic hypothesis fixed before observing results.

In the fixed-stream diagnostic, T2 and frozen T1 rank the same stream at the full budget coordinate. Both have the same scores, tie order, and matched calls. Fixed-stream T2 therefore isolates ranking rather than pacing. Closed-loop T2 uses the exogenous plan of ten opportunities per history for pacing and cap construction. B3 and the comparator policies receive the same cap, but may spend differently. The random baseline uses seeds 7, 23, 41, 61 and 83, and deterministic methods report one run per condition. The quoted ranges across seeds describe allocation variability, not uncertainty across histories.

## Reproduction

```powershell
python -m scripts.run_t2_development results/updateset-v3-final/outcomes.jsonl --nli data/models/nli-deberta-v3-xsmall-a150876 --output results/t2-step23
python -m scripts.render_t2_development results/t2-step23/report.json --aggregate docs/t2_step23_aggregate.json --plot docs/t2_step23_budget.svg
python -m pytest -q
```

The fixture evaluator counts exact current slots, historical visibility, deletion absence at two times, and tentative or temporary values incorrectly adopted as current. Missed correct transitions are represented in current-state accuracy. A deletion absence check alone can pass without prior storage, so it is interpreted with the supplied source claims and replay behavior. Runtime totals are shared across policies because verifier calls reuse cached responses. Logical verification attempts count against the cap even on cache hits.

## Why T1 underspent

The frozen T1 cutoff is 0.363898. Recomputing the Step 22 source-span conflicts through the deployed V3 feature builder reproduced zero threshold crossings. The actual Memora prefix had zero eligible conflicts because its chronological source was same-day and the existing candidate gate requires a strictly later effective date than the competing fact's start. Pacing cannot recover absent or ineligible candidates.

| Stream | Scored reference candidates | Mean similarity | Mean contradiction | Mean explicit-date conflict | Mean gap (days) | Mean provenance | Mean budget fraction | Median score | At cutoff | At cutoff if fraction forced to .5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 training | 120 | .765 | .611 | .492 | 50.0 | .717 | .839 | .220 | 29 | 74 |
| V3 calibration | 70 | .778 | .364 | .157 | 47.6 | .686 | .788 | .159 | 17 | 27 |
| V3 independent evaluation, diagnostic | 42 | .810 | .531 | .310 | 55.7 | .607 | .746 | .217 | 11 | 21 |
| Step 22 fictional oracle, diagnostic | 8 | .666 | .769 | .000 | 1.0 | .000 | 1.000 | .122 | 0 | 3 |
| Fresh Step 23 fictional development | 20 | .729 | .794 | .250 | 75.6 | .325 | 1.000 | .146 | 4 | 5 |

The Step 22 diagnostic maximum was 0.308. Its provenance, temporal markers and observation gaps were lower than those in the training stream, even with higher average NLI contradiction. The deployed standardizer uses the frozen means and strictly positive scales. Unit tests confirmed replay passes the real remaining fraction and maintains the cap. No implementation defect was found in these checks.

Holding all other inputs constant, increasing remaining budget from zero to one decreases the full-model logit by **1.901**, using a standardized coefficient of −0.44774 and scale 0.23555. The learned sign discourages a first call and creates a feedback loop because the budget fraction only declines after a call. The counterfactual half budget is a diagnostic intervention. It was not used to change T1's threshold or training. The combination of covariate shift, this learned association and cutoff transfer explains the Step 22 zero-call behavior. The budget-matched curves also show ranking weaknesses across candidates even when the allocation rule guarantees calls.

## Downstream results

Each entry is **actual calls / current-state checks correct** out of 40 checks across two fresh histories. B4 entries are means across five seeds. For 25%, per-history floor rounding produces 4/20 actual fixed calls. The other fixed caps were 0, 2, 10 and 20. B2 stayed at 0 calls and 24/40 in both modes.

| Fixed-stream policy | 0% | 10% | 25% | 50% | 100% |
| --- | --- | --- | --- | --- | --- |
| B3 | 0 / 24 | 2 / 26 | 4 / 28 | 10 / 30 | 20 / 38 |
| B4 | 0 / 24 | 2 / 25.2 | 4 / 27.2 | 10 / 31.2 | 20 / 38 |
| B5 | 0 / 24 | 2 / 24 | 4 / 24 | 10 / 28 | 20 / 38 |
| T1, no-NLI, and T2 | 0 / 24 | 2 / 24 | 4 / 26 | 10 / 34 | 20 / 38 |
| H-paced | 0 / 24 | 2 / 28 | 4 / 32 | 10 / 38 | 20 / 38 |

The fixed rankings of T1 and T2 are identical by design. The seven-feature ablation produced the same pooled counts on these histories. At 50%, B4's fixed seed range was 30–32 correct.

| Closed-loop policy | 0% | 10% | 25% | 50% | 100% |
| --- | --- | --- | --- | --- | --- |
| B3 | 0 / 24 | 2 / 26 | 4 / 28 | 10 / 30 | 20 / 38 |
| B4 | 0 / 24 | 1.6 / 25.2 | 3.2 / 26 | 5.2 / 27.2 | 5.2 / 27.2 |
| B5 | 0 / 24 | 2 / 24 | 4 / 24 | 8 / 24 | 8 / 24 |
| Full T1 | 0 / 24 | 2 / 24 | 4 / 26 | 4 / 26 | 4 / 26 |
| T1 no-NLI | 0 / 24 | 1 / 24 | 2 / 24 | 2 / 24 | 1 / 24 |
| T2 | 0 / 24 | 2 / 24 | 4 / 26 | 10 / 30 | 20 / 38 |
| H-paced | 0 / 24 | 2 / 26 | 4 / 28 | 10 / 36 | 20 / 38 |

T2 filled every cap in these histories with ten opportunities each. It improved current correctness over T1 at larger requested budgets by making more calls. At equal spend, H-paced outperformed T2 at 10%, 25%, and 50%. T2 tied B3 at ten and twenty calls. A reliable learned utility advantage remains unestablished. A variable or misspecified planning horizon, real extraction omissions, and new histories are all untested.

All persistent policies preserved 20/20 historical checks and 4/4 deletion-absence checks, with zero incorrect adoptions of the nine explicitly tentative or temporary alternatives. One confirmed replacement was incorrectly judged historical, explaining the 38/40 ceiling with all candidates verified. That failure is a missed update, distinct from harmful adoption of a proposed value. At 50% the B4 closed-loop seed range was 24–28 correct. These two constructed histories and five random draws support diagnostic comparisons only.

The run made 20 actual Qwen calls and 2,066 cache hits, using 5,491 input and 225 output tokens. Summed provider latency was 22.92 seconds and wall time was 46.73 seconds. All fresh replies passed validation and cost USD 0. Tests passed with 95 discovered tests and 36 subtests, including pinned upstream tests and one third-party AnyIO warning.

- [Budget-performance curves](t2_step23_budget.svg)
- [Frozen protocol](t2_step23_freeze.json) and [complete aggregates and seeds](t2_step23_aggregate.json)
