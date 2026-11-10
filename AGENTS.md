# Agent instructions for TRACE-Mem

Read `README.md` fully before taking action. Your purpose is to help the student research team build a reproducible memory-evaluation study, not to claim scores or publication acceptance.

## Permission gate

The CS9548 course outline restricts AI-generated assessment code/report content unless explicitly permitted by the instructor. **Do not generate assessed implementation or paper text until the team documents written permission** in `docs/ethics_and_permissions.md`. Allowed preparatory tasks pending permission: identify source repos and versions, inspect public benchmark documentation, document research design, recommend tests, and review human-written code.

## Scope

Prioritize Memora data audit, chronological replay, temporal-rule baseline, budget-matched random and fixed-threshold verification, then logistic-regression-based TRACE-Mem. Do not build an unrelated chat UI, multi-agent swarm, or large model fine-tuning. Never train on benchmark test labels.

## Agent workflow

1. Identify a single narrowly scoped issue and expected acceptance tests.
2. List files affected, source/license constraints and intended run commands.
3. Build behind a test when permission allows, and document failure modes.
4. Validate on synthetic development fixtures before touching held-out benchmark data.
5. Log exact command output, dependencies, seed, model identity, latency, and token cost.
6. State what was done, what remains, and any blocked tasks, without inventing results.

## Nonnegotiable correctness tests

- Corrected job/location fact updates the current answer.
- Past-tense question can retrieve historical but still permitted fact.
- A short visit does not replace a residence record.
- Deletion/privacy removal is obeyed by storage and retrieval.
- Ambiguous contradictory claim never silently overwrites.
- Random baseline matches the learned controller's verifier-call budget.
- Replay + cached model outputs reproducible with the same seed.
- Benchmarks cannot leak answer keys into retrieval or policy labels.

## Definition of done

Documentation matches executable behavior; all relevant tests pass; provenance is preserved; results can be reproduced from pinned commits and manifests; no unsupported novelty or performance claims are made.
