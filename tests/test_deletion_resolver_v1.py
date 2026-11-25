"""Guard deletion proposals and authorization changes independently."""

from datetime import date
import json

import pytest

from scripts.run_deletion_scope import answer_cache_checks, score
from trace_mem.deletion_resolver_v1 import Candidate, propose
from trace_mem.evidence_index_v1 import EvidenceIndexV1, EvidenceRecord
from trace_mem.llm_tasks import MockProvider


DAY = date(2025, 1, 2)


def candidate(key, value, aliases=()):
    return Candidate(key, "job", value, f"My job is {value}.", DAY, aliases, "job")


def backend(intent="forgetting", relation="paraphrase", target=0, inspect=None):
    def respond(_task, payload):
        if inspect:
            inspect(json.loads(payload))
        return json.dumps(dict(intent=intent, relation=relation, target=target))
    return MockProvider(respond)


def vectors(texts):
    return [[1.0] for _ in texts]


def test_scope_alias_and_broad_guard():
    candidates = (candidate("a", "Green Press", ("Green Team",)), candidate("b", "Violet Desk"))
    result = propose(backend(), vectors, "Please forget the Green Team.", [], "Green Team", candidates, DAY)
    assert result.targets == ("a",) and result.relation == "alias"
    broad = propose(backend(inspect=lambda _: pytest.fail("broad requests must stay pending")),
                    vectors, "Forget all my information.", [], "", candidates, DAY)
    assert broad.relation == "broad" and not broad.targets


def test_model_cannot_override_conflicts_or_correction():
    candidates = (candidate("a", "Green Press"), candidate("b", "Green Press"))
    duplicate = propose(backend(), vectors, "Forget Green Press.", [], "Green Press", candidates, DAY)
    assert duplicate.relation == "ambiguous" and not duplicate.targets
    correction = propose(backend(), vectors, "I no longer work at Green Press. My new job is Violet Desk.",
                         [], "Green Press", candidates, DAY)
    assert not correction.targets


def test_proposal_has_no_privacy_authority_and_cache_checks_live_lineage():
    index = EvidenceIndexV1()
    index.add(EvidenceRecord("a", "Green Press.", "source", DAY, DAY, "job"))
    index.revoke()
    result = propose(backend(), vectors, "Forget Green Press.", [], "Green Press",
                     (candidate("a", "Green Press"),), DAY)
    assert result.targets == ("a",)
    assert index.quarantined and not index.retrieve("job", DAY, vectors, k=2).identifiers
    assert all(answer_cache_checks().values())


def test_score_distinguishes_unresolved_and_false_deletion():
    result = score([{"semantic": ["a", "b"], "gold": ["a"], "pool_size": 4},
                    {"semantic": [], "gold": ["c"], "pool_size": 3}], "semantic")
    assert result["precision"] == result["recall"] == 0.5
    assert result["false_targets"] == result["unresolved_targeted_requests"] == 1
    assert result["hypothetical_retained_if_proposals_applied"] == 5
