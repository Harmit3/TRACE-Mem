# TRACE-Mem offline evidence package

This release reproduces the Step 30 and 31 statistics and the principal Step 34 figures from sanitized synthetic outcome counts. It supports an independent audit of the arithmetic starting at the saved observations. Replicating the original interventions or testing generalization requires a separate experiment.

## Run from the package directory

Use CPython 3.14.0 for the reference environment. The numerical check uses only the Python standard library and works offline.

```text
python reproduce.py --output reproduced
```

To regenerate the two vector figures in SVG and PDF, create a fresh virtual environment and install the fully pinned plotting stack once. For offline installation, download the pinned wheels on a connected machine for the target platform and use the local wheel directory.

```text
python -m venv .venv
# Activate the environment, or invoke its Python directly.
python -m pip install -r requirements.txt
python reproduce.py --figures --output reproduced
```

After installation the script needs no network, model, GPU, benchmark download, original checkout or ignored results directory. See the [reviewer guide](reviewer-guide.md) and [blank independent review record](independent-review-checklist.md).

## Contents and provenance

| File | Contents |
| --- | --- |
| `data/history.jsonl.gz` | One numeric record per history, policy, condition and seed. Stable H/F aliases preserve pairing across both steps. |
| `data/family.jsonl.gz` | Per-condition family totals after averaging repeated seeds within each history. |
| `data/frozen-reference.json` | The 230 original condition summaries and 184 family-bootstrap intervals, excluding traces. Used only for verification after recomputation. |
| `manifest.json` | Historical report, configuration, controller and figure fingerprints. Includes allowlisted analysis settings and verifier spending. |
| `checksums.sha256` | Exact packaged-file hashes. Match this list to a trusted published commit to authenticate the package. |
| `reproduce.py`, `figures.py` | Standard-library statistics and optional Matplotlib figures. |

The records derive from author-generated fictional histories in Steps 30 and 31. Only bounded counts, enumerated QA statuses, policy settings and opaque synthetic identifiers are exported. The release contains no benchmark text, response text, evidence field, private annotation, model checkpoint, training feature vector, third-party dataset material or cache. Source digests are provenance pointers and can be checked against archival originals by their custodian. The reviewer package is alias-only at row level. Repository authorship and history remain visible in Git. It is not a double-blind submission. Project-owner authorization covers public distribution of the numeric package and authored scripts. No new license is asserted over upstream resources or the repository as a whole. Frozen model IDs and hashes identify dependencies used in the old experiments without redistributing model assets.

## Spending and numeric conventions

A logical call is a replay request, including when another condition already produced an exact cached verdict. Step 30 logged 16,489 logical verifier calls, including 814 fresh and 15,675 exact cache hits. It had no per-request-key token join in the original ledger, so per-history logical tokens are unavailable there. Step 31 logged 20,450 logical calls and zero fresh verifier calls. Its retained per-history logical tokens include reuse costs based on the validated earlier ledger. Reader requests have a separate budget and are outside these verifier counts. Calls do not imply an equal number of tokens or equal wall time.
