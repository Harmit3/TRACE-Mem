# Local semantic models

TRACE-Mem supports configurable local embedding and NLI checkpoints. Mock providers and the standard test suite use only Python's standard library. The optional [requirements file](../requirements-semantic.txt) pins direct dependencies. Capture the resolved environment, Python version, and device with each real run.

## Installation and checkpoints

On Windows, create an isolated environment using the project Python version and install the optional requirements:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-semantic.txt
```

The reference embedding checkpoint is [all-MiniLM-L6-v2 at revision 1110a24](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41). The reference NLI checkpoint is [nli-deberta-v3-small at revision fa28048](https://huggingface.co/cross-encoder/nli-deberta-v3-small/tree/fa2804872c3b4bd748f38c0185cc85775361e735). Both model cards list Apache-2.0. Allow disk space for approximately 660 MB of weights plus tokenizer files and dependencies. Both providers default to CPU and local files only. Use `local_files_only=False` for the first anonymous Hub download, or supply a local checkpoint directory. Inference runs locally and requires no API key.

```python
from trace_mem.semantic import (
    SemanticEvidence, SentenceTransformerProvider, TransformersNLIProvider,
    retrieve_semantic,
)

embed = SentenceTransformerProvider(
    "sentence-transformers/all-MiniLM-L6-v2",
    revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
)
infer = TransformersNLIProvider(
    "cross-encoder/nli-deberta-v3-small",
    revision="fa2804872c3b4bd748f38c0185cc85775361e735",
)
semantic = SemanticEvidence(embed, infer)
```

## Behavior and limits

- Pass `semantic=semantic` to either T1 replay entry point. Cosine similarity and the NLI contradiction probability replace the first two controller proxies. The other six features retain their definitions. Use the same feature configuration for training and inference. Supply an embedding callable and an NLI callable returning `NLIScores` for deterministic tests.
- NLI receives the existing fact as premise and the new claim as hypothesis. It returns contradiction, entailment, and neutral probabilities using the checkpoint's named labels. Its output informs verification selection. The existing verifier and temporal rules still govern state transitions. Context, temporality, truncation, and compact fact rendering can affect NLI judgments. Calibration and benchmark accuracy remain unmeasured.
- Call `retrieve_semantic(memory, question, entity=persona, as_of=day, k=5, embed=embed)` to retrieve facts across predicates, or supply a predicate filter. Entity identity is exact. The effective-date filter and current deletion state apply before embedding. Rank by cosine similarity with ascending fact-ID tie-breaking. Each hit retains its fact and provenance. The implementation embeds eligible facts per query and keeps no persistent vector index or cache.
- Use only the question text and replay-derived facts as retrieval inputs. Keep rubric text, expected answers, and evaluator evidence in the scoring process. The Memora adapter only reads session files and projects the speaker and message fields into events, alongside date and source ordering fields.

The offline tests check provider contracts, routing, and privacy boundaries with mocks. Real-weight inference and benchmark evaluation remain to be verified.
