# Step 24 · Full weekly Memora development diagnostic

Step 24 intentionally runs the unchanged original automatic extractor across the complete reserved weekly development persona, including all 15 official questions. This is a separately declared diagnostic. The failed extraction promotion gates and prior findings remain part of the research record. The reserved held-out personas remain outside all inference and scoring.

Commit `5dcc614` froze the persona, questions, policies, caps, seeds, and metrics before requests. The pinned upstream source and conversation/rubric tree IDs are inherited from [Step 19](memora_step19_freeze.json). The source adapter passes only session text and chronological metadata to extraction. Retrieval and generation receive only filtered memory and answer-blind question fields. Scorer labels are confined to the separate adjudication process.

## Coverage, spending, and scoring

- B0–B5, T1, T1-no-NLI, T2 and H-paced share the original automatic extraction, local Qwen reader and direct-v2 verifier, and MiniLM top-8 retrieval. The learned policies use the committed T1 artifacts. Full T1 and T2 use pinned DeBERTa evidence; no-NLI and H-paced do not use contradiction scores.
- Fixed-stream exact allocations floor the requested percentages of the frozen B2 candidate count. Closed-loop hard caps floor the same percentages against an exogenous budget reference of 15 opportunities, corresponding to 0, 1, 3, 7 and 15 calls. T2 and H-paced are tested at planning horizons of 5, 15 and 30 with the same caps. No realized candidate count enters closed-loop cap construction or its adaptive decision rule. The planned horizons are a declared stress test, not fitted forecasts.
- Closed-loop verification opportunities can differ from the fixed B2 stream because state can diverge. Achieved coverage uses the fixed-stream count as a shared denominator and is undefined if that count is zero. Actual calls are counted once per method, budget, seed and unique question cutoff, even if several questions read that state. Fixed-stream and closed-loop comparisons stay separate. B4 uses five seeds, while deterministic methods run once per cell.
- The structural audit counts same-effective-date and same-observation-date conflicts separately, plus multiple simultaneously eligible target facts, deferrals and exact deletion resolution. The event-like predicate heuristic identifies possible multi-valued collisions. It cannot establish from predicate names alone that competing facts should coexist or that a deletion was missed in extraction.
- Storage is the serialized payload of the unique facts visible on at least one observed effective date at the cutoff. It excludes Python heap, model weights, SQLite and raw source text. Reader abstentions and judge/reader errors are counted separately. Macro FAMA averages scored questions with explicit coverage. Presence/absence counts retain their denominators. Historical wording is flagged by a frozen lexical rule, rather than treated as a validated temporal question category.
- The judge is the same adapted local Qwen version previously checked on fictional fixtures. The offline join uses the exact upstream FAMA function. Shared model identity and the small validation set limit judge independence and reliability. Published hosted-judge scores and this diagnostic have different adjudication configurations.

## Run and resume

```powershell
python -u -m scripts.extract_memora_full third_party/Memora results/memora-step24-full --reuse results/memora-step22/responses.sqlite
python -u -m scripts.replay_memora_full third_party/Memora results/memora-step24-full --outcomes results/updateset-v3-final/outcomes.jsonl --nli data/models/nli-deberta-v3-xsmall-a150876
python -u -m scripts.judge_memora_full third_party/Memora results/memora-step24-full --validation results/memora-step20-validation/report.json
python -m scripts.render_memora_full results/memora-step24-full docs/memora_step24_artifacts
python -m pytest -q
```

Each phase refuses a mismatched freeze and reuses completed work from the same directory. Extraction checkpoints a session, replay checkpoints a cutoff/cap/seed/horizon combination, and adjudication checkpoints a distinct answer and rubric evaluation. An optional read-only import brings only successful keyed responses into the new extraction cache. Prior ledgers, predictions, and caches are preserved. The first launch encountered a Windows SQLite attachment issue before any model calls. Commit `1e00c4a` corrected the cache import and restarted in a fresh directory.
