# Step 32 independent LongMemEval diagnostic

This evaluation uses the author-published cleaned LongMemEval_S bundle. It is an exploratory external diagnostic of the frozen TRACE-Mem stack. Previous TRACE-Mem experiments and the Memora held-out boundary were preserved.

## Source and freeze

- Official repository commit `9e0b455f4ef0e2ab8f2e582289761153549043fc`. The MIT license and adjudication script hashes are pinned in the manifest. The benchmark authors' repository identifies the September 2025 cleaned history release. [LongMemEval repository](https://github.com/xiaowu0162/LongMemEval/tree/9e0b455f4ef0e2ab8f2e582289761153549043fc)
- Dataset revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`. The MIT-tagged English JSON contains 500 questions and occupies 277,383,467 bytes. Its SHA-256 matches the publisher's LFS pointer, `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`. [Cleaned LongMemEval_S download](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/blob/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json)
- Frozen protocol and sample at `9c9c99f`. Seed 32491 selects two from each of the six official nonabstention types, followed by two from the IDs marked with the official abstention suffix. The six strata alternate in two rounds before abstention. Selection uses only IDs and types. The intended sample includes 3,141 pre-cutoff user turns across the 14 full histories. No substitute cases are chosen when a history cannot complete extraction.

## Architecture and isolation

```mermaid
flowchart LR
    A[500 official rows] --> M[Metadata-only selection]
    M --> P[Chronological allowlisted inputs]
    P --> B[Isolated BM25 and MiniLM transcript retrieval]
    P --> X[Frozen extractor and controller replay]
    X --> G[Retained facts with source provenance and authorization]
    G --> R[Evidence Index V2 and Reader V2]
    B --> L[Hash-locked predictions]
    R --> L
    L --> S[Isolated scoring and evidence recall]
    A -. annotations after lock .-> O[Isolated oracle and scorer]
    O --> S
