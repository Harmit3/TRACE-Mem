# Reproducibility checklist

## What reran in Step 34

- [x] Independently recomputed 230 condition summaries and 184 paired intervals from 200 Step 30/31 checkpoint files. The files contain the same 100 histories in ten families. Verified realized budget ceilings, fixed quota matching, repeat-weighted B4 and logical-call accounting.
- [x] Verified 39 historical artifacts. Regenerated summaries and visual outputs for Steps 22–26 and 29–33 from their saved reports and scoring checkpoints. Reproduced Step 18's evaluation JSON and four figures byte-for-byte from the original fit. The later authorization rerun changes the fit manifest hash without changing the metrics. Step 21's published aggregate omits the private per-case entries from the local report. [Artifact checks](../research/tables/artifact-verification.csv)
- [x] Reaudited the v2 and v3 releases and regenerated the v3 no-NLI projection into a new directory. The v2 audit verifies 500 cases and 601 candidate IDs. The v3 audit verifies 200 histories, 40 families, 726 candidates, 232 feature rows and no normalized pilot text overlap under its test.
- [x] Ran the repository suite. 131 tests and 36 subtests passed. A pre-existing third-party AnyIO deprecation warning remains.
- [x] Prior research outputs remained read-only. No training, benchmark expansion, or inference ran.

## Public dependencies and local inputs

