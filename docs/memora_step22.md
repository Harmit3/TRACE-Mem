# Step 22 · Controlled downstream Memora diagnostic

The protocol and annotation proposals were committed at `6ae9387` before Step 22 model predictions. The pinned Memora revision and development persona are inherited from Step 19. The slice is the first 12 sessions in date/session/turn order, with no replacement of sessions after results. The experiment uses the already frozen first remembering question, applies the eight existing policies, and leaves the held-out personas untouched.

## Source packet and experimental conditions

The ignored local review worksheet contains the 12 conversations, source IDs, eight verbatim value spans, and four focused questions for a reviewer. Each row remains marked as pending human review. The task completion reference, retention of generic duties, and whether to represent reasons for preferences are among the open judgments. We used the eight literal proposals directly in the span-oracle diagnostic. These proposals are source-checked and AI-authored, with no claim of independent human review. No clear deletion was supplied as Memora oracle input. The same-day snapshot cannot establish historical validity transitions.

The automatic condition uses the unchanged original Qwen extractor. The span-oracle condition uses the same model-powered reader and verifier but injects only the frozen source-grounded claim stream. Both use the same MiniLM retrieval, pinned DeBERTa, local Qwen generation settings, and the previously frozen T1 artifacts. The experimental hybrid extractor is outside Step 22.

Two additional fictional histories isolate downstream behavior with inputs and checks declared by construction. They cover confirmed replacements, uncertain alternatives, historical visibility, and an explicit privacy deletion. They have natural-language queries with expected answer values. Their scores are diagnostic and have no Memora rubric.

We convert requested coverage to a per-history cap with floor rounding using the eligible B2 reference stream. Fixed-stream methods receive the same number of calls whenever enough eligible candidates exist. Closed-loop methods share the cap and can underspend. The fixed experiment can rank using its complete reference stream. The closed-loop policies decide from information at the current prefix. Original and oracle scores can differ in eligible stream size, so report actual calls rather than relying on a requested percentage alone.

Exact slot checks are measured in stored memory before answer generation. Historical checks retrieve an earlier effective date after replay. Deletion checks measure absence at current and historical dates, so empty memory can pass these checks by abstaining from storage. Facts outside the oracle vocabulary are reported as uncorroborated by this packet. That is a narrow diagnostic and can include reasonable alternate predicate labels or omitted evidence. Fictional answer checks look for a frozen expected literal, leaving unsupported auxiliary text ungraded.

## Reproduction

```powershell
python -m scripts.run_memora_controlled third_party/Memora --nli data/models/nli-deberta-v3-xsmall-a150876 --output results/memora-step22
python -m scripts.render_memora_controlled results/memora-step22 --plot docs/memora_step22_budget.svg
python -m scripts.adjudicate_memora_local third_party/Memora results/memora-step22/predictions-automatic.json results/memora-step20-validation/report.json results/memora-step22-judge-auto
python -m scripts.adjudicate_memora_local third_party/Memora results/memora-step22/predictions-span-oracle.json results/memora-step20-validation/report.json results/memora-step22-judge-oracle
python -m pytest -q
```

Use `--packet-only` to export the review packet without inference. Raw conversations, annotations, predictions and caches remain in ignored local directories.

## Observed Memora result

The slice contained 185 turns, including 89 user turns, all dated June 1, 2025. The selected question is dated June 7. The first eight sessions overlap the earlier smoke, and the remaining four were included by chronological position. The automatic extractor emitted five claims and had zero provider validation failures. None of the five exactly matched a predicate/value pair from the eight proposed spans. This does not establish that all five claims were unsupported. In the span-oracle condition B1 retained 8/8 proposed facts while the temporal policies retained 7/8. The latter deferred the second different coffee expense under the same predicate and day. This is a visible limitation of the single-slot temporal model for multi-valued events.

Both input streams had **zero eligible verification conflicts**. Every method made zero calls at all five requested percentages. Coverage is undefined with a zero denominator. This slice cannot distinguish verification policies or establish a source-grounded historical or deletion score. All 32 method-by-mode predictions across both conditions abstained. Separate adapted local adjudication produced 0/4 memory-presence matches, 7/7 forgetting-absence matches, and FAMA 0.000 for each row. The FAMA arithmetic is upstream's pinned function. These scores use the local Qwen judge on a partial source history and have no published Memora comparability.

## Observed fictional temporal diagnostics

The source-span fixtures exposed four eligible conflicts in each history, eight in total. At 0% and 10%, floor rounding allowed zero calls. At 25%, 50%, and 100%, the matched fixed-stream totals were two, four, and eight calls. Entries are correct current-state checks out of 16.

| Requested coverage | Calls per matched policy | B3 | B4 | B5 | Full T1 | No NLI |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0% | 0 | 12 | 12 | 12 | 12 | 12 |
| 10% | 0 | 12 | 12 | 12 | 12 | 12 |
| 25% | 2 | 14 | 12 | 14 | 12 | 12 |
| 50% | 4 | 14 | 14 | 16 | 12 | 12 |
| 100% | 8 | 16 | 16 | 16 | 16 | 16 |

B0, B1, and B2 stayed at 8/16, 11/16, and 12/16. In closed loop at the 100% cap, B3 used eight calls for 16/16, B4 used two for 14/16, and B5 used three for 12/16. Both frozen T1 variants made zero closed-loop calls at every cap and stayed at 12/16. In the automatic fictional replay, only six reference conflicts remained. Fixed-stream T1 scored 8/16 at two calls and 10/16 at six calls. Closed-loop T1 made zero calls and stayed at 6/16. This diagnostic provides no evidence of a budget-efficiency advantage for the learned controller.

Across persistent methods the fictional oracle retained 8/8 historical checks, compared with 6/8 in the automatic condition. Both streams passed all four deletion-absence checks. The automatic persistent policies retained up to six current predicate/value pairs outside the oracle, while the oracle policies retained zero such pairs. This check cannot determine whether a missed or differently named fact is fabricated. Under fixed-stream T1 at 100% oracle budget, the reader returned the expected literal on one query and abstained on the other even though the memory layer passed all 16 current-state checks. The two fictional histories are pass/fail probes, with negligible support for population inference.

## Resources and artifacts

Replay used 138 actual Qwen requests, 342 cache hits, 28,036 input tokens, 1,177 output tokens, 115.84 seconds of summed provider latency and 133.42 seconds wall time. All fresh responses passed schema validation. The two scorer runs used 22 additional Qwen requests, 330 cache hits, 2,356 input and 182 output tokens. Scoring wall times were 15.92 seconds for automatic and 25.22 seconds for oracle, measured while replay was still running. Spend was USD 0. Tests passed with 92 workspace tests and 36 subtests, including the pinned upstream checkout and one third-party deprecation warning.

- [Budget curve](memora_step22_budget.svg) and [aggregate replay results](memora_step22_aggregate.json)
- [Adapted local FAMA aggregates](memora_step22_local_fama.json)
- Human-review worksheet at `results/memora-step22/review-packet.md`, with the machine-readable packet alongside it.
