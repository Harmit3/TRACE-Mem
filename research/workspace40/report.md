# Workspace comparative evaluation

Freeze 50addd8, evaluated implementation c8918f2. From the repository root, run `python -m scripts.workspace_pilot results/step40-repeat.json` with local Ollama and the pinned cached MiniLM available. The command refuses an existing output. The Step 39B Cedar Town fixture served as the development smoke before the pilot. The held-out engineering fixture was internally authored and run once. The scoring file is opened after all requests. Review the [protocol](protocol.md), [inputs](inputs.json), [scoring key](scoring.json) and [observations](results.json).

## Live results

| Mode | Exact answers | Current answers | Historical answer | Retrieval precision | Retrieval recall | Input/output tokens | Mean elapsed seconds | Exact abstentions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Standard | 1/5 | 0/3 | 0/1 | undefined (zero retrieved) | 0/4 | 1631/10 | 1.39 | 5/5 |
| Conventional RAG | 1/5 | 0/3 | 0/1 | 4/8 | 4/4 | 2243/56 | 2.33 | 3/5 |
| TRACE-Mem | 2/5 | 1/3 | 0/1 | 4/4 | 4/4 | 1937/57 | 0.69 | 3/5 |

All modes correctly returned UNKNOWN on the forgotten badge. The forbidden string appeared in zero of three deletion answers or their retrieved notes. There were zero generation transport failures in 15 requests. Exact-answer failures were 4/5, 4/5 and 3/5 respectively. Both retrieval modes had one additional employment answer beginning with UNKNOWN followed by an explanation. Under the frozen exact-match rule these counted as incorrect and did not count as exact abstentions.

On the three current questions and one historical question, TRACE-Mem supplied only the correct value each time. RAG returned the correct and superseded values each time. On the historical residence question, Qwen still answered UNKNOWN in both arms. On employment, Qwen described the saved date as future even with the correct job present. On preference, TRACE-Mem returned ginger and RAG returned the older mint. The standard baseline abstained on all four answerable questions.

TRACE-Mem used 306 fewer generation input tokens than RAG and 306 more than standard. This pilot isolates reviewed memory availability in separate query conversations. The runner seeded the persistent store directly and supplied controlled distractor turns. It did not run an assistant through every original history turn. Each prompt admitted one of 24 distractor turns. Both retrieval arms used the shared lexical-first hybrid ranker and local MiniLM. Conventional RAG searched all retained versions with their start dates visible. TRACE-Mem filtered by the selected as-of date. Both arms honored explicit forgetting.

## Extraction, verification and engineering

Three separate Qwen structured extraction calls returned empty arrays. These missed both labeled facts and correctly returned empty for the incidental event. Recall was 0/2. Precision was undefined because there were zero predictions. Extraction used 177 input and 6 output tokens across 6.57 seconds. This is coverage evidence for the structured fallback only. The deterministic fast path and user review remain available. The pilot supplied reviewed facts separately to isolate reader and retrieval behavior.

One attempted ambiguous overwrite produced zero changes in the store. Verification was disabled in the matched comparison, with zero calls, tokens and latency attributable to verification. The learned policy requires calibrated conflict pairs, features and an arrival horizon. This pilot supplies reviewed values and lacks that stream. It provides no estimate of adaptive verification benefit.

Windows CPython 3.14.0, Ollama 0.40.13, Qwen2.5 7B Q4_K_M local ID 845dbda0ea48, RTX 2060, existing hardware, USD 0. The extraction stage preceded generation. First-use model/encoder loading, warm caches and arm order affect wall times. No repeated timing trials were performed. Generation token totals exclude local embedding computation. The combined extraction, retrieval and generation paths have no established end-to-end benefit on these observations.

Engineering verification passed 173 tests and 36 subtests with one existing AnyIO warning. Coverage includes stream-write interruption, provider timeout, oversized input rejection, simultaneous reads and forgetting, SQLite integrity, stale proposal denial and the original research demonstration. Client cancellation can precede provider shutdown. The public reproduction verified 27,000 history rows, 2,300 family rows, 230 summaries and 184 intervals. The fixture, implementation and analysis were AI-assisted. Broader extraction, date grounding, additional untouched families and replicated cold/warm measurements remain open.
A live Edge smoke on the separate Cedar Town development fixture passed proposal confirmation, cross-chat semantic retrieval, reload, deletion, selection of all three strategies and rendering the three-row results dashboard.
