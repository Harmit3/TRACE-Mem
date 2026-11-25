# TRACE-UpdateSet v3 longitudinal release

## Frozen collection protocol

The independent synthetic release uses seed 6931, 200 histories, and three chronological decision points per history. Training has 100 histories from 20 scenario families. Calibration and independent evaluation each have 50 histories from ten distinct families. Every family is authored separately and instantiated five times with natural fictional places, dates and sources. Cases within a family are clustered. No previous pilot or benchmark content is included.

Each decision has an independently authored current and historical state or a pending annotation. Gold stays in the evaluator. The blind packet contains only the seeded prior and time-available conversation through the ambiguous turn. It excludes later turns, outcomes and gold. The extractor sees each focal turn and the verifier sees the chronological conversation prefix. Only the models and feature code already validated locally are used. No inference providers or model prompts are tuned on this release.

Seed the memory prior and carry forward deployed B2 state across all three turns. Identify each eligible single-target exact-entity conflict on the anchored predicate. Fork the same prefix for both decisions and advance B2 only. Only a verified update can supersede in the alternate arm. Score current and prior anchored values immediately after each candidate. This is an isolated candidate counterfactual on a chronological B2 prefix and cannot establish closed-loop performance.

Each history has a preregistered cap of one to three verification calls. Deduct actual verification attempts, including unsuccessful attempts. Compute all eight v3 features before verification using the actual pre-call remaining fraction. Persist ineligible and budget-exhausted claims, extraction and verifier failures, harmful changes, unchanged decisions and corrections. Cases awaiting gold remain pending. Outcome and feature rows are never filtered based on whether they help. Keep the label definition and feature definitions frozen.

Use the validated local Qwen direct-v2 digest and configuration, cached MiniLM, and pinned DeBERTa-v3-xsmall NLI. See the [NLI check](updateset_v3_nli.md) for neutral false contradictions and observed redundancy. Report a no-contradiction projection on the same rows for a future ablation. Correlation and class-support diagnostics are descriptive. No controller fit or calibration is authorized here.

```powershell
python -m scripts.collect_updateset_v3_final prepare data/updateset-v3-final
python -m scripts.collect_updateset_v3_final run data/updateset-v3-final --model data/models/nli-deberta-v3-xsmall-a150876 --output results/updateset-v3-final
```

Resume using the same command and directory. Atomic per-history checkpoints and a local response cache support recovery. The freeze file pins inputs, settings, dependency versions, feature order and collection code. Partitions, review packet, raw results and ledgers stay local and ignored. The run reports every ten histories. Prior experiments remain separate.
