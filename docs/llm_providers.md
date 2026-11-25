# LLM providers and label collection

The provider stack uses Python's standard library. `LLMTasks` exposes claim extraction (`complete` for replay), verification (`verify`), and answer generation (`answer`). It validates task-specific JSON before caching. Answers receive only eligible facts and may cite only supplied fact IDs. Schema validation does not establish entailment or accuracy.

Ollama also receives the task's JSON schema in its `format` parameter. See the [verified local setup](ollama_local.md) for the installed model, hardware and real smoke commands.

Use a model that returns JSON text and reports token usage. Record its exact ID or local digest and service version. [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat) · [OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion) · [Ollama local chat](https://docs.ollama.com/api/chat)

## Local setup and collection

Install [Ollama](https://ollama.com/download) and select a locally installed model with `ollama list`. In PowerShell, set `$env:OLLAMA_NO_CLOUD = '1'` in the server's environment and start `ollama serve` if needed. Use a loopback origin. `OLLAMA_HOST` defaults to `http://127.0.0.1:11434`.

```powershell
$model = Read-Host 'Enter exact locally installed Ollama model tag'
python -m trace_mem.collect_labels data/updateset-v1-seed23 data/updateset-v1-ollama --database results/ollama-run.sqlite --backend ollama --model $model --reference trace-updateset-v1-ollama --max-requests 78 --timeout 120 --max-output-tokens 256 --seed 23
python -m trace_mem.data.updateset validate data/updateset-v1-ollama
```

The seed-23 release has 78 eligible train/validation conflicts. The collector compares the B2 decision with the verifier-gated replay decision. It skips test rows and noneligible cases. The model receives the old fact, new claim, dates and source conversation. Gold is joined afterward. Ambiguous cases require independent gold before helpfulness is defined. Real outcomes may yield too few positives or negatives for training.

Rerun with the same database, model settings, and unfinished output path to resume. Validated responses are cached by task, model, settings, and input hash. Earlier attempts and spending reservations persist. Use one ledger per run and keep it local. Response caches can contain generated private text and must follow the project's retention requirements.

## Remote configuration

`.env.example` lists variable names. Set the relevant API key through the process environment or a secret manager. The CLI does not load dotenv files. Remote runs require approval for the particular run, `--allow-paid`, a positive USD cap, and current upper-bound input and output rates in USD per million tokens.

```powershell
python -m trace_mem.collect_labels data/updateset-v1-seed23 data/updateset-v1-remote --database results/remote-run.sqlite --backend $backend --model $model --reference trace-updateset-v1-remote --max-requests 78 --timeout 60 --retries 0 --max-input-tokens 4096 --max-output-tokens 256 --allow-paid --max-spend $maxSpend --input-price $inputPrice --output-price $outputPrice
```

For an explicitly approved run, set `$backend` to `openai` or `openrouter` and supply the approved model, spending limit and rates. The ledger reserves the configured maximum token charge before each attempt. It reconciles successful usage at the configured rates and retains reserves when usage is unknown. The preflight estimate uses UTF-8 bytes plus framing allowance. Reported token overruns stop subsequent misses. Rates and token ceilings determine the local spending estimate. Vendor billing remains authoritative. Set a provider-side limit where available. [OpenRouter price filters](https://openrouter.ai/docs/guides/routing/provider-selection)

The request cap includes retries. Selected transient HTTP errors and network failures retry with bounded backoff. Malformed responses stop collection and remain uncached. The CLI reports attempts, statuses, billed token counts where reported, summed latency, cache hits, model identity and estimated USD.

## Security and offline tests

Generated data, caches and credentials belong in ignored paths. Enable the tracked guard with `git config --local core.hooksPath .githooks` or run `python scripts/check_staged.py` directly. It blocks private artifact paths and recognized key formats without printing contents. It cannot detect arbitrary private prose or deliberate bypasses. Review the staged diff and use remote secret detection where available.

Run `python -m unittest discover -s tests -v` for tests with deterministic responses and injected HTTP transports. These tests produce no genuine training labels.
