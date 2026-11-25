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
