# Experiment log

## Memora replay adapter synthetic check

Codex implemented and tested the text-only adapter. Team review is pending. The adapter reads session JSON from one persona-period directory, validates provenance and turn order, and uses an inclusive date cutoff. It opens no rubric files and emits no annotation fields. Invalid sessions fail before any events are yielded. Benchmark source and terms are recorded in the [data audit](data_audit.md).

Run `python -m unittest discover -s tests -v` from the repository root. On Python 3.14.0 the command reported:

```text
test_malformed_history_fails_before_emitting_events (test_memora.MemoraReplayTest.test_malformed_history_fails_before_emitting_events) ... ok
test_replay_orders_numerically_and_includes_cutoff_day (test_memora.MemoraReplayTest.test_replay_orders_numerically_and_includes_cutoff_day) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.080s

OK
```

Standard library dependencies only. The fixtures have fixed inputs and no random seed. No model, model calls, tokens, or model cost. No held-out histories were replayed with the adapter.

## Temporal memory synthetic check

Codex implemented the in-memory transition engine and exact entity/predicate retrieval. The engine uses inclusive start dates and exclusive end dates. The caller supplies explicit supersession targets and opaque source references. Deletion removes the payload from the store and blocks reuse of the deleted ID. No persistence, index, or model cache is present in this milestone. Restart and cache privacy still require integration tests when those layers exist.

From `origin/main` at `e0fa071`, `python -m unittest discover -s tests -v` reported `Ran 6 tests in 0.021s` and `OK` on Python 3.14.0. The four added cases cover correction and history, visits and expiry, deletion, and deferral and invalid transitions. Standard library only, deterministic fixtures, no seed, model calls, tokens, or model cost. Human review is pending.

GitHub's pull-request integration previously returned HTTP 403. The [temporal memory comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/temporal-memory?expand=1) is available for manual review.

## Claim extraction and baseline replay

Codex implemented the structured extraction prompt and parser, predicate/value conflict detection, and B1/B2 fact transitions. B1 appends confirmed claims and obeys explicit deletion. B2 defers unresolved conflicts and supersedes only on an explicit correction with a unique eligible target and later effective date. Both currently use exact predicate and value matching. Semantic retrieval and live model integration remain open.

`python -m unittest discover -s tests -v` reported `Ran 7 tests in 0.015s` and `OK` on Python 3.14.0. The integrated baseline test uses a fixed completion function and checks identical replay traces on repetition. No model calls, tokens, costs, or held-out evaluation. Human review is pending.

