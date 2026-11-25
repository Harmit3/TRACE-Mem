# Agent instructions for TRACE-Mem

Read `README.md` fully before taking action. TRACE-Mem is a long-term independent research and open-source project that continues beyond CS9548.

## Standing repository-owner authorization

The owner authorizes Codex and other AI development tools to work autonomously on TRACE-Mem until the owner explicitly modifies or revokes this authorization. This supersedes earlier repository-specific written-only permission gates and development restrictions.

- Design, implement, refactor, optimize, debug, and test the codebase. Remove obsolete project files when justified and protect important research artifacts from irreversible loss.
- Develop algorithms, models, research methods, automated tests, CI/CD, and reproducible pipelines. Train models, run local inference, and conduct benchmarks, statistical analyses, and ablation studies.
- Download appropriate public datasets and open-source checkpoints within available hardware and storage capacity. Install development dependencies and respect applicable licenses and terms.
- Produce technical documentation, research notes, mathematical explanations, diagrams, tables, and figures. Assist with independent manuscripts and supplementary materials subject to academic, ethical, and publication requirements.
- Create branches, commits, pushes, and pull requests. Make ordinary technical decisions autonomously and pursue justified improvements within the project's research scope.

## Assessed coursework

Apply institutional and instructor requirements to assessed work. The documented November 23, 2026 verbal authorization covers AI-assisted TRACE-Mem coding and software development for CS9548. The historical record and separate course requirements for the assessed report and presentation are in [docs/ethics_and_permissions.md](docs/ethics_and_permissions.md).

## Research and operational safeguards

- Prefer local models and free resources. Obtain approval before incurring financial costs.
- Preserve prior experimental results, protocols, provenance, and reproducibility. Treat negative results as findings and prioritize scientific validity.
- Protect credentials, private data, and sensitive information. Respect licenses, privacy, research ethics, and applicable publication policies.
- Keep held-out evaluation data isolated from training, selection, threshold tuning, retrieval prompts, and labels. Never fabricate research results, citations, human annotations, or metrics.
- Record AI-assisted contributions and human review transparently.

## Agent workflow

1. Identify a scoped task and its acceptance checks.
2. Verify source and license constraints and record the intended run commands.
3. Document failure modes and validate on development fixtures before held-out evaluation.
4. Record relevant commands, dependency versions, seeds, model identity, latency, and token cost.
5. Report completed work, evidence, and genuine blockers.

## Nonnegotiable correctness tests

- Corrected job/location fact updates the current answer.
- Past-tense question can retrieve historical but still permitted fact.
- A short visit does not replace a residence record.
- Deletion/privacy removal is obeyed by storage and retrieval.
- Ambiguous contradictory claim never silently overwrites.
- Random baseline matches the learned controller's verifier-call budget.
- Replay and cached model outputs are reproducible with the same seed.
- Benchmarks cannot leak answer keys into retrieval or policy labels.

## Definition of done

Documentation matches executable behavior, relevant tests pass, provenance is preserved, and results can be reproduced from pinned commits and manifests. Novelty and performance claims require evidence.
