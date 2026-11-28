from concurrent.futures import ThreadPoolExecutor
import sqlite3
import subprocess
import sys

import pytest

from trace_mem.mcp_store import Practice, initialize


def test_competing_reviews_and_transaction_rollback(tmp_path):
    root = tmp_path / "A"
    initialize(root)
    store = Practice(root)
    store.grant("agent-a", "budget", read=True, propose=True)

    def propose(value):
        return Practice(root).propose("agent-a", "add", "budget", value, "2025-01-01", None,
                                      "permanent", "fiction:1")["proposal_id"]

    def approve(key):
        try:
            return Practice(root).decide(key, True)
        except ValueError:
            return "stale"

    with ThreadPoolExecutor(2) as pool:
        keys = list(pool.map(propose, ["500", "800"]))
        assert sorted(pool.map(approve, keys)) == ["approved", "stale"]
    with pytest.raises(ValueError):
        store.decide(keys[0], True)
    with pytest.raises(RuntimeError), store.transaction() as db:
        db.execute("DELETE FROM facts")
        raise RuntimeError("simulated interruption")
    assert len(Practice(root).read("agent-a", "recall", "budget")["evidence"]) == 1
    other = tmp_path / "B"
    initialize(other)
    assert Practice(other).read("agent-a", "recall", "budget")["status"] == "abstain"
    assert Practice(other).status("agent-a", keys[0])["status"] == "unavailable"


def test_temporary_grants_and_delete_race(tmp_path):
    root = tmp_path / "practice"
    initialize(root)
    store = Practice(root)
    store.grant("agent-a", "visit", True, True, True)
    def write(kind, value):
        return store.propose("agent-a", kind, "visit", value, "2025-01-01", "2025-01-06",
                             "temporary", "fiction:trip")["proposal_id"]
    first = write("add", "Cedar")
    store.grant("agent-a", "visit")
    with pytest.raises(ValueError):
        store.decide(first, True)
    store.grant("agent-a", "visit", True, True, True)
    store.decide(write("add", "Cedar"), True)
    assert store.read("agent-a", "recall", "visit", "2025-01-05")["status"] == "found"
    assert store.read("agent-a", "recall", "visit", "2025-01-06")["status"] == "abstain"
    key = write("forget", None)
    with ThreadPoolExecutor(2) as pool:
        reading = pool.submit(store.read, "agent-a", "history", "visit")
        deleting = pool.submit(store.decide, key, True)
        assert deleting.result() == "approved"
        assert reading.result()["status"] in {"found", "abstain"}
    assert Practice(root).read("agent-a", "history", "visit")["status"] == "abstain"


def test_foreign_db_refused(tmp_path):
    with sqlite3.connect(tmp_path / "practice.sqlite3") as db:
        db.execute("CREATE TABLE other(x)")
    with pytest.raises(ValueError, match="Unsupported"):
        Practice(tmp_path).pending()


def test_interrupted_process_keeps_last_committed_state(tmp_path):
    root = tmp_path / "practice"
    initialize(root)
    store = Practice(root)
    store.grant("agent-a", "budget", read=True, propose=True)
    key = store.propose("agent-a", "add", "budget", "500", "2025-01-01", None,
                        "permanent", "fiction:1")["proposal_id"]
    store.decide(key, True)
    script = ("import os,sqlite3,sys; db=sqlite3.connect(sys.argv[1]); "
              "db.execute('BEGIN IMMEDIATE'); db.execute('DELETE FROM facts'); os._exit(17)")
    assert subprocess.run([sys.executable, "-c", script, str(store.file)]).returncode == 17
    assert Practice(root).read("agent-a", "recall", "budget")["evidence"][0]["value"] == "500"
