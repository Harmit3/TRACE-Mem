# Step 24 · Full weekly Memora development diagnostic

Step 24 intentionally runs the unchanged original automatic extractor across the complete reserved weekly development persona, including all 15 official questions. This is a separately declared diagnostic. The failed extraction promotion gates and prior findings remain part of the research record. The reserved held-out personas remain outside all inference and scoring.

Commit `5dcc614` froze the persona, questions, policies, caps, seeds, and metrics before requests. The pinned upstream source and conversation/rubric tree IDs are inherited from [Step 19](memora_step19_freeze.json). The source adapter passes only session text and chronological metadata to extraction. Retrieval and generation receive only filtered memory and answer-blind question fields. Scorer labels are confined to the separate adjudication process.

## Coverage, spending, and scoring

- B0–B5, T1, T1-no-NLI, T2 and H-paced share the original automatic extraction, local Qwen reader and direct-v2 verifier, and MiniLM top-8 retrieval. The learned policies use the committed T1 artifacts. Full T1 and T2 use pinned DeBERTa evidence; no-NLI and H-paced do not use contradiction scores.
- Fixed-stream exact allocations floor the requested percentages of the frozen B2 candidate count. Closed-loop hard caps floor the same percentages against an exogenous budget reference of 15 opportunities, corresponding to 0, 1, 3, 7 and 15 calls. T2 and H-paced are tested at planning horizons of 5, 15 and 30 with the same caps. No realized candidate count enters closed-loop cap construction or its adaptive decision rule. The planned horizons are a declared stress test, not fitted forecasts.
- Closed-loop verification opportunities can differ from the fixed B2 stream because state can diverge. Achieved coverage uses the fixed-stream count as a shared denominator and is undefined if that count is zero. Actual calls are counted once per method, budget, seed and unique question cutoff, even if several questions read that state. Fixed-stream and closed-loop comparisons stay separate. B4 uses five seeds, while deterministic methods run once per cell.
- The structural audit counts same-effective-date and same-observation-date conflicts separately, plus multiple simultaneously eligible target facts, deferrals and exact deletion resolution. The event-like predicate heuristic identifies possible multi-valued collisions. It cannot establish from predicate names alone that competing facts should coexist or that a deletion was missed in extraction.
- Storage is the serialized payload of the unique facts visible on at least one observed effective date at the cutoff. It excludes Python heap, model weights, SQLite and raw source text. Reader abstentions and judge/reader errors are counted separately. Macro FAMA averages scored questions with explicit coverage. Presence/absence counts retain their denominators. Historical wording is flagged by a frozen lexical rule, rather than treated as a validated temporal question category.
- The judge is the same adapted local Qwen version previously checked on fictional fixtures. The offline join uses the exact upstream FAMA function. Shared model identity and the small validation set limit judge independence and reliability. Published hosted-judge scores and this diagnostic have different adjudication configurations.

## Run and resume

```powershell
python -u -m scripts.extract_memora_full third_party/Memora results/memora-step24-reproduction --reuse results/memora-step22/responses.sqlite
python -u -m scripts.replay_memora_full third_party/Memora results/memora-step24-reproduction --outcomes results/updateset-v3-final/outcomes.jsonl --nli data/models/nli-deberta-v3-xsmall-a150876
python -u -m scripts.judge_memora_full third_party/Memora results/memora-step24-reproduction --validation results/memora-step20-validation/report.json
python -m scripts.render_memora_full results/memora-step24-reproduction docs/memora_step24_artifacts
python -m pytest -q
```

Each phase refuses a mismatched freeze and reuses completed work from the same directory. Extraction checkpoints a session, replay checkpoints a cutoff/cap/seed/horizon combination, and adjudication checkpoints a distinct answer and rubric evaluation. An optional read-only import brings only successful keyed responses into the new extraction cache. Prior ledgers, predictions, and caches are preserved. The first launch encountered a Windows SQLite attachment issue before any model calls. Commit `1e00c4a` corrected the cache import and restarted in a fresh directory.

## Extraction and structural failure audit

The complete run processed 151 sessions and 2,390 turns, of which 1,163 were user turns. The extractor emitted 88 claims from 84 user turns (7.22%). There was one invalid response. The output comprised 64 assertions, five uncertain claims, one correction, and 18 deletion claims. The B2 chronological trace added 41 claims, superseded one, and deferred 46.

Of 27 claims with a conflicting active value, only ten had a unique eligible verification target. Nine had a competitor with the same effective date, eight had a competitor observed on the same date, and nine encountered multiple target facts. These categories can overlap. Three deferred event-like clashes used the predicate `visit`. Those are candidates for a representation problem and were not separately human-annotated. **All 18 extracted deletion requests failed exact target resolution** on the B2 reference trace. Thus a correct forgetting-absence check can co-occur with no actual deletion transition, particularly when the original fact was never stored or was not retrieved.

Extraction used 1,037 fresh local requests, 126 cache hits, 201,084 input tokens, and 4,136 output tokens. Summed latency was 526.96 seconds and elapsed time was 540.98 seconds.

