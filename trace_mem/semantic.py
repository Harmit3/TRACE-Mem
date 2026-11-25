"""Local semantic model adapters and retrieval over eligible in-memory facts."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
import math
from typing import Literal

from trace_mem.memory import Fact, TemporalMemory


Embed = Callable[[Sequence[str]], Sequence[Sequence[float]]]
Relation = Literal["contradiction", "entailment", "neutral"]


@dataclass(frozen=True, slots=True)
class NLIScores:
    contradiction: float
    entailment: float
    neutral: float

    def __post_init__(self) -> None:
        scores = (self.contradiction, self.entailment, self.neutral)
        if (any(not math.isfinite(x) or not 0 <= x <= 1 for x in scores)
                or not math.isclose(sum(scores), 1, abs_tol=1e-6)):
            raise ValueError("NLI scores must be a normalized three-class distribution")

    @property
    def label(self) -> Relation:
        labels: tuple[Relation, ...] = ("neutral", "entailment", "contradiction")
        return max(labels, key=lambda label: getattr(self, label))


Infer = Callable[[str, str], NLIScores]


class SentenceTransformerProvider:
    def __init__(self, model: str, *, revision: str | None = None, device: str = "cpu",
                 local_files_only: bool = True) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model, revision=revision, device=device,
                                          local_files_only=local_files_only, token=False,
                                          trust_remote_code=False, model_kwargs={"use_safetensors": True})

    def __call__(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        vectors = self._model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False)
        return vectors.tolist()


class TransformersNLIProvider:
    def __init__(self, model: str, *, revision: str | None = None, device: str = "cpu",
                 local_files_only: bool = True, max_length: int = 256) -> None:
        if type(max_length) is not int or max_length < 1:
            raise ValueError("Maximum NLI input length must be a positive integer")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        settings = dict(revision=revision, local_files_only=local_files_only,
                        token=False, trust_remote_code=False)
        self._tokenizer = AutoTokenizer.from_pretrained(model, **settings)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model, use_safetensors=True, **settings,
        ).to(device).eval()
        mapping = {str(label).casefold(): int(index)
                   for index, label in self._model.config.id2label.items()}
        if set(mapping) != {"contradiction", "entailment", "neutral"} or set(mapping.values()) != {0, 1, 2}:
            raise ValueError("NLI model must label contradiction, entailment and neutral explicitly")
        self._labels = mapping
        self._device = device
        self._max_length = max_length
        self._torch = torch

    def __call__(self, premise: str, hypothesis: str) -> NLIScores:
        tokens = self._tokenizer(premise, hypothesis, return_tensors="pt", truncation=True,
                                 max_length=self._max_length)
        with self._torch.inference_mode():
            logits = self._model(**tokens.to(self._device)).logits
            probabilities = logits[0].float().softmax(dim=-1).tolist()
        return NLIScores(**{label: probabilities[i] for label, i in self._labels.items()})


def _unit_embeddings(embed: Embed, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
    vectors = tuple(tuple(row) for row in embed(texts))
    if len(vectors) != len(texts) or not vectors or not vectors[0]:
        raise ValueError("Expected one nonempty embedding per input")
    width = len(vectors[0])
    normalized = []
    for vector in vectors:
        if len(vector) != width or any(not math.isfinite(x) for x in vector):
            raise ValueError("Embedding dimensions must match and values must be finite")
        norm = math.hypot(*vector)
        if not norm or not math.isfinite(norm):
            raise ValueError("Embedding norm must be finite and positive")
        normalized.append(tuple(x / norm for x in vector))
    return tuple(normalized)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right))))


def fact_text(entity: str, predicate: str, value: str) -> str:
    return f"{entity} | {predicate} | {value}"


@dataclass(frozen=True, slots=True)
class SemanticEvidence:
    embed: Embed
    infer: Infer

    def compare(self, premise: str, hypothesis: str) -> tuple[float, NLIScores]:
        left, right = _unit_embeddings(self.embed, (premise, hypothesis))
        return _cosine(left, right), self.infer(premise, hypothesis)


@dataclass(frozen=True, slots=True)
class SemanticHit:
    fact: Fact
    similarity: float


def retrieve_semantic(
    memory: TemporalMemory, query: str, *, entity: str, as_of: date, k: int, embed: Embed,
    predicate: str | None = None,
) -> tuple[SemanticHit, ...]:
    """Rank only visible facts for the exact entity. Ties use opaque fact IDs."""
    if type(k) is not int or k < 0:
        raise ValueError("k must be a nonnegative integer")
    if not query.strip() or not entity.strip():
        raise ValueError("Query and entity cannot be empty")
    if k == 0:
        return ()
    eligible = memory.retrieve(entity, predicate, as_of=as_of)
    if not eligible:
        return ()
    texts = (query, *(fact_text(f.entity, f.predicate, f.value) for f in eligible))
    vector, *facts = _unit_embeddings(embed, texts)
    hits = [SemanticHit(f, _cosine(vector, embedding)) for f, embedding in zip(eligible, facts)]
    return tuple(sorted(hits, key=lambda hit: (-hit.similarity, hit.fact.fact_id))[:k])
