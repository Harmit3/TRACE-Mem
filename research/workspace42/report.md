# Step 42 long-history engineering pilot

Fixture and endpoint freeze 6fe317d. Measured candidate f93c13b. Reproduce with `python -m scripts.workspace_long_history results/long-history-repeat.json` at the measured revision in the reference Windows environment with Qwen, the optional CPU worker and cached MiniLM. The runner refuses an existing output. Questions are shared across nested prefixes; the source initial turn and distractor generator are fixed. No private conversations or human responses were used. See [protocol](protocol.md), [inputs](inputs.json) and [all 54 observations](results.json).

## What was measured

The six histories contained 16, 62, 124, 247, 493 and 985 turns. Word-and-punctuation counts were 1,016, 4,006, 8,036, 16,031, 32,021 and 64,001. These are approximations of accumulated content tokens. They exclude chat templates and are not Qwen tokenizer measurements. Ollama reported the actual active prompt counts. At most 1,030 prompt tokens were used under the common 4,096 context configuration, 32 output tokens and 1,024-character memory budget. The conservative byte-based assembler and recent-turn ceiling discarded the early factual turn even at the shortest length. All lengths therefore test the same beyond-available-history condition. The data do not identify a crossover length.

| Estimated length | Standard exact | Conventional hybrid RAG exact | TRACE-Mem exact |
| --- | --- | --- | --- |
| 1k | 0/3 | 1/3 | 3/3 |
| 4k | 0/3 | 1/3 | 3/3 |
| 8k | 0/3 | 1/3 | 3/3 |
| 16k | 0/3 | 1/3 | 3/3 |
| 32k | 0/3 | 1/3 | 3/3 |
| 64k | 0/3 | 1/3 | 3/3 |

| Mode | Retrieval precision | Retrieval recall | Current / historical exact | Generated calculation | Actual input/output | Total wall seconds |
| --- | --- | --- | --- | --- | --- | --- |
| Standard | undefined | 0/24 | 0/6 and 0/6 | 0/6 | 16002/36 | 20.00 |
| Conventional RAG | 12/24 | 12/24 | 0/6 and 0/6 | 6/6 | 16794/42 | 26.27 |
| TRACE-Mem | 24/30 | 24/24 | 6/6 and 6/6 | 6/6 | 5718/18 | 6.98 |

Standard answered UNKNOWN 18 times. RAG abstained on all 12 location questions and computed 20 on every project question. TRACE-Mem used exact, date-authorized lookup for the 12 residence answers (zero model tokens) and the same local Qwen for the six calculations. Both retrieval arms received the same reviewed revisions, field authorization, CPU MiniLM and lexical ranking. RAG could consider prior versions with explicit sharing consent. Both included some irrelevant project evidence. No request failures. First-use model/encoder loading, arm order and the direct route affect wall times; these totals are descriptive.

Disk memory snapshot size was 1,623 bytes. The synthetic SQLite file ranged from 24,576 to 385,024 bytes, including allocated free pages. This measures source-mode storage; encrypted desktop sizes will differ. Fact acquisition used a prepared reviewed store, separate from the original conversation and consistent across retrieval arms. One uncertainty probe was deferred by scripted review; extraction took about 1.1 ms and zero model tokens. The deleted badge was absent from storage. These two deterministic checks are not scored reader probes. No verifier ran (zero calls, tokens or measured inference overhead). The study does not estimate autonomous ingestion cost over 64k tokens or test independent histories, adversarial retention or broad user benefit.

## Semantic retrieval probe

On four additional frozen paraphrases, lexical search had 0/4 top-one hits and local MiniLM had 1/4. MiniLM returned education for the enrollment paraphrase and returned nothing for the home, paycheck and undertaking paraphrases. It loaded successfully; the previous 0.30 threshold and lexical-first ranking were retained. This does not justify enabling the worker by default. The test used short field/value pairs and one spelling per query. No tuning followed.

## Reproducibility and limits

Model Qwen2.5 7B Instruct Q4_K_M, temperature zero, seed 23, RTX 2060, local Ollama and existing cached MiniLM revision c9745ed1d9f207416be6d2e6f8de32d1f16199bf. Direct answers, generated answers and software checks have separate evidence. The six lengths reuse a single trajectory and three questions; no independence, statistical significance or native-context expansion claim follows. Frozen protocol and scoring values were not fed to retrieval or generation; questions and authored history entered the application as inputs. Operational identifiers, random UUIDs, machine clock and cache warmth may vary across repeats. Future work should test short histories fully retained by Standard, an independently tokenized recent-history baseline, more diverse paraphrases and naturally extracted unreviewed trajectories. The desktop encryption, usability and named-reference hardening that followed the pilot were tested separately without rerunning or rescoring the frozen measurements.
