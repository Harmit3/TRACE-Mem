# Qwen TRACE-UpdateSet paired outcomes

## Frozen run

PR #18 was merged at `7a455b0`. Before collection, the local comparison utility verified Ollama 0.40.13 and installed Qwen2.5 7B Q4_K_M digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`. The prior 40-case validation report passed, and the live prompt and schema SHA-256 `186d105583c4fa4ecba72b82f9179acd8c140d72dc661679911654a5de8a8eb8` matched the frozen report. See [the gate and configuration](qwen_verifier.md).

The collection used the direct-v2 mode, seed 23, temperature zero, 4,096-token context, 256 output cap, 120-second timeout, zero retries, and a cap of 78 local requests. The configured 4,096 input ceiling reserves space for the output cap. The collector used one SQLite ledger with validated-response caching and resumability. The run completed in one execution with zero cache hits.

The verifier received only the old fact, proposed claim, dates, and source conversation. The collector joined outcomes against existing gold after inference. It skipped the held-out test split and all noneligible cases. The outcome audit checked every skipped row against the source, including all 28 test cases, and verified that no original gold or case inputs changed.

```powershell
$env:OLLAMA_HOST = 'http://127.0.0.1:11434'
python -m trace_mem.collect_labels data/updateset-v1-seed23 data/updateset-v1-qwen --database results/qwen-labels.sqlite --backend ollama --model qwen2.5:7b-instruct-q4_K_M --reference seed23-qwen7b-845dbda0ea48-direct-v2 --max-requests 78 --max-input-tokens 4096 --max-output-tokens 256 --context-tokens 4096 --timeout 120 --seed 23 --retries 0 --verification-mode direct-v2
python -m trace_mem.data.updateset validate data/updateset-v1-qwen
python -m scripts.summarize_updateset_outcomes data/updateset-v1-seed23 data/updateset-v1-qwen results/qwen-labels.sqlite data/updateset-v1-seed23-eligible-human-review.jsonl
```

The collection command requires a new output directory. Use the same ledger and unfinished output path to resume an interrupted run. Use the audit commands to inspect the completed run without calling the model.

## Observed outcomes

| Split | Paired decisions | Helpful | Not helpful | Awaiting human gold |
| --- | ---: | ---: | ---: | ---: |
| Train | 60 | 0 | 40 | 20 |
| Validation | 18 | 0 | 12 | 6 |
| Held-out test | 0 | 0 | 0 | 0 in collection |

All 78 pairs agreed. Train had 20 supersede-to-supersede pairs and 40 defer-to-defer pairs. Validation had 6 supersede-to-supersede pairs and 12 defer-to-defer pairs. Only the 52 pairs with existing independent synthetic rule gold received helpfulness labels. Because every pair agreed, none can satisfy the current helpfulness definition even if additional gold is adjudicated. The 26 unresolved labels stay null pending human review.

This release cannot fit binary logistic regression. Both training and validation need independently labeled cases where verification sometimes corrects a wrong unverified decision, along with negative cases. Future data should document how disagreement cases were sampled and preserve disjoint validation and test sets. No controller was trained.

## Run provenance and usage

- Source `cases.jsonl` SHA-256 `c42b23464cc25c86a912b720af3509b2601003cf55ff24fce4a9c6b16012fba4`.
- Paired `cases.jsonl` SHA-256 `f6d11105acfa99250ccca9e22c9fe391bdb715aff5db177a92c18fd652e695c0`.
- Unchanged 26-case review packet SHA-256 `1dffda1962e49c1de62aa82f566bb31ba9148ec180adb78d6464111d2024ae08`.
- 78 successful schema-valid requests, zero failures, zero retries, zero cache hits, 23,614 input and 962 output tokens, USD 0 provider cost.
- Provider latency was 73,644.810 ms summed, 944.164 ms mean, 857.067 ms median, 1,071.590 ms nearest-rank p95, and 6,484.585 ms maximum.

The outcome files, ledger, and review packet remain local and Git-ignored. This is a synthetic dataset with real local model decisions. It produces no benchmark result or claim about real-world accuracy.
