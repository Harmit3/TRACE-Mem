
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
