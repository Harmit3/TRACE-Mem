"""Source authority, cache invalidation, and deterministic reader safety regressions."""

from datetime import date
import json

import pytest

from scripts.run_reader_safety import safety
from trace_mem.evidence_index_v1 import EvidenceIndexV1, EvidenceRecord
from trace_mem.llm_tasks import MockProvider
from trace_mem.memory import Fact, Source
from trace_mem.reader_v2 import arithmetic, parse_proposal, read


DAY = date(2025, 1, 3)


def fact(key, text, source=None):
    return Fact(key, "fixture", "text", text, Source(DAY, source or key), DAY)


def test_reader_canonicalizes_null_only_and_preserves_negation():
    evidence = (fact("f", "The course does not meet on Tuesday; it meets on Friday."),)
    result = read(MockProvider(lambda *_: '{"status":"insufficient","quotes":[{}]}'),
                  "When?", evidence, as_of=DAY, mode="short")
    assert result.answer.text is None and not result.answer.citations and result.canonicalized_abstention
    proposal = {"status": "supported", "quotes": [{"fact_id": "f", "quote": "Tuesday"}]}
    grounded = read(MockProvider(lambda *_: json.dumps(proposal)),
                    "When?", evidence, as_of=DAY, mode="short")
    assert grounded.answer.text == evidence[0].value and grounded.answer.citations == ("f",)
    for invalid in ({"fact_id": "missing", "quote": "Tuesday"},
                    {"fact_id": "f", "quote": "Saturday"}):
        with pytest.raises(ValueError, match="not supported"):
            parse_proposal(json.dumps({"status": "supported", "quotes": [invalid]}), evidence)


def test_subtotal_deduplicates_source_and_ignores_future_intentions():
    rows = (fact("a", "I spent $9.20 on coffee.", "same"),
            fact("b", "I spent $9.20 on coffee.", "same"),
            fact("c", "I plans to spend $42 on coffee."),
            fact("d", "I spent $4.20 on lunch."),
            fact("e", "I spent $6.84 on coffee."))
    result = arithmetic("How much have I spent on coffee in total?", rows)
    assert result.text == "Subtotal from 2 retrieved records: $16.04."
    assert result.citations == ("a", "e")
    assert arithmetic("How much have I spent on coffee in total?",
                      rows + (fact("f", "I spent $7.20 on coffee.", "same"),)) is None


def test_fixture_safety_and_unknown_scope_do_not_embed_quarantined_text():
    embed = lambda texts: [[1.0, 0.0] for _ in texts]
    assert all(safety(["where", "earlier address", "historic home", "paraphrase"], embed).values())
    index = EvidenceIndexV1()
    index.revoke()
    index.add(EvidenceRecord("later", "Private alias.", "later", DAY, DAY, "opaque"))

    def forbidden(_):
        raise AssertionError("Denied text must not be embedded during retrieval")

    assert not index.retrieve("lookup", DAY, forbidden, k=4).identifiers
