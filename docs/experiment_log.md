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
