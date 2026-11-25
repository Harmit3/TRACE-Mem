# Step 20 · Memora extraction and local adjudication readiness

Step 19 was merged in PR #28 at `06713f8`. Step 20 preserved the trained T1 artifacts, frozen persona split, original predictions, and caches. The contextual extractor and local judge were frozen at `3327581` before inference. This milestone used only pinned local Qwen and did not open held-out rubric answers.

## Why the original smoke extracted two claims

I reviewed the 55 focal user turns in the first eight development sessions before inspecting the individual cached extraction responses. Under a retention criterion covering concrete facts that could support future personal recall, seven turns were clear candidates and 48 did not independently add such a fact. Examples of excluded material include greetings, questions about AI, backchannel acknowledgments, generic opinions, and statements that merely elaborated on an already named preference. This is a turn-level development audit and depends on the retention definition.

Five clear candidates produced empty arrays: a music preference, two specific expenses, a named work task, and its subsequent completion. One of the two nonempty responses mislabeled a scheduled content performance review as employment. The other captured a completed step-count activity. Neither context-window exhaustion nor downstream filtering explains the sparse output on this prefix. Every original user turn has a successful cached response, and the failures of coverage are present in the raw structured outputs. Benchmark memory-operation annotations and rubric answers played no role in this classification.

The original prompt used isolated messages and focused its examples on employment. Its schema allowed unrestricted predicate strings and represented both subject and object relationships through a flat predicate/value pair. Thus syntactically valid output can still conflate a pet name with the user's name, classify an event as a job, or assign a noncanonical predicate to a deletion target. The candidate prompt adds explicit retention categories and replacement rules, lets at most three earlier user messages from the same session resolve references, and rejects duplicate and extra-field responses. It excludes assistant text and prior sessions. Exact-match deletion still requires the extractor to recover both the predicate and target value.

## Local extraction validation

The frozen protocol contains 18 fictional cases and 12 expected claims, including three deletion targets. Expected tuples were specified directly from the inputs before inference and did not come from Qwen or benchmark labels. These are authored rule fixtures without independent human annotation. Metrics use case-insensitive exact predicate, value, and intent matches. A semantically reasonable predicate alias can count as an exact-match error.

| Extractor | Exact matches / emitted / expected | Precision | Recall | F1 | Deletion target recall | Validation failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original | 5 / 10 / 12 | .500 | .417 | .455 | 1 / 3 | 1 |
| Contextual candidate | 3 / 5 / 12 | .600 | .250 | .353 | 0 / 3 | 1 |

The original had five unmatched predictions and the candidate had two. In the original, one prediction introduced an unsupported workplace placeholder and another collapsed a pet's name into an unqualified name. The contextual candidate's two unmatched predictions retained stated values but changed the expected intent or predicate. Neither extractor labeled either confirmed replacement as a correction. The original produced one uncertain claim and one explicit deletion. The contextual candidate produced assertions only. The change therefore shifted the intent mix that feeds T1's uncertainty feature and reduced opportunities to create or remove memory facts. This establishes a shift on the fixtures only. It cannot quantify how often T1 crosses its decision threshold on the full benchmark history.

The candidate failed every frozen promotion criterion including recall, F1 gain, and deletion-target recall. The original also fell below the candidate's minimum recall and precision. The full reserved development replay with a validated extractor remains blocked. The candidate is implemented behind its validation gate and the original remains the default. Neither prompt was retuned after seeing the results.

The comparison and judge validation used 48 actual requests, 9,763 input tokens, 622 output tokens, 45.94 seconds of summed provider latency, and 46.54 seconds wall time. Two responses failed provider validation, one per extractor. Both variants used the same pinned Qwen, decoding, context, and response schema. The original used 3,337 input and 239 output tokens and the candidate used 5,099 input and 287 output tokens across 18 requests each.

## Adapted local adjudication

The local Qwen judge matched all 12 predeclared source-grounded binary checks (six yes and six no) covering mentions, negation, uncertainty and historical versus current facts. No human reliability estimate was collected. The fixture result establishes basic instruction following. It does not establish reliability on diverse Memora answers, and using Qwen for both answer generation and local judgment can create correlated errors.

A separate process sent each completed Step 19 prediction and its development rubric check to the judge. Expected labels stayed outside judge prompts and were used only for the offline join. The official pinned arithmetic evaluated four memory-presence and seven forgetting-absence checks per row. **All eight methods scored 0.000 FAMA in both fixed-stream and closed-loop modes**, with 0/4 presence and 7/7 absence matches per row. All 16 predictions were abstentions from the existing eight-session prefix. These are adapted local plumbing results with no observed method separation and no claim of comparability with Memora's published hosted judges.

There were 176 logical check evaluations, 11 actual Qwen requests, 165 cache hits, 1,178 input and 91 output tokens, 8.27 seconds summed provider latency and 9.48 seconds wall time. No paid calls or full-history inference were performed. The Step 19 prefix retains its original zero eligible conflicts, two memory adds per persistent method, and no verification attempts.

```powershell
python -m scripts.validate_memora_quality results/memora-step20-validation-reproduction
python -m scripts.adjudicate_memora_local third_party/Memora results/memora-step19-smoke/predictions.json results/memora-step20-validation/report.json results/memora-step20-prefix-judge-reproduction
```

The full single-question development runner accepts `--extraction-validation` for a passing report matching the frozen validation design and Qwen digest. The recorded report does not pass. Any further extractor revision should use a new independently frozen set that includes temporal reference resolution and natural multi-turn deletion targets.
