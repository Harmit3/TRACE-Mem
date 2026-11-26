# Step 31 verification robustness and budget sensitivity

This post-hoc study reuses the 100 synthetic histories from Step 30. It tests whether the earlier advantage survives changes to the planner's horizon, whether it beats an early-call policy, and how budget use and stale targets affect memory state. No held-out Memora material is used. Step 29 authorization and all previous experiments remain separate.

## Frozen procedure

Origin main at `8ffc040` contains the Step 30 merge. Protocol and runner were frozen at `b6aa346` before Step 31 inference. The runner hashes the frozen report, checks all 100 checkpoints against it, reproduces the published aggregate, and checks common nominal-horizon replay results per history. Scenario contents, gold rules, features, trained weights and thresholds, prompts, and transition rules are unchanged.

The historical cohort has five nominal opportunities per history. The five tested expectations are 2, 3, 5, 7, and 10. Each planner receives an exogenous expectation and can observe only the opportunities and expenditures already seen. The actual cap is unchanged for a history across all horizon conditions. Aggregate allowances are 0, 50, 125, 250, and 500 calls. No unknown-horizon estimator is included. B3, B5, T1 and T1 without NLI have no planning horizon. On the fixed stream, pacing does not operate and the adaptive arms are ranked by their frozen score. B3 represents early-call verification up to the cap and always-verify at 100%.

The added T2-no-NLI diagnostic uses the existing no-NLI artifact, its own sorted score reference over the same training candidates, and the original adaptive pacing function. Comparison to H-paced changes both the score source and NLI availability. Full-versus-reduced and threshold-versus-paced comparisons add evidence about those components, but different realized spending and different score distributions limit causal attribution. The report includes the predeclared difference-in-differences. It describes interaction between the deployed score and pacing variants under the same cap.

Chronological traces log live conflict availability, selected target, remaining calls, verdict, whether the verdict was applied and the post-turn state. Fixed replay can spend a call against an earlier B2 target that is no longer live. Chronological replay instead generates the target from its own state. Turn positions are 1–5 among prepared conflicts. Helpful and harmful verification counts compare the applied outcome with the B2 disposition for the live target against synthetic gold. Harmful adoption counts bad proposed values retained at the relevant dates, whether verified or not.

All arms use the same managed Evidence Index V2 projection from retained temporal memory. Current and historical deletion checks exercise both the store and authorized evidence projection. The reader sees only permitted projected facts. The 30-history reader sample uses history members 0, 3, and 6 in each family at nominal horizon and 50% cap. Each question contributes one correct, incorrect, abstained, invalid, or contradictory outcome. A short answer citing two different slot values is contradictory even if one is correct. Subtotals exercise the deterministic Reader V2 arithmetic contract.

Paired accuracy intervals resample the same ten scenario families 2,000 times with seed 9001. Comparisons at 10%, 25%, 50%, and 100% are reported for every horizon. The intervals are descriptive, unadjusted and based on previously examined histories. Holding a call count fixed does not hold verifier prompt tokens fixed. The aggregate includes both logical input and output tokens per condition and actual fresh-request usage.

## Reproduction

Use the Step 30 checkpoint directory, exact V3 fit outcome release, and pinned local DeBERTa, MiniLM and Ollama Qwen installations. The run validates model and artifact hashes before inference. It reuses Step 30 successes only when the task, URL, body, settings, and pinned model identity match. The old verifier ledger did not store request keys beside usage. Its all-success, one-writer, no-retry response and attempt tables have matching contiguous insertion sequences, which the runner checks before associating token counts. New requests persist usage with the exact request key. The old caches open read-only. Fresh failures with missing usage interrupt the run rather than silently lowering logical costs.

```powershell
python -m scripts.run_step31 results/step30 results/updateset-v3-final/outcomes.jsonl data/models/nli-deberta-v3-xsmall-a150876 results/step31
python -m scripts.summarize_step31 results/step31/report.json docs/step31_artifacts
python -m pytest -q
```

## Results

The original 50% T2 minus H-paced comparisons reproduced exactly across the 100 checkpoints. The difference was +6.7 points in chronological replay (95% interval +0.7 to +12.3) and −11.3 on the fixed stream (−16.3 to −6.3). All common replays matched the Step 30 accuracy, spending, eligibility and deletion counts.

### Planning error and the B3 comparison

Chronological T2 minus B3 in percentage points, with paired 95% family intervals.