[Manual stacked comparison](https://github.com/Harmit3/TRACE-Mem/compare/feat/temporal-memory...feat/claim-baselines?expand=1)

## Verification selection and accounting

Codex implemented seeded random and ranked exact-count selection for the common fixed stream, plus call accounting that charges failures against the cap. These are policy components. Verifier-driven state transitions, closed-loop replay and learned scoring remain open.

`python -m unittest discover -s tests -v` reported `Ran 9 tests in 0.021s` and `OK` on Python 3.14.0. The standard-library fixtures use seed 7 for random selection and an injected timeout for failure accounting. No model calls, tokens, costs, or benchmark scores. Human review is pending.

[Manual stacked comparison](https://github.com/Harmit3/TRACE-Mem/compare/feat/claim-baselines...feat/verification-budget?expand=1)

## Logistic scoring

Codex implemented deterministic L2-regularized logistic training with training-only feature normalization and score validation. This milestone uses synthetic labels to exercise learning and equal-size selection. Feature extraction, independent annotation, held-out calibration, and threshold selection remain pending.

`python -m unittest discover -s tests -v` reported `Ran 11 tests in 0.049s` and `OK` on Python 3.14.0. Standard library only. Full-batch optimization uses no random initialization. The random comparison uses seed 7. Zero model calls, tokens, and model cost. Human review is pending.

[Manual stacked comparison](https://github.com/Harmit3/TRACE-Mem/compare/feat/verification-budget...feat/logistic-controller?expand=1)

## Verified transition integration and real-data ingest check

Codex connected the verifier to chronological temporal replay. A selected single, eligible conflict can replace a fact only on an update verdict. A timeout leaves the existing fact intact and consumes the call. Other verdicts currently defer. Policy-specific gates and the live verifier and reader remain to be wired.

`python -m unittest discover -s tests -v` reported `Ran 12 tests in 0.048s` and `OK` on Python 3.14.0.

For an ingest-only smoke check, stream `git -C <memora-clone> archive a6493188efc836d6511ed5e4163fe3ba87da30ff data/weekly/content_writer/conversations` into a temporary directory and call `list(replay(history))` for the weekly content-writer history. This is outside the proposed held-out pilot. The run printed `sessions 151 events 2390 roles {'user': 1163, 'assistant': 1227}` and `elapsed_seconds 1.457` including extraction from the archive. No rubric files, random seed, model calls, model tokens, or model cost. This measures ingestion coverage only. No official scoring was run. Model API credentials for the official judging path were unavailable in the environment.

[Manual stacked comparison](https://github.com/Harmit3/TRACE-Mem/compare/feat/logistic-controller...feat/verifier-replay?expand=1)

## B4 and B5 matched replay

Codex integrated B4 random and B5 heuristic selection into chronological replay. The paired entry point extracts once, freezes evidence from B2, and enforces the same exact integer call target for both methods. Mock tests cover chronological calls from synthetic Memora files, score ties, stable seeds, invalid or infeasible budgets, zero-budget equivalence to B2, timeout and malformed verdicts, and a stale target after policy divergence. Read [the evaluation protocol](evaluation_protocol.md) for the distinction between fixed-stream and closed-loop comparisons.

Base revision `1c9e119`. On Python 3.14.0, `python -m unittest discover -s tests -v` reported `Ran 16 tests in 0.056s` and `OK`. Standard library only. The paired tests use seed 2 and injected extraction and verification providers. No live model calls, tokens, provider charges, or benchmark scores. Human review is pending.

The GitHub integration previously returned HTTP 403 for pull-request creation. Use the [manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/budget-matched-baselines?expand=1).

## T1 chronological replay

Codex implemented the eight README features as deterministic lexical and rule proxies and wired logistic scores into both the fixed-stream B4/B5/T1 diagnostic and closed-loop T1 replay. The fixed-stream diagnostic uses chronological tie-breaking and equal realized attempts. Closed-loop replay uses the current memory, remaining call fraction, and a supplied threshold under a hard cap.

Base revision `6904a06`. On Python 3.14.0, `python -m unittest discover -s tests -v` reported `Ran 22 tests in 0.059s` and `OK`. Standard library only. New tests cover feature values and order, invalid inputs, reproducible selection with seed 2, live state updates, budget exhaustion, and failed verification. Tests use synthetic coefficients and mock providers. No independent training or calibration, model calls, tokens, charges, or benchmark results. Human review is pending.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/t1-trace-controller?expand=1)

## Semantic retrieval and NLI wiring

Codex implemented local provider adapters, prefiltered top-k retrieval, and optional NLI and cosine features for both T1 replay paths. Named-label resolution supports checkpoints with different output orders. An integration fixture selects a different candidate through NLI, preserves the equal B4/B5/T1 call target, and checks that a rubric sentinel never reaches the model input boundary.

Base revision `d65289b`. On Python 3.14.0, `python -m unittest discover -s tests -v` reported `Ran 28 tests in 0.103s` and `OK`. The integration fixture uses seed 2, deterministic embeddings and mock NLI, extraction and verification. No real model inference, paid API calls, or benchmark measurements. The optional direct dependencies and reference checkpoint pins are in the [semantic model guide](semantic_models.md).

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/semantic-retrieval-nli?expand=1)

## TRACE-UpdateSet v1 generation

Codex implemented and exercised the [independent dataset pipeline](updateset.md) on base `8b43848`. The generate, validate and annotation-packet commands in that guide succeeded on Python 3.14.0 in 0.896 seconds combined. The annotation command printed `{"pending_cases": 30}`. Standard library only, seed 23, with no benchmark inputs, model calls, tokens or cost.

| Split | Rows | Synthetic rule gold | Awaiting human gold | Helpfulness labels |
| --- | ---: | ---: | ---: | ---: |
| Train | 140 | 120 | 20 | 0 |
| Validation | 42 | 36 | 6 | 0 |
| Test | 28 | 24 | 4 | 0 |
| Total | 210 | 180 | 30 | 0 |

The generated and validated manifests matched. `cases.jsonl` SHA-256 is `c42b23464cc25c86a912b720af3509b2601003cf55ff24fce4a9c6b16012fba4`. Actual paired outcomes and human records are pending. No benchmark evaluation or controller training ran. `python -m unittest discover -s tests -v` reported `Ran 35 tests in 1.801s` and `OK`. Mock decisions and annotation-format examples existed only in test fixtures.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/trace-updateset?expand=1)

## T1 training infrastructure

Codex implemented gold-blind paired collection, scikit-learn training and validation calibration, budget-aware threshold selection, and JSON model artifacts. The tests use synthetic decisions, dataset seed 23 and training seed 7. They exercise fit, calibration diagnostics, artifact round trip, replay, train-only means, test-outcome isolation and failure handling. Python 3.14.0 and scikit-learn 1.8.0 on base `be7dd90`. No live model calls, tokens or cost.

The existing 210-case release validated with zero helpfulness labels. Only test fixtures were fitted. No research model, calibration result or benchmark metric was produced. `python -m unittest discover -s tests -q` reported `Ran 40 tests in 3.270s` and `OK`.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/controller-training?expand=1)

