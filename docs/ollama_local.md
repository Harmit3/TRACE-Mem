# Local Ollama research setup

## Verified machine and model

| Item | Observed |
| --- | --- |
| OS | Windows 11 Pro |
| CPU | Intel Core i7-9750H, 6 cores and 12 logical processors |
| RAM | 23.87 GiB installed, 12.90 GiB available at inspection |
| GPU | NVIDIA GeForce RTX 2060, 6,144 MiB VRAM, 5,955 MiB free before inference |
| Other graphics | Intel UHD Graphics 630 and spacedesk display adapter |
| Disk free | C 117.35 GiB, D 931.38 GiB at inspection |
| Runtime | Ollama client and loopback server 0.40.13 |
| Installed model | `llama3.2:3b`, 3.2B GGUF Q4_K_M, 2,019,393,189 bytes |
| Model digest | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` |
| Active model footprint | 2,561,000,078 bytes, all reported in VRAM, with 4,096-token runtime context |

Use the already-installed `llama3.2:3b` for a local pilot. It is instruction-tuned, fits this GPU at the observed context size, and passes the small structured smoke after prompt changes. Its extraction and verification quality on broader cases remains unknown. No weights were downloaded. Verify the local digest with `/api/tags` before every frozen run because a tag can change. [Ollama model entry](https://ollama.com/library/llama3.2:3b) · [Meta model card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct)

The local `/api/show` metadata and model registry identify the Llama 3.2 Community License and associated Acceptable Use Policy. Before publicly releasing an artifact trained using model outputs, review §1(b)(i), which includes a naming condition for a distributed model trained using Llama outputs. [License](https://ollama.com/library/llama3.2:3b/blobs/fcc5a6bec9da) · [Acceptable Use Policy](https://ollama.com/library/llama3.2:3b/blobs/a70ff7e570d9)

## Reproduce the local smoke and prepare collection

The service was started with `OLLAMA_HOST=127.0.0.1:11434` and `OLLAMA_NO_CLOUD=1`. If it is stopped, set these variables in one PowerShell session and start `ollama serve`. The client already defaults to the loopback HTTP endpoint.

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
Invoke-RestMethod http://127.0.0.1:11434/api/tags
python -m scripts.smoke_ollama --model llama3.2:3b --output results/ollama-smoke
python -m trace_mem.data.updateset validate data/updateset-v1-seed23
```

For label collection, use the verified digest and keep all artifacts under ignored `data/` and `results/` paths. The validated seed-23 release has 60 eligible training conflicts and 18 validation conflicts. Of those, 40 train and 12 validation rows already have synthetic rule gold. The remaining 20 train and 6 validation rows need independent human adjudication. The verifier receives only the case evidence and never sees the gold fields. Case eligibility, exact collector options, and resume behavior are described in the [provider guide](llm_providers.md).

```powershell
python -m trace_mem.collect_labels data/updateset-v1-seed23 data/updateset-v1-ollama --database results/ollama-labels.sqlite --backend ollama --model llama3.2:3b --reference seed23-llama3.2-3b-a80c4f17acd5 --max-requests 78 --timeout 120 --max-output-tokens 256 --seed 23
python -m trace_mem.data.updateset validate data/updateset-v1-ollama
```

Keep the ledger and unfinished output path when resuming. The initial smoke cases informed prompt development, so treat the final smoke as an integration check. Verify the verifier on a broader independently reviewed development sample before collecting the full release. A valid JSON result can still carry an incorrect decision. Record actual class counts before training.
