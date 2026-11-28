---
title: "TRACE-Mem experimental supplement"
subtitle: "Frozen configurations, outcome definitions and reproducibility"
---

## Which populations support which claim?

The training release contains 200 synthetic histories in 40 families. The split placed 20 families in training, ten in calibration and ten in evaluation. Labeled candidate counts were 112, 63 and 37 respectively. These are decisions conditional on an eligible conflict. Unlabeled or pending outcomes cannot supply negative labels. The evaluation set for fitting the scorer is separate from the primary replay cohort.

The primary replay cohort was generated with seed 61843 and contains ten histories in each of ten additional authored families. Each history supplies two true replacements, a misleading correction, uncertainty, an archive mention, a deletion and distractors. Candidate preparation deliberately introduces imperfect intent. The five B2 opportunities per history determine the nominal budget scale. Study 31 perturbs the planning horizon on the same histories. Family-disjoint evaluation cannot remove dependence from shared authorship or repeated update archetypes.

## Model and controller configuration

The verifier is local Qwen2.5 7B Instruct Q4_K_M, with a 4,096-token configuration, output cap 256 and seed 23 in the Step 30 manifest. MiniLM-L6-v2 provides cosine similarity of pooled, normalized embeddings. The pinned DeBERTa-v3-xsmall NLI model compares old and proposed assertions at the same effective date. The complete model digests, controller fingerprints and runner configuration are recorded in the [run manifest](../../docs/step30_artifacts/run-manifest.json).

The feature order is semantic similarity, contradiction, exact entity match, explicit overlapping temporal conflict, elapsed observation days, direct-source fraction, intent uncertainty and remaining-call fraction. An exact entity guard makes entity match constant in training. Each training fold fits its own standardizer. Five family-group folds compare balanced logistic fits over inverse regularization strengths 0.01, 0.1, 1, 10 and 100. Pooled average precision selects 0.01 for both the full and no-NLI artifacts. The final fit uses the entire training partition. Calibration fits a scalar logistic model with inverse regularization 1 on held-out logits. Calibration can change probability scale while preserving ranking. The no-NLI artifact is separately fitted with the absent column padded to zero weight.

T1 applies its frozen decision threshold to the scored live pair and stops at the cap. T2 neutralizes the budget feature and compares the score to a training-reference quantile determined by remaining calls and the exogenous horizon. H-paced uses the same pacing function with a heuristic score. B3 checks eligible writes in arrival order. B4 provides a seeded random comparator, and B5 uses a fixed heuristic. All methods record actual expenditure. A ceiling can leave calls unspent. See the equations and pseudocode in the [master manuscript](master.pdf).

## Complete results and ablations

The [complete machine-readable grid](../tables/verification-grid.csv) gives each policy, replay design, nominal budget, horizon, exact numerator, denominator, historical count, cap, actual calls and staleness. The [frozen numerical reference](../../reproducibility/data/frozen-reference.json) includes the 230 summaries and 184 paired intervals, including contrasts outside the main text. The [claim-to-evidence matrix](../final_claim_index.md) distinguishes the primary contrast, post-hoc perturbation, external diagnostic and engineering pilot.

| Comparison | Observation | Interpretation |
| --- | --- | --- |
| T2 vs H-paced, nominal 50% | Fixed 341 vs 409; chronological 434 vs 394, each out of 600 with 250 calls | Target availability and allocation jointly change between designs |
| T1 vs separate no-NLI fit | Both 56.8% fixed. Chronological 63.7% with 231 calls vs 55.8% with 171 | Different spending prevents a pure NLI effect estimate |
| Doubled planning horizon | T2 59.0% with 211 calls, B3 68.7% with 250 | Anticipated future opportunities never arrived |
| Reader, nominal chronological cohort | T2 7/30, B3 6/30, H-paced 12/30 | Correct retained state alone is insufficient for question answering |
| External ingestion | Only one managed LongMemEval case completed and every compared arm missed it | No paired external superiority estimate |

The primary endpoint compares entire predicted value sets with the authored gold sets over six date-specific checks per history. Secondary historical checks use a separate denominator. Two thousand paired resamples draw ten family means with replacement using seed 9001. The 95% percentile intervals describe this authored cohort. Multiple secondary intervals are unadjusted. The oracle's five correct generated short answers out of ten, despite its correct state, locate a downstream bottleneck. Earlier Memora and subsequent extraction and reader gates retained their negative results.

## Cost and failure accounting

Step 30 took 1,021 seconds. The verifier recorded 16,489 logical calls, of which 814 were fresh and 15,675 reused cached outcomes. The fresh requests consumed 233,459 input and 9,537 output tokens and 730.4 seconds of summed latency. Costs are for the grid with shared caches. A production latency forecast would require a separate workload. The local workstation used an RTX 2060. Reader usage is itemized separately in the original aggregate.

The Step 42 packaged-application pilot used a reviewed store and one nested trajectory. Six prefix lengths and three probes in each of three modes yielded 54 dependent paths. Direct date lookup accounted for twelve answers. Verification cost was zero. Both retrieval modes generated six correct calculations. The optional encoder recovered one of four paraphrases. This pilot answers a question about authorized accessibility after truncation; it cannot validate acquisition from arbitrary conversations or the learned allocator.

## Reproduce and interpret

From the source root run the following commands with CPython 3.14. The first regenerates counts using only the standard library. The second checks paper claims against the saved aggregates. To regenerate vector figures install the pinned plotting requirements from the reproducibility directory and add the figures option to the first command.

~~~text
python reproducibility/reproduce.py --output results/reproduced
python -m scripts.verify_manuscript
python reproducibility/reproduce.py --figures --output results/reproduced-figures
~~~

The sanitized 27,000 history-level rows and 2,300 family rows retain pairing without releasing benchmark dialogues or model weights. The independent aggregation code verifies numerical reproducibility from observations. A new implementation of the intervention on new histories is a different scientific test. The [future validation protocol](../validation_protocol_v2.md) retains its own review gates. Its completion is unnecessary for distributing this bounded exploratory report.
