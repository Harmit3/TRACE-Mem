# Step 26 · Reader reliability and deletion-aware evidence

The Step 26 branch starts from the Step 25 review branch, which contained the fetched main at `5dbf815`. Step 25 had not merged at synchronization. Commit `f962aa9` froze the original and revised readers, evidence index, reader questions, safety probes, token settings, and acceptance thresholds before inference. No extractor, T1, or T2 behavior changed.

## Reader v2

Reader v2 uses the pinned local Qwen checkpoint to select exact text and source references. The validator rejects unknown citations, fabricated quote spans, duplicate entries, and malformed supported answers. A model-selected abstention becomes a canonical empty answer and zero citations. A selected quote is rendered within its entire source passage to preserve qualifiers and negation. The drafting profile adds a fixed heading and composes from the passages. This limits open-ended synthesis. A literal match establishes source fidelity, while relevance and semantic adequacy still require evaluation.

The output profiles allow 192 tokens for short answers, 320 for recommendations, 384 for reasoning and 768 for drafting. Both readers retain the 4,096-token context and use the same retrieval ordering, eight-fact limit, and conservative 3,000-byte evidence envelope. Reader v2 sums supported expenses or step counts using decimal arithmetic only for recognizable sum questions. It removes duplicate source references, skips prospective entries, refuses inconsistent same-source values, and labels results as subtotals of retrieved evidence. It cannot certify that retrieval found every event or that two separate reports describe distinct transactions.

## Evidence Index v1

The prototype retains raw excerpts and compatible structured facts under one provenance and authorization registry. Each retained record has a source reference, observation and effective dates, a scope, optional parent lineage, and an optional supersession link. Closed historical visibility accounts for when the replacement was observed. Query-time authorization applies current revocations and scope restrictions regardless of the requested historical date. Linked derivatives inherit restrictions from their parents. Epoch changes invalidate existing retrieval handles and change downstream cache identities. A selected source or scope that cannot be resolved blocks the entire managed index conservatively. The index uses stored references for filtering before scoring, so embedding never receives a denied record during retrieval.

```mermaid
flowchart LR
    A[Chronological source excerpts] --> P[Provenance and authorization registry]
    B[Structured temporal facts] --> P
    D[Source or scope deletion] --> P
    P --> R[Authorized time-visible records]
    R --> M[MiniLM ranking and epoch-bound handle]
    M --> V[Reader v2 quote validation or subtotal]
    V --> Q[Answer or abstention]
```

Scope and lineage must be known to tie paraphrased evidence to an original source. Stale handles cannot reauthorize retrieval. Bytes already copied by a client, external caches and detached indexes do not share that guarantee. The diagnostic retains original artifacts locally. This is a synchronous prototype and its tests cannot establish comprehensive deletion safety.

## Frozen comparison

All 15 public development questions use the original Step 24 extraction and Step 25 source nominations. Rubric material remains in a separate scoring process. The retrieval arms are structured B2, isolated transcript retrieval, the managed evidence index, and the deliberately labeled source oracle. The Step 25 transcript and oracle arms retain their prior privacy limitations and are diagnostics only. Both readers receive identical facts within each arm. Unscored failures are reported both separately and as zero in the failure-inclusive average. A shared-question comparison includes only questions valid in every arm for both readers. The benchmark judge is the existing adapted local Qwen implementation with the exact pinned FAMA arithmetic.

```powershell
python -u -m scripts.run_reader_safety third_party/Memora results/memora-step24-final results/memora-step25 results/memora-step26
python -m scripts.summarize_reader_safety third_party/Memora results/memora-step26 results/memora-step25 docs/memora_step26_artifacts
python -m pytest -q
```
