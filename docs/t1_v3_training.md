
# T1 training on the frozen V3 candidate stream

This exploratory run uses the frozen longitudinal V3 release merged in PR #26. Run the existing V3 integrity audit first. The trainer checks literal release hashes and the pinned feature order, MiniLM and DeBERTa revisions, and Qwen digest. It reads recorded feature vectors directly. The V1 training entry point and deployed artifact schema still work.

## Protocol frozen before fitting

- Use verified candidates with independently established helpfulness labels for supervised steps. Keep pending gold in coverage denominators and omit it from scoring against gold. Failed and budget-exhausted candidates are unscored in this release and remain in the eligible-count denominator.
- Fit L2 logistic regression with balanced class weights, no resampling, and seed 23. For each of five shuffled stratified group folds, fit scaling exclusively on that fold's training data. Group by scenario family. Both variants use identical folds and rows. Select C from 0.01, 0.1, 1, 10 and 100 by pooled out-of-fold average precision, with ties preferring smaller C. Refit scaling and regression on the complete labeled training partition. Constant coordinates use unit scale and contribute zero fitted weight.
- Fit a regularized sigmoid calibrator on calibration logits and established calibration labels only. Use C=1 with no class weights. Keep the original score if the fitted slope is nonpositive. Record raw and transformed coefficients. Compare the evaluation Brier scores descriptively.
- Choose thresholds separately at 0%, 10%, 25%, 50% and 100% using all scored calibration candidates and the repository threshold function. Equal-score groups stay together and the calibration cap rounds down. Export the 25% cutoff as the default. Report classification at a predeclared score of 0.5. Save artifact hashes before opening evaluation labels.
- Compare the full model, the matched seven-feature fit excluding NLI, the training-prevalence intercept, B5 uncertainty, and a contradiction-only score on evaluation. The two heuristic scores are raw scores for ranking, and their probability metrics are descriptive. The no-NLI artifact pads the omitted coordinate with zero weight for compatibility with the eight-slot loader.
- For budget diagnostics, rank the 42 scored evaluation candidates and select the floor of the requested fraction; break ties by frozen stream order. Include seed-23 B4 random allocation. Report calls and coverage over both scored candidates and all eligible candidates, including those lacking scores. Report transferred thresholds separately without an offline cap so transfer under- or overspend is visible. Deployed replay retains its per-history hard cap.
- Report percentile intervals across 2,000 paired family bootstrap replicates on labeled evaluation candidates. Report valid replicate counts and omit single-class samples from rank metric intervals. Intervals condition on the trained parameters and observed families and do not account for model refit or dataset shifts.

This experiment compares recorded B2 fixed-prefix counterfactuals. Changes to the policy during chronological replay can alter later state, candidate eligibility, and remaining budget. Neither synthetic allocation nor a deployment smoke test measures closed-loop memory quality or benchmark performance.

## Reproduction

```powershell
python -m pip install -r requirements-training.txt
python -m scripts.audit_updateset_v3_final data/updateset-v3-final results/updateset-v3-final
python -m scripts.train_t1_v3 fit data/updateset-v3-final results/updateset-v3-final results/updateset-v3-final-no-nli results/t1-v3-fit
python -m scripts.train_t1_v3 evaluate data/updateset-v3-final results/updateset-v3-final results/updateset-v3-final-no-nli results/t1-v3-fit --output results/t1-v3-eval
python -m pytest -q
```

Use new output directories to repeat phases. The command refuses to overwrite previous results. The collection ledger, review packet and candidate rows remain local. Training, evaluation and plotting use the local Python environment and make no inference requests.

## Observed results

The fit and evaluation protocol was committed at `5f30bba` before fitting. The artifacts and calibration thresholds were committed at `18ce948` before independent scoring. Training used 112 labeled candidates, including 22 positives from 9 families. Calibration used 63 labeled candidates, including 17 positives from 6 families. Independent evaluation used 37 labeled candidates, including 6 positives from 4 families. Five of the 42 scored evaluation candidates have pending gold, and 19 more eligible candidates exhausted their collection budget before scoring. Funding cost was USD 0 and the experiment made no inference requests.

