# TRACE-UpdateSet

TRACE-UpdateSet v1 generates fictional memory-decision cases from templates in `trace_mem.data.updateset`. It has no Memora or LongMemEval input. The generated release records the exact generator hash, settings, payload hash and per-split counts. Keep generated cases and annotation sidecars under the ignored `data/` directory.

## Reproduce the synthetic release

```powershell
python -m trace_mem.data.updateset generate data/updateset-v1-seed23 --seed 23 --train 140 --validation 42 --test 28
python -m trace_mem.data.updateset validate data/updateset-v1-seed23
python -m trace_mem.data.updateset annotation-packet data/updateset-v1-seed23 data/updateset-v1-seed23-review.jsonl
```

Use a fresh output directory. Validation checks the case hash and recomputes the generated inputs and distribution from the manifest. It rejects duplicate IDs, duplicate normalized conversation text, and overlap in persona, scenario family, or conversation history between splits. Pin one release for comparisons because varying the seed changes instantiations of the same template families.

Each case contains the conversation, an old fact, a new claim, observation and effective dates, source references, the proposed operation, gold decision provenance, optional paired policy decisions, and the derived helpfulness label. The proposal is a simple intent-based guess. The gold rule comes from the template's independent scenario definition. Supersession and deletion require the old fact ID. The other operations use a null target. Effective intervals use inclusive starts and exclusive ends.

There are seven broad categories in each split with distinct scenario families and fictional personas and histories. Gold rules supersede on explicit replacement, defer unresolved contradictions, add when the old fact expired, preserve nonoverlapping facts as historical, keep time-bounded temporary events separate from permanent predicates, and remove the designated fact on explicit deletion. Ambiguous cases begin with null gold.

## Independent annotation and outcome collection

1. Export the annotation packet. Assign two reviewers to independently label the pending cases using the conversation, effective dates, and source references. Reviewers should have no access to proposals, policy outcomes, or one another's judgments before submitting. Preserve disagreement and adjudication records privately, using opaque references in the dataset.
2. Adjudicate disagreements and import one final gold entry per case. Use a JSONL record with fields `case_id` and `gold`. The gold object contains `origin: "human_annotation"`, `reference` pointing to the adjudication, and `decision` with `operation` and `target_id`. Leave unresolved cases pending. Synthetic rule entries are immutable.
3. Run a fixed unverified policy and the corresponding verified policy from the same prior state. Give their runner only conversation and fact/claim inputs plus non-label run identifiers. Keep the gold, proposed operation, scenario metadata and helpfulness fields out of policy inputs. Record the decisions independently of gold. Use a JSONL record with `case_id` and `outcomes`. The outcomes object contains `origin` (`recorded_verifier` or `synthetic_mock`), `reference` identifying the run, and `unverified` and `verified` decision objects. Save the runner config and commit, verifier identity and revision, seed, and failure handling with the referenced run.
4. Import each sidecar into a new release. Helpfulness is true only when the unverified decision disagrees with gold and the verified decision agrees, including the target when applicable. All other observed comparisons are false. Missing gold or paired outcomes yields a null label.

```powershell
python -m trace_mem.data.updateset import-gold data/updateset-v1-seed23 data/updateset-v1-gold --records data/adjudicated-gold.jsonl
python -m trace_mem.data.updateset import-outcomes data/updateset-v1-gold data/updateset-v1-labeled --records data/paired-outcomes.jsonl
python -m trace_mem.data.updateset validate data/updateset-v1-labeled
```

The importer verifies IDs, schema and declared provenance. Human independence and fidelity of recorded verifier decisions require review of the referenced records. Use mock outcomes for pipeline tests only. Fit on eligible training labels, select calibration and thresholds using validation only, and reserve test for the frozen analysis.

## Limitations

The generator instantiates 21 hand-authored families. Its two-turn histories, exact target IDs, templated phrasing, and balanced category counts are useful for exercising the pipeline. They give limited evidence about real conversations, indirect requests or transfer. The duplicate check catches normalized exact matches. Broader semantic overlap and distribution artifacts require human audit. This release contains zero human annotations and zero observed verification-helpfulness labels.
