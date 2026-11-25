# Local verifier revision and frozen validation

## Original failure analysis

The [original 12-case result](ollama_label_collection.md) is preserved. Its five false updates were used only to diagnose the failure modes and design the revisions. They were excluded from the new evaluation denominator.

| Original case | Why the update was incorrect | Evidence needed for a replacement |
| --- | --- | --- |
| n2 temporary stay | The wedding accommodation was limited to a weekend and the user reaffirmed their home. | A current change of permanent residence. |
| n3 historical site | The warehouse was a previous training site. The event preceded the current worksite. | Confirmation that the warehouse is the current worksite. |
| n4 another person's commute | The bus was used by someone else and the user confirmed their own route. | A changed commute attributed to the user. |
| n6 alias | The expanded subscription name referred to the existing plan. | A distinct replacement plan with an effective change. |
| n7 unassigned transfer | A staffing need was mentioned without a transfer decision or named assignee. | A confirmed transfer for the user that is already in effect. |

The direct revision gives explicit current-person, current-time and replacement criteria. The evidence variant asks a first call to classify and quote the evidence. A second call reviews the original input and extracted evidence. An update must have both a confirmed evidence category and an exact quote from the conversation. The exact-match check establishes that the words appeared. It cannot establish that they support the conclusion.

## Frozen experiment

Commit `ce2d8f9` fixed the prompts, validators, cases and acceptance rule before inference. The new set contains 16 confirmed changes and 24 no-update cases, with distinct fictional values and statements. Negative cases include temporary, historical, hypothetical, future, uncertain, third-party, unrelated, alias, negated and conflicting examples. The synthetic expectations were written before seeing model output and only the evaluation process received them. The fixtures were independently specified from the prior diagnostic set. There was no external human adjudication.

- Model `llama3.2:3b`, digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` on loopback Ollama 0.40.13.
- Seed 23, temperature 0, 4,096 input ceiling, 256 output cap, 120-second timeout, zero retries. Each variant used a fresh ledger.
- Cases SHA-256 `efc13d87a1d81121b4432fe325c062acb3561f443e5a0bda756e895f78d85d82`.
- Combined prompt and schema SHA-256 `eeb7ecdfa5b58f059cefe5533a0972c5cd07191e80ed64318f29f110a940432a`.
- Acceptance required at least 34 of 40 correct, no false updates, no failed cases and at least 80% update recall. This preserves the original zero-false-update and zero-failure criteria.

```powershell
python -m scripts.validate_ollama_verifier_v2
python -m scripts.validate_ollama_verifier_v2 --output results/ollama-verifier-v2-recheck
```

## Observed results

| Variant | TP / TN / FP / FN | Accuracy | False-update rate | Update precision | Update recall | Schema compliance | Mean ms per case |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original, on new cases | 16 / 3 / 21 / 0 | 47.5% | 87.5% | 43.2% | 100% | 40/40 | 318.2 |
| Revised direct | 16 / 1 / 23 / 0 | 42.5% | 95.8% | 41.0% | 100% | 40/40 | 254.1 |
| Two-stage evidence | 16 / 1 / 23 / 0 | 42.5% | 95.8% | 41.0% | 100% | 80/80 | 837.0 |

False-update rate uses the 24 no-update cases as denominator. Schema compliance uses provider attempts. There were zero technical failures and zero cache hits. The variants ran sequentially. Latency includes local call and cache-ledger overhead, and can be affected by warm-up and run order.

The two-stage variant matched the revised direct verdict on update versus no update for every case. Its extractor called every input a confirmed replacement, so the structured category did not distinguish positives from negatives. Both revisions added false updates on one unrelated case and one conflicting case relative to the original. The evidence variant increased calls from 40 to 80 and increased mean case latency about 3.3 times relative to the revised direct prompt.

The comparison exited 1 because neither revision passed. The raw development report and read-only evaluation ledgers remain ignored under `results/ollama-verifier-v2-frozen/`. No research collection ran. The 26-case annotation packet still has SHA-256 `1dffda1962e49c1de62aa82f566bb31ba9148ec180adb78d6464111d2024ae08`.

## Next local candidate

Consider `qwen2.5:7b-instruct-q4_K_M` for a separately frozen verifier check. Its listed 4.7 GB Q4 weights are a plausible fit for 6 GiB VRAM with a short context. Runtime buffers may require partial CPU offload, for which 24 GiB system RAM provides headroom. This is a hardware estimate and an untested candidate. The registry and original model card list Apache-2.0. Download approval is pending. [Ollama model entry](https://ollama.com/library/qwen2.5:7b-instruct-q4_K_M) · [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
