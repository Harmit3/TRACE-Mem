# Memora source audit

Preparatory research notes for WP1. The inventory and session metadata checks used a temporary clone outside the TRACE-Mem worktree with no checkout.

## Source and inventory

- Memora revision `a6493188efc836d6511ed5e4163fe3ba87da30ff`. The dataset documentation explicitly applies Apache-2.0 to the data. Use an external checkout and preserve upstream license and attribution if any redistribution is needed. [Pinned dataset documentation](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/data/README.md)
- LongMemEval code revision `9e0b455f4ef0e2ab8f2e582289761153549043fc` (MIT). Use the cleaned dataset revision `98d7416c24c778c2fee6e6f3006e7a073259d48f` (MIT in the dataset card). Reserve the oracle variant for explicitly labeled oracle experiments because upstream selects its sessions using evidence. [Code and release notes](https://github.com/xiaowu0162/LongMemEval/tree/9e0b455f4ef0e2ab8f2e582289761153549043fc) [Pinned dataset card](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/98d7416c24c778c2fee6e6f3006e7a073259d48f)

| Memora period | Session files | Rubric files | Total Git blob bytes | Questions documented upstream |
| --- | ---: | ---: | ---: | ---: |
| Weekly | 1,551 | 10 | 6,695,643 | 150 |
| Monthly | 6,150 | 10 | 25,201,413 | 150 |
| Quarterly | 19,913 | 10 | 82,755,431 | 300 |

Reproduce the inventory with `git -C <memora-clone> ls-tree -r -l a6493188efc836d6511ed5e4163fe3ba87da30ff data`. Group by period, count `conversations/session_*.json` and `evaluation_questions_*.json` separately, and sum the size column for both. The question audit below independently confirms the documented totals. Local tools reported Git 2.47.1.windows.2 and Python 3.14.0. The Python launcher listed only 3.14, while the TRACE-Mem setup targets 3.11. The inventory used Git and PowerShell with zero model calls and zero model tokens.

## Replay and scoring boundaries

The metadata audit streamed `git -C <memora-clone> archive HEAD data` at the pinned Memora revision into Python 3.14.0. It parsed session JSON and emitted only aggregate counts. For each period, each of the ten persona histories had zero duplicate session IDs. Across all 27,614 sessions there were zero missing documented top-level keys, filename/ID mismatches, persona/path mismatches, or sessions with non-increasing turn numbers. Sorting each history by numeric session ID yielded zero adjacent date inversions.

| Period | Adjacent sessions sharing a date within a history |
| --- | ---: |
| Weekly | 1,481 |
| Monthly | 5,870 |
| Quarterly | 18,993 |

This confirms that date alone cannot order sessions. The proposed replay order within a persona and period is date, numeric session ID, then turn number. These checks cover key presence and order. They do not validate nested content or establish that histories from different periods are independent.

- Session records document `session_id`, `date`, `persona`, `session_type`, `operation`, `operation_details`, and `conversation` with numbered turns and speaker/message fields. Treat `share_memory`, the operation fields, and session type as benchmark annotations. A proposed text-only replay would allow dates, session and turn identifiers, speaker and message into the model pipeline.
- Question files organize remembering, reasoning and recommending questions. Allow question text and relevant query time at inference. Restrict evidence fields, rubric subquestions and expected answers to the scorer. The released annotations describe benchmark evidence and expected omissions. Independently annotate TRACE-UpdateSet decisions and verification utility.
- Hold out complete personas across periods to account for potential overlap, then freeze exact question IDs and artifact hashes before tuning.
- Distinguish explicit removal requests from supersession during replay. Test that superseded permitted facts remain available to historical queries and that deleted payloads do not survive in searchable history, caches or logs. Use synthetic development fixtures first.
- Follow the official agent evaluation path under `evals/agent_eval/`. The shared `fama_score` lives in `evals/model_eval/model_based_evaluator.py`. The official judge checks recall and omission separately. Validate missing answers, abstentions, judge failures and questions with no omission checks before claiming scorer parity. The official aggregator is `evals/model_eval/aggregate_results.py`. [Pinned evaluation guide](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/evals/README.md)

## Question metadata

The audit streamed the same Git archive into Python and grouped sessions and rubrics by period and persona. All 600 questions have a session on the question date in the matching history. Zero histories contain a session dated after a matching question, and there were zero duplicate question IDs within histories. Recounting checks by type matched every rubric's declared total, recall count and omission count. Only aggregate metadata was emitted.

| Period | Remembering | Reasoning | Recommending | Questions without omission checks |
| --- | ---: | ---: | ---: | ---: |
| Weekly | 50 | 50 | 50 | 52 |
| Monthly | 50 | 50 | 50 | 50 |
| Quarterly | 100 | 100 | 100 | 102 |

The dates support replaying each released history through the question date inclusive. Document the end-of-day assumption because date-only fields cannot establish finer query placement relative to same-day sessions. Include questions with and without omission checks in scorer parity tests.

Remaining audit work includes deeper nested schema checks, duplicate-content checks, deletion validation, a frozen subset manifest, and a timed synthetic smoke test to estimate evaluation cost. Assessed implementation requires the team's written instructor permission record in `docs/ethics_and_permissions.md`.