The first replay invocation retried identical terminal reader failures for several policy cells. It was stopped after writing partial checkpoints. The final replay restarted from verbatim copies of the completed extraction manifest and session checkpoints under `results/memora-step24-final`. It imported the successful responses from the partial replay and now memoizes terminal reader errors under the same request key. The prompt, token limit, model, decoding and answer validation were preserved. Reuse means a shared response failure is propagated to all matching predictions, rather than retried for each policy. The interrupted replay ledger remains in `results/memora-step24-full`.

## Verification spending

All 15 questions share the June 7 cutoff. With ten B2-reference candidates, matched fixed-stream methods spent 0, 1, 2, 5 and 10 calls for requested budgets of 0%, 10%, 25%, 50% and 100%, respectively. The 25% point achieved 20% because of floor rounding. B0–B2 spent zero by design. Closed loop used the same announced caps across policies and produced the spending below.

| Closed-loop method | 0% | 10% | 25% | 50% | 100% |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0, B1, B2 | 0 | 0 | 0 | 0 | 0 |
| B3 | 0 | 1 | 3 | 6 | 6 |
| B4 (five-seed mean) | 0 | .8 | 2.2 | 2.6 | 2.6 |
| B5 | 0 | 1 | 1 | 1 | 1 |
| Frozen T1 and no-NLI | 0 | 0 | 0 | 0 | 0 |
| T2, horizon 15 | 0 | 0 | 1 | 3 | 6 |
| H-paced, horizon 15 | 0 | 0 | 0 | 2 | 6 |

At the 100% requested point the hard cap is 15 and the fixed-reference denominator is ten. T2 and H-paced each used six calls, equivalent to 40% utilization of the cap and 60% coverage relative to the fixed reference. Of 2,400 prediction rows, 216 carried reader errors, including responses that could not be validated. Four unique terminal failures accounted for these rows, with 212 failure-cache reuses. These errors count against reported coverage.

At a 50% request, T2 spent 6, 3 and 1 calls at horizons 5, 15 and 30. H-paced spent 6, 2 and 0. At 100%, those counts were 6, 6 and 1 for T2 and 6, 6 and 2 for H-paced. The always-verify B3 policy encountered only six eligible conflicts in its high-budget live state, compared with ten on the B2-reference trace. B4 spent 0–4 calls across its five seeds at the 50% and 100% caps. Frozen T1 and its no-NLI ablation made zero closed-loop calls throughout.

## Adapted local benchmark results

**Every method at every budget and planning horizon had macro FAMA 0.000 on the scored predictions.** This held for remembering, reasoning and recommending. Across the 2,400 prediction rows, 2,184 were scorable (91.0%), including 2,034 abstentions and 150 nonempty outputs. Across those rows the local judge credited 0/5,762 memory-presence checks and 3,474/3,474 forgetting-absence checks. These pooled counts include repeated question evaluations across method cells and seeds. Scored coverage per cell ranged from 13/15 to 15/15. Two distinct reader responses failed schema validation and two were incomplete or refused. There were no judge errors.

The learned policies showed **no measurable answer-quality advantage over H-paced**. Horizon changes moved call counts without moving FAMA. The B2 memory contained 41 current facts and 42 historically visible distinct facts (11,597 modeled bytes). B1 retained 64 current facts (17,472 bytes) and carried out one deletion. At the highest closed-loop cap, T2 and H-paced each retained 42 current facts and 43 historically visible unique facts (11,836 bytes) and recorded zero deletes. Thus perfect judged omission reflects the answers' exclusions and does not demonstrate reliable memory deletion. None of the 15 questions matched the frozen historical wording rule. Historical state is measured structurally, without a benchmark historical-accuracy claim.

The largest observed bottlenecks are sparse extraction, unresolved deletions, single-slot conflicts, and widespread reader abstention despite stored facts. No independent alignment audit establishes how many rubric targets existed in extracted memory. The results cannot separate extraction misses from retrieval or reader failures for each question. The local judge uses the same Qwen checkpoint as the reader and was validated only on the earlier small fictional set. One development persona and a shared cutoff leave generalization unresolved.

## Resource ledger and artifacts

| Completed phase | Actual requests | Provider cache hits | Input / output tokens | Summed provider latency | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Extraction | 1,037 | 126 | 201,084 / 4,136 | 526.96 s | 540.98 s |
| Final replay | 23 | 2,328 | 7,528 / 835 | 52.89 s | 93.24 s |
| Local adjudication | 65 | 4 | 7,296 / 544 | 46.33 s | 47.25 s |

The final replay reused prior successful responses and memoized 212 terminal errors. The interrupted replay had 38 completed requests and one unresolved reservation, with 13,436 input and 3,274 output tokens recorded for the completed requests. These are separate from the completed-phase table. Spending was USD 0. The final workspace run passed 100 tests and 36 subtests, including pinned upstream tests, with one third-party AnyIO warning.

- [Budget curves](memora_step24_artifacts/budget.svg)
- [Extraction and conflict plot](memora_step24_artifacts/failure-analysis.svg)
- [Aggregate results by mode, method, seed, horizon and task](memora_step24_artifacts/aggregate.json)
