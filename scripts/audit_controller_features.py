"""Audit the frozen v2 vectors and optionally measure local MiniLM embeddings."""

import argparse
from collections import Counter
from datetime import date
import json
import math
from pathlib import Path
from statistics import correlation, pvariance

from scripts.audit_v2_full_release import audit_release, _date, _source
from trace_mem.claims import Claim
from trace_mem.controller import FEATURE_NAMES, semantic_pair
from trace_mem.data.updateset_v2 import sha
from trace_mem.memory import Fact


MINILM = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


def statistics_for(rows: list[tuple[str, list[float], bool | None]]) -> dict:
    columns = list(zip(*(features for _, features, _ in rows)))
    variable = [len(set(column)) > 1 for column in columns]
    correlations = {}
    for i, left in enumerate(columns):
        for j in range(i + 1, len(columns)):
            if variable[i] and variable[j]:
                correlations[f"{FEATURE_NAMES[i]}:{FEATURE_NAMES[j]}"] = correlation(left, columns[j])
    return {
        "rows": len(rows), "missing_values": sum(
            len(vector) != len(FEATURE_NAMES) or any(not math.isfinite(x) for x in vector)
            for _, vector, _ in rows),
        "unique_vectors": len({tuple(vector) for _, vector, _ in rows}),
        "positive_vectors": len({tuple(vector) for _, vector, label in rows if label is True}),
        "negative_vectors": len({tuple(vector) for _, vector, label in rows if label is False}),
        "variance": dict(zip(FEATURE_NAMES, map(pvariance, columns))),
        "pearson_nonconstant": correlations,
        "families": dict(Counter(family for family, _, _ in rows)),
    }


def _pair(candidate: dict) -> tuple[str, str]:
    c, f = candidate["claim"], candidate["target"]
    claim = Claim(c["predicate"], c["value"], c["intent"],
                  date.fromisoformat(c["effective_on"]), _date(c["expires_on"]))
    target = Fact(f["fact_id"], f["entity"], f["predicate"], f["value"], _source(f["source"]),
                  date.fromisoformat(f["valid_from"]), _date(f["valid_to"]), f["supersedes"])
    return semantic_pair(claim, target, target.entity)


def local_cosines(pairs: list[tuple[str, str]]) -> tuple[list[float], dict]:
    import torch
    import transformers
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(MINILM, revision=REVISION, local_files_only=True)
    model = AutoModel.from_pretrained(MINILM, revision=REVISION, local_files_only=True,
                                      use_safetensors=True).eval()
    inputs = sorted({text for pair in pairs for text in pair})
    vectors = {}
    with torch.inference_mode():
        for i in range(0, len(inputs), 16):
            batch = inputs[i:i + 16]
            encoded = tokenizer(batch, padding=True, truncation=True, max_length=256,
                                return_tensors="pt")
            hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            normalized = torch.nn.functional.normalize(pooled, dim=1)
            vectors.update(zip(batch, normalized))
    scores = [float(torch.dot(vectors[left], vectors[right]).clamp(-1, 1)) for left, right in pairs]
    return scores, {"model": MINILM, "revision": REVISION, "torch": torch.__version__,
                    "transformers": transformers.__version__, "device": "cpu",
                    "pooling": "attention-mask mean and L2 normalization",
                    "max_length": 256, "batch": 16, "threads": 4, "unique_texts": len(inputs)}


def measure(dataset: Path, release: Path, *, local: bool) -> dict:
    audit_release(dataset, release)
    data = (release / "outcomes.jsonl").read_bytes()
    cases = [json.loads(line) for line in data.splitlines()]
    candidates = [(r["split"], r["family"], c) for r in cases if not r["pilot"]
                  for c in r["candidates"] if "features" in c]
    result = {"outcomes_sha256": sha(data), "recorded": {}}
    for split in ("train", "validation"):
        result["recorded"][split] = statistics_for([
            (family, c["features"], c["helpful"]) for group, family, c in candidates if group == split
        ])
    if local:
        # The model receives no IDs, labels, gold, outcomes, or split metadata.
        cosines, model = local_cosines([_pair(c) for _, _, c in candidates])
        result["embedding_only"] = {"model": model, "groups": {}}
        for split in ("train", "validation"):
            group = [(family, [score, *c["features"][1:]], c["helpful"])
                     for (part, family, c), score in zip(candidates, cosines) if part == split]
            result["embedding_only"]["groups"][split] = statistics_for(group)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("release", type=Path)
    parser.add_argument("--cached-minilm", action="store_true")
    args = parser.parse_args()
    print(json.dumps(measure(args.dataset, args.release, local=args.cached_minilm), sort_keys=True))
