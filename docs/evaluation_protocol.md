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

## Planned scorer parity checks

Use synthetic answers and fixed judge outcomes for recall-only, mixed recall and omission, abstention, tied judgment and all-judge failure. Require per-check outcomes and per-question FAMA to agree with the pinned scorer. Record the judge models, prompt and decoding settings, retries, error counts and cache identity for any eventual live evaluation.

This draft is for team review. Scorer behavior above was inspected in the pinned source. No model or scorer was executed.
