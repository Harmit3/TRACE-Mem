"""Frozen adversarial checks for sanitized spans and managed lineage."""

from datetime import date

import pytest

from scripts.run_authorized_evidence import checked_span, overlap
from trace_mem.authorized_answer_cache import AuthorizedAnswerCache
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.llm_tasks import Answer


def test_mixed_source_independent_fields_and_restriction_intersection():
    utterance = "Remove Red. Keep Blue. Remove Green."
    left = checked_span(utterance, "Remove Red.")
    middle = checked_span(utterance, "Keep Blue.")
    right = checked_span(utterance, "Remove Green.")
    assert not overlap(left, middle) and not overlap(right, middle)
    assert overlap(checked_span(utterance, utterance), left)
    assert overlap(checked_span(utterance, utterance), right)
    with pytest.raises(ValueError, match="unambiguous"):
        checked_span("same same", "same")


def test_historical_and_alternate_views_only_see_positive_grants():
    d1, d2, d3 = (date(2025, 1, n) for n in (1, 2, 3))
    fields = (Field("p1", "first", "negative", "preference", d1, d1, d2),
              Field("p2", "second", "positive", "preference", d2, d2, d3),
              Field("p3", "third", "negative now", "preference", d3, d3),
              Field("allowed", "mixed", "independent project", "note", d1, d1))

    def embed(texts):
        assert "removed reminder" not in texts[1:] and "secret recipient" not in texts[1:]
        return [[1, 0] for _ in texts]

    index = EvidenceIndexV2(fields, "fixtures")
    for day, phase in ((d1, "p1"), (d2, "p2"), (d3, "p3")):
        handle = index.retrieve("who was on the original list or task?", day, embed, k=8)
        assert set(handle.identities) == {phase, "allowed"}
        assert len(index.materialize(handle, "fixture")) == 2
        assert not index.retrieve("paraphrased secret", day, embed, k=8,
                                  view=("hidden", "older-raw-copy")).identities
    broken = Field("clone", "mixed", "secret recipient", "summary", d1, d1, parents=("allowed",))
    with pytest.raises(ValueError, match="composition"):
        EvidenceIndexV2(fields + (broken,), "fixtures")


def test_rebuild_invalidates_stale_answer_and_handle():
    day = date(2025, 1, 1)
    field = Field("allow", "ref", "unrelated permitted information", "note", day, day)
    index = EvidenceIndexV2((field,), "grant")
    query = index.retrieve("note", day, lambda inputs: [[1, 0] for _ in inputs], k=1)
    fact, = index.materialize(query, "fixture")
    cache = AuthorizedAnswerCache(index, "fixture")
    cache.store("key", query, Answer(fact.value, (fact.fact_id,)))
    assert cache.fetch("key") is not None
    index.rebuild((field,), "grant")
    assert not index.materialize(query, "fixture") and cache.fetch("key") is None
