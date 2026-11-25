# Memora local development replay

## Source and selection

The official Memora checkout is pinned to `a6493188efc836d6511ed5e4163fe3ba87da30ff`. Its code and released data are Apache-2.0. The repository and dataset remain in an ignored external checkout. The [source audit](data_audit.md) inventories all 27,614 sessions and 600 questions. The [frozen protocol](memora_step19_freeze.json) pins the conversations tree and rubric blob for each subset, verified against the pinned revision. [Pinned license](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/LICENSE) · [Pinned data documentation](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/data/README.md)

The development selection is the third weekly persona in path order and the first remembering question in file order. The plumbing smoke limits the transcript to the first eight sessions. Its predictions may lack the evidence needed by the question. The held-out pilot reserves the first two weekly personas across all periods, with 303 sessions and 30 questions in the weekly pilot. Only Git object metadata for those rubrics was inspected during this milestone. Commit `90ef6af` froze both partitions and the local run settings before inference.

## Replay

- Project only session dates, IDs, roles, and text. Extract each user event once and reuse the same claims across methods, replaying by date, session ID, and turn. The question object carries only its text, date, task and ID. Only text and an effective date enter the reader or retrieval. Gold checks, memory evidence, operation annotations, and share-memory markers stay outside inference.
- Use one pinned Qwen model for extraction, direct-v2 verification, and the citation-validated reader. Verifiers receive the current user turn and candidate facts. Use MiniLM top-8 ranking over visible facts for the exact persona. A single explicit ISO date selects a historical view, constrained to the question observation date. Questions with relative time, intervals, or multiple dates currently fall back to the question date.
- B0 is the no-persistent-memory floor and abstains without evidence. B1 appends assertions, B2 applies temporal transitions, and B3 verifies eligible conflicts up to the hard cap. All persistent policies handle exact-match deletion before retrieval. Indirect or paraphrased deletions can be missed if extraction does not resolve the target. Append-only B1 still enforces explicit privacy deletion.
- Fixed-stream B4, B5, full T1, and no-NLI T1 receive exactly the lesser of the configured cap and the B2 candidate count. B3 verifies the first eligible candidates up to the same cap. B5 ranks by extraction uncertainty. Scores use the fixed reference with budget fraction 1.0. A fixed-stream call is counted even when the selected B2 target has become stale in the intervention replay, and stale verdicts do not modify state.
- Closed-loop B4 draws a seeded verification decision with probability 0.25 at each live eligible conflict. B5 verifies uncertain candidates. Both T1 variants apply their committed thresholds to the shared V3 features and live remaining-budget fraction. The no-NLI variant uses the padded artifact and skips DeBERTa. Policy-specific call counts can differ under the shared hard cap. Memora text inputs do not supply validated evidence-source categories, so V3 provenance is recorded as unknown.
- The provider ledger tracks actual requests, token totals, failure statuses, cache hits, and aggregate provider latency. Verification attempts include failures and cache hits for budget fairness. The run also records end-to-end elapsed time and the pinned model/configuration freeze. Response caches and predictions contain public benchmark-derived text and stay in ignored local run directories.

## Local commands

```powershell
git clone --no-checkout https://github.com/geniesinc/Memora.git third_party/Memora
git -C third_party/Memora checkout --detach a6493188efc836d6511ed5e4163fe3ba87da30ff
python -m scripts.run_memora third_party/Memora --nli data/models/nli-deberta-v3-xsmall-a150876 --output results/memora-step19-smoke --smoke
python -m pytest -q
```

Reuse the same output directory and freeze to resume with the response cache. Keep a fresh output directory for the full single-question development run, which omits `--smoke`. The command exposes the development partition only. Use the [local model installation guide](semantic_models.md) and pinned [V3 NLI setup](updateset_v3_nli.md) to prepare cached checkpoints.

## Official scoring boundary