## LLM providers and resumable outcome collection

Codex implemented three HTTP adapters, validated task prompts, durable request and spending accounting, an ignored response cache, a commit guard, and a TRACE-UpdateSet collection CLI. The offline tests simulate responses and failures. The resume fixture uses dataset seed 23 and provider seed 7. Base revision `484d67c`. Python 3.14.0 and standard-library HTTP and SQLite for providers. `python -m unittest discover -s tests -v` reported `Ran 48 tests in 3.892s` and `OK`.

No live inference, paid requests, actual model tokens, charges, or research labels were produced. A loopback Ollama catalog probe found no reachable service. The [provider guide](llm_providers.md) documents commands and ledger assumptions.

The staged-file guard initially flagged a credential-shaped string in its own test fixture. The fixture now assembles the synthetic value at runtime so the guard can remain enabled without a test-file exemption.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...feat/llm-providers?expand=1)

## Local Ollama readiness and live development smoke

On base `7ce2ee9`, Codex started Ollama 0.40.13 on loopback with cloud disabled and verified the installed Llama 3.2 3B Q4_K_M digest. See [local setup](ollama_local.md) for hardware, license, and exact collection command. No model downloads or paid requests.

`python -m scripts.smoke_ollama --model llama3.2:3b --output results/ollama-smoke-initial` used two fresh ledgers and seed 23. Six of eight responses validated. Both correction extractions failed schema validation. The uncertain extraction was empty and the uncertain verification returned `update` in both passes. An intermediate run with JSON schema constraints alone still had six valid responses. A synthetic diagnostic call showed invented same-day expiry and multiple predicates on the correction, so Codex added examples and explicit instructions to omit unstated dates.

`python -m scripts.smoke_ollama --model llama3.2:3b --output results/ollama-smoke-examples` then returned these actual results:

| Task and case | Output in both passes | Pass 1 ms | Pass 2 ms |
| --- | --- | ---: | ---: |
| Extract correction | job, Birch Lab, correct | 785.3 | 490.9 |
| Verify correction | update | 278.2 | 237.7 |
| Extract uncertain claim | job, Cedar Lab, uncertain | 503.2 | 486.1 |
| Verify uncertain claim | insufficient_evidence | 257.6 | 254.0 |

Eight of eight responses validated and both passes agreed. Ollama reported 927 input and 80 output tokens per pass, zero cache hits and USD 0 provider cost. These are prompt-development examples, with no independent evaluation, training labels or benchmark measurements.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...docs/ollama-local-readiness?expand=1)

## Frozen Ollama verifier validation

