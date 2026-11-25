"""Versioned v3 feature contract shared by collection and live replay."""

from dataclasses import dataclass

from trace_mem.claims import Claim
from trace_mem.controller import features_for, semantic_pair
from trace_mem.memory import Fact, Source
from trace_mem.semantic import Embed, Infer, _cosine, _unit_embeddings


MINILM = "sentence-transformers/all-MiniLM-L6-v2"
MINILM_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
NLI = "cross-encoder/nli-deberta-v3-xsmall"
NLI_REVISION = "a150876415327c80daeff35ca6f68f5ed8cf5c24"
DIRECT_SOURCE = {"direct", "dated_record"}


class CachedMiniLM:
    """Use the cached checkpoint's mean pooling locally."""

    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            MINILM, revision=MINILM_REVISION, local_files_only=True)
        self.model = AutoModel.from_pretrained(
            MINILM, revision=MINILM_REVISION, local_files_only=True, use_safetensors=True).eval()

    def __call__(self, texts):
        with self.torch.inference_mode():
            tokens = self.tokenizer(list(texts), padding=True, truncation=True, max_length=256,
                                    return_tensors="pt")
            hidden = self.model(**tokens).last_hidden_state
            mask = tokens["attention_mask"].unsqueeze(-1)
            return ((hidden * mask).sum(dim=1) / mask.sum(dim=1)).tolist()


@dataclass(frozen=True, slots=True)
class V3Features:
    embed: Embed
    infer: Infer | None = None

    def __call__(self, claim: Claim, target: Fact, *, entity: str, source: Source,
                 budget_remaining_fraction: float) -> tuple[float | None, ...]:
        if entity != target.entity:
            raise ValueError("V3 requires an exact entity match")
        base = features_for(claim, target, entity=entity, source=source,
                            budget_remaining_fraction=budget_remaining_fraction)
        pair = semantic_pair(claim, target, entity)
        left, right = _unit_embeddings(self.embed, pair)
        contradiction = self.infer(*pair).contradiction if self.infer is not None else None
        # Provenance measures attributable evidence availability, not truthfulness.
        provenance = (int(source.kind in DIRECT_SOURCE) + int(target.source.kind in DIRECT_SOURCE)) / 2
        return (
            _cosine(left, right), contradiction, base[2],
            base[3] * claim.explicit_effective_date, base[4], provenance, base[6], base[7],
        )
