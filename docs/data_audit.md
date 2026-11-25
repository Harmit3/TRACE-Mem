# Memora source audit

Preparatory research notes for WP1. The inventory below was collected from a temporary clone outside the TRACE-Mem worktree with no checkout. The remaining audit checks require record-level validation.

## Source and inventory

- Memora revision `a6493188efc836d6511ed5e4163fe3ba87da30ff`. The dataset documentation explicitly applies Apache-2.0 to the data. Use an external checkout and preserve upstream license and attribution if any redistribution is needed. [Pinned dataset documentation](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/data/README.md)
- LongMemEval code revision `9e0b455f4ef0e2ab8f2e582289761153549043fc` (MIT). Use the cleaned dataset revision `98d7416c24c778c2fee6e6f3006e7a073259d48f` (MIT in the dataset card). Reserve the oracle variant for explicitly labeled oracle experiments because upstream selects its sessions using evidence. [Code and release notes](https://github.com/xiaowu0162/LongMemEval/tree/9e0b455f4ef0e2ab8f2e582289761153549043fc) [Pinned dataset card](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/98d7416c24c778c2fee6e6f3006e7a073259d48f)

| Memora period | Session files | Rubric files | Total Git blob bytes | Questions documented upstream |
| --- | ---: | ---: | ---: | ---: |
| Weekly | 1,551 | 10 | 6,695,643 | 150 |
| Monthly | 6,150 | 10 | 25,201,413 | 150 |
| Quarterly | 19,913 | 10 | 82,755,431 | 300 |

Reproduce the inventory with `git -C <memora-clone> ls-tree -r -l a6493188efc836d6511ed5e4163fe3ba87da30ff data`. Group by period, count `conversations/session_*.json` and `evaluation_questions_*.json` separately, and sum the size column for both. Question totals come from the documented counts per persona. Local tools reported Git 2.47.1.windows.2 and Python 3.14.0. The Python launcher listed only 3.14, while the TRACE-Mem setup targets 3.11. The inventory used Git and PowerShell with zero model calls and zero model tokens.

## Replay and scoring boundaries

- Session records document `session_id`, `date`, `persona`, `session_type`, `operation`, `operation_details`, and `conversation` with numbered turns and speaker/message fields. Treat `share_memory`, the operation fields, and session type as benchmark annotations. A proposed text-only replay would allow dates, session and turn identifiers, speaker and message into the model pipeline.
- Question files organize remembering, reasoning and recommending questions. Allow question text and relevant query time at inference. Restrict evidence fields, rubric subquestions and expected answers to the scorer. The released annotations describe benchmark evidence and expected omissions. Independently annotate TRACE-UpdateSet decisions and verification utility.
- Compare candidate ordering against timestamp, numeric session ID and turn sequence. Check the relationship between question dates and available history before freezing a replay protocol. Hold out complete personas across periods to account for overlapping histories, then freeze exact question IDs and artifact hashes before tuning.
- Distinguish explicit removal requests from supersession during replay. Test that superseded permitted facts remain available to historical queries and that deleted payloads do not survive in searchable history, caches or logs. Use synthetic development fixtures first.
- Follow the official agent evaluation path under `evals/agent_eval/`. The shared `fama_score` lives in `evals/model_eval/model_based_evaluator.py`. The official judge checks recall and omission separately. Validate missing answers, abstentions, judge failures and questions with no omission checks before claiming scorer parity. The official aggregator is `evals/model_eval/aggregate_results.py`. [Pinned evaluation guide](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/evals/README.md)

Remaining audit work includes missing-field and duplicate counts, timestamp and deletion validation, a frozen subset manifest, and a timed synthetic smoke test to estimate evaluation cost. Assessed implementation requires the team's written instructor permission record in `docs/ethics_and_permissions.md`.
