# Reviewer onboarding

This is an invitation to assess a pending study. The protocol packet and tooling were prepared internally with AI assistance. A reviewer is free to request revisions, decline, or recommend a narrower scope. The project owner will coordinate outreach personally.

## Start here

- Read the [one-page overview](reviewer_research_summary.md), [protocol v2](validation_protocol_v2.md), [analysis plan](statistical_analysis_plan.md) and [execution readiness audit](final_execution_readiness.md).
- Use the [public release](../reproducibility/README.md) to inspect Steps 30 and 31 without benchmark access. See the [source repository](https://github.com/Harmit3/TRACE-Mem) for revision history.
- From the repository root, run `python reproducibility/reproduce.py --output results/reviewer-offline`. The numeric path uses only Python 3.14's standard library. For figures, install `reproducibility/requirements.txt` in a fresh virtual environment and add `--figures`. Verify the packaged checksums and complete the [blank replication record](../reproducibility/independent-review-checklist.md) only after actually running the checks.
- The previous results can be verified offline. Confirming the scientific result requires approved new families and later model execution.

## Distinct responsibilities

**Fixture author.** After protocol approval, design conflict mechanisms using the [taxonomy](conflict_mechanism_taxonomy.md) and [fixture specification](fixture_authoring_specification.md). Record candidate order, observed/effective times, dependencies, verbatim authorized spans and rules for determining gold. Revise unsupported mechanisms before sealing fixtures. Do not use prior model outputs to design the gold.

**Gold reviewer.** Review anonymized sources, timelines, gold and overlap records from a separate author. Work without policy names or any model outcomes. Verify facts, permission, time boundaries, answerability and why each mechanism differs from prior families. Maintain a discrepancy log. Escalate uncertain scopes and leave unresolved gold pending. Complete the [blank protocol and gold forms](protocol_approval_checklist.md) only after real review.

**Project owner.** Coordinate consent and access, preserve conflicts-of-interest disclosures, ensure separate author and gold roles, and approve the executable freeze only after independent review. Internal engineering evaluation does not constitute independent scientific approval.

## Estimated workload

Allow roughly 2–4 hours for first-pass protocol and reproducibility review. If the full 90-family proposal is approved, authoring at 1–2 hours per family would take about 90–180 hours. At 5–10 minutes per history, first-pass gold review of 360 histories would take 30–60 hours, plus overlap review, revisions and adjudication. These are planning assumptions, not assigned obligations. A reviewer may prefer a smaller protocol-only contribution or a prospectively approved narrower study. No commitments or authorship arrangements are assumed.
