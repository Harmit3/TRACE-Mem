# Controller feature-quality audit

## Frozen diagnostic protocol

Use the immutable seed-2407 full candidate release and exclude all 44 pilot cases. Verify hashes and recompute the original vectors and labels using the release audit. Compute population variance, distinct vector counts, and Pearson correlations only for nonconstant columns. Include eligible candidates awaiting gold in feature statistics, and count class-specific vectors only for known labels. Keep train and validation separate. Use no held-out test input.

For the local embedding sensitivity check, replace just the recorded lexical coordinate in an in-memory diagnostic copy. Use the already cached MiniLM checkpoint `c9745ed1d9f207416be6d2e6f8de32d1f16199bf` on CPU. Use attention-masked mean pooling, L2 normalization, maximum length 256, batch size 16, four Torch threads and cosine similarity. Model input has only the predicate, claim/fact value and pair-local subject marker. Gold, split and case metadata, saved outcomes, and the verifier's verdict are excluded from model calls. The diagnostic does not train a model, introduce synthetic noise, change any source record, or claim NLI inference.

## V3 design before collection

Create a separate extension only after the feature contract and adjudication plan are frozen. Start with disjoint scenario families and independent authoring groups per split. Vary actual observation gaps and evidence sources by construction, using short and long intervals, direct and reported claims, dated records, vague time expressions, retractions, and multi-turn clarification. Include cases with no update and cases where verification could hurt as well as help. Use natural fictional values with no embedded split or case suffix. Assign independent gold before inference. Keep ambiguous cases for blinded human adjudication and keep the existing v2 and v1 test artifacts intact.

- Keep exact entity matching as an eligibility guard. Expect it to be constant under that policy. Changing it to create variance would alter the task.
- Replace provenance presence with a preregistered observable evidence feature only after collecting distinct source types with attributable references. Distinguish source type or evidence completeness from reliability inferred from gold.
- Preserve the interval overlap guard. If the temporal feature needs useful variation within eligible cases, predeclare an observable measurement such as effective-date specificity or interval geometry. Record whether the extractor supplied a date explicitly. Use real chronology and timestamp variation for the gap.
- Compute cosine and NLI with pinned local checkpoints and one shared renderer for collection and replay. Fail if the required checkpoint is missing. Use the NLI model's contradiction score with validation of the renderer and domain. Compare against the declared lexical and rule proxies as an ablation.
- Preserve the extractor's observed uncertainty. Do not replace it with authored intent. Record extraction failures and no eligible conflict cases.
- To study budget as a feature, collect a separate chronological protocol with a frozen pre-outcome allocation schedule or a fixed independent prefix policy and actual remaining budget. A one-call isolated intervention necessarily starts with a full budget.

Freeze all inputs, feature definitions, source IDs, budget schedule, model revisions, and acceptance checks before collection or feature inference. Keep candidate decisions and source evidence grouped by conversation and family. Reserve new independent families for calibration and later evaluation. Treat case-level repetitions as clustered evidence.
