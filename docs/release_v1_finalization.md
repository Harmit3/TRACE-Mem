# TRACE-Mem v1.0.0 — finalization handoff (draft)

Step 38 was merged in PR #46 at cf53976eed3c74ee8262fe0b1f70af0d66505eb3. This is release preparation, not a published release or a new scientific result. The RC archive verification remains tied to its original commit.

## Proposed release notes

TRACE-Mem is an exploratory research prototype for selective budget-aware verification of temporal conversational memory. It includes chronological replay, temporal facts, verification policies, authorized evidence retrieval, an offline demonstration with fictional inputs and a scripted verifier, and public numeric reproduction materials.

Step 38 recorded 152 passing tests, 36 passing subtests, one deprecation warning, and verification of 27,000 history rows, 2,300 family rows, 230 summaries and 184 paired intervals. See the verification checklist below for the release branch rerun.

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

The `--version` option sets the archive directory prefix. Citation versioning and release tags are separate. Verify the final archive CRC, contents and extracted execution. Use its newly printed commit, byte size and SHA-256; do not reuse the RC checksum. Tag the exact reviewed commit v1.0.0 and publish its archive and checksum after the rights and attribution checks and final-tree verification pass.

## Verification checklist

- [x] On Windows with Python 3.14.0 and Git 2.47.1.windows.2, root `python -m pytest -q` passed 152 tests and 36 subtests in 11.36 seconds, including all five packaging tests. There were no collection errors. The existing AnyIO plugin emitted one deprecation warning.
- [x] Root `pytest.ini` limits default discovery to `tests/` and excludes generated artifacts, archived releases, environments and third-party directories from recursive discovery. The extracted RC and archived results stayed in place.
- [x] Built the v1.0.0-format source ZIP from commit `3204c0c38d7261c0cd36e457dcfdb42100e3ced4`. All 289 files matched the reviewed Git tree under the expected prefix. The ZIP CRC and embedded commit checks passed. Size is 1,790,795 bytes. Independent SHA-256 verification returned `bd4b877d8784d4c6eb981c3d78f23ce011c7e43458a5c473b66eedc02a42810b`.
- [x] From the extracted archive, numeric reproduction verified 27,000 history rows, 2,300 family rows, 230 summaries and 184 paired intervals. All eight demo and packaging tests passed there, including the loopback HTTP replay and archived dashboard endpoint.
- [ ] Confirm the reuse license, third-party notices, rights holders and citation attribution.
- [ ] Rebuild and verify the exact approved publication tree, then tag and publish the archive with its own checksum. The recorded ZIP predates this verification note and the pending metadata changes.

The verification reproduces saved numerical observations. Independent scientific replication remains pending. No new research experiments were run.