Memora FAMA combines per-question memory-presence accuracy and forgetting-absence accuracy with a penalty weighted by the fraction of omission checks. The runner reports operational metrics and generates predictions without judging. The separate scorer reads development rubrics only after inference and runs the exact pinned `fama_score` function on checks from an external adjudicator. Provide a JSON object with `judge_reference`, `predictions_sha256`, and `judgments`. Each judgment row identifies `mode`, `method` and `question_id`, and maps each rubric check ID to one yes/no value in `checks`. The scorer validates the prediction file hash, exact check coverage, and all row joins.

```powershell
python -m scripts.score_memora_checks third_party/Memora results/memora-step19-smoke/predictions.json results/memora-step19-smoke/judgments.json results/memora-step19-smoke/scored.json
```

The pinned agent evaluator uses OpenAI for its native reader and routes its three published judges through OpenRouter. The default judges are GPT-4.1, Claude Haiku 4.5 and Gemini 2.5 Flash. The official requirements include OpenAI, python-dotenv, tqdm, requests and agent-specific SDKs. The FAMA arithmetic has no remote dependency. A local or manual adjudicator can provide exploratory checks with documented provenance. Reproducing the published evaluation configuration requires its hosted judges. [Pinned evaluation guide](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/evals/README.md) · [Pinned agent scorer](https://github.com/geniesinc/Memora/blob/a6493188efc836d6511ed5e4163fe3ba87da30ff/evals/agent_eval/memory_to_answer.py)

## Observed smoke runs

| Run | Actual Qwen requests | Cache hits | Input / output tokens | Summed provider latency | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Memora eight-session prefix, cold response cache | 56 | 13 | 10,820 / 189 | 34.29 s | 44.23 s |
| Same Memora prefix, warm response cache | 0 new | 69 new | 0 / 0 new | 0 s new | 7.43 s |
| Fictional conflict and deletion diagnostic | 5 | 12 | 954 / 85 | 6.47 s | 16.55 s |

The Memora smoke processed 114 events, of which 55 were user turns, and extracted two claims with no extraction failures. The 16 method-by-mode predictions all abstained without reader errors. The prefix offered zero eligible verification conflicts. This run confirms schema, cutoff, retrieval and reader plumbing. It does not estimate memory quality. There were no external judges, FAMA scores, or paid calls.

The separately frozen fictional diagnostic at `211b290` ran with the same local task prompts. It extracted three claims and invoked DeBERTa twice. Qwen labeled the explicit employer replacement as an assertion. Closed-loop B2 deferred it, and neither T1 variant crossed its frozen threshold. Closed-loop B3 verified the claim and returned the new employer. In fixed-stream mode, B3, B4, B5 and both T1 variants used one logical call each and returned the new employer. All persistent methods removed the old value from historical retrieval. There were no verifier failures or reader errors. These observations describe one fictional transcript.

```powershell
python -m scripts.smoke_memora_conflict --nli data/models/nli-deberta-v3-xsmall-a150876 --output results/memora-step19-conflict
```

On the RTX 2060 with 6 GiB VRAM and approximately 23.9 GiB system RAM, Ollama reported 5.15 GB resident for Qwen, including 4.20 GB VRAM, with a 4,096-token context. MiniLM and DeBERTa ran on CPU. GB figures are decimal. The observed mean was 0.61 seconds per uncached provider request on the small Memora prefix. If average latency carries over and each user turn needs one request, extraction alone would take about 12 minutes for the full single-question development history (1,163 user turns) or 24 minutes for the two held-out pilot histories (2,337 user turns, counted from conversation metadata). These are planning estimates. Reader and verifier requests, CPU scoring, longer inputs, cold model loading, cache reuse, and official judging can change total runtime.

Before a held-out run, assess extraction coverage and indirect deletion handling on the complete development history, freeze the evaluation and scoring configuration, and choose either the hosted published judge setup with cost approval or a separately labeled exploratory adjudication protocol. The current CLI runs development only. Closed-loop and fixed-stream results should remain separately reported.
