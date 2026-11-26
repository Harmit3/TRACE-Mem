# Workspace on Windows

Double-click `launch-workspace.bat` with the Python 3.14 Windows launcher installed. Keep the console open. Workspace binds to 127.0.0.1. If port 8770 is occupied, run `py -3.14 -m trace_mem.workspace --port 8771 --open-browser`.

Start Ollama and run `ollama list` to check installed models. Reload Workspace after starting the service. For local-only use, disable Ollama cloud features in the service environment. The model picker reads installed tags from loopback. This machine has Qwen2.5 7B Instruct Q4_K_M and Llama 3.2 3B. Workspace defaults to Qwen for general conversation. Choose Llama under Generation settings for the smaller model. With Ollama unavailable, select offline memory lookup and try the fictional sample notes. No model download is required on this machine.

Start a new chat and send a message. Local AI chats support streamed text, basic Markdown, fenced code, copying, stopping generation and regenerating the latest eligible answer. Search matches titles and transcript text. Renaming and deletion apply to the selected conversation. Offline lookup remains a transient utility. Stop disconnects the request. Provider work may continue until the next stream write.

Try “I live in fictional Cedar Town.” Review the proposed residence and confirm it, then start a new conversation and ask where your home is. The extractor recognizes short English first-person statements for residence, work, preferences, visits and possible moves. Other wording may require manual entry. Suggestions carry source chat and turn IDs. Conflicts require explicit correction through Edit. Optional conflict verification allows one local call per proposal and provides an advisory verdict. The research Budget class accounts for attempts. The frozen learned controller has no validated deployment threshold for this chat task.

The context inspector shows selected notes, selection reasons, serialized size, included history turns and provider-reported prompt and output token counts. The assembler reserves output space within 4,096 tokens and applies a conservative UTF-8 size estimate. MiniLM runs on CPU from the local pinned research checkpoint when its dependencies are available. Selection falls back to label and value overlap and pins. The 0.30 cosine cutoff was adjusted on the fictional home query after its score of 0.343 missed the original 0.35 cutoff. This is development tuning.

## Storage and privacy

By default the memory JSON and version-1 chat SQLite database live in the user's .trace-mem-workspace directory. Existing alpha memories load directly. Schema initialization is transactional and newer unknown chat schemas are rejected. Use a single running Workspace per data path. Forget removes all versions of the label and makes all existing turns ineligible for model context, regeneration and proposal acceptance. Those transcripts remain visible and searchable until deleted. Previously displayed replies, provider logs and backups may contain copies. A user can explicitly reintroduce information. Storage is plaintext. Use --data outside Git for private data.

## Engineering checks and roadmap

The complete suite passed 171 tests and 36 subtests on Python 3.14.0. It includes the original demo, API and persistence tests plus chat search, rename, restart, privacy invalidation and deletion. The numeric reproduction verified 230 summaries and 184 paired intervals. Run the opt-in fictional browser test with `python -m scripts.workspace_browser_smoke` on Windows with Playwright, Edge, Ollama and the local MiniLM checkpoint.

Future work includes broader evaluated extraction, better long-history paging and retrieval scaling, encrypted storage, multi-process coordination, broader browser/accessibility testing, verified provider-side cancellation and quality evaluation across independent scenarios. This AI-assisted engineering milestone used fictional development inputs. Independent research validation remains pending.
The Edge smoke passed with Qwen selected. The first request used 40 input and 48 output tokens. A second conversation retrieved the confirmed residence by MiniLM cosine similarity and used 115 input and 48 output tokens. The browser then reloaded both chat entries and forgot the memory.
