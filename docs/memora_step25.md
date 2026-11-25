# Step 25 · Failure isolation and retrieval recovery

Step 25 uses the full 151-session development history and 15 previously frozen weekly questions from Step 24. The source nominations, transcript exclusions, common context envelope, reader controls, and judge controls were committed at `57eac6c` before inference. No controller or extractor behavior is changed. The held-out personas remain isolated.

## Evidence boundary

For each question, source turns were nominated using the public question and chronological user messages only. The restricted benchmark rubric, evidence annotations, and expected answers were not used to choose source excerpts, build either index, or prepare reader input. The 79 question–source nominations are analyst proposals with pending human review. Some are partial, especially compound calculations, draft revisions, and recommendations. Source alignment by turn ID measures recovery of nominated evidence. It does not certify factual coverage, semantic correctness, or exhaustive recall.

- **Structured B2** replays the preserved Step 24 extracted claims under the original temporal policy, then uses MiniLM top-8 retrieval at the question cutoff.
- **Transcript diagnostic** ranks chronological user turns directly using the same MiniLM checkpoint and excludes already identified edit sessions, removed material, assistant utterances, and future evidence. Reliable deletion and restriction enforcement cannot be established for text indexing. This arm is isolated to the local development diagnostic and is unsuitable for deployment. Its raw outputs and excerpts remain local.
- **Source-oracle diagnostic** supplies the manually nominated verbatim turns in frozen order. It uses the same cutoff and privacy exclusions. Its source selection observes the public question but sees no expected answer. The same eight-item and conservative 3,000-byte envelope can truncate long nomination lists. The separate label distinguishes source access from automated retrieval.

All three arms use the unchanged pinned Qwen reader, 4,096-token context, 256-token output cap, seed 23, and citation validator. The byte envelope is conservative rather than a tokenizer count, and actual provider tokens are reported separately. The rubric-only process applies the same adapted local Qwen judge and exact pinned FAMA arithmetic as Step 24. Llama and Qwen also receive the same newly frozen fictional adjudication cases. No scientific ground-truth accuracy claim follows from the small fixtures or the shared Qwen identity of reader and judge.

## Reproduction

```powershell
python -u -m scripts.run_memora_failure_isolation third_party/Memora results/memora-step24-final results/memora-step25 data/models/nli-deberta-v3-xsmall-a150876 results/updateset-v3-final/outcomes.jsonl
python -m scripts.summarize_memora_failure_isolation third_party/Memora results/memora-step25 docs/memora_step25_artifacts
python -m pytest -q
```

The extraction checkpoints and errors from Step 24 are read-only dependencies. The first command exports raw diagnostic outputs and proposed human-review evidence to the ignored local directory. Only redacted aggregate metrics and a numbered failure matrix live under docs.
