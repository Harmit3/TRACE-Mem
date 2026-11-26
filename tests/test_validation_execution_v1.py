from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3

import pytest
import trace_mem.validation_v2 as runtime

from scripts.run_validation_v1 import PREFLIGHT, approved, fingerprint
from trace_mem.baselines import PreparedClaim
from trace_mem.causal_horizon_v1 import CalendarPlanner
from trace_mem.claims import Claim
from trace_mem.evidence_index_v2 import EvidenceIndexV2, Field
from trace_mem.llm_tasks import MockProvider
from trace_mem.memory import Fact, Source
from trace_mem.providers import ProviderConfig, ProviderError
from trace_mem.validation_adapters_v1 import QWEN, VerifierAdapter, bind_reader, verify_contract
from trace_mem.validation_v2 import Episode, ExactLedger, ExecutionPaused, replay


DAY = date(2026, 1, 1)


def test_approval_blocks_before_any_backend_and_pins_contract():
    config = json.loads(PREFLIGHT.read_bytes())
    verify_contract(config["pins"])
    assert len(fingerprint(config, "primary")) == 64
    with pytest.raises(ValueError, match="Blocked"):
        approved(config, "primary", None, None, None)
    config["pins"]["feature_order"].reverse()
    with pytest.raises(ValueError, match="Feature order"):
        verify_contract(config["pins"])


def test_verifier_sends_only_pair_and_approved_source_and_meters_malformed():
    config = ProviderConfig("ollama", QWEN, 0, context_tokens=4096)
    packets = []
    def transport(url, headers, body, timeout):
        assert url.startswith("http://127.0.0.1:")
        packets.append(body)
        return body
    adapter = VerifierAdapter(config, lambda _: ('{"verdict":"made up"}', 42, 8, QWEN, True), transport)
    current = Claim("office", "Maple", "correct", DAY)
    old = Fact("private-id", "subject", "office", "Old", Source(DAY, "opaque"), DAY)
    assert adapter(current, old, "The office is Maple now.") == ("invalid", 42, 8)
    packet = json.loads(packets[0]["messages"][1]["content"])
    assert set(packet) == {"proposed", "existing", "conversation"}
    assert packet["conversation"] == ["The office is Maple now."]
    assert "private-id" not in str(packet) and "opaque" not in str(packet)


def test_reader_embeds_only_authorized_visible_evidence():
    seen = []
    def embed(texts):
        seen.extend(texts)
        return [[1, 0] for _ in texts]
    def reply(task, payload):
        facts = json.loads(payload)["facts"]
        assert [fact["value"] for fact in facts] == ["permitted"]
        return json.dumps({"status": "supported", "quotes": [
            {"fact_id": facts[0]["fact_id"], "quote": "permitted"}]})
    fields = (Field("permitted", "p", "permitted", "office", DAY, DAY),
              Field("future", "f", "future-only", "office", DAY + timedelta(days=1), DAY))
    answer = bind_reader(MockProvider(reply), embed)("What office?", EvidenceIndexV2(fields, "approved"), DAY)
    assert answer.text == "permitted"
    assert "future-only" not in seen


def test_same_day_and_closing_day_timing():
    plan = CalendarPlanner(DAY, DAY + timedelta(days=6))
    assert plan.future(DAY, 1) > plan.future(DAY, 0)
    assert plan.future(DAY + timedelta(days=6), 10) == 0
    # Same-day replacement does not pass the existing effective-time conflict guard.
    events = tuple(PreparedClaim(Claim("office", value, "correct", DAY), Source(DAY, str(i)), str(i))
                   for i, value in enumerate(("old", "new")))
    episode = Episode("h", "f", DAY, DAY, events, frozenset({"0", "1"}), ())
    class Unused:
        def call(self, *args):
            pytest.fail("Same-day exact update should not be sent to verifier")
    replayed = replay(episode, "B3", 2, "closed-loop", {}, {}, None, Unused())
    assert replayed[1]["calls"] == 0
    assert {f.value for f in replayed[0].retrieve("subject", "office", as_of=DAY)} == {"old"}


def test_interruption_preserves_physical_reservation_and_valid_cache(tmp_path):
    ledger_path = tmp_path / "test.sqlite"
    old = Fact("f", "subject", "office", "Old", Source(DAY, "x"), DAY)
    claim = Claim("office", "Next", "correct", DAY)
    def interrupted(*args):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        ExactLedger(ledger_path, "frozen", 2).call(claim, old, "approved", interrupted)
    ledger = ExactLedger(ledger_path, "frozen", 2)
    assert ledger.call(claim, old, "approved", lambda *_: ("update", 12, 3))[3]
    assert not ledger.call(claim, old, "approved", lambda *_: pytest.fail("Cache miss"))[3]
    with pytest.raises(ExecutionPaused, match="Physical verifier limit"):
        ledger.call(claim, old, "altered", lambda *_: pytest.fail("Dispatch beyond cap"))
    with sqlite3.connect(ledger_path) as db:
        db.execute("UPDATE outcomes_v1 SET verdict='same'")
    assert ledger.stats()["interrupted_or_unknown"] == 1
    with pytest.raises(ExecutionPaused, match="Invalid exact-cache"):
        ledger.call(claim, old, "approved", lambda *_: pytest.fail("Bad cache reuse"))


def test_timeout_recovery_is_unmetered_and_never_cached(tmp_path):
    old = Fact("f", "subject", "office", "Old", Source(DAY, "x"), DAY)
    claim = Claim("office", "Next", "correct", DAY)
    def timeout(*args):
        raise TimeoutError()
    ledger = ExactLedger(tmp_path / "meter.sqlite", "frozen", 2)
    result = ledger.call(claim, old, "approved", timeout)
    assert result[:4] == ("invalid", None, None, True)
    assert ledger.call(claim, old, "approved", lambda *_: ("same", 12, 3))[3]


def test_condition_resume_reuses_committed_rows(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    engineering = [(Episode("h1", "toy-a", DAY, DAY, (), frozenset(), ()), None, "toy"),
                   (Episode("h2", "toy-b", DAY, DAY, (), frozenset(), ()), None, "toy")]
    # Isolate persistence rather than inventing a research cohort or an approval.
    monkeypatch.setattr(runtime, "check_reviewed", lambda *_: engineering)
    attempts = []
    def evaluate(episode, gold, question, policy, *args):
        attempts.append((episode.identity, policy))
        if len(attempts) == 2:
            raise KeyboardInterrupt()
        return runtime.failed_condition()
    monkeypatch.setattr(runtime, "evaluate", evaluate)
    receipt = {"backend_fingerprint": "engineering-only"}
    kwargs = dict(rules={}, feature={}, provider=None, reader=None)
    with pytest.raises(KeyboardInterrupt):
        runtime.run_reviewed(engineering, receipt, tmp_path / "results/test", **kwargs)
    rows, _ = runtime.run_reviewed(engineering, receipt, tmp_path / "results/test", **kwargs)
    assert len(rows) == 8
    assert attempts.count(("h1", "B3")) == 1
    assert attempts.count(("h1", "T2")) == 2
    assert all(r["current_total"] == 6 and r["reader_total"] == 1 for r in rows)