Both models selected C=0.01. The full model's calibration slope was 2.266 and the no-NLI slope was 2.239. The default deployed thresholds targeting 25% calibration coverage are 0.363898 and 0.379341, respectively. Brier scores before the exploratory calibration transform were 0.1963 and 0.2060. The full model's 10-bin exploratory ECE was 0.1735 and the ablation's was 0.1851.

| Evaluation method | Accuracy | Balanced accuracy | Precision | Recall | F1 | AUROC | Average precision | Brier | TN/FP/FN/TP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Full T1 | .892 | .801 | .667 | .667 | .667 | .962 | .849 | .0945 | 29/2/2/4 |
| No NLI | .919 | .817 | .800 | .667 | .727 | .962 | .877 | .0954 | 30/1/2/4 |
| Intercept | .838 | .500 | .000 | .000 | .000 | .500 | .162 | .1370 | 31/0/6/0 |
| B5 uncertainty | .054 | .167 | .061 | .333 | .103 | .167 | .128 | .3311 | 0/31/4/2 |
| Contradiction | .486 | .626 | .217 | .833 | .345 | .651 | .282 | .4525 | 13/18/1/5 |

The paired family-bootstrap 95% percentile interval for full minus no-NLI average precision was [−.167, .083]. Full T1 AUROC was [.931, 1.000], and average precision was [.775, 1.000]. The observed performance and intervals describe this small synthetic cohort. They leave the advantage of adding NLI unresolved. Reliability bins have small counts, and apparent improvements in Brier score require independent confirmation.

| Standardized feature | Full T1 | No NLI |
| --- | ---: | ---: |
| Semantic similarity | −.0312 | −.0574 |
| Contradiction | .3360 | omitted |
| Exact entity match | .0000 | .0000 |
| Temporal conflict | .0764 | .1018 |
| Observation gap | .1952 | .1967 |
| Provenance | .2337 | .2326 |
| Uncertainty | −.3536 | −.3496 |
| Remaining budget | −.4477 | −.4518 |
| Intercept | −1.0735 | −1.1630 |

These are effective logit coefficients after the exploratory calibration transform. Entity match remains an eligibility guard and was constant in training. Coefficient signs are descriptive associations within the recorded prefix and candidate policy.

| Requested budget | Calls | Coverage of scored / all eligible | Known helpful selected, full / no NLI / B4 / B5 |
| ---: | ---: | --- | --- |
| 0% | 0 | 0% / 0% | 0 / 0 / 0 / 0 |
| 10% | 4 | 9.5% / 6.6% | 3 / 4 / 4 / 0 |
| 25% | 10 | 23.8% / 16.4% | 6 / 5 / 5 / 0 |
| 50% | 21 | 50.0% / 34.4% | 6 / 6 / 5 / 0 |
| 100% | 42 | 100% / 68.9% | 6 / 6 / 6 / 6 |

At the transferred 25% cutoff, full T1 selected 11 candidates and captured 6 helpful (26.2% coverage of scored candidates), while no NLI selected 8 and captured 5 (19.0%). Transferred thresholds can miss their coverage targets. The recorded budget feature uses the collection policy's call history, and the 19 budget-exhausted alternatives have no recorded counterfactual labels. The seeded B4 result describes one random allocation draw.

The repeated fit reproduced coefficients, calibration, thresholds and selection scores. Run commit metadata and dependent hashes differ on a later commit. Repeated evaluation from the same freeze reproduced the aggregate JSON and all four SVGs byte for byte. The full committed artifact loads through `trace_mem.training.load_model` and was smoke-tested with synthetic chronological events, injected features, and a one-call hard cap. Runtime V3 replay should use the shared `V3Features` builder with pinned providers. Under the current eight-slot replay interface, the ablation's ignored NLI slot still needs a numeric placeholder if replayed without NLI. The ablation here was evaluated offline.

- [Fit freeze](t1_v3_artifacts/fit-freeze.json) · [Full artifact](t1_v3_artifacts/full.json) · [No-NLI artifact](t1_v3_artifacts/no_nli.json) · [Aggregate results and intervals](t1_v3_artifacts/evaluation.json)
- [Precision–recall](t1_v3_artifacts/precision-recall.svg) · [Reliability](t1_v3_artifacts/reliability.svg) · [Confusion matrices](t1_v3_artifacts/confusion.svg) · [Budget allocation](t1_v3_artifacts/budget-allocation.svg)