Codex verified the loopback runtime, froze the development fixtures and go/no-go criteria at `e063325`, then ran `python -m scripts.validate_ollama_verifier --output results/ollama-verifier-dev-seed23` on base `b3d92c0`. The command exited 1 for a failed gate. The 12 uncached local calls yielded seven correct decisions, five false updates, zero missed updates and zero technical failures. Reported usage was 3,229 input and 102 output tokens, 5,285.85 ms summed latency and USD 0 provider cost. The [validation report](ollama_label_collection.md) records the exact configuration and SHA-256 fingerprints.

The pending-case export printed 26 cases, 20 train and six validation. The 78-case collection did not run. All research helpfulness counts remain zero. `python -m unittest discover -s tests -q` reported `Ran 50 tests in 2.989s` and `OK` on Python 3.14.0.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/ollama-label-collection?expand=1)

## Revised local verifier validation

On base `a6dd6ac`, Codex analyzed the original false updates and froze two revisions and a fresh 40-case validation at `ce2d8f9`. `python -m scripts.validate_ollama_verifier_v2 --output results/ollama-verifier-v2-frozen` exited 1. The original, direct revision and evidence revision made 21, 23 and 23 false updates respectively. All 160 calls validated, with zero retries, failures, cache hits or provider cost. Ollama reported 10,789/327, 10,909/321, and 25,492/1,543 input/output tokens respectively. See [the validation report](ollama_verifier_v2.md) for exact model identity, hashes, configuration, accuracy, recall, precision, latency and the hardware-based candidate recommendation.

`python -m unittest discover -s tests -q` reported `Ran 52 tests in 3.925s` and `OK` on Python 3.14.0. The original report and 26-case review packet were preserved. No research labels were collected and no weights were downloaded.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/ollama-verifier-v2?expand=1)

## Qwen2.5 local verifier comparison

Codex verified the merge of PR #17, downloaded the approved Qwen 7B Q4_K_M checkpoint, checked local license and model digests, and froze the comparison at `06843ae`. `python -m scripts.compare_local_verifiers --qwen-digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e --output results/qwen-llama-frozen` exited 0. Qwen passed with 38/40 correct and zero false updates. Llama scored 18/40 correct with 22 false updates. All 80 responses validated with zero technical failures, cache hits, or provider cost. The [comparison report](qwen_verifier.md) preserves setup, resource measurements, prompt and schema audit, observed smoke variation, and full metrics.

No research labels were collected. The annotation packet SHA-256 remained `1dffda1962e49c1de62aa82f566bb31ba9148ec180adb78d6464111d2024ae08`. `python -m unittest discover -s tests -q` reported `Ran 54 tests in 3.178s` and `OK`.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/qwen-verifier?expand=1)

## Actual Qwen paired decisions on TRACE-UpdateSet

On base `7a455b0`, Codex verified the pinned verifier settings and ran the [documented local collection and release audit](qwen_updateset_outcomes.md). Ollama 0.40.13 served the validated Qwen direct-v2 model at seed 23. The collector returned `{"ok": 78}` with zero failures, cache hits, or cost, 23,614 input tokens, 962 output tokens, and 73,644.810 ms provider latency. The 60 training and 18 validation pairs all agreed. Gold-supported labels were 0 positive / 40 negative for train and 0 positive / 12 negative for validation. Twenty train and six validation labels remain pending human gold.

The outcome audit verified the source lineage and unchanged held-out test rows. No model fit ran. The original review packet hash was unchanged. The first test run exposed a Windows file lock in a SQLite test fixture. Closing the fixture connection fixed it. `python -m unittest discover -s tests -q` then reported `Ran 55 tests in 3.751s` and `OK`.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/qwen-updateset-outcomes?expand=1)

## TRACE-UpdateSet v2 paired pilot

On base `45b3c80`, Codex audited the v1 agreement and froze the 500-case generator, independent gold, family-balanced 44-case sample, and production B2 paired replay at `6fea82f`. The local Qwen pilot produced five positive and six negative training labels and three positive and seven negative validation labels. Two eligible cases still need gold, 20 cases had no eligible conflict, and one extraction failed. There were eight corrections, zero harmful anchor changes, seven changes that left the anchored state incorrect, and 28 unchanged decision traces.