```

The schema stores aligned session texts, dates, IDs and answer-session IDs. Sessions are filtered against the exact question timestamp before sorting, using the upstream ordinal as the tie-breaker. The model-facing copy contains only the question text, cutoff day, and chronological turns with numeric source ordinals and user or assistant roles. The original session names can encode gold and are never used in model-facing prompts. Answer text, answer-session labels, `has_answer` and question types never enter the blind extractor, rankers, verifier, or reader. TRACE-Mem's internal validity intervals still use dates, so multiple same-day updates may be ineligible even though ingestion order is preserved.

BM25 uses lowercased word tokens, standard length normalization with `k1=1.2` and `b=0.75`, and chronological ties. MiniLM ranks the same turns by cosine similarity. Both roles are indexed. Annotated recall uses the official session IDs and explicitly tagged turns, remapped to ordinal sources. It measures micro recall among answerable questions on the context actually sent to Reader V2 after trimming. Missing or empty gold annotations have no recall denominator. The official implementation also defines retrieval metrics such as NDCG and uses a user-turn index in the cited script. This diagnostic reports its specified post-trimming recall instead. [Official retrieval implementation](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/run_retrieval.py)

For the isolated oracle, the official tagged turns form the candidate set, with session fallback when a case has no tagged turns. BM25 ranks this reduced set to fit the shared envelope. Oracle abstention receives empty context. The oracle measures reader limitations under annotated access and its abstention accuracy is partly built into the condition. Transcript diagnostic and oracle access are unrestricted research conditions. Neither grants production authorization.

The unchanged user-turn extractor runs over each complete chronological prefix without manually supplied claims. A failed turn or an interrupted extraction disqualifies that history from managed benchmark scoring. Deletion intent or a possible source restriction triggers conservative history quarantine. Managed replay embeds only retained, currently visible facts whose values occur verbatim, case-insensitively in their originating user turn. Pending, deleted, superseded current, rejected, or source-unverified facts are excluded. This conservative rule can omit valid paraphrases and does not establish general deletion safety.

B1, B2, B3, B5, T1, T2, the paced no-NLI diagnostic and H-paced use identical completed histories. The absolute caps are two and five per history. Paced arms receive a fixed horizon of five as an input before replay. Verifier payloads are restricted to the current claim, current conflict, and current user turn. Raw support annotations and target counts are unavailable. Audit counts on incomplete prefixes are reported as such. Prompt equality and the pinned Qwen digest govern cache reuse. Failed preflight or malformed outputs remain explicit.

Reader V2 uses the same reasoning profile, eight-item maximum and 2,600-byte selection envelope in all arms, with its existing evidence and abstention contract. Actual provider context limits are retained. The scoring stage begins only after blind predictions have been written and hash-locked. The pinned official prompt builder is loaded in isolation and its type-specific rules are used with pinned local Qwen and strict yes/no output. Structured null answers are scored against the official abstention indicator without a judge call. The official script's hosted and 70B judge options differ from this local setup. [Official scoring implementation](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/evaluation/evaluate_qa.py)

Failure-inclusive accuracy includes reader and judge failures in the denominator of completed cases. Scored-only accuracy excludes invalid responses. Incomplete managed cases are separately listed, with no extrapolation from successful histories. Per-history equal realized spending comparisons are descriptive, especially at zero calls. No estimate from this sample supports a confirmatory superiority claim.

## Reproduction

Place the official clone and pinned cleaned JSON at the ignored locations below. Ensure the pinned Ollama Qwen, MiniLM and DeBERTa installations and original V3 outcomes are present. Commands run from the TRACE-Mem root.

```powershell
python -m scripts.longmemeval_inputs data/longmemeval/s.json results/step32
python -m scripts.longmemeval_extract results/step32
python -m scripts.longmemeval_blind results/step32 data/models/nli-deberta-v3-xsmall-a150876 results/updateset-v3-final/outcomes.jsonl
python -m scripts.longmemeval_score results/step32 data/longmemeval/s.json third_party/LongMemEval
python -m scripts.summarize_longmemeval results/step32/safe-report.json docs/step32_artifacts
python -m pytest -q
```

An optional `--retrieval-only` call can checkpoint the blind transcript predictions while extraction runs. It never opens scoring labels. Model-facing copies, raw predictions, extracted facts, caches, and worksheets stay under ignored local paths.

## Results

All 14 frozen questions completed in BM25, MiniLM, and the separately isolated oracle. Only one history qualified for managed policy scoring. The table reports adapted local results. Parenthesized percentages are failure-inclusive.

| Condition | Correct over completed | Correct over scored | Official abstention cases correct | Invalid reader | Invalid judge | Session recall | Turn recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 transcript | 3/14 (21.4%) | 3/10 | 1/2 | 4 | 0 | 14/18 | 11/19 |
| MiniLM transcript | 2/14 (14.3%) | 2/11 | 2/2 | 3 | 0 | 13/18 | 10/19 |
| Isolated oracle | 6/14 (42.9%) | 6/13 | 2/2 | 0 | 1 | 15/18 | 16/19 |
| Each managed policy and cap | 0/1 | 0/1 | No completed cases | 0 | 0 | 0/1 | 0/1 |

BM25, MiniLM, and the oracle abstained on 6, 8, and 6 questions respectively. MiniLM's two correct answers were both abstentions. BM25 also answered one single-session user and one single-session assistant case correctly. On the sole common case, L02, both transcript baselines retrieved the tagged session and turn but the reader abstained. The oracle retrieved the same official evidence and its answer was judged incorrect. All managed arms missed the annotated evidence and abstained. Managed TRACE-Mem had lower completion and evidence coverage than transcript retrieval. There was no difference in answer accuracy on the one common case.

### Extraction and verification

The limit was reached at exactly 2,000 fresh extraction requests. Of 3,141 eligible user turns, 2,017 were processed, including failures and cache hits. Extraction emitted 228 claims on 124 turns, 6.1% of processed turns. Sixteen turns failed, comprising seven byte-ceiling rejections before inference, seven schema failures and two incomplete or refused outputs. Eight histories reached their final user turn. Seven had extraction errors. L09 stopped after 147 of 267 turns, and L10 through L14 received no extraction requests. No partial history was scored as complete. Prefix audits identified 42 eligible B2 conflicts, nine unresolved extracted deletion claims and three possible source restriction signals. Only L02 passed both extraction completeness and the authorization gate.

L02 was a single-session assistant question. The original extractor consumes user turns only. It produced 20 claims across 14 of 293 turns. T2 retained seven authorized source fields after two source-provenance rejections at each cap. The seven live conflicts exceeded its planning horizon by two. B3, T2, T2-no-NLI and H-paced spent the full cap at two and five. T1 and B5 spent zero at both caps. There were 28 logical verifier attempts across policy and cap combinations, from five distinct fresh exact requests, with no failures. At the two-call cap, T2 used 575 logical input and 26 output tokens, B3 used 618 and 26, and H-paced used 649 and 28. All four full-spending policies used 1,477 and 66 tokens at the five-call cap. The zero-answer tie at matched spending cannot establish a verification advantage.

The oracle's 16/19 turn recall and six correct outcomes point to additional reader limitations even when supporting evidence is supplied. The abstention-only MiniLM successes show why answerable questions and abstention cases need separate reporting. The 14-question sample, one clean managed history, strict quarantine, user-only original extractor, and adapted judge restrict interpretation. The primary blockers for a broader managed comparison are extraction completeness and coverage, followed by reader reliability.

### Resource use and artifacts

| Stage | Fresh requests | Input tokens | Output tokens | Summed request latency |
| --- | ---: | ---: | ---: | ---: |
| Original extraction | 2,000 | 443,402 | 10,688 | 997.2 s |
| Blind reader | 24 | 19,300 | 616 | 62.6 s |
| Verifier | 5 | 1,477 | 66 | 4.2 s |
| Oracle reader | 11 | 3,594 | 565 | 25.5 s |
| Adapted judge | 12 | 3,669 | 25 | 5.0 s |
| Total | 2,052 | 471,442 | 11,960 | 1,094.6 s |

Extraction wall time was 1,022 seconds. The RTX 2060 showed 4,129 MiB in use in a sampled run observation. Fresh paid spend was USD 0. Logical invalid reader results can recur from cached terminal failures or preflight limits. Physical usage is reported separately. MiniLM revision was `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, DeBERTa revision `a150876415327c80daeff35ca6f68f5ed8cf5c24`, and Ollama Qwen digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`.

The blind prediction SHA-256 is `5b5bc4916789a219463a5a28dcf8af6986e6d3015dcb02d20f8bf57e558203bf`. The aggregate and both figures regenerated byte-for-byte. All 126 tests and 36 subtests passed. Six cases were exported to the ignored `results/step32/human-review.json` with anonymous answers and blank human decision fields. Raw predictions, reference answers, annotated transcripts and the worksheet stay local.

- [Aggregate and safe question-level results](step32_artifacts/aggregate.json)
- [Accuracy and recall comparison](step32_artifacts/comparison.png)
- [Question-level failure matrix](step32_artifacts/question-outcomes.png)
