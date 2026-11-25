"""Reproducibility and boundary checks for the full development diagnostic."""

from datetime import date, timedelta
import sqlite3

from scripts.extract_memora_full import checkpoint_value, restore, seed_cache
from scripts.replay_memora_full import combinations, inspect_claims
from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim
from trace_mem.memory import Source


def prepared(i, predicate, value, day, *, intent="assert"):
    return PreparedClaim(Claim(predicate, value, intent, day),
                         Source(day, f"{i}/1"), f"{i}/1/0")


def test_checkpoint_round_trip_and_seed_cache_ignores_old_ledger(tmp_path):
    item = prepared(1, "task", "buy stamps", date(2025, 1, 1))
    assert restore(checkpoint_value(item)) == item
    previous = tmp_path / "prior results.sqlite"
    current = tmp_path / "current results.sqlite"
    for file in (previous, current):
        with sqlite3.connect(file) as db:
            db.executescript("CREATE TABLE response(key TEXT PRIMARY KEY, text TEXT);"
                             "CREATE TABLE attempt(status TEXT);")
            if file == previous:
                db.execute("INSERT INTO response VALUES ('fixture', '{}')")
                db.execute("INSERT INTO attempt VALUES ('ok')")
    seed_cache(current, previous)
    seed_cache(current, previous)
    with sqlite3.connect(current) as db:
        assert db.execute("SELECT * FROM response").fetchall() == [("fixture", "{}")]
        assert db.execute("SELECT * FROM attempt").fetchall() == []


def test_same_day_eventlike_clash_and_exact_delete_accounting():
    day = date(2025, 1, 1)
    later = day + timedelta(days=1)
    proposals = [
        prepared(1, "task", "send invoice", day),
        prepared(2, "task", "file receipts", day),
        prepared(3, "task", "make call", later),
        prepared(4, "task", "send invoice", later, intent="delete"),
        prepared(5, "job", "unrecognized value", later, intent="delete"),
    ]
    audit = inspect_claims(proposals)
    assert audit["counts"]["eligible"] == audit["counts"]["same_effective_day"] == 1
    assert audit["counts"]["b2_defer"] == 3
    assert audit["deferred_eventlike_predicates"] == {"task": 2}
    assert audit["counts"]["delete_claims"] == 2
    assert audit["counts"]["unresolved_delete"] == 1


def test_closed_loop_uses_exogenous_capacity_and_horizon_sensitivity():
    design = {"closed_loop_budget_reference": 15, "budgets_percent": [0, 50, 100],
              "random_seeds": [7, 23], "primary_horizon": 15, "horizon_sensitivity": [5, 15, 30]}
    cold = [r for r in combinations(design, 0) if r[0] == "closed-loop"]
    dense = [r for r in combinations(design, 25) if r[0] == "closed-loop"]
    assert cold == dense
    assert {r[2] for r in cold} == {0, 7, 15}
    assert {r[4] for r in cold} == {5, 15, 30}
    assert all(r[-1] == ("B4",) for r in cold if r[3] == 23)
