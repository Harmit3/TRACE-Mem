# TRACE-UpdateSet v3 feasibility pilot

## Frozen design

The v3 pilot contains 24 independently authored fictional cases across 12 disjoint families. Each partition has four families with two cases each. All cases are included in declared order. Prior facts, dialogue, provenance fields and anchor gold were authored before inference. Names and values contain no case suffixes. An uncertain case in each partition is left open for blinded adjudication. Only the evaluator reads gold. No v1 or v2 case files or held-out benchmark files are inputs.

The production extractor sees the focal user turn. The verifier sees the prior fact, claim, and role-tagged transcript. The case initializer seeds the prior fact and both arms fork the identical B2 prefix. Use only the first eligible conflict with the seeded fact. Score the anchored current and prior values with the same case-level helpfulness rule as v2. Keep all 24 rows.

Each partition has a fixed eight-call verifier cap in this ordered pilot. Features see the actual unused fraction before the call. Only an eligible request debits that partition's budget. This run-wide resource pool gives observable budget variation across cases. Deployed replay uses the same feature builder and its own actual replay budget. No budget value is assigned from a label or expected outcome.

The vector uses real locally cached MiniLM cosine, named NLI contradiction when available, exact entity eligibility, overlap with an explicitly extracted effective date, observation gap in days, proportion of direct or dated-record source references, observed extraction intent, and remaining verification fraction. The provenance coordinate measures attributable evidence and does not assert reliability. The pilot records NLI as missing. A deployed controller with this feature builder rejects an incomplete vector.

Freeze all settings in the generated manifest. Use the validated Qwen direct-v2 configuration, cached MiniLM on CPU and no NLI weights in the pilot. The technical pilot criteria are retaining all 24 cases, at least four nonconstant available features, at most two technical failures, and gold-free inputs with no raw case IDs. Report the classes by partition and family. Passing this engineering check does not authorize larger collection or training.

```powershell
python -m scripts.updateset_v3_pilot generate data/updateset-v3-pilot
python -m scripts.updateset_v3_pilot pilot data/updateset-v3-pilot --output results/updateset-v3-pilot
```

The frozen source, blind annotation packet, response ledger and outcomes remain under ignored local directories.

## NLI candidate pending approval

The candidate is [DeBERTa-v3-xsmall NLI](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall/tree/a150876415327c80daeff35ca6f68f5ed8cf5c24), Apache-2.0, with a 283 MB safetensors file plus tokenizer artifacts. The pinned config exposes named contradiction, entailment and neutral classes through the existing Transformers sequence classifier. It is a plausible CPU fit with 24 GiB RAM while Ollama uses the GPU. Runtime behavior and domain accuracy are unverified pending download approval. No weights have been downloaded.

## Observed pilot results

PR #23 was merged at `1ec58f6`. The methodology, feature builder, dataset, and criteria were frozen at `6f3b7f3` before the pilot. The generated case SHA-256 is `1dd10bb727971a7fa1c27366b2cdf7e71f047c493f150f9c2a539615926a81d5`. The outcomes SHA-256 is `a88d4bdb52a1521fe982d401147dd98d52cf56fade077dd476b6ff278fe9ccb1`.

| Partition | Cases | Verified | Helpful | Not helpful | Pending gold | Ineligible | Extraction failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 8 | 6 | 3 | 2 | 1 | 2 | 0 |
| Calibration | 8 | 4 | 2 | 1 | 1 | 4 | 0 |
| Evaluation | 8 | 4 | 2 | 1 | 1 | 3 | 1 |

There were seven helpful corrections, seven unchanged anchored decisions and zero harmful anchored changes. Positive support spans three train families and two families in each other partition. Negative support spans two train families and one family per other partition. The three ambiguous cases remain pending in `data/updateset-v3-pilot/pending-review.jsonl`, separate from all v1 and v2 annotations.

Among the 14 verified rows, six available features varied. MiniLM cosine and observation gap each had 14 distinct values. Remaining budget had six, provenance three, and explicitly dated conflict and uncertainty two each. Entity match stayed 1 by design. Contradiction is missing on all 14 rows. The largest observed absolute Pearson correlations were provenance–uncertainty −0.711, time gap–provenance +0.703, provenance–budget +0.667, and temporal specificity–provenance +0.612. These are descriptive estimates from a small clustered pilot.

Ollama made 38 actual local requests, 37 successful and one invalid extraction, with zero verifier failures, retries, cache hits, or provider cost. Reported usage was 8,897 input and 962 output tokens, with 81,315.10 ms summed provider latency. The technical gate passed. The tiny class support, ordering effects in a shared budget, and absent NLI still preclude a reliable fit or calibration claim. No larger collection or controller training ran.
