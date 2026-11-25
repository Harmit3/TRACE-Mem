# V3 local NLI validation and diagnostic features

## Checkpoint and frozen validation

PR #24 was merged at `124e0f5`. The approved local checkpoint is [cross-encoder/nli-deberta-v3-xsmall at a150876415327c80daeff35ca6f68f5ed8cf5c24](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall/tree/a150876415327c80daeff35ca6f68f5ed8cf5c24), Apache-2.0. The 283,353,172-byte safetensors file matched published SHA-256 `4e4fc4977f8d29d2a164255c8f69b9d6c158deeb309bb5e70445b94666ccd9e9`. The SentencePiece model matched its published LFS SHA-256, and the other six downloaded files matched published Git blob IDs and byte sizes. The weights, tokenizer and cache are ignored locally.

The checkpoint loaded locally on CPU with a fast DeBERTa tokenizer. The installed stack was Python 3.14.0, Torch 2.10.0+cpu, Transformers 5.22.2, safetensors 0.8.0, tokenizers 0.23.3 and psutil 7.2.2. The fast tokenizer used the downloaded tokenizer files without installing the optional SentencePiece Python package. The config maps 0 to contradiction, 1 to entailment, and 2 to neutral. The adapter maps outputs by configured label name, then applies softmax.

Commit `5d766aa` froze 24 synthetic natural-language pairs, eight per class, and the gate before inference. The case SHA-256 is `b3f0a1e6a8fd599d852355518448ff0e03a77eac69216daf77acb41a65a661fb`. The gate required accuracy and contradiction recall of at least 75%, recall of at least 50% for each other class, and zero failures. These independent synthetic expectations measure sentence relations. They do not measure whether a memory write is authorized.

| Expected class | Correct / total | Contradiction score, min / median / max |
| --- | ---: | --- |
| Contradiction | 8 / 8 | 0.9753 / 0.9962 / 0.9994 |
| Entailment | 8 / 8 | 0.000389 / 0.000535 / 0.001484 |
| Neutral | 4 / 8 | 0.0050 / 0.4379 / 0.9988 |

Accuracy was 20/24 (83.3%). Contradiction precision was 8/12 (66.7%) and recall was 8/8 (100%). The gate passed with zero technical failures. All four errors were neutral cases classified as contradiction, involving a different month, a tentative transfer, another person's job, and an unconfirmed draft. Three of those false positives exceeded 0.98. Treat the contradiction feature as evidence and keep write decisions behind the independent verifier.

CPU NLI inference on four threads averaged 76.08 ms, with a 65.88 ms median and 294.96 ms maximum over 24 pairs. Python process RSS was 240,103,424 bytes before model load, 785,866,752 bytes after loading NLI, and 803,946,496 bytes after the validation. These are process snapshots that include interpreter, dependencies and allocator overhead.

## Diagnostic reconstruction and feature audit

The shared `V3Features` builder uses the pinned NLI score with anonymized natural assertions aligned to the eligible effective date. It preserves uncertainty as modal language. Collection and deployed replay can use `V3Features(CachedMiniLM(), pinned_nli(model_dir))`. This renderer is a model input convention. It cannot resolve omitted context or establish calibrated scores.

The diagnostic opened the original pilot SQLite cache read-only and allowed only the published extraction request key. It rebuilt the first eligible conflict from the seeded B2 prefix and the saved extractor response. It used the recorded pre-call budget fraction, checked that the other seven features could be reproduced, and wrote only a new score for each of the 14 eligible rows. Verifier cache entries, verdicts and gold were outside reconstruction. Ten source cases lacked an eligible feature row and remain in the unchanged original pilot. The original outcome SHA-256 remains `a88d4bdb52a1521fe982d401147dd98d52cf56fade077dd476b6ff278fe9ccb1`.

| Feature | Distinct | Range | Population variance |
| --- | ---: | --- | ---: |
| MiniLM cosine | 14 | 0.5377 to 0.7284 | 0.001939 |
| NLI contradiction | 14 | 0.0515 to 0.9988 | 0.132910 |
| Entity match | 1 | 1 | 0 |
| Explicit-date conflict | 2 | 0 to 1 | 0.25 |
| Observation gap in days | 14 | 6 to 120 | 1339 |
| Provenance | 3 | 0 to 1 | 0.122449 |
| Extraction uncertainty | 2 | 0.5 to 1 | 0.042092 |
| Remaining budget fraction | 6 | 0.375 to 1 | 0.034518 |

There were 14 distinct complete vectors with zero missing coordinates. Contradiction correlated with uncertainty at −0.9984, provenance at +0.6936, and temporal conflict at +0.5212. The near-collinearity with extraction intent is observed despite real NLI weights. The renderer's modal wording and this small sample are plausible contributors. Entity match is fixed by eligibility and has no defined Pearson correlation.

```powershell
python -m scripts.validate_v3_nli data/models/nli-deberta-v3-xsmall-a150876 results/updateset-v3-pilot results/updateset-v3-nli-diagnostic-1
```

Use a fresh output path for a recheck. The versioned diagnostic feature SHA-256 is `290a02e95ded4a6b1c42f3bdea8af93673a138cab78ef261a42ea86935686b29`. Outputs stay under ignored `results/`.

## Hardware compatibility

With both CPU models loaded the Python process used 907,333,632 bytes RSS. A separate local Qwen request succeeded with both models resident. It returned `same`, which did not authorize an update, and took 14.29 seconds including load. A subsequent combined MiniLM and NLI calculation completed. Python RSS was 909,295,616 bytes. Ollama reported about 3.91 GiB VRAM for Qwen at a 4,096-token context, and the system still reported about 11.57 GiB available RAM. This checks coexistence through a sequential smoke with all models resident. It does not measure sustained parallel throughput.

Full collection and controller training remain pending. The 24-case pilot and tiny family counts do not support reliable calibration. A broader independently reviewed NLI set should examine neutral and temporal cases before relying on this feature at scale.
