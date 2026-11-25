# Replay acceptance cases

Proposed synthetic fixtures for review before implementation. Run each scenario from an empty store and specify any warm cache explicitly. Use fictional claims, fixed dates and deterministic cached model responses. A model call is unnecessary for checking storage, retrieval or replay behavior.

| Case | Synthetic sequence | Expected checks |
| --- | --- | --- |
| Correction | On March 1, a user reports working at Alder Labs. On March 5, they say they now work at Birch Labs. | A current query resolves to Birch Labs. The earlier employment record is superseded and its revision has a source reference and timestamp. |
| Historical retrieval | Replay the correction and ask where the user worked on March 3. | The historical query resolves to Alder Labs. A query for March 5 resolves to Birch Labs under the fixture's inclusive start and exclusive end convention. |
| Visit | The user lives in Oak City and reports a weekend trip to Pine City. | The current residence remains Oak City. Any stored visit is a separate fact with bounded dates when supplied. |
| Deletion | After the correction, the user explicitly asks to remove the Alder Labs employment detail. Restart and replay with the same cache. | No current or historical retrieval surfaces the detail after the removal. Inspect persisted facts, search indexes, replay caches and diagnostic logs for the removed payload. Verify a restart cannot resurrect it. |
| Ambiguity | The user reports working at Alder Labs, then says they might join Birch Labs. | The second event leaves the current job intact. Any deferred proposal is traceable and cannot be returned as the current job. |
| Verifier failure | Trigger verification on an ambiguous update and return a timeout or malformed judgment. | The current and historical records are unchanged. The attempted call and failure are accounted for. |
| Equal budgets | Give random, threshold and learned policies the same deterministic sequence of eligible conflicts. Test budgets of zero, one and more than the sequence can support. | The zero-budget run makes zero calls. For each feasible target, realized verifier invocations match exactly. If the target is infeasible, surface the shortfall explicitly. Count failed invocations against the cap. |
| Replay reproducibility | Repeat the same ordered events, seed, config and complete response cache. Include two sessions on the same date. | Stable session and turn ordering produces identical transitions, retrieval outputs and verifier selections. Compare semantic trace fields while checking wall-clock latency separately. |
| Label isolation | Place distinct synthetic sentinel values in scorer-only fields, then rerun with those fields changed and all model inputs fixed. | Extraction, retrieval, reader and verifier prompts, controller features and policy-training labels are identical. Only scoring may depend on the sentinel values. |

## Proposed data boundaries

- Replay receives a namespaced history identifier, ordered source references, conversation messages and timestamps. Keep effective dates stated in the conversation distinct from observation times.
- A candidate update carries proposed values, effective dates and provenance. Every committed transition points to its source and records its observation time. Historical retrieval applies the query's effective time and the privacy state at the point of retrieval.
- Reader input contains the query and eligible facts. Evaluators receive committed predictions and scorer-only rubrics. Controller development receives independent synthetic or annotated decisions with lineage recorded outside final benchmark data.
- For the budget test, define a common eligible conflict stream for the isolated policy comparison. In closed-loop replay, log differing candidate streams and any shortfall because earlier policy decisions can alter later eligibility.

Once implementation is authorized, use the repository's planned `pytest -q` entry point to exercise these cases before a development-set smoke evaluation. This document records proposed acceptance criteria. No executable fixtures or experiment results accompany it.
