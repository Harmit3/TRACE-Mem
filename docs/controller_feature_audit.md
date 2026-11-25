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

V3 should cross evidence types and timing bands with operation families in each split rather than making a feature level synonymous with a family or label. The authoring matrix should include direct reports, contextual confirmations, dated documents, hearsay and conflicting sources, with both updates and nonupdates where coherent. Use blinded adjudicators on disagreement-sensitive cases, and write a provenance codebook before reading model outcomes. No v3 cases or annotations were generated in this audit.

## Findings

PR #22 was merged at `ca5bb0d`. Diagnostic settings and the semantic input fix were frozen at `f8b9427`. The untouched v2 outcome SHA-256 is `facd1d44bc0401bbbc7d8f9ef39940c0bd7039a56f770f427e3420319c28bca0`.

| Feature | Train population variance | Validation population variance | Recorded source |
| --- | ---: | ---: | --- |
| Semantic similarity | 0.035324 | 0.025624 | Token Jaccard. V2 did not configure a semantic provider. |
| Contradiction score | 0.005582 | 0 | Rule proxy. With an eligible conflict it equals `1 - uncertainty / 2`. |
| Entity match | 0 | 0 | Exact match required by eligibility. All eligible rows equal 1. |
| Temporal conflict | 0 | 0 | Eligible claims overlap the live target, and each observed score is 1. |
| Time gap | 0 | 0 | The authored observation dates differ by exactly 21 days. |
| Provenance | 0 | 0 | Both opaque reference strings are always present. This is presence, not evidence quality. |
| Uncertainty | 0.022327 | 0 | Observed extractor intent, encoded as 0.5 for assert or 1 for uncertain in the train rows. Validation has only assert. |
| Remaining budget | 0 | 0 | One-call counterfactuals start with fraction 1, not a live replay trajectory. |

The three defined recorded train correlations were similarity–contradiction −0.2465, similarity–uncertainty +0.2465, and contradiction–uncertainty −1.0000. Constant pairs have undefined Pearson correlation. Validation has only one nonconstant column, so it has no defined feature-pair correlations.

Among 232 eligible nonpilot train rows and 58 eligible nonpilot validation rows, there were no invalid or missing feature rows. The recorded vectors had only four and three unique values, respectively. Eligible rows covered eight train families and six validation families out of 11 sampled per split. Labeled train rows span seven families, with positives from three. Labeled validation rows span six, with positives from three.

The 35 validation positives share `[0.2, 0.75, 1, 1, 21, 1, 0.5, 1]`. Each was extracted as assert. Across explicit, implicit and indirect replacement families, the only shared old/new token was an artificial case suffix, giving exactly one shared token over five unique tokens. Consequently even the sole varying feature in validation is confounded with template wording and ID-like tokens.

## Local model sensitivity check

```powershell
python -m scripts.audit_controller_features data/updateset-v2-seed2407 results/updateset-v2-full --cached-minilm
```

The cached CPU MiniLM run encoded 540 distinct texts using Torch 2.10.0+cpu and Transformers 5.22.2. Replacing only the lexical feature gave 232 distinct train vectors and 58 distinct validation vectors, including 35 distinct positive validation vectors. The cosine population variances were 0.007970 and 0.006943. Train cosine correlation with contradiction was −0.3493 and with uncertainty was +0.3493. This demonstrates sensitivity to the real embedding. It cannot establish useful signal, and embeddings still see the frozen v2 suffixes embedded in fact values.

No mock features were used in the v2 release or this model diagnostic. V2 explicitly used lexical and rule defaults. The first coordinate in this diagnostic is a real embedding, while contradiction remains the original proxy. The reference NLI checkpoint and Sentence Transformers package were unavailable in the local inventory. No NLI weights were downloaded and no remote inference ran. The configured NLI route uses named classifier probabilities when a local checkpoint is supplied. Real NLI effects still need a separately frozen check.

The implementation now renders model-facing feature pairs with pair-local subject markers, removing raw persona IDs that encoded split and case membership. The exact entity feature and provenance metadata remain available independently. V2's recorded rule features and outcome files were preserved. V3 should remove ID suffixes from natural values at generation time rather than rewriting this release.

The result supports an exploratory fit only. More distinct cosine values do not increase the number of independent families or vary timing, provenance, and budget. Reliable calibration remains blocked by clustered scenarios and a narrow validation distribution. No controller was trained.
