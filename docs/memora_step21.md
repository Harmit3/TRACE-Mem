# Step 21 · Evidence-grounded hybrid extraction

## Architecture

The experimental path separates candidate evidence identification from claim normalization. A deterministic first stage selects up to six verbatim focal clauses with personal-memory cues. It never retrieves from another user or from the future. The second stage asks the local model to output a closed-schema predicate, value, intent, and source-snippet index, plus an existing-memory target index for deletion. The normalizer rejects missing source values, fabricated dates, duplicate claims, and target mismatches. Some references can use up to two preceding user turns from the same session. That path preserves both the focal and contextual excerpts. A source match confirms literal provenance. It does not establish the truth or semantic interpretation of a claim.

The causal prototype applies accepted claims through the existing temporal B2 transition engine. A per-entity quote sidecar attaches retained excerpts to fact IDs and ranks only time-visible evidence with local MiniLM. On a resolved deletion the prototype removes matching stored facts, purges and retires the entire quote sidecar, clears the transient context, and blocks exact predicate/value re-addition. This conservative rule discards unrelated quotes and leaves aliases and paraphrased structured re-addition as limitations. Local public/synthetic model response caches are outside retrieval and are separate from the memory deletion guarantee. Unresolved deletion requests remain a documented failure mode. The original structured-only architecture remains the benchmark comparison and is unchanged.

## Validation protocol

Commit `17bbbf7` froze the extraction stages, 20 fictional cases, predicate equivalence map, and promotion gates before inference. The cases cover abstention, implicit replacements, tentative plans, personal facts, relationships, preferences, expenses, tasks, activities, dates, contextual mentions, and deletion. Gold was fixed directly from authored scenarios before outputs and contains no human annotation claims or benchmark answers. Exact scoring uses predicate, normalized value, and intent. Alias-normalized semantic scoring is a constrained equivalence measure using the frozen alias map. It leaves open-ended paraphrase matching and temporal-date scoring outside the gate. Source grounding separately measures literal source value presence and semantically correct grounded claims. For the hybrid, verbatim evidence references are mandatory.

All extraction comparisons use the same local settings. Original, contextual, and Qwen hybrid use the pinned Qwen2.5 checkpoint. The same hybrid architecture with pinned Llama 3.2 3B tests an independent normalization backend. MiniLM and DeBERTa compute the unchanged V3 feature vector on eligible fixture conflicts; T1 inference uses the committed model and threshold. Feature summaries describe only fixtures with a known prior target and an eligible emitted candidate.

```powershell
python -m scripts.validate_memora_hybrid --nli data/models/nli-deberta-v3-xsmall-a150876 --output results/memora-step21-validation-reproduction
python -m pytest -q
```

## Bounded follow-up design

A bounded development study can separate extraction quality from downstream memory behavior using 12 sessions selected by chronology from the existing development persona before anyone inspects model outputs. Have a reviewer annotate eligible source spans, correction operations, deletion targets, and query answerability from those sessions. Freeze the cases and two independent synthetic query fixtures. Compare the existing structured stack and a span-oracle input condition using the same pinned reader and one fixed verification call per eligible history. Report unsupported storage, retained evidence, retrieval quality, and per-case outcomes, and keep any adapted local FAMA separate. The span-oracle condition isolates the effect of extraction and should be labeled as an upper-bound diagnostic. The frozen held-out personas remain reserved.

## Observed results

| Method | Emitted / expected | Exact P / R / F1 | Alias-normalized P / R / F1 | Grounded correct / emitted | Unsupported literal values | Exact deletions | Invalid responses |
| --- | --- | --- | --- | --- | ---: | --- | ---: |
| Original Qwen | 14 / 16 | .286 / .250 / .267 | .357 / .313 / .333 | 5 / 14 | 1 | 0 / 3 | 2 / 20 |
| Contextual Qwen | 4 / 16 | .500 / .125 / .200 | .500 / .125 / .200 | 2 / 4 | 0 | 0 / 3 | 1 / 20 |
| Hybrid Qwen | 3 / 16 | 1.000 / .188 / .316 | 1.000 / .188 / .316 | 3 / 3 | 0 | 0 / 3 | 14 / 18 |
| Hybrid Llama | 4 / 16 | .250 / .063 / .100 | .250 / .063 / .100 | 1 / 4 | 0 | 0 / 3 | 14 / 18 |

The deterministic stage skipped two focal messages, yielding 18 normalization requests per hybrid backend. The Qwen hybrid retained an appointment, a historical residence and a tentative employment claim. Its high precision reflects a three-claim denominator. Neither hybrid backend resolved any deletion target. The original emitted one deletion with a noncanonical predicate. The frozen alias map does not cover every plausible naming variation, so the alias-normalized figures should be read with that constraint. Unsupported-value counts refer to emitted claims and omit rejected responses. The provider ledger does not preserve invalid raw responses, so it cannot separate the recorded invalid responses by individual rejection reason. Llama produced a source-literal appointment with the wrong predicate and two asserted employer mentions on the implicit replacement case. This run provides no basis to adopt Llama as an independent extractor. It was not tested for this milestone as a judge.

The hybrid stored 58 UTF-8 excerpt bytes across Qwen fixtures and 132 across the Llama fixtures, excluding record and index overhead. Real MiniLM retrieval selected the eligible excerpts. The purge and exact re-addition restrictions passed deterministic regression tests. No real delete transition was exercised because the model resolved no deletion target.

| Method | Eligible fixture conflicts | Average contradiction | Average temporal conflict | Mean frozen T1 score | Above frozen threshold |
| --- | ---: | ---: | ---: | ---: | --- |
| Original Qwen | 2 | .560 | .500 | .581 | 1 / 2 |
| Contextual Qwen | 0 | — | — | — | — |
| Hybrid Qwen | 1 | .121 | .000 | .273 | 0 / 1 |
| Hybrid Llama | 1 | .999 | 1.000 | .720 | 1 / 1 |

The Qwen hybrid retained the lower-scoring tentative conflict and omitted the implicit replacement, which the original emitted. The Llama conflict was the implicit replacement but carried an assertion intent. Differences primarily reflect which conflicts reached the unchanged T1 scorer. Candidate counts are too small for a stable distribution-shift estimate. No controller parameters or thresholds changed.

Across 76 local requests, the recorded usage was 17,466 input tokens, 2,796 output tokens, 127.03 seconds of summed provider latency, and 135.91 seconds wall time. Thirty-one responses were invalid, and spending was USD 0. The Qwen hybrid failed the semantic recall, exact F1 gain, and deletion requirements. The complete Memora development run was gated off. This milestone produced no new benchmark answers, verification calls, or adapted FAMA scores. Step 20's prior truncated-prefix result remains separate.

[Machine-readable aggregate](memora_step21_aggregate.json)
