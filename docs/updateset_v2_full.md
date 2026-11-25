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

## Observed full release

PR #20 was merged at `9ff82ee`. The protocol and collector were frozen at `350e54e) before the first full-run request. The collection finished all 500 cases. The table reports candidate counts except for the cases, no-conflict and extraction-failure columns.

| Partition | Cases | Verified | Helpful | Not helpful | Awaiting gold | Harmful | Unchanged | Changed but still incorrect | Ineligible claims | No eligible conflict | Extraction failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train nonpilot | 328 | 232 | 89 | 113 | 30 | 0 | 113 | 30 | 154 | 97 | 0 |
| Validation nonpilot | 128 | 58 | 35 | 23 | 0 | 0 | 12 | 11 | 106 | 69 | 1 |
| Train pilot | 22 | 13 | 5 | 6 | 2 | 0 | 6 | 2 | 10 | 8 | 1 |
| Validation pilot | 22 | 10 | 6 | 4 | 0 | 0 | 2 | 2 | 18 | 12 | 0 |
| Total | 500 | 313 | 135 | 146 | 32 | 0 | 133 | 45 | 288 | 186 | 2 |

The 32 awaiting-gold counts are verified candidates. All 45 unresolved v2 cases remain in the original review packet, including cases without a verifier-eligible claim. The separate v1 review packet still contains 26 cases. The original pilot outcome hash, v1 source and paired release hashes, and the v1 review hash were unchanged. The new pilot partitions above are a reprocessing under the candidate protocol. The original 44-case pilot remains separate.

Ollama reported 770 actual requests, 768 successful responses, two invalid extractions, zero verifier failures, and 43 cache hits. The ledger recorded 191,270 input tokens, 19,168 output tokens, and USD 0 cost. Summed provider latency was 1,232.13 seconds, with a mean of 1,600.17 ms and nearest-rank p95 of 3,667.35 ms per actual attempt. The validated Qwen digest is `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.

| Local artifact | SHA-256 |
| --- | --- |
| Source cases | `0c16a0964402e5cbd9d8fc435a2b899bb13771e6037fbb4e8668ea85d178d475` |
| Run freeze | `f1f1879b73db686f1d0dbeb52d096c3c26f0d7585ce875e5c363eb3ac5b069da` |
| Complete candidate outcomes | `facd1d44bc0401bbbc7d8f9ef39940c0bd7039a56f770f427e3420319c28bca0` |
| Aggregate report | `e4355377b02ddb4ee546c80d2d9d9a30ff602538a1076e34b002d392c601b857` |

## Training and calibration assessment

```powershell
python -m scripts.audit_v2_full_release data/updateset-v2-seed2407 results/updateset-v2-full
```

The audit verified 500 case identities, 601 distinct candidate IDs, the pilot partition, the source and outcome hashes, gold, labels, and all recorded feature values. There were no missing feature rows among eligible candidates. Ineligible candidates have no feature vector by design.

Nonpilot training has 89 positive and 112 negative case IDs. One negative case contributes two candidates. Nonpilot validation has 35 positive and 23 negative case IDs. Training has three positive families and four negative families. Validation has three positive and three negative families. Thus the binary fit has both classes, but hundreds of rows do not represent hundreds of independent scenarios.

Five features are constant in nonpilot training, including the 21-day observation gap and one-call budget fraction. Contradiction is determined by uncertainty in these fixtures. Lexical similarity has three distinct values. Validation varies only in lexical similarity. All 35 nonpilot validation positives share one complete feature vector. Training has two feature vectors that occur with both labels. This supports an exploratory fit on a narrow synthetic task, with inadequate independent support for a reliable calibration or generalization claim. More independent, varied conflict families, richer timing, provenance and budget variation, and blinded human review remain needed. No controller fit or calibration ran.
