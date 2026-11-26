# Final execution readiness

**Engineering handoff complete. Scientific execution remains blocked pending independent review and explicit approval.** Step 37 added the versioned runtime bindings and exercised engineering-only cases. It did not generate a final history, run model inference, modify frozen weights, or contact a reviewer.

## Verified engineering

- A metadata-only check confirmed the installed Qwen model manifest digest and Ollama 0.40.13. Six MiniLM files and seven DeBERTa files matched their pinned SHA-256 values. Two archived controller files and one frozen outcome file used to reconstruct training-only reference vectors also matched. The feature order, direct-v2 verifier and Reader V2 prompts/schemas and inference options match the committed pins. SHA checks of installed files and metadata are distinct from checking model outputs. [Machine preflight](execution_preflight.json)
- The entry point blocks without an approved receipt and frozen cohort. It strictly parses the JSON shapes, checks raw file and normalized cohort digests, validates role fields and pins adapter/backend configuration. A receipt is a record, so human authenticity and independence must be checked separately. The engine does not start a model before matching approval and running asset checks.
- Model-facing verifier inputs contain only the two competing facts and the current authorized verbatim span. The no-NLI arm and heuristic skip contradiction inference. MiniLM embeds only authorized, visible materialized candidates and the approved query. Reader V2 receives trimmed evidence from Evidence Index V2, with no transcript fallback. Unauthorized citations, missing answers and failed outputs remain failures. Gold and observed future arrivals are confined to scoring and retrospective diagnostics.
- Case-condition checkpoints bind results to their exact key and digest. A restart reuses already committed conditions. Each fresh verifier call reserves its own persisted row before dispatch. A killed process leaves its unresolved reservation charged to the ceiling. Exact reusable verifier entries match the request key, backend fingerprint and payload digest. Reader V2 uses the original exact Ollama cache and schema validation. An interrupted condition may re-run logical work. The separate physical ledgers retain interrupted attempts and measured tokens.
- Primary is chronological cap 2 only, up to 1,440 case-condition rows, 2,880 verifier and 1,440 reader physical reservations. Each verifier/reader call has 120-second timeout and zero automatic retries. The per-history logical ceiling remains two even with warm cache. Exhausting a physical cap pauses without treating unfinished conditions as results. Successful conditions commit individually. Secondary cap 0/5 and fixed-stream cap 0/2/5 each need a separate approved stage and output directory.

## Internal methodological review

The Step 36 estimand remains mean within-family paired difference with equal family weights, comparing T2 with B3 and H-paced at the same two-call ceiling. It retains 2,160 planned current checks per policy, including incomplete histories scored zero when no trustworthy state is available. Ten thousand family-paired draws with seed 360091 and 1.25/98.75 percentiles implement the two 97.5% marginal intervals. Equal realized calls or token expenditure remain separate descriptive questions.

The planner counts prior eligible items in the supplied sequence even when their observation days tie. On the closing day there is no forecast after the current decision, so a remaining call can be spent on an eligible current candidate. Day-granularity does not make earlier and later same-day effective states distinguishable. The frozen conflict guard requires a later effective date than the target's start. Engineering tests confirm that same-effective-day replacements are ineligible and do not silently overwrite the prior value. Authors must distinguish observed ordering from effective validity and cannot claim intraday state resolution.

Prepared claims enter the normal temporal transition path. They bypass raw-text extraction, so state and verification results will be conditional on those reviewed inputs. The engine also assumes one subject, exact predicates, a single eligible target, modeled future-effective values, and explicit authorized deletion scope. Mechanisms needing multi-entity inference, general event entailment, untrusted linkage or broad autonomous deletion should be prospectively excluded or separately scoped. Surface edits or graph relabeling cannot establish independent families. Independently review the causal dependency and how its structure changes gold. All methodological review reported here was internal and AI-assisted.

## Future commands and freeze

Run from the repository root. Prepare the actual protocol, per-case cohort and stage receipt only after independent review. Use ignored local paths. `execution_preflight.json` is a machine-readable contract with a blank approval template. The cohort is a JSON array of `{episode, gold, question}` records following the fixture contract, with ISO date strings, lists for sets, `{claim, source, fact_id}` event entries and `[fact_id, approved_span]` support entries. A separate gold object never enters the policy callbacks. Check the fixture taxonomy and the approved exclusions outside model execution.

```powershell
python -m scripts.run_validation_v1 verify-assets --nli data/models/nli-deberta-v3-xsmall-a150876 --outcomes results/updateset-v3-final/outcomes.jsonl
python -m scripts.run_validation_v1 fingerprints --stage primary --protocol results/approved/protocol.md --cohort results/approved/cohort.json
python -m scripts.run_validation_v1 preflight --stage primary --cohort results/approved/cohort.json --protocol results/approved/protocol.md --receipt results/approved/primary-receipt.json --nli data/models/nli-deberta-v3-xsmall-a150876 --outcomes results/updateset-v3-final/outcomes.jsonl
python -m scripts.run_validation_v1 run --stage primary --cohort results/approved/cohort.json --protocol results/approved/protocol.md --receipt results/approved/primary-receipt.json --nli data/models/nli-deberta-v3-xsmall-a150876 --outcomes results/updateset-v3-final/outcomes.jsonl --output results/independent-primary
```

Resume with the identical command and a single writer. The optional stage commands substitute `secondary` or `fixed` and require their own approved receipt and new output. Do not expand the primary resource cap or treat overflow as a failed scientific condition while resuming. Any change to recipe, hardware limits or model artifacts requires a reviewed freeze before proceeding.

## Human responsibilities still open

1. The owner reviews and personally sends the [draft inquiry](collaboration_inquiry.md), if desired.
2. An independent reviewer approves a protocol revision before final fixture generation. A separate author creates the families, and independent gold review adjudicates disjointness, source authorization, feasibility and reader labels without model predictions.
3. The project owner and independent parties attest the actual frozen artifacts, selected stage and resources. Their signatures and private review forms stay outside this repository.
4. Run only after preflight passes on those inputs. If independent review or the cohort is unavailable, keep the experiment pending.

[Reviewer overview](reviewer_research_summary.md) · [Onboarding](reviewer_onboarding.md) · [Blank approvals](protocol_approval_checklist.md)