| Evidence | Public material | Existing local requirements and unresolved access |
| --- | --- | --- |
| Engineering checks and early mock replay | `trace_mem/`, `tests/`, pinned dependency lists, replay contracts | None for fixture-only tests. Full workspace discovery can include pinned upstream tests, so record the command, environment and discovery scope. |
| V1 and V2 training-data experiments and provider tests | Generators, manifests and commands in [v1](updateset.md), [v2](updateset_v2.md), [v2 release](updateset_v2_full.md), [local Ollama](ollama_local.md) and [verifier comparison](qwen_verifier.md) | Generated data under `data/`, local response ledgers and model versions. Real reviewed labels, prompt logs and weights are excluded from the public project. Earlier smoke entries provide prose or command receipts where no complete per-call checkpoint is linked. |
| V3 preparation and T1 model | [V3 release](updateset_v3_final.md), [NLI validation](updateset_v3_nli.md), public model artifacts and [fit protocol](t1_v3_training.md) | Generated seeded histories, outcomes JSONL, frozen feature projection and fit manifest. Original Step 18 preliminary and later authorization reruns have distinct manifests. Do not permit pending gold to enter calibration or scoring. |
| Memora Steps 19–27 | [Memora implementation](https://github.com/geniesinc/Memora) at `a6493188efc836d6511ed5e4163fe3ba87da30ff`, local runner and freeze documents, original renderers, safe aggregates | Local dev-only transcripts, predicted outputs, evidence nominations, translated local rubric inputs and grader caches. Keep held-out personas unopened. Re-render with the documented render function rather than a CLI that starts adjudication. |
| Step 29 human-assisted recovery | [Protocol and aggregate](memora_step29.md), provenance and revocation code | The private 18-decision worksheet, reviewed spans and derivative plans are required for full reproduction. Exact human input is not replaceable with generated annotations. Provide controlled access only with consent and source permissions. |
| Step 30 | [Freeze](step30_freeze.json), executable fictional generator, public model artifacts, [aggregate](step30_artifacts/aggregate.json) | `results/step30/report.json` and all `histories/*.json` for offline audit. Reproduction from generation also needs the V3 synthetic outcomes and identical local inference settings and responses. |
| Step 31 | [Freeze](step31_freeze.json), prior policies, [aggregate](step31_artifacts/aggregate.json) | `results/step31/report.json` and all its checkpoints. A new replay requires the original Step 30 report and exact-response caches. The token reconstruction depends on the archived verifier ledger's single-writer ordered history. |
| Step 32 | [Cleaned dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/98d7416c24c778c2fee6e6f3006e7a073259d48f) and [code](https://github.com/xiaowu0162/LongMemEval/tree/9e0b455f4ef0e2ab8f2e582289761153549043fc), both MIT, [freeze](step32_freeze.json) and safe outputs | Use upstream download and verify SHA. Local selected inputs, blind predictions and score sheets are separate. The safe report can be rendered offline. Human worksheet remains local and pending. Failed extraction response bodies are absent from the original cache. Never make the 486 reserve questions model-visible while reproducing this sample. |
| Step 33 | Fictional fixture source, [freeze](step33_freeze.json), [promotion report](step33_extraction_reader.md) and safe analyzed outputs | Saved validation and forensic result files under `results/step33`. The forensic and secondary judge stages use already examined Step 32 artifacts, preserved read-only. Rendering needs only safe metrics. |

Exact model revisions for the central verification experiments are Qwen `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, MiniLM `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, and DeBERTa `a150876415327c80daeff35ca6f68f5ed8cf5c24`. Step 33 includes a separate pinned Llama digest in its judge audit. The provider settings fix the local generation seed and context length. Code and cached outputs are more reliable for byte-level reproduction than a seed alone. Dependencies and local Windows versions are recorded per run. Check license requirements before distributing any model checkpoint.

## Offline reproduction commands

From the workspace root with the archived local result folders available:

```powershell
python -m pytest -q
python -m scripts.audit_step34
python -m scripts.verify_step34_artifacts results/step34-artifact-check-new
python -m scripts.summarize_step30 results/step30/report.json results/step34/step30
python -m scripts.summarize_step31 results/step31/report.json results/step34/step31
python -m scripts.summarize_longmemeval results/step32/safe-report.json results/step34/step32
python -m scripts.summarize_step33 results/step33 results/step34/step33
```

## Step 35 public release and validation

The [standalone package](../reproducibility/README.md) contains 11 files totaling 503,798 bytes on disk. It has 27,000 history-condition-seed records and 2,300 family-condition records. The release binds packaged bytes with SHA-256 and records the source report, freeze, published aggregate, controller and figure digests. Logical per-history token usage is retained for Step 31. The Step 30 archive only supports fresh-token totals at the verifier level, so its per-history logical token fields are absent.

Internal validation copied only the manifest-listed files and checksum list to a new directory, used a fresh CPython 3.14.0 virtual environment on Windows 11 x64 build 26300, discarded inherited Python paths, and installed plotting wheels without an index. With NumPy 2.4.2, Matplotlib 3.10.8 and the transitive versions in [requirements.txt](../reproducibility/requirements.txt), the numerical check took 2.25 seconds and the full run with two figures in both SVG and PDF took 3.81 seconds. All 230 summaries and 184 intervals matched within absolute tolerance 1e-12. All four figure files matched their original SHA-256 values. `pip check` found no broken requirements. No inference, benchmark download, original result path, or third-party reviewer participated in the isolated computation. Rendering may vary outside the pinned environment.

Independent reproduction of the original model interventions would still need new inference or controlled access to exact archived inputs and responses. Step 29 also requires private human-approved grants. Do not distribute private worksheets, benchmark answers or response caches. The [blank review record](../reproducibility/independent-review-checklist.md) and [proposed next protocol](../research/independent_validation_protocol.md) are pending external review.

## Step 36 prospective execution boundary

The [protocol v2 review packet](../research/independent_reviewer_packet.md) and [blank approvals](../research/protocol_approval_checklist.md) are ready for independent review. The prospectively estimated adjusted interval widths and observed latency extrapolations are recorded separately. `trace_mem.causal_horizon_v1` wraps the frozen pacing logic. `trace_mem.validation_v2` provides exact request-key metering, deterministic replay, private checkpoints, and paired statistics. `trace_mem.fixture_independence_v1` checks normalized wording and canonical transition graphs. Run `python -m pytest -q tests/test_validation_v2.py` for the synthetic engineering checks.

A later operator must independently validate the reviewed fixture registry, blind source and gold files, instantiate the original pinned feature builders and Reader V2 with the approved backend receipt, and compare the run fingerprint. Use `frozen_rules` to load verified published score artifacts with the original frozen training-reference vectors. Project-owner authorization for repository work is separate from scientific approval and creates neither independent review nor permission to substitute internal cases. No final dataset or model inference was produced in Step 36.
