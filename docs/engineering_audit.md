# Step 38 engineering audit

Baseline: origin/main at the merge of Step 37 PR #45. The [chronological experiment inventory](../research/tables/experiment-inventory.csv), subsequent experiment-log entries, and current executable paths are the release record. Step 28 was the human review workflow between the resolver and field-level enforcement milestones. The audit separates implementation, prior research and planned work.

| Milestones | Components and review basis | Release finding |
| --- | --- | --- |
| 1–9 | Memora schema audit, replay, memory and budget invariants, deterministic selection, logistic feature path and semantic scoring | Core flows are implemented and tested. The prior README still described proposed CLIs and delivery gates. The new index links existing entry points instead. |
| 10–18 | TRACE-UpdateSet schema, generation, local providers, verifier gates and collection, V2/V3 feature audits, NLI, frozen full and no-NLI artifacts | V1 zero-positive outcomes, limited candidate diversity, and exploratory calibration remain part of the record. No artifact or weight changes. |
| 19–25 | End-to-end runner, original/contextual/hybrid extraction experiments, controlled replay, pacing, development benchmark and failure isolation | Transcript retrieval and source oracle recover evidence in diagnostic settings only. Downstream score interpretation requires retrieval, extraction and scoring coverage. |
| 26–29 | Reader V2, quarantine, resolver, review and field-level grants | Managed evidence applies source and field restrictions with lineage and cache boundaries. Autonomous release and comprehensive privacy remain unproven. Reviewed approvals and raw source material stay private. |
| 30–33 | Synthetic verification replay, horizon robustness, LongMemEval and extraction/reader reliability | Numeric evidence supports conditional effects and a reversal. Limited completion and failed gates preclude an external superiority claim or promotion of the revised components. |
| 34–37 | Evidence audit, public arithmetic reproduction, future independent protocol and runner | Prior artifact audit traces the 230 summaries and 184 paired intervals. The Step 37 entry point is ready for its gated study. This release leaves permissions, gold and cohort preflight intact. |

## What Step 38 fixed

- The repository lacked a practical no-model walkthrough. The offline console exercises policy, budget, validity, uncertainty, provenance and deletion using the existing engine. Archived results are isolated from replay controls and stay labeled by experimental mode and denominator.
- The repository lacked an explicit source candidate archive procedure. The packaging command accepts a committed revision, rejects private directories, symbolic links, nested repositories and common credential/cache/weight filenames, then emits an archive hash.
- The landing page presented implemented modules as future work and contained obsolete academic setup. It now links stable execution paths and separately documents optional dependencies and historically failed candidates.
- Engineering verification uses the existing lifecycle, policies, adaptive cap, evidence cache, leakage and recovery tests. New tests exercise the entry point's inputs, serving boundary and archived result selection. No evidence supports changing frozen controller or extractor behavior in this maintenance milestone.

## Known limitations

Day-level representation, single-target conflicts and exact predicate eligibility are implemented assumptions. Same-day states, complex multi-valued relationships, autonomous deletion semantics and broad extraction/reader coverage remain limitations. Experiments involving pinned inference need separate model assets and some original runs require private provenance or exact caches. A root redistribution/reuse license and individual citation metadata still need maintainer confirmation. The offline demo intentionally exposes only a single fictional history and three policies, with other comparisons available through archived results.

Consult the [public reproduction package](../reproducibility/README.md), [research claims](../research/final_claim_index.md), and [release guide](technical_release.md) for operational scope and remaining publication work.
