# T1 training and calibration

Install [the training dependency](../requirements-training.txt) in the project virtual environment. Training uses [scikit-learn 1.8.0](https://pypi.org/project/scikit-learn/1.8.0/) on Python 3.11 or later. Loading a trained JSON artifact and replaying with it only requires the standard library unless local semantic providers are enabled.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-training.txt
python -m unittest discover -s tests -v
```

## Collect outcomes

Use `trace_mem.training.collect_pairs` with a validated [TRACE-UpdateSet](updateset.md) release, a new output directory, and distinct unverified and verified decision callbacks. Each callback receives the same immutable `DecisionInput` with the old fact, new claim, source and conversation. It receives no gold, prior outcomes, proposal or helpfulness label. The verified callback can call a fixed verifier and must return the resulting memory decision. Both callbacks return `{"operation": operation, "target_id": target_or_null}`. Keep the policy rules shared where applicable, and log the verifier checkpoint or API model, prompts, failure handling and run config under the supplied run reference.

Collection skips test cases and rows that already have outcomes. It joins the pair with gold through the existing independent decision comparator. A provider exception aborts the collection and publishes no new release. To include handled failures, explicitly return the policy decision taken after failure and record the failure in the referenced run log. Mark fixture outcomes as `synthetic_mock`. The default fitter excludes them, and an opted-in artifact records that it contains mock outcomes.

## Fit and load

```powershell
python -m trace_mem.training data/updateset-v1-labeled data/t1-model.json --target-fraction 0.25 --seed 7
```

The fitter uses the existing eight-feature order. With the Python API, supply `semantic` and a stable `semantic_reference` together to use pinned local model features. Reuse the same feature configuration in replay. Eligible rows must have gold, paired outcomes and a single replay-eligible conflict. This excludes deletes, nonoverlapping history and temporary events on a separate predicate. Both train and validation require positive and negative labels. The fitter excludes test examples from feature construction, fitting, calibration, threshold selection and metrics.

StandardScaler learns feature means and scales on train. The first logistic regression fits training examples. A second logistic regression fits a sigmoid calibrator on validation logits. Its affine logit transform folds into the serialized coefficients so the existing replay scorer can use it directly. The current dataset represents one decision per independent case, so its budget feature is fixed at 1. Those rows cannot estimate how remaining budget affects verification usefulness.

Threshold selection takes the highest-scoring validation groups that fit `floor(fraction × eligible validation rows)`. It leaves a tied group out in full when the group would exceed the cap. Threshold 1 disables selection. A validation cutoff does not predict realized online calls. Keep the hard cap in `run_t1` and compare realized calls per history. Fixed-stream comparisons still rank the common eligible stream against an exact call target.

Call `load_model(path)` to obtain the controller and threshold for replay. The JSON artifact records feature order, normalized and calibrated coefficients, dataset hash, seed, dependency version and outcome provenance. Validation accuracy, precision, recall, F1, Brier score, ten-bin calibration summaries and expected calibration error describe the same split used to tune the model. Independent evaluation remains a separate step. Run the synthetic fixtures for software verification. The repository contains no research model artifact or research metrics.