The commands, observed split counts, hashes, settings, token usage and latency are in the [v2 protocol and report](updateset_v2.md). Python 3.14.0. `python -m unittest discover -s tests -q` reported `Ran 57 tests in 8.491s` and `OK`. V1 source and paired release hashes and the 26-case v1 review hash were unchanged. No training, paid inference or benchmark evaluation ran.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/trace-updateset-v2?expand=1)

## Full TRACE-UpdateSet v2 candidate release

On base `9ff82ee`, Codex froze the candidate protocol at `350e54e` and finished the 500-case local Qwen run. The logged command and complete split counts are in the [release report](updateset_v2_full.md). There were 313 verified candidates and 288 ineligible claims. Nonpilot counts were 89 positive / 113 negative for train and 35 positive / 23 negative for validation. The run logged 770 actual Ollama calls, 43 cache hits, two invalid extractions, 191,270 input and 19,168 output tokens, 1,232.13 seconds summed provider latency and USD 0 cost.

The release audit recomputed candidate features and labels and verified 500 rows and 601 unique IDs. The prior pilot and v1 artifacts were preserved. `python -m unittest discover -s tests -q` reported `Ran 61 tests in 10.424s` and `OK` on Python 3.14.0. No controller training, paid requests, or benchmark analysis ran.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/updateset-v2-full?expand=1)

## Controller feature-quality audit

On base `ca5bb0d`, Codex verified the full v2 release and froze a local diagnostic at `f8b9427`. The nonpilot records had four distinct train vectors across 232 eligible candidates and three validation vectors across 58. All 35 validation positives shared one vector. The recorded contradiction and uncertainty features were perfectly negatively correlated in training. No missing feature rows were found.

`python -m scripts.audit_controller_features data/updateset-v2-seed2407 results/updateset-v2-full --cached-minilm` used the cached MiniLM revision and produced 232 and 58 distinct vectors by replacing only cosine similarity in a diagnostic copy. The [feature audit](controller_feature_audit.md) records variances, correlations, family support, model versions, the ID-rendering correction and the proposed v3 design. The local report SHA-256 is `e7c339edaaabbed0beb9ceb341d2a4705836ad510cd2f3929340cac7070d3d09`. Python 3.14.0. No NLI inference, model downloads, paid calls, controller fit or benchmark evaluation. The frozen v2 artifact hash was unchanged.

`python -m unittest discover -s tests -q` reported `Ran 63 tests in 2.897s` and `OK`.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/controller-feature-audit?expand=1)

## TRACE-UpdateSet v3 feasibility pilot

On base `1ec58f6`, Codex froze 24 natural-text cases, 12 disjoint families, independent synthetic gold, and a shared v3 feature builder at `6f3b7f3`. The [pilot commands and report](updateset_v3.md) record 14 verified cases, seven positives, four negatives, three awaiting human gold, nine ineligible cases, and one invalid extraction. The run used the cached local MiniLM checkpoint and the validated Qwen direct-v2 verifier, with 38 local requests, 8,897 input and 962 output tokens, 81,315.10 ms summed latency and zero paid cost. NLI was deliberately missing pending approval. No controller fitting, full-scale collection or benchmark evaluation ran.

The v1 artifacts and annotated-data hashes were unchanged. The v2 release passed its audit with all 500 cases and 601 candidate IDs intact. `python -m unittest discover -s tests -q` reported `Ran 67 tests in 6.107s` and `OK` on Python 3.14.0.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/updateset-v3-pilot?expand=1)

## Step 16 local NLI validation and v3 reconstruction

On base `124e0f5`, Codex reused the previously downloaded checkpoint after integrity verification, preserved the original v3 run, and froze the independent set and gate at `5d766aa`. The [NLI report](updateset_v3_nli.md) contains the command, checkpoint provenance, confusion counts, probability ranges, all eight feature statistics and hardware snapshots. Accuracy was 20/24 and contradiction recall was 8/8 with four false contradictions on neutral cases. NLI mean latency was 76.08 ms on four CPU threads. All 14 eligible pilot feature rows were reconstructed into a separate local diagnostic. No original labels or features changed.

