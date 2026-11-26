# TRACE-Mem v1.0.0 — finalization handoff (draft)

Step 38 was merged in PR #46 at cf53976eed3c74ee8262fe0b1f70af0d66505eb3. This is release preparation, not a published release or a new scientific result. The RC archive verification remains tied to its original commit.

## Proposed release notes

TRACE-Mem is an exploratory research prototype for selective budget-aware verification of temporal conversational memory. It includes chronological replay, temporal facts, verification policies, authorized evidence retrieval, an offline demonstration with fictional inputs and a scripted verifier, and public numeric reproduction materials.

Step 38 recorded 152 passing tests, 36 passing subtests, one deprecation warning, and verification of 27,000 history rows, 2,300 family rows, 230 summaries and 184 paired intervals. These are historical RC results, not a rerun on the final source tree.

At 250 calls, T2 exceeds H-paced by 6.7 percentage points in chronological replay but trails by 11.3 points in the matched fixed stream. Planning-horizon sensitivity, extraction coverage and reader reliability remain limitations. General superiority, production safety and end-to-end QA benefits are unestablished. See [research evidence audit](research_evidence_audit.md).

## Maintainer decisions

- Proposed license: MIT for project-owned materials that the rights holders are authorized to license, subject to review of third-party notices and exclusions. This proposal does not grant reuse rights.
- Confirm rights holders, authors and individual contributions before finalizing CITATION.cff. Do not invent affiliations, ORCIDs or a DOI. Set citation version to 1.0.0 as part of the approved release.
- Independent replication and the 90-family study remain future work.

## Finalization procedure

Commit the confirmed license, notices and citation metadata. Review the staged privacy check and exact final tree, then run the full test suite, numeric reproduction, and local browser demo in the reference environment.

```text
python -m pytest -q
python reproducibility/reproduce.py --output results/reproduced-v1
python -m scripts.package_technical_release HEAD results/step38/TRACE-Mem-1.0.0.zip --version 1.0.0
```

The new --version option changes the archive directory prefix, not the repository version or release status. Verify the final archive CRC, contents and extracted execution. Use its newly printed commit, byte size and SHA-256; do not reuse the RC checksum. Tag the exact reviewed commit v1.0.0 and publish its archive and checksum after the rights and attribution checks and final-tree verification pass.

## Focused verification

Five local Git-fixture tests passed on Python 3.13.5 and Git 2.47.3: RC prefix, final prefix and checksum output, invalid-version rejection, private-path refusal, and refusal to overwrite an existing archive. These tests used a standalone copy of the revised script, not a full repository checkout. No full-suite rerun or final archive was performed. No scientific artifacts, controllers or approval gates were changed. AI-assisted changes are limited to packaging and release documentation.
