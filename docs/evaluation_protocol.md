# Pilot evaluation protocol draft

## Endpoint and paired comparisons

Use the official Memora FAMA implementation pinned in the [dataset manifest](dataset_manifest.json). The proposed primary pilot endpoint is the paired difference in mean per-question FAMA between T1 and B4 at the 25% target. Report the realized call count, eligible candidates, and question denominator alongside each estimate. Report B5 and the other predeclared budgets as secondary comparisons. Freeze the target-count rule, method configurations and pilot membership before generating predictions. Treat two pilot personas as a reproducibility check with descriptive results.

## Scorer behavior to preserve

- The pinned agent path uses `evals/agent_eval/memory_to_answer.py`, which defines its own `fama_score`. The direct-model path defines the same formula in `evals/model_eval/model_based_evaluator.py`. Exercise the agent path when validating the adapter.
- With no omission checks, FAMA reduces to recall accuracy. With no recall checks, FAMA is zero. In multi-judge mode a tie fails the strict majority check. A check for which every judge fails counts as incorrect. Record judge failures and coverage to distinguish service reliability from memory behavior.
- The scorer applies recall and omission checks to free-form answers. An answer that abstains can pass omission checks yet miss required recall. Track semantic abstentions, missing predictions and generation failures separately. Keep per-method coverage and paired denominators visible when reporting any secondary analysis.
- Freeze predictions before giving the scoring process access to rubric text, expected answers or evidence. Check the boundary with the synthetic sentinel case in [replay acceptance](replay_acceptance.md).

## Proposed call matching

Use a common verification-free replay of the history as a diagnostic to define the eligible conflict stream. Record the event IDs and candidate evidence available at each event. For a budget fraction `p` and `N` eligible candidates in that stream, use `B = floor(p × N)` per history and disclose the resulting integer targets.

- **Fixed-stream diagnostic.** Freeze candidate evidence before running any policy. Use seeded sampling without replacement for B4. For T1 and B5, rank the common candidates by their respective scores and select exactly `B`, breaking score ties by chronological event and candidate order. This is a retrospective comparison of selection quality, since ranking can use scores for later candidates. It cannot substantiate online performance.
- **Closed-loop pilot.** Apply the same hard target `B` to each policy. Each decision uses only the history and policy state available at that step. Fit learned and heuristic thresholds on independent development data and freeze them before the pilot. Record candidates, attempted invocations, failures, retries and unused capacity for every method. Charge each attempted invocation, including retries, against the cap. Report paired FAMA as budget-matched only when realized attempts agree per persona. If they differ, report the comparison with both realized costs and keep it separate from the fixed-stream result.

Synthetic checks should include fractional rounding, zero eligible candidates, tied scores at the cutoff, failed calls, and a closed-loop case where an early verification removes a later conflict. This last case should expose the call shortfall without either exceeding the cap or querying the verifier on a known ineligible event.

### Implemented fixed-stream B4 and B5 replay

Call `run_matched_baselines(replay(history), complete, entity=persona, calls=B, seed=seed, verify=verify)` from `trace_mem.baselines` (import `replay` from `trace_mem.data.memora`). Extract once and run the verification-free B2 reference to freeze each eligible claim and its unique target. B4 samples uniformly without replacement. B5 ranks uncertain claims first, then implicit changes, then explicit corrections. Chronological order breaks ties at the budget cutoff. The same integer target is mandatory for both methods. An infeasible target raises before any verifier calls.

Each arm invokes the verifier in chronological order on the selected reference evidence. A call counts even if an earlier verified update caused the arm to diverge from the reference. Apply a verdict only when the reference target is still the arm's eligible target. Otherwise record a stale target and use the ordinary B2 rule for that step. The result records selection IDs, attempts, failures, and stale-target counts per method. This interface implements the fixed-stream diagnostic. The closed-loop pilot and its independently tuned thresholds are separate work.

### T1 replay and feature definitions

Pass `controller=...` to `run_matched_baselines` to add T1 to the fixed-stream diagnostic. T1 ranks the identical reference candidates by logistic score and breaks ties by chronological candidate order. All methods attempt exactly the same integer number of verifier calls. The budget fraction is frozen at 1 for a positive target and 0 for a zero target because selection happens before any diagnostic calls. These rankings can use later candidates.

`run_t1(replay(history), complete, entity=persona, controller=controller, threshold=threshold, calls=B, verify=verify)` is the closed-loop entry point. It scores the eligible live conflict before each call, using the actual fraction of the budget remaining. Scores at or above the threshold trigger verification while capacity remains. Only an update verdict supersedes the target. An exception or malformed verdict consumes one attempt and defers the update. The run can use fewer calls than the cap. Compare closed-loop methods as budget-matched only when their realized attempts match independently of the fixed-stream diagnostic.

The ordered feature vector uses the defaults below. A configured [local semantic provider](semantic_models.md) replaces the first two values with cosine similarity and NLI contradiction probability without changing feature order.

| Feature | Calculation |
| --- | --- |
| Semantic similarity | Jaccard overlap of case-folded word tokens in the two values. |
| Contradiction score | Same entity and predicate with different values, weighted by `1 - uncertainty / 2`. |
| Entity match | Exact entity identity. |
| Temporal conflict score | Competing values with overlapping effective intervals. |
| Time gap | Days between the two source observations. |
| Provenance score | Fraction of the two source references that are present. This measures trace availability. |
| Uncertainty | 1 for uncertain claims, 0.5 for implicit assertions, and 0 for explicit corrections. |
| Budget remaining fraction | Frozen reference value of 1 for fixed-stream ranking or live remaining calls divided by cap in closed-loop replay. A zero-call run skips feature scoring. |

These features require structured text, an intent and valid dates. Missing optional expiry means an open interval, missing references reduce the provenance score, and invalid or nonfinite numeric inputs are rejected. The logistic fitter learns normalization from its training rows and uses unit scale for constant features. Synthetic coefficients and labels exercise the implementation. Independent TRACE-UpdateSet labels, probability calibration and a development-selected online threshold remain pending.

## Planned scorer parity checks

Use synthetic answers and fixed judge outcomes for recall-only, mixed recall and omission, abstention, tied judgment and all-judge failure. Require per-check outcomes and per-question FAMA to agree with the pinned scorer. Record the judge models, prompt and decoding settings, retries, error counts and cache identity for any eventual live evaluation.

This draft is for team review. Scorer behavior above was inspected in the pinned source. No model or scorer was executed.
