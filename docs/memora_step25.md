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
python -m scripts.audit_reader_contract third_party/Memora results/memora-step24-final results/memora-step25 data/models/nli-deberta-v3-xsmall-a150876 results/updateset-v3-final/outcomes.jsonl
python -m scripts.summarize_memora_failure_isolation third_party/Memora results/memora-step25 docs/memora_step25_artifacts
python -m pytest -q
```

The extraction checkpoints and errors from Step 24 are read-only dependencies. The first command exports raw diagnostic outputs and proposed human-review evidence to the ignored local directory. Only redacted aggregate metrics and a numbered failure matrix live under docs.

## Observed stage isolation

Source evidence was found for all 15 questions under the nomination protocol. These 79 question–turn pairs are evidence candidates, with incomplete or uncertain semantics still pending human review. Nine nominations shared a source turn with any extracted claim. Seven survived in B2 memory at question time, and all seven reached the structured reader context. Thus the clearest measured structured-path gaps occur before retrieval. This source-ID comparison does not certify that the stored value correctly expressed a fact or rule out retrieval errors on as-yet unreviewed supporting turns.

Direct transcript retrieval recovered 47/79 nominations and the source oracle supplied 61/79. The oracle omitted 18 through its common top-eight envelope, leaving some multi-event questions incompletely evidenced. The B2 context recovered 7/79. Structured B2 produced one nonempty answer, 13 abstentions, and one invalid response. The transcript condition produced five answers, nine abstentions, and one invalid response. The source oracle produced seven answers, five abstentions, and three invalid responses. The two bypasses increased access to nominated evidence but left reader failures present.

The four unique Step 24 terminal requests were reconstructed from the old prediction keys, frozen policies, and preserved replay responses. Both long drafting outputs stopped at the 256-token ceiling before completing JSON. The two recommendation errors returned well-formed JSON with a null answer and two citations, violating the reader's abstention contract. Both patterns reproduced without changing the prompt or decoder. The two-request supplemental field probe disambiguates the recommendation failures without storing generated text in the published results.

On ten fictional reader fixtures, the pinned reader passed 6/10. It passed 4/5 answerable cases and 2/5 unanswerable cases. The other four emitted invalid outputs, including three unanswerable questions with distractor evidence. The adaptation judged the benchmark separately. On twelve independent fictional yes/no cases, Qwen matched 12/12 and Llama 10/12. Llama made one false-positive and one false-negative judgment. This checks limited binary behavior; human confirmation of benchmark scoring remains pending.

## Adapted development scores

| Representation | Nominated turns in reader context | Nonempty / abstention / invalid | Scored | Memory-presence checks | Forgetting-absence checks | Macro FAMA |
| --- | ---: | --- | ---: | --- | --- | ---: |
| Structured B2 | 7/79 | 1 / 13 / 1 | 14/15 | 0/37 | 22/22 | .000 |
| Transcript diagnostic | 47/79 | 5 / 9 / 1 | 14/15 | 6/37 | 18/20 | .106 |
| Source-oracle diagnostic | 61/79 | 7 / 5 / 3 | 12/15 | 12/34 | 19/20 | .233 |

On the ten questions scored in all three arms, macro FAMA was .000, .123, and .204, respectively. The bypass improvements on this shared comparison set demonstrate a source-access bottleneck under the local diagnostic. They leave open whether the extra content is safe to reveal and useful on new histories. Two of 20 omission checks failed for the transcript diagnostic and one of 20 failed for the oracle, reinforcing the exposure risk. No scored reasoning question earned positive FAMA in any arm, and a steps question with all seven nominations retrieved still elicited abstention. Stronger evidence access alone did not resolve reader and multi-event reasoning failures. There were no benchmark judge execution errors. Semantic disagreement with a human benchmark reviewer has not been measured.

## Resources, tests, and review

- Main diagnostic, terminal reproductions, and judge fixtures took 166.47 seconds wall time. The main reader used 40 fresh requests, 14 cache hits, 12,508 input and 1,951 output tokens. The four historical error reproductions used 1,379 input and 577 output tokens. The two supplementary schema probes used 641 input and 65 output tokens.
- Benchmark adjudication used 124 fresh requests, four cache hits, 19,616 input and 1,037 output tokens, and 98.27 seconds wall time. The full milestone used 194 requests, 36,961 input and 3,822 output tokens, and 246.95 seconds of summed fresh-provider latency. Spending was USD 0.
- All 104 discovered tests and 36 subtests passed, with the existing third-party AnyIO warning. The result includes tests discovered in the pinned upstream checkout.
- The local human review worksheet is `results/memora-step25/human-review.md`. It includes every question, scoped source candidates, retained source references, answers and unresolved judgments. None is marked human-approved.

[Failure matrix](memora_step25_artifacts/failure-matrix.csv) · [Evidence and answer comparison](memora_step25_artifacts/comparison.svg) · [Stage attrition and FAMA](memora_step25_artifacts/stage-isolation.svg) · [Aggregate and shared-question results](memora_step25_artifacts/aggregate.json)
