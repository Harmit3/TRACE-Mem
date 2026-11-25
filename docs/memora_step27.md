# Step 27 · Deletion scope resolution and authorization boundary

Step 27 starts from merged PR #35 at `8368c3c`. The Step 26 branch was fast-forwarded. Commit `aa033ef` froze the versioned resolver, 16 independent fictional fixtures, acceptance thresholds, and 18 source-review entries before model inference. The new experiment uses the preserved Step 24 extraction checkpoints and only the reserved development persona's user turns. It does not access rubric answers or change the frozen controllers.

## Resolver and privacy boundary

The baseline matches predicate and value exactly against the structured replay state. Resolver v1 first bounds candidates to chronologically available sources, then applies deterministic scope, broad-request, temporary-restriction, and duplicate-target rules. It prioritizes normalized literal and known-alias matches, ranks remaining candidates with pinned MiniLM, and gives a bounded subset of source excerpts and recent context to pinned local Qwen for verification. The model returns intent, relation, and a candidate index. Unsupported candidate IDs, ambiguous matches, broad requests, and no-target responses stay unresolved. A semantic proposal has no authority to revoke or release evidence.

Source IDs link original utterances to B2 selections and managed evidence records. Existing lineage makes source or scope revocation apply to derivatives through historical and alternate retrieval paths. The new volatile answer-cache gate binds cached answers to evidence handles and rechecks current authorization, epoch, and citation IDs on every fetch. Raw copied bytes or detached external caches remain outside the guarantee. The tests cover managed paths and known lineage only.

Several real deletion requests concern a single field inside a mixed turn. Releasing an entire source because part of it remains eligible can reveal the removed field. A reviewer must identify the allowed and denied ranges and decide how derivative records should be handled. Separating preference correction from erasure also requires scope review before using evidence that was already quarantined. No model result clears quarantine.

## Reproduction and worksheet

```powershell
python -u -m scripts.run_deletion_scope third_party/Memora results/memora-step24-final results/memora-step27
python -m pytest -q
```

The worksheet at `results/memora-step27/review.md` includes all source requests, up to two earlier same-session user turns, analyst and model target candidates, and five explicit approval choices. Every case defaults to pending with no release. The matching JSON holds the same metadata. Both remain ignored local files. Synthetic metrics compare expected target IDs against proposals. They are measured separately from the 18 real analyst classifications and from human authorization.

## Actual resolver results

The 16 frozen cases contain seven uniquely targeted resolutions. Counts below are model or exact-match proposals. No deletion was applied to a real record.

| Method | Correct / proposed targets | Precision | Recall | False targets | Requests with a false target | Targeted requests unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Predicate/value exact match | 3/10 | .300 | .429 | 7 | 6/16 | 4 |
| MiniLM + deterministic rules + Qwen | 6/6 | 1.000 | .857 | 0 | 0/16 | 1 |

The exact baseline hypothetically retained 14 of the 24 candidate-record slots if all its proposals were applied. The semantic proposals would retain 18. These are candidate counts across fixtures and exclude real evidence release. The frozen precision/recall/false-target gate passed. The missed case used a known alias. An alias can influence ranking without being visible in the excerpt supplied to the verifier, and the verifier abstained. The semantic resolver matched 15/16 fixture intent labels. These authored fixtures offer narrow evidence and cannot establish real-world precision.

All 13 safety assertions passed. They include the original historical, paraphrased, alternate-lineage and stale-handle checks and separate tests of cache use before and after revocation. The volatile answer-cache guard stops replay of previously cached content through the managed path. It does not erase data already copied outside that path.

## Real scope audit and decision boundary

All 18 unresolved B2 requests were examined against chronological source turns. The analyst classifications are **14 targeted forgetting requests, two preference corrections, two extraction errors, and zero temporary restrictions**. The extraction errors were document-edit setup turns with no designated field. The later request in each thread is a separate record. Several forgetting requests are document-scoped removals where a single source turn includes both permitted and restricted fields.

The resolver labeled 12 requests as forgetting, four as extraction errors, and two as unresolved, agreeing with the analyst category on 14/18. It returned **zero single-target proposals**. Thus the authored-fixture target scores do not transfer to this real history. The worksheet contains the chronological context, proposed source IDs, mixed-turn notes, and approval options for each request. All 18 remain pending. No inference approval was treated as authorization.

**Authorized evidence recovery is zero.** The Step 26 quarantine remains in place. Reader V2 did not receive newly released evidence or run a new Memora benchmark. Adapted FAMA, memory presence, forgetting absence, and abstention rates for a recovered-evidence condition are unavailable. The original Step 26 quarantined result remains separately documented. The next authorization decision requires explicit human review of scopes and derivatives.

The local run used 30 fresh Qwen requests, 10,976 input tokens, 700 output tokens, 54.24 seconds of summed provider latency, and 72.16 seconds wall time, with USD 0 spend. All 112 discovered tests and 36 subtests passed, including the pinned upstream checkout. The existing third-party AnyIO warning remained.

[Machine-readable fixture and source-category aggregates](memora_step27_aggregate.json)
