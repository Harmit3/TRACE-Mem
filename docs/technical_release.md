# Technical release guide

The standalone source candidate is **1.0.0-rc.1**. The release combines an offline demonstration, the frozen research code and public reproduction materials. Independent scientific replication is a future opportunity. It does not gate exploratory software release.

## Install and run

Create a fresh CPython 3.14 environment from the repository root or extracted source archive. On Windows:

```powershell
python -m venv .venv
.venv/Scripts/python -m trace_mem.demo
.venv/Scripts/python reproducibility/reproduce.py --output results/reproduced
```

On Unix-like systems, use `.venv/bin/python`. Open the loopback URL printed at startup. The demo and numeric verification use the standard library. To produce figures, install the plotting pins then add `--figures` to the reproduction command. To run engineering tests, install pytest 9.2.0 and the required numeric stack. Semantic model and live benchmark commands have additional local prerequisites.

```text
python -m pip install -r reproducibility/requirements.txt
python -m pip install pytest==9.2.0 -r requirements-training.txt
python -m pytest -q
```

For optional live runs consult [provider setup](llm_providers.md), [semantic checkpoints](semantic_models.md), and the [artifact-specific reproduction checklist](reproducibility_checklist.md). Keep benchmark downloads, caches and results at their ignored local paths. Run the benchmark and independent-run preflight checks before any future model inference.

## Build the source package

```text
python -m scripts.package_technical_release HEAD results/step38/TRACE-Mem-1.0.0-rc.1.zip
```

The script packages one committed tree, refuses common private and binary asset paths, and emits its commit, byte size and SHA-256. Review the committed tree before distribution because a path or secret heuristic cannot establish the safety of arbitrary content. GitHub source downloads can also be tied to a specific commit.

## Security, privacy and licensing

- The offline demo binds to IPv4 loopback, rejects unrelated Host headers, and serves allowlisted resources. It has no upload, provider, arbitrary file, or user-text endpoint. Keep it local. It is a development server without authentication.
- Inspect the staged diff and run `python scripts/check_staged.py` before committing. The archive uses committed files only. Never publish private annotations, credential files, benchmark transcripts or expected answers, restricted fields, local caches or model weights.
- Public reproduction files contain original synthetic counts and stable aliases. Benchmark and local inference documentation records upstream provenance and terms. The archive does not redistribute upstream models, runtimes or datasets.
- The repository lacks a declared root reuse license. Distribution of this reviewed snapshot is authorized by the maintainer. Downstream reuse rights require a maintainer-selected license and review of any applicable upstream notices.
- Citation metadata uses the project name as collective attribution. Individual names and contributions, affiliations, ORCIDs and a release DOI remain unverified.

## Technical release checklist

- [x] Preserve frozen artifacts and negative results.
- [x] Include the offline demonstration, documented feature inventory, and linked archived results.
- [x] Keep experimental candidates and independent validation separate from the release path.
- [ ] Reviewer checks the proposed branch and merges it.
- [ ] Maintainer confirms reuse terms and final individual citation metadata, then tags and distributes v1.0.
- [ ] For an exploratory preprint, use the [publication checklist](../research/preprint_checklist.md). Independent replication remains open.

## Release candidate verification

- Source ZIP from commit `25af8698638649a806d83014efd9495811f015bd`. It contains 286 files, is 1,789,815 bytes, and has SHA-256 `c760e6eb5575c0fbe61d5d88996e28321aa6df720036232c02e991d3f07f4a8b`. ZIP CRC and the path checks passed. This verification record was added after packaging.
- Fresh Windows 11 AMD64 virtual environment with CPython 3.14.0. The browser demo started using only the standard library, the replay endpoint returned the verified fictional office, and headless Edge 158.0.4370.33 hydrated both the replay and archived results. The browser check tested rendering and data loading. Full cross-browser and accessibility certification remain outside this check.
- Offline reproduction verified 27,000 history rows, 2,300 family rows, 230 summaries and 184 paired intervals in 2.51 seconds. With the pinned plotting wheels installed from the local cache, the command took 5.89 seconds and generated four files across SVG and PDF. The isolated plotting environment passed `pip check`.
- The development environment ran `python -m pytest -q` with 152 passed and 36 subtests passed in 21.88 seconds. Its existing AnyIO pytest plugin emitted one deprecation warning. `node --check trace_mem/demo_web/app.js` and the staged privacy guard passed.
- Frozen controllers, experimental aggregates, approval-gate configuration and public reproduction inputs have no changes relative to the Step 37 merge.
