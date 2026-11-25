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
