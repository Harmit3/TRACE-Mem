# TRACE-Mem

TRACE-Mem studies whether selective, budget-aware verification improves temporal memory as conversations evolve. It implements chronological replay, a temporal fact store, verification policies, authorized evidence retrieval, and an offline research console. The frozen evaluations show conditional benefits for learned allocation and substantial limits on end-to-end question answering.

## Start here

The **1.1.0 research source snapshot** includes an offline fictional demonstration, the research code and numeric evidence, and the independent [conference manuscript](research/conference_manuscript.pdf). The [final audit and release guide](docs/step43.md) links the editable sources, installation instructions, limitations, and submission checks. The **0.42.1 Windows Workspace beta** is a separate private build for supervised rehearsal. Use its practice profile for fictional conversations. See the [desktop quick start](desktop/START%20HERE.txt).

From the repository root with CPython 3.14 (the reference environment):

```text
python -m trace_mem.demo
python reproducibility/reproduce.py --output results/reproduced
```

Open http://127.0.0.1:8765 in your browser. Both commands run offline using the standard library. The console runs actual memory transitions on fictional inputs with a scripted verifier, and separately displays archived research results. For optional figures, scientific dependencies, and the test suite, see the [release guide](docs/technical_release.md). For the live walkthrough, see the [demonstration guide](docs/demonstration_guide.md).

## Implementation and research map

| Area | Entry points and evidence |
| --- | --- |
| Memory lifecycle and replay | [Architecture and feature inventory](docs/architecture.md), [engineering audit](docs/engineering_audit.md), [replay contracts](docs/replay_acceptance.md), [engine](trace_mem/memory.py), [policy runner](trace_mem/memora_benchmark.py) |
| Training and model adapters | [V3 dataset and fitted controller](docs/controller_training.md), [features](trace_mem/features_v3.py), [semantic models](docs/semantic_models.md), [providers](docs/llm_providers.md) |
| Authorization and answers | [Evidence Index V2](docs/memora_step29.md), [Reader V2](trace_mem/reader_v2.py), [cache authorization](trace_mem/authorized_answer_cache.py) |
| Experiments and figures | [Experiment log](docs/experiment_log.md), [chronological inventory](research/tables/experiment-inventory.csv), [publication figures](research/figures/), [results tables](research/tables/) |
| Reproduction | [Public numeric release](reproducibility/README.md), [artifact dependencies](docs/reproducibility_checklist.md), [evidence audit](docs/research_evidence_audit.md) |
| Publication and future work | [Final claim index](research/final_claim_index.md), [preprint checklist](research/preprint_checklist.md), [manuscript outline](research/manuscript_outline.md), [bibliography](research/references.bib), [pending independent protocol](research/final_execution_readiness.md) |

## What the experiments show

- Step 30 used 100 synthetic histories across ten design families. At 250 calls per arm, T2 scored 434/600 current-memory checks versus 394/600 for H-paced in chronological replay. The matched fixed stream reversed the ranking at 341/600 versus 409/600. The T2-minus-H-paced paired family intervals were +0.7 to +12.3 and −16.3 to −6.3 percentage points, respectively. These estimate different interventions. [Step 30](docs/step30_controller_reevaluation.md)
- Step 31 reused those histories. At the 50% allowance, doubling the planning horizon reduced T2 spending to 211/250 and its accuracy to 59.0%, versus B3 at 250 calls and 68.7%. At the nominal horizon, the T2-minus-B3 interval included zero. The reader subset gives no positive transfer estimate. [Step 31](docs/step31_verification_robustness.md)
- LongMemEval local judging found 3/14 correct for BM25, 2/14 for MiniLM, and 6/14 for oracle evidence. Only one managed history completed and the compared managed arms missed it. Step 33's extraction and reader candidates missed their promotion gates. [Step 32](docs/longmemeval_step32.md) · [Step 33](docs/step33_artifacts/metrics.json)
- Human-reviewed field restrictions supported bounded Evidence Index V2 evaluation. Autonomous deletion resolution, general privacy protection, and external superiority remain unproven. The 90-family experiment is future work and retains its own review gates. Independent replication remains pending and is separate from technical release readiness. [Claim index](research/final_claim_index.md)

For citation metadata see [CITATION.cff](CITATION.cff). AI assistance and the instructor's verbal coding authorization are documented in the [permissions record](docs/ethics_and_permissions.md). Independent research materials are separate from assessed CS9548 report and presentation content.
