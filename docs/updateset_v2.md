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
