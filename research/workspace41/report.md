# Matched local model pilot

Protocol and scoring keys froze at e8257d0. See [protocol](protocol.md) and [raw per-case measurements](results.json). From the Step 41 implementation run `python -m scripts.workspace_model_pilot results/model-repeat.json` on a Windows development environment with psutil and both local Ollama models installed. The script refuses an existing output. Inputs are fictional, authored with AI assistance and used once for this comparison. Engineering results do not establish independent scientific validation.

| Outcome | Qwen2.5 7B Instruct Q4_K_M | Llama 3.2 3B |
| --- | ---: | ---: |
| Extraction TP / FP / FN | 4 / 1 / 2 | 3 / 0 / 3 |
| Hybrid extraction precision / recall / F1 | .800 / .667 / .727 | 1.000 / .500 / .667 |
| Extraction input / output tokens, 6 actual requests | 387 / 217 | 459 / 50 |
| Extraction elapsed, eight messages | 24.86 s | 9.86 s |
| Generated arithmetic, two repetitions | 2/2 | 0/2 |
| Generated abstention, exact UNKNOWN | 2/2 | 0/2 |
| Injection marker returned or retrieved | 0/2 | 0/2 |
| Direct current, historical and missing-slot checks | 6/6 | 6/6 |
| Answer-stage input / generated tokens | 1058 / 14 | 986 / 268 |
| All 12 answer-path calls, wall time | 11.16 s | 9.88 s |
| Highest sampled provider VRAM allocation | 3.94 GiB | 2.39 GiB |
| Sampled system-wide used RAM | 14.60–14.85 GiB | 14.21–14.39 GiB |

Each model got the same eight extraction messages and two repetitions of six questions at seed 23. Three personal-memory lookups per repetition used the deterministic reader and consumed zero model tokens. Three other answers per repetition were actual model outputs. Resource snapshots measure allocation after a call, not peak instantaneous GPU use or per-model process RAM. The first extraction took 17.10 s for Qwen with an empty provider model list and 7.75 s for Llama with only Qwen resident. The first arithmetic request took 8.70 s and 6.40 s respectively, the second 0.34 s and 0.61 s. Extraction and generation use different context limits. Execution order and model loading confound timing.

Both missed the paraphrased paycheck and research-project statements. Qwen recovered the tentative residence but produced an unsupported uncertain job for a split-residence statement. Llama made no false proposal on that case. Both correctly applied the deterministic multi-claim and correction patterns. Llama recognized missing ticket evidence but failed the exact-output rule by explaining its abstention. It failed the two-session arithmetic request despite receiving the approved duration. Qwen produced 37 twice. The repeated questions measure timing and consistency rather than independent scenarios. No transport errors occurred. Hardware was the existing RTX 2060 with 6 GiB VRAM, around 24 GiB system RAM, and Ollama 0.40.13. Cost USD 0.

Retain Qwen as the default for this supervised pilot under the frozen ranking rule. Llama is a useful lower-memory option. More unrelated synthesis tasks, ambiguous-date cases and paraphrased weakly supported memories are needed before making a general recommendation. The protective projection, rather than either model's capacity to ignore an injected instruction, accounts for the absence of the marker in retrieved notes.
