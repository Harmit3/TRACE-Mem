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
