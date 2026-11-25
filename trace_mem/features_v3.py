"""Versioned v3 feature contract shared by collection and live replay."""

from dataclasses import dataclass
import hashlib
from pathlib import Path

from trace_mem.claims import Claim
from trace_mem.controller import features_for, semantic_pair
from trace_mem.memory import Fact, Source
from trace_mem.semantic import Embed, Infer, TransformersNLIProvider, _cosine, _unit_embeddings


MINILM = "sentence-transformers/all-MiniLM-L6-v2"
MINILM_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
NLI = "cross-encoder/nli-deberta-v3-xsmall"
NLI_REVISION = "a150876415327c80daeff35ca6f68f5ed8cf5c24"
NLI_WEIGHTS_SHA256 = "4e4fc4977f8d29d2a164255c8f69b9d6c158deeb309bb5e70445b94666ccd9e9"
DIRECT_SOURCE = {"direct", "dated_record"}


def pinned_nli(directory: Path) -> TransformersNLIProvider:
    with (directory / "model.safetensors").open("rb") as weights:
        if hashlib.file_digest(weights, "sha256").hexdigest() != NLI_WEIGHTS_SHA256:
            raise ValueError("Local NLI weights do not match the pinned revision")
    return TransformersNLIProvider(str(directory), local_files_only=True, device="cpu")


def nli_pair(claim: Claim, target: Fact) -> tuple[str, str]:
    """Compare natural assertions at the same eligible effective date."""
    date = claim.effective_on.isoformat()
    subject = "The person"

    def statement(value: str, possible: bool) -> str:
        if claim.predicate == "job":
            text = f"{subject} {'might work' if possible else 'works'} at {value}"
        elif claim.predicate == "residence":
            text = f"{subject} {'might live' if possible else 'lives'} at {value}"
        else:
            text = f"{subject}'s {claim.predicate} {'might be' if possible else 'is'} {value}"
        return f"On {date}, {text[0].lower() + text[1:]}."

    return statement(target.value, False), statement(claim.value, claim.intent == "uncertain")


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
        contradiction = self.infer(*nli_pair(claim, target)).contradiction if self.infer is not None else None
        # Provenance measures attributable evidence availability, not truthfulness.
        provenance = (int(source.kind in DIRECT_SOURCE) + int(target.source.kind in DIRECT_SOURCE)) / 2
        return (
            _cosine(left, right), contradiction, base[2],
            base[3] * claim.explicit_effective_date, base[4], provenance, base[6], base[7],
        )
