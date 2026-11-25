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
