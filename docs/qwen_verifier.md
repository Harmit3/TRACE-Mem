# Pinned Qwen and Llama verifier comparison

## Implementation audit

| Area | Finding |
| --- | --- |
| Prompt and roles | Ollama gets one system message with the task and one user message containing JSON with the existing fact, proposal and conversation. Gold and expected decisions stay in the evaluator. The candidate's intent and value can still bias the model. The comparison retains the same format and direct-v2 prompt for both models. |
| Schema | Ollama receives a JSON schema that constrains keys and allowed verdicts. It does not check whether the selected verdict is supported by the user evidence. |
| Enum ordering | The first evidence category was confirmed replacement. Reversing the evidence enum on the original five false-update cases and one positive diagnostic left all six categories and final verdicts unchanged. Both orders made all five false updates. This probe offers no evidence that ordering caused those failures. |
| Truncation | The original provider checked a byte-based input estimate but did not explicitly set Ollama context or reserve output space within it. The comparison sets `num_ctx=4096`, reserves 256 tokens for output and rejects requests above its conservative remaining allowance. The largest reported input was 281 tokens for each model. No response hit its output ceiling. |
| Parsing | The adapter rejects incomplete completions and invalid usage. The verifier requires one JSON object, exactly one verdict field and a known verdict. The evidence mode separately checks exact quote membership. Validation scores only the normalized verdict, and records schema or provider errors separately. |
| Caching | The cache key covers the task, model, schema, options, and messages. A configured context change now changes the key. All comparison, smoke and audit ledgers were fresh and reported zero cache hits. No observed false updates came from cached responses. |

The enum diagnostic is reproducible with `python -m scripts.audit_ollama_enum` when its output directory is absent. It uses only diagnostic inputs from the original validation. All 24 diagnostic requests validated with zero provider cost.

## Approved download and smoke

The approved `ollama pull qwen2.5:7b-instruct-q4_K_M` completed with digest verification. Ollama 0.40.13 reported a 7.6B GGUF Q4_K_M model, 4,683,087,332 bytes on disk, and digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`. The local `/api/show` license text and the published model card identify Apache-2.0. [Ollama tag](https://ollama.com/library/qwen2.5:7b-instruct-q4_K_M) · [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)

`python -m scripts.smoke_ollama --model qwen2.5:7b-instruct-q4_K_M --output results/qwen-smoke` produced eight schema-valid responses with zero paid cost. Both passes verified the correction as `update` and deferred the uncertain case with `insufficient_evidence`. Correction extraction returned Birch Lab with `correct` on pass 1 and `assert` on pass 2. Both uncertain extractions returned Cedar Lab with `uncertain`. Per-call latency was 543.1–6,640.3 ms, including the initial model load. The smoke used the original prompt and was separate from the frozen comparison.

## Fresh frozen comparison

PR #17 was merged on base `1bf28d2`. Commit `06843ae` froze a fresh synthetic set of 40 cases and both model configurations before evaluation. The 16 updates and 24 no-updates were independently specified from the prior runs. They are synthetic fixtures with no human adjudication. The gate remains at least 34 correct, zero false updates, zero failed cases and at least 80% update recall.

- Cases SHA-256 `9200b1dd7fe867b465e5417fd9cf3dece3f98e58b90b1a7058a7b4960df4f54f`.
- Direct-v2 prompt and schema SHA-256 `186d105583c4fa4ecba72b82f9179acd8c140d72dc661679911654a5de8a8eb8`.
- Both models used temperature 0, seed 23, context 4,096, configured input ceiling 4,096 with output allowance deducted, maximum output 256, 120-second timeout and zero retries.
- Llama digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`.

| Model | TP / TN / FP / FN | Accuracy | False-update rate | Precision | Recall | Schema | Mean case latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Llama 3.2 3B | 16 / 2 / 22 / 0 | 45.0% | 91.7% | 42.1% | 100% | 40/40 | 348.2 ms |
| Qwen2.5 7B | 14 / 24 / 0 / 2 | 95.0% | 0.0% | 100% | 87.5% | 40/40 | 995.9 ms |

Both arms had zero technical failures. Qwen passed and missed two actual replacements involving a library preference and a courier. Qwen logged 10,928 input and 490 output tokens, and Llama logged 10,908 input and 325 output tokens. Ollama reported Qwen resident at 5,152,041,860 bytes, of which 4,199,263,764 were in VRAM (about 3.91 GiB). Llama reported 2,561,000,078 bytes resident, entirely in VRAM (about 2.39 GiB). These are post-run resident snapshots, and sequential model loads influence timing. The small development comparison establishes no benchmark accuracy.

```powershell
$digest = '845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e'
python -m scripts.compare_local_verifiers --qwen-digest $digest --output results/qwen-llama-recheck
```

Prior failed reports and the local 26-case human review packet remain unchanged. No research labels were collected. The validated mode is available for the next collection run through `--backend ollama --model qwen2.5:7b-instruct-q4_K_M --verification-mode direct-v2 --context-tokens 4096 --seed 23 --timeout 120`. Confirm the installed digest again before collection. Human adjudication remains pending, and the observed helpfulness distribution must be checked before training.
