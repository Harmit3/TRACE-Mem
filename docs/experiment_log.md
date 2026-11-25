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