The coexistence check used one local Qwen request, with 270 input and 11 output tokens, 14,285.54 ms provider latency, and USD 0 cost. `python -m unittest discover -s tests -q` reported `Ran 70 tests in 5.953s` and `OK`. No full collection or training ran.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/v3-local-nli?expand=1)

## Final TRACE-UpdateSet v3 longitudinal release

On base `44fe6cc`, Codex froze the generator, gold and collector at `e58a91c`. The [release report](updateset_v3_final.md) records the commands, hashes, counts and audit. All 600 decision points completed. The run recorded 232 successful verification comparisons, 45 helpful, 167 not helpful, and 20 awaiting gold. The no-NLI projection preserves their labels and groups. All prior experiments were preserved.

Qwen reported 788 requests, 44 cache hits, 185,845 input and 20,362 output tokens and 1,099.063 seconds summed provider latency at zero provider cost. Four extraction failures were retained. MiniLM and NLI ran locally on CPU. No training, calibration fitting, paid requests or benchmark evaluation ran. `python -m unittest discover -s tests -q` reported `Ran 73 tests in 3.617s` and `OK`.

[Manual comparison](https://github.com/Harmit3/TRACE-Mem/compare/main...research/updateset-v3-final?expand=1)

## Step 18 · First fitted T1 on frozen longitudinal V3

- Collection merge PR #26 at `8211618`. Protocol commit `5f30bba`; model and threshold freeze `18ce948`. Seed 23, Python 3.14.0, scikit-learn 1.8.0, NumPy 2.4.2, Matplotlib 3.10.8. No inference calls, tokens or API spending during fit or scoring.
- The release audit reproduced 200 histories, 40 families, 726 candidate keys and 232 paired vectors. Frozen inputs, previous experiments and pending reviews were preserved. AI-assisted contribution was implementation, validation and experiment logging under the documented verbal coding authorization.
- At 25% rank-matched coverage, full T1 selected all 6 labeled helpful candidates in 10 calls, versus 5 for no NLI, 5 for seeded B4 and 0 for B5. Full T1 average precision was .849 versus .877 for the ablation. The paired family-bootstrap interval for the difference was [−.167, .083].
- The rerun reproduced the model parameters and thresholds, and evaluation JSON and all four figures were byte-identical. The independent partition has just 6 positives from 4 families. This was an exploratory fixed-prefix evaluation. No closed-loop or Memora performance was measured.
- [Protocol, exact commands, aggregate metrics and figures](t1_v3_training.md).
- Final regression suite: 75 tests and 36 subtests passed. Pytest emitted one third-party anyio deprecation warning.

### Step 18 reproducibility check after standing authorization update

Reran the release audit, fit both controller variants in a new ignored output directory, and reran independent scoring using the original committed fit freeze. Both fits reproduced the published numerical parameters, thresholds, and grouped selection scores. The aggregate evaluation JSON and four SVGs were byte-identical to the original local run. The published SVGs use LF line endings. The 75-test suite and 36 subtests passed with one third-party deprecation warning. This repeated scoring uses the existing evaluation partition and preserves the original artifacts.

## Step 19 · Local Memora integration and prefix smoke

- Reconciled training-branch authorization and artifacts with main at merge `77fb488`. Pinned Memora at `a6493188efc836d6511ed5e4163fe3ba87da30ff`. Froze the development and held-out subsets in `90ef6af` before inference. No held-out scoring rubrics were read.
- Ran the eight-session development prefix using pinned local Qwen, MiniLM and DeBERTa with frozen T1 artifacts. Across 55 user turns, 56 fresh requests, and 13 cache hits, extraction found two claims and zero eligible verifier conflicts. All 16 predictions abstained, with no errors. There were 10,820 input and 189 output tokens, 34.29 seconds summed provider latency and 44.23 seconds wall-clock. A rerun made zero new inference requests and added 69 cache hits.
- The separately frozen fictional conflict and deletion probe used five fresh requests and two NLI evaluations. One verification attempt per fixed-stream verifier system produced the updated answer, and all persistent methods suppressed the deleted value. The closed-loop T1 variants did not escalate the conflict. These are diagnostic observations.
- Official offline arithmetic parity confirmed for empty, recall-only, omission-penalty and clamped-at-zero cases. Official hosting and judging remain separate from local inference. No FAMA scores were produced. Spending was USD 0.
- TRACE-Mem test run passed 78 tests and 36 subtests. Test discovery with the local upstream checkout also passed 83 tests and 36 subtests. Both emitted one third-party deprecation warning. AI-assisted contributions include implementation, tests and reproducibility documentation.
- [Frozen configuration, exact run commands, official scoring audit and resource estimates](memora_step19.md).

## Step 20 · Development extraction audit and adapted local judge

- Started from PR #28 merge `06713f8` and froze the contextual prompt, 18 extraction cases, 12 binary judge checks, and gates at `3327581`. The original 55-turn prefix had seven clearly extractable focal turns by development review. Five emitted empty arrays, one categorized a calendar event as a job, and one captured the intended activity.
- At identical local Qwen settings, original precision/recall/F1 were .500/.417/.455, and contextual precision/recall/F1 were .600/.250/.353. Deletion targets matched 1/3 and 0/3. The contextual extractor failed promotion. The full development history was left unrun because neither extractor met acceptance criteria.
- Local judge agreement was 12/12 on predeclared fictional checks. On the original truncated predictions, all eight systems in each mode had four failed presence checks, seven passed absence checks, and 0.000 using pinned FAMA arithmetic. Every prediction abstained. This is an adapted local scoring smoke.
- Validation used 48 actual requests, 9,763 input tokens, 622 output tokens and 46.54 seconds wall time. Prefix adjudication used 11 actual requests, 165 cache hits, 1,178 input tokens, 91 output tokens and 9.48 seconds wall time. Spend was USD 0. Prior artifacts and held-out separation were preserved.
- All discovered tests passed, with 87 tests and 36 subtests including the pinned checkout. One third-party AnyIO deprecation warning remained. AI assistance covered implementation, fixture authoring, analysis and documentation. [Protocol and results](memora_step20.md).

## Step 21 · Evidence-grounded hybrid extraction

- Started at merged PR #29 at `077ca2e`; froze the single hybrid design, 20 fictional cases and gates at `17bbbf7`. Existing structured policies, T1 artifacts, and previous extraction failures were preserved.
- Exact F1 for original, contextual, Qwen hybrid and Llama hybrid was .267, .200, .316 and .100, respectively. Qwen hybrid recall was 3/16; each hybrid backend had 14 invalid responses and no exact deletion matches. The promotion gate failed. There was no complete development replay, no new benchmark score, and no held-out access.
- The unchanged T1 scored two original candidates, one Qwen hybrid candidate and one Llama hybrid candidate (contextual emitted none). Stored excerpt payload across isolated cases was 58 real bytes for Qwen and 132 for Llama, excluding structure overhead.
- Local runs used 76 requests, 17,466 input tokens and 2,796 output tokens, with 135.91 seconds wall time and USD 0 spend. Tests passed for 85 TRACE-Mem tests and 36 subtests. Workspace discovery including pinned upstream tests passed 90 tests and 36 subtests, with one third-party deprecation warning. AI assistance covered implementation, authored fixtures, analytics and technical documentation.
- [Architecture, observed metrics and bounded follow-up](memora_step21.md).

## Step 22 · Bounded Memora and downstream verification

- Started at merged PR #30 `d53b0db`; froze the first 12 development sessions, eight source-checked proposals, fictional temporal checks, and the budget grid at `6ae9387`. The worksheet includes 185 transcript rows and four explicit review questions. Human review remains pending.
- The automatic Memora stream emitted five claims. The span-oracle temporal methods retained seven of eight proposed facts. Both streams had no eligible verifier conflicts. All 32 adapted local FAMA rows scored 0.000 because the predictions abstained. Held-out personas and answers were untouched.
- On two fictional span-oracle histories, both frozen T1 variants scored 12/16 at four matched calls, while B4 scored 14/16 and B5 scored 16/16. Both T1 variants made zero closed-loop calls at every cap. These are diagnostic outcomes from two histories.
- The replay and separately labeled local scoring used 160 actual local calls and zero paid resources. All 92 discovered tests and 36 subtests passed. AI assistance covered implementation, source-span proposals, fictional fixtures, analytics and documentation. [Protocol, aggregate results and budget plot](memora_step22.md).

## Step 23 · Frozen T1 underspend and adaptive allocation

- Started from PR #31 at `8b76872`, then froze T2, H-paced, two new fictional histories and five random seeds at `1abd2e6` before verification inference. Neither extraction nor the frozen T1 artifacts changed. No Memora data was opened.
- The Step 22 oracle stream had zero of eight scores above cutoff. At a forced half-budget coordinate, three would cross. Full budget depresses the T1 logit by 1.901 relative to empty budget. Together with shorter observation gaps, lower provenance, and sparse explicit dates, this explains threshold underspend. The actual Memora prefix supplied zero eligible conflicts.
- At a 50% closed-loop cap, full T1 used four calls for 26/40, T2 used ten for 30/40, and H-paced used ten for 36/40. At the 100% cap, T2 and H-paced tied B3 at 38/40 using twenty calls. Under matched fixed-stream allocations, T2 and T1 have identical rankings. These outcomes do not establish a learned utility advantage.
- Twenty fresh local requests, 2,066 cache hits, 5,491 input and 225 output tokens, 22.92 seconds summed provider latency, and 46.73 seconds wall time. Spending USD 0. Tests passed with 95 tests and 36 subtests, including pinned upstream tests. AI assistance covered implementation, fixture authoring, analytics, and documentation. [Audit, tables and plots](t2_step23.md).

## Step 24 · Full weekly Memora development diagnostic

- Started at merged PR #32 at `5f0b684`. Froze the diagnostic in `5dcc614`. Used all 151 sessions and all 15 questions from the reserved weekly development persona. Extraction, controller artifacts and thresholds, previous promotion gates, and held-out personas were preserved.
- The original extractor emitted 88 claims across 1,163 user turns. B2 saw 27 clashes, ten eligible conflicts, and 18 unresolved exact deletion targets. The two frozen T1 variants used zero closed-loop calls. T2 and H-paced reached six of ten reference opportunities at the largest primary cap. Varying the horizon moved spending without improving answer quality.
- All policies had adapted local FAMA 0.000 on scored predictions at every budget and horizon. Across 2,400 rows, 2,184 were scorable, 2,034 abstained, and 216 had reader errors. No held-out question or published hosted evaluation was run.
- The completed phases recorded 1,125 fresh local requests, 215,908 input and 5,515 output tokens. The stopped replay ledger remains separate. Spend was USD 0. All 100 discovered tests and 36 subtests passed, including pinned upstream tests. AI assistance covered implementation, testing, analysis, and technical documentation. [Full results, budgets and plots](memora_step24.md).

## Step 25 · End-to-end failure isolation

- Started at merged PR #33 `5dbf815`; froze 15 question-only evidence nominations, privacy exclusions, common context limits, and fictional controls at `57eac6c` before inference. Preserved the 151-session extraction, frozen controllers, and held-out boundary.
- Of 79 nominated question–source pairs, nine were extracted, seven were represented by B2, and all seven appeared in its reader context. The transcript and oracle diagnostics supplied 47 and 61. Adapted macro FAMA was .000/.106/.233 across scored questions and .000/.123/.204 on the ten questions valid in all arms. Omission failures and unresolved deletion safety keep the raw-context arms diagnostic only.
- Reproduced two cap-truncated invalid JSON results and two null answers with two citations. The original reader passed 6/10 fictional fixtures. Qwen and Llama judges matched 12/12 and 10/12 frozen fictional checks. Human review of development evidence and answer adequacy remains pending.
- Local inference used 194 fresh requests, 36,961 input and 3,822 output tokens, with USD 0 spend. All 104 tests and 36 subtests passed. AI assistance covered implementation, source evidence proposals, fixture authoring, analysis and reporting. [Diagnostic, matrix and plots](memora_step25.md).
