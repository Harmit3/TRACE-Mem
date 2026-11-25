# Frozen verifier check and label collection status

The local Ollama 0.40.13 server matched `llama3.2:3b` digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`. The verifier prompt, response schema, 12 new development cases, and pass gate were frozen before inference at `e063325`. The prompt was unchanged from the previous local smoke. Development expectations were defined in code before inference and used only to score returned verdicts.

| Setting | Frozen value |
| --- | --- |
| Prompt and response schema SHA-256 | `c518ad578c2a58b381d8c0b404b6ec5fd115b8e4193c4da334bb14fd4c23ae30` |
| Development cases SHA-256 | `7f1504b756a13a26699248a97dc3a8632b1b1463a3ef4f511773fe58deea0f5b` |
| TRACE-UpdateSet cases SHA-256 | `c42b23464cc25c86a912b720af3509b2601003cf55ff24fce4a9c6b16012fba4` |
| Generation | Seed 23, temperature 0, 256 maximum output tokens, 4,096 input ceiling |
| Transport | Loopback, 120-second timeout, zero retries, one fresh SQLite ledger |
| Gate | At least 10 of 12 correct update decisions, zero false updates and zero technical failures |

## Observed validation

The frozen verifier failed the gate. It returned `update` for all five actual replacements, including one phrased as an assertion. It also returned `update` for five of seven cases where the right decision was to preserve the previous fact. The five errors covered a temporary stay, historical employment, another person's commute, an alias, and an unassigned transfer. The two explicitly uncertain cases returned `insufficient_evidence`. This small, independently constructed synthetic set identifies failure modes and establishes no benchmark accuracy.

All 12 calls returned valid schema. The run logged zero technical failures and cache hits, 3,229 input tokens, 102 output tokens, 5,285.85 ms total provider latency and USD 0 provider cost. The local report and resumable response cache are under `results/ollama-verifier-dev-seed23/`.

## Collection and review

| Split | Eligible for this collection | Pending human gold | Paired outcomes collected | Helpful | Not helpful |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 60 | 20 | 0 | 0 | 0 |
| Validation | 18 | 6 | 0 | 0 | 0 |
| Test | Excluded | Excluded | 0 | 0 | 0 |

The gate blocked the 78-case collection. Keep the failed development set as regression evidence. Any revised verifier requires a separately frozen, untouched development check. Keep recorded verifier decisions and human annotations independent. See [annotation and import instructions](updateset.md#independent-annotation-and-outcome-collection).

The blind review packet is local at `data/updateset-v1-seed23-eligible-human-review.jsonl`. It contains 26 pending cases, their source conversation and fact/claim inputs. Its SHA-256 is `1dffda1962e49c1de62aa82f566bb31ba9148ec180adb78d6464111d2024ae08`. Human annotations are pending.

```powershell
python -m scripts.validate_ollama_verifier --output results/ollama-verifier-dev-recheck
python -m scripts.export_eligible_annotations data/updateset-v1-seed23 data/review-copy.jsonl
```
