"""Read-time authorization for cached responses derived from evidence handles."""

from trace_mem.evidence_index_v1 import EvidenceHandle, EvidenceIndexV1
from trace_mem.llm_tasks import Answer


class AuthorizedAnswerCache:
    """Volatile cache. A policy mutation invalidates all prior answer handles."""

    def __init__(self, index: EvidenceIndexV1, entity: str):
        self.index = index
        self.entity = entity
        self._answers: dict[str, tuple[EvidenceHandle, Answer]] = {}

    def store(self, key, handle, answer):
        facts = self.index.materialize(handle, self.entity)
        if (not facts or not answer.text or not answer.citations
                or not set(answer.citations) <= {fact.fact_id for fact in facts}):
            raise ValueError("Cached answer lacks live source authorization")
        self._answers[key] = handle, answer

    def fetch(self, key):
        if key not in self._answers:
            return None
        handle, answer = self._answers[key]
        live = self.index.materialize(handle, self.entity)
        if not live or not set(answer.citations) <= {fact.fact_id for fact in live}:
            del self._answers[key]
            return None
        return answer
