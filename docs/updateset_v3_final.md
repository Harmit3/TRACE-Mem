# TRACE-UpdateSet v3 longitudinal release

## Frozen collection protocol

The independent synthetic release uses seed 6931, 200 histories, and three chronological decision points per history. Training has 100 histories from 20 scenario families. Calibration and independent evaluation each have 50 histories from ten distinct families. Every family is authored separately and instantiated five times with natural fictional places, dates and sources. Cases within a family are clustered. No previous pilot or benchmark content is included.

Each decision has an independently authored current and historical state or a pending annotation. Gold stays in the evaluator. The blind packet contains only the seeded prior and time-available conversation through the ambiguous turn. It excludes later turns, outcomes and gold. The extractor sees each focal turn and the verifier sees the chronological conversation prefix. Only the models and feature code already validated locally are used. No inference providers or model prompts are tuned on this release.

Seed the memory prior and carry forward deployed B2 state across all three turns. Identify each eligible single-target exact-entity conflict on the anchored predicate. Fork the same prefix for both decisions and advance B2 only. Only a verified update can supersede in the alternate arm. Score current and prior anchored values immediately after each candidate. This is an isolated candidate counterfactual on a chronological B2 prefix and cannot establish closed-loop performance.

Each history has a preregistered cap of one to three verification calls. Deduct actual verification attempts, including unsuccessful attempts. Compute all eight v3 features before verification using the actual pre-call remaining fraction. Persist ineligible and budget-exhausted claims, extraction and verifier failures, harmful changes, unchanged decisions and corrections. Cases awaiting gold remain pending. Outcome and feature rows are never filtered based on whether they help. Keep the label definition and feature definitions frozen.

Use the validated local Qwen direct-v2 digest and configuration, cached MiniLM, and pinned DeBERTa-v3-xsmall NLI. See the [NLI check](updateset_v3_nli.md) for neutral false contradictions and observed redundancy. Report a no-contradiction projection on the same rows for a future ablation. Correlation and class-support diagnostics are descriptive. No controller fit or calibration is authorized here.

```powershell
python -m scripts.collect_updateset_v3_final prepare data/updateset-v3-final
python -m scripts.collect_updateset_v3_final run data/updateset-v3-final --model data/models/nli-deberta-v3-xsmall-a150876 --output results/updateset-v3-final
```

Resume using the same command and directory. Atomic per-history checkpoints and a local response cache support recovery. The freeze file pins inputs, settings, dependency versions, feature order and collection code. Partitions, review packet, raw results and ledgers stay local and ignored. The run reports every ten histories. Prior experiments remain separate.

## Observed release

The v3 NLI integration was merged in PR #25 at `44fe6cc`. Commit `e58a91c` froze the generation, gold and collection code before inference. The completed run contains 200 histories and all 600 decision points. There are 535 decisions with synthetic gold and 65 pending human review, split 30 train, 20 calibration and 15 evaluation. The blind packet is `data/updateset-v3-final/pending-review.jsonl`.

| Partition | Decisions | Verified candidates | Helpful | Not helpful | Pending gold among verified | Unchanged | Ineligible claims | Budget exhausted | Extraction failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 300 | 120 | 22 | 90 | 8 | 92 | 190 | 53 | 1 |
| Calibration | 150 | 70 | 17 | 46 | 7 | 50 | 63 | 27 | 3 |
| Evaluation | 150 | 42 | 6 | 31 | 5 | 36 | 142 | 19 | 0 |
| Total | 600 | 232 | 45 | 167 | 20 | 178 | 395 | 99 | 4 |

There were zero harmful anchored-state changes and zero verifier failures. Eight gold-backed changed decisions remained incorrect. Budget-exhausted claims were kept without verification labels. The absence of observed harm applies only to the anchored predicate and evaluated candidate comparisons.

Ollama made 788 requests, of which 784 validated and four failed extraction validation. The ledger recorded 44 cache hits, 185,845 input and 20,362 output tokens, and USD 0 cost. Provider latency was 1,099.063 seconds summed, 1,394.75 ms mean and 2,838.90 ms p95. These timings cover Qwen requests. MiniLM and NLI ran on CPU and were not separately timed in this collection.

## Integrity, features and ablation

```powershell
python -m scripts.audit_updateset_v3_final data/updateset-v3-final results/updateset-v3-final --ablation results/updateset-v3-final-no-nli
```

The audit verified 726 candidate keys, all groups and the causal budget fraction, checked labels against gold, and found no cross-partition focal-text matches or matches against the prior v3 pilot text. Synthetic examples remain clustered within family, and exact-match checks cannot rule out conceptual similarity. Gold stays out of production requests and no benchmark answers were opened. Past artifact hashes were unchanged.

| Feature | Train variance | Calibration variance | Evaluation variance |
| --- | ---: | ---: | ---: |
| MiniLM cosine | 0.011925 | 0.016907 | 0.009387 |
| NLI contradiction | 0.215398 | 0.205961 | 0.208649 |
| Entity match | 0 | 0 | 0 |
| Explicit-date conflict | 0.249931 | 0.132449 | 0.213719 |
| Observation gap | 1766.314167 | 1936.829592 | 1653.269841 |
| Provenance | 0.103056 | 0.101224 | 0.149235 |
| Extraction uncertainty | 0.039427 | 0.056939 | 0.053430 |
| Remaining fraction | 0.058765 | 0.066604 | 0.066453 |

Each partition had seven varying features, exact entity match stayed fixed, and no eligible vectors were missing. There were 120, 69 and 42 distinct complete vectors in train, calibration and evaluation. Removing contradiction leaves these distinct counts unchanged. The strongest train correlation is contradiction with explicit-date conflict (+0.565). Contradiction–uncertainty correlations are −0.274, −0.203 and −0.326 by partition, weaker than the v3 pilot. The [safe aggregate JSON](updateset_v3_final_summary.json) includes all variances, ranges and defined pairwise Pearson correlations.

The no-NLI projection has the same 232 verified candidate rows, groups and label status, with only the contradiction coordinate removed. No ablation model was fit. Use matched data, seeds and tuning rules for a future comparison. The previous [NLI check](updateset_v3_nli.md) showed high-confidence false contradictions on neutral cases. The present feature variance does not establish NLI accuracy or added utility.

| Artifact | SHA-256 |
| --- | --- |
| Frozen histories | `d93d7e2ad0cf9dce8ca70d7bcb6ac0b0aeac2de7d6e3dc27218866ebb8c97c58` |
| Blind review packet | `c170dbfe3c08eb17679677d7494200b7d5aa151665d743e2d11fdeb61ab9c5a1` |
| Runtime freeze | `6c714578c002a685e8df13f47b464d01d473d7c47ae14f8270de2798c8ac0b3c` |
| Candidate outcomes | `837820ce735c3040d14ae1ace8cd24ef6ffc7c2986098e90ec95e0817fb81dc0` |
| No-NLI projection | `401ebeb99582c7d78e31fe2ff529ee796fe58e05c0567847402024a2a9b93b38` |

## Limits on calibration

Positive examples come from 9 train families, 6 calibration families and 4 evaluation families, compared with 18, 8 and 5 negative families. Positive counts are 22, 17 and 6 distinct histories. The release supports exploratory comparisons. It cannot support a reliable calibration or generalization claim from these counts and this clustered design. Provenance is authored synthetic metadata. The seed-fact source category varies by design and is not an observed source reliability estimate. The scenarios use two anchored predicates and fixed-prefix interventions, leaving transfer and closed-loop behavior unmeasured. No further collection, model fit, or calibration run was performed.
