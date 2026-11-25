# TRACE-UpdateSet v2 full candidate collection

## Frozen protocol

Use every case in the seed-2407 release in frozen order. Keep the original 44 pilot cases tagged and report them separately. The other 456 cases form the nonpilot partitions. These partitions are held out at the case level from the pilot and share its template families within each split. Training and validation have disjoint family, persona and conversation identifiers. No v1 or external benchmark answers are read.

Use the pinned local Qwen and direct-v2 settings from the [validated comparison](qwen_verifier.md), including Ollama 0.40.13, seed 23, temperature zero, 4,096-token context, 256 output cap, 120-second timeout and zero retries. Run production claim extraction once per case on the focal user turn. Use the case's seeded prior fact to initialize the ordinary B2 replay prefix. Keep every extracted claim, including ones without a conflict. For each claim in extraction order, identify the B2-eligible target using the live unverified prefix. A scored candidate must uniquely target the case's seeded fact. Other claims follow B2 and may influence subsequent eligibility.

Fork the same prefix for both arms. The unverified branch uses the deployed B2 transition and advances the shared prefix. The verified branch applies the same production verifier-to-transition rule using one local verdict and the role-tagged conversation. It does not advance the prefix for later comparisons. This creates a fixed-prefix counterfactual per candidate and measures a one-call intervention. It does not estimate closed-loop behavior. Each record retains the claim, target and source, prefix trace, both anchored decisions and transitions, verdict, operational status, and independent gold reference when available. Later extracted claims are outside an earlier candidate's state comparison.

Generate all eight features from the extracted claim, prior target and source before the verifier runs. Use the existing standard-library feature definitions with token Jaccard similarity, rule contradiction, exact entity match, interval conflict, observation gap in days, provenance presence, extraction-intent uncertainty, and remaining-budget fraction fixed to one for an independent one-call intervention. Neither labels, gold, nor verified state enter feature extraction or model requests. The fixed fraction, seeded target and narrow timeline can leave features constant. Report feature ranges, missingness, and distinct counts by partition.

Score the case's anchored predicate at the focal and prior observation dates using the frozen gold. A positive fixes an incorrect unverified state, and a harmful change breaks a correct state. All other observed comparisons with gold are negative. Record unchanged state, failures, ineligible claims and pending annotations explicitly. A failed verifier call supplies no helpfulness label. No cases are dropped based on outputs.

```powershell
python -m scripts.collect_updateset_v2 data/updateset-v2-seed2407 results/updateset-v2-full
```

Use that same command and directory to resume. Atomic per-case checkpoints and a content-addressed provider cache prevent repeating completed calls. The local freeze record captures source and code hashes, settings, feature order, and pilot IDs. Resume rejects changes to those inputs. Outputs under `results/` remain ignored.