| Planning horizon | 10% budget | 25% budget | 50% budget | 100% budget |
| --- | ---: | ---: | ---: | ---: |
| 40% | +0.8 [+0.2, +1.5] | +1.2 [+0.3, +2.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 60% | −1.8 [−3.8, +0.2] | −0.8 [−3.0, +1.2] | +2.3 [+0.5, +4.2] | 0.0 [0.0, 0.0] |
| 100% | −2.5 [−4.7, −0.7] | −0.5 [−2.8, +1.7] | +3.7 [−1.7, +9.0] | 0.0 [0.0, 0.0] |
| 140% | −2.5 [−4.7, −0.7] | −1.5 [−4.2, +1.0] | −4.3 [−10.2, +1.3] | −5.8 [−9.0, −2.8] |
| 200% | −2.8 [−4.8, −1.0] | −2.3 [−4.8, +0.2] | −9.7 [−16.3, −3.2] | −21.7 [−26.3, −16.0] |

At 50%, B3 spent 250 calls and scored 68.7%. The horizon grid shows that T2's edge over H-paced is sensitive to both planning error and realized spending.

| Planning horizon | T2 accuracy and calls | H-paced accuracy and calls | T2-no-NLI accuracy and calls |
| --- | ---: | ---: | ---: |
| 40% | 68.7%, 250 | 68.7%, 250 | 68.7%, 250 |
| 60% | 71.0%, 250 | 72.0%, 250 | 71.0%, 250 |
| 100% | 72.3%, 250 | 65.7%, 250 | 68.2%, 250 |
| 140% | 64.3%, 231 | 43.2%, 55 | 61.7%, 219 |
| 200% | 59.0%, 211 | 37.0%, 0 | 58.0%, 208 |

At 200% horizon, even the 100% allowance left 205 of 500 calls unused by T2. T2 achieved 78.0% against B3's 99.7%. H-paced used 93 calls and scored 48.5%. Its ranking score similarly failed to trigger any calls at 10%, 25%, and 50% when the horizon doubled. Its loss to T2 in those cells mixes policy quality and substantial spending differences. The 40% horizon forced all three adaptive policies to coincide with B3 at the 50% allowance.

### Decision timing and stored state

All compared policies saw 500 live conflicts at nominal horizon and 50% in both modes. Conflict availability therefore cannot explain the reversal on these histories. In the fixed stream, T2 spent 94 calls on stale targets and H-paced spent 70. Only 75 of T2's applied calls were helpful, compared with 99 for H-paced. Among T2's 94 stale calls, 21 still displayed the same fact value as the live target. The replay guard compares complete facts, so equality of the displayed value alone does not authorize application. The tie trace shows how accepting an earlier update can change the later fact's predecessor and make a frozen target stale despite the same value.

In chronological replay neither policy had stale targets. The average call position moved to 2.56 of five for T2 and 3.96 for H-paced. T2 obtained 122 helpful calls, retained 12 harmful proposals, and reached 84.8% historical accuracy. H-paced obtained 85 helpful calls, retained 60 harmful proposals, and reached 65.6% historical accuracy. B3 called earlier at position 1.80, obtained 107 helpful calls, retained 46 harmful proposals, and scored 86.4% historically. No applied verification worsened the immediate decision relative to the same-state B2 disposition in the grid. Unverified proposals could still harm memory.

The T2 win trace shows it skipping an uncertain assertion and spending that call on a subsequent implicit correction after B3 exhausted its budget. In the loss trace it skips a true implicit correction, spends its final call on an archival reference, and then admits a misleading correction through the unverified fallback. These are examples from the prespecified strata. Timing, ranking, and evolving targets change jointly between modes, so the contrast does not estimate the isolated contribution of stale targets.

### Learning, NLI, and pacing

At 50% in nominal closed loop, T2 gained 4.2 points over T2-no-NLI with 250 calls each (95% interval +0.5 to +7.7). Those frozen variants differ in the score and its reference distribution. On the 50% fixed stream the matching learned models tied. The score-by-pacing interaction at nominal 50% was −3.7 points (−9.8 to +1.7), so this comparison does not establish a positive interaction. T2 exceeded T1 by 8.7 points (+3.8 to +12.8), with 250 calls versus 231. Under the same 50% cap T1-no-NLI used 171. The T2 versus T1 result therefore combines pacing and realized spending. All contrasts and logical token costs appear in the aggregate.

### Reader, safety, and resources

On the expanded 30-history sample at 50%, the short-reader results were as follows. There were no contradictory answers. All seven conditions passed 30/30 deterministic subtotal checks.

| Policy | Correct | Incorrect | Abstained | Invalid |
| --- | ---: | ---: | ---: | ---: |
| B3 | 6 | 6 | 10 | 8 |
| B5 | 6 | 8 | 10 | 6 |
| T1 | 7 | 4 | 10 | 9 |
| T1-no-NLI | 7 | 7 | 10 | 6 |
| T2 | 7 | 5 | 9 | 9 |
| H-paced | 12 | 0 | 11 | 7 |
| T2-no-NLI | 7 | 4 | 10 | 9 |

All 26,000 repeated current and historical deletion checks passed in both the temporal store and managed index. They exercise one deletion pattern per synthetic history. No restricted value was passed to the reader. There were zero failed verifier attempts. The 20,450 logical verifier calls all reused exact Step 30 responses and represented 5,877,405 input and 234,847 output tokens across the grid. At nominal 50%, T2 used 72,091 logical input and 2,745 output tokens, B3 used 71,654 and 2,911, and H-paced used 71,486 and 2,933. Logical usage counts repeated operations across conditions.

Fresh inference comprised 39 short-reader requests with 15 invalid outputs. It used 12,931 input and 1,319 output tokens in 76.5 seconds of summed request latency at USD 0. The full local run took 157 seconds. A GPU sample during the run measured 4,109 MiB in use. Ignored run outputs and checkpoint files occupied about 19 MiB, excluding the separate regeneration copy. All 122 tests and 36 subtests passed. The aggregate, traces, and plots regenerated byte-for-byte.

## External evaluation readiness

The frozen architecture is ready for a bounded independent diagnostic with a predeclared horizon strategy and explicit spending and reader failure endpoints. It is premature to use it for a confirmatory external superiority claim. T2 did not consistently beat B3, lost accuracy when it overestimated arrivals, and gave weaker short answers than H-paced on the reused cohort. This study has ten synthetic families and source-authored candidates. An independent evaluation should retain B3 and H-paced as comparators and report end-to-end accuracy and invalid outputs alongside memory correctness. The Memora held-out boundary remains intact.

- [Full grid, costs, and paired intervals](step31_artifacts/aggregate.json)
- [Horizon sensitivity](step31_artifacts/horizon.png)
- [Budget curves](step31_artifacts/budget.png)
- [Paired comparisons](step31_artifacts/paired.png)
- [Chronological and fixed-stream decision traces](step31_artifacts/decision-traces.md)
