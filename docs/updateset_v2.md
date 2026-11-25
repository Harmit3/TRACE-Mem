# TRACE-UpdateSet v2 pilot protocol

## Why v1 yielded no positives

The v1 collector compared only single-target eligible conflicts. Its B2 shorthand superseded exactly when the supplied intent was `correct`, matching the deployed B2 branch for those eligible cases. The verified arm applied a supersession only when Qwen returned `update`; otherwise both implementations deferred. The generator supplied `correct` on the 26 clean eligible replacements, `assert` on the 26 unresolved contradictions, and `uncertain` on the 26 pending cases. Qwen agreed with the corresponding B2 action on all 78. The supplied intent gave B2 an unrealistically direct correction signal. Many richer v1 cases, including deletion, separate-predicate visits and nonoverlapping history, fell outside current T1 eligibility.

Controller features were never used to collect these pairs. Training would build the eight features only after collection, with frozen conflict eligibility and independent gold, so feature scoring cannot explain this agreement. A positive requires a wrong unverified decision and a right verified decision. An identical pair cannot satisfy that predicate, even after adjudication.

## Frozen generation and sampling

V2 is a separate release with no benchmark inputs. Seed 2407 creates 350 training and 150 validation cases from 11 distinct template families per split. Personas and history IDs are unique, and the split-specific template texts and values differ. Each case has a prior fact, a short role-tagged conversation, and one focal user turn. The corpus covers implicit and indirect changes, renamings, temporary and historical mentions, future transitions, contradiction, references to prior turns, other people, explicit changes, and unresolved cases. It does not extend or modify the v1 held-out test.

Before extraction, the generator assigns independent current-value and historical-preservation gold from the scenario. An unresolved case has null gold and goes to the blind review packet. No generated record contains a claim intent or an extractor output. Repeated templates are scale instantiations with varied IDs, rather than 500 independent human conversations.

Randomly select two cases without replacement from every family in each split, giving 22 training and 22 validation cases. Freeze IDs before running the extractor. This is family-balanced and deliberately covers rare scenario shapes. It estimates behavior on this synthetic design, with no population weighting. Keep all selected cases, including negative, ambiguous, and extraction-ineligible outcomes.

## Paired procedure

Load the pinned local Qwen digest and validated direct-v2 schema and prompt using the same temperature, seed, context and caps. Separately use the existing production extraction prompt and callback on the focal user event, exactly once per case. The first two turns establish the prior snapshot and provide verifier context. The B2 extractor operates on the focal turn alone, as deployed. This evaluates one decision from a seeded state and cannot measure full multi-session replay accuracy.

Feed the exact same extraction response into both arms. Run the production B2 entry point twice from identical initial facts. The verified arm can spend at most one call on the first eligible conflict with the seeded fact, under the unchanged replay eligibility rules. It receives role-tagged conversation text. Both arms retain all extracted claims and apply the same temporal transition machinery. The evaluator sees the case metadata and gold only after replay.

Compare the anchored predicate's values at the focal date and at the prior observation date against gold. A helpful case changes an incorrect baseline state to a correct state. A harmful change does the reverse and counts as not helpful. Report identical transition traces separately from identical anchor states. Rows without eligible calls or gold, or with provider failures, remain in the report and have no helpfulness label. These are case-level pilot labels. A later training release needs a documented candidate-level mapping, including multi-claim cases.

```powershell
python -m scripts.updateset_v2_pilot generate data/updateset-v2-seed2407
python -m scripts.updateset_v2_pilot pilot data/updateset-v2-seed2407 --output results/updateset-v2-seed2407-pilot
```

Use the same output directory to resume an interrupted run with the SQLite response cache. Completed pilot outcomes, case files, and review packets stay ignored. V1 files and its 26-case review packet stay untouched.

## Observed pilot

Generation and sampling were committed at `6fea82f` before inference. V2 produced 500 cases, with 455 synthetic gold decisions and 45 pending human gold decisions. Train had 127 replacement, 191 preserve, and 32 pending decisions. Validation had 55 replacement, 82 preserve, and 13 pending decisions. The new blind packet is at `data/updateset-v2-seed2407/pending-review.jsonl`. It is separate from the existing 26-case v1 packet.

| Pilot outcome | Train | Validation |
| --- | ---: | ---: |
| Sampled cases | 22 | 22 |
| Eligible verifier calls | 13 | 10 |
| Helpful and corrected the anchored state | 5 | 3 |
| Not helpful | 6 | 7 |
| Harmful anchored-state change | 0 | 0 |
| Changed but still incorrect | 2 | 5 |
| Unchanged decisions | 14 | 14 |
| Eligible with gold pending | 2 | 0 |
| No eligible conflict | 8 | 12 |
| Extraction failure | 1 | 0 |

The rows describe overlapping quantities. Harmful and still-incorrect changes are subsets of not helpful when gold is present. Unchanged decisions include ineligible cases. The seven changes that left the anchored state wrong and all unchanged negative pairs remain in the pilot. Both splits contain both classes on this small sample. This does not establish sufficient sample size, calibration quality, generalization, or an absence of harm outside the anchored predicate.

There were 44 logical extraction requests and 23 verifier requests. Two requests were served from the cache. The ledger recorded 65 actual calls, 64 valid responses and one invalid extraction. It reported 15,775 input tokens, 1,668 output tokens, and zero provider cost. Total provider latency was 113,372.56 ms, mean 1,744.19 ms and nearest-rank p95 2,869.99 ms per actual call. The run used the pinned Qwen 7B Q4_K_M on Ollama 0.40.13, direct-v2 schema hash `186d105583c4fa4ecba72b82f9179acd8c140d72dc661679911654a5de8a8eb8`, seed 23, 4,096-token context, 256 maximum output tokens, 120-second timeout and zero retries.

| Artifact | SHA-256 |
| --- | --- |
| V2 cases | `0c16a0964402e5cbd9d8fc435a2b899bb13771e6037fbb4e8668ea85d178d475` |
| V2 review packet | `65d7c0f77d84e62c0719b62f92716fe6d1cbc093d011d9426b2626caef7516f1` |
| Pilot identifiers | `17ec2675353be46cb663396c4b0077cb775c991a30fa8ddd98c02476fc83fc88` |
| Pilot outcomes | `68182c644b52637fe2601b6b32c6fd159d4265f04c49bf4a0256a279b2418d20` |

Eligibility still requires an exact predicate match against a single live fact and a compatible date. Extraction can miss a contextual reference or emit a differing predicate, leaving no conflict for T1 to verify. A larger run needs a fixed protocol for auditing those cases and aligning case gold to candidate-level features. The v2 evaluator currently checks case-folded exact value strings and history on the anchored predicate. It cannot adjudicate semantic equivalence or unrelated fact quality. The pilot did not fit a controller, run a benchmark, or modify v1 cases, outcomes, or annotations.
