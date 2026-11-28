"""Check the conference paper's numerical claims against archived machine-readable results.

Run from the repository root. --local also checks the custodian's V3 training archive.
"""
import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_bytes())


def one(rows, **criteria):
    row, = (row for row in rows if all(row[k] == v for k, v in criteria.items()))
    return row


def interval(row):
    return tuple(round(100 * row[k], 1) for k in ("difference", "lower", "upper"))


def primary():
    d = load("docs/step30_artifacts/aggregate.json")
    protocol = load("docs/step30_freeze.json")
    assert (d["histories"], d["families"], protocol["seed"]) == (100, 10, 61843)
    assert protocol["budget_percents"] == [0, 10, 25, 50, 100]
    assert (protocol["bootstrap"]["replicates"], protocol["bootstrap"]["seed"]) == (2000, 9001)
    assert protocol["nominal_opportunities"] == 5
    for mode, counts, bounds in (
        ("fixed", [222, 356, 409, 341], (-11.3, -16.3, -6.3)),
        ("closed-loop", [222, 412, 394, 434], (6.7, 0.7, 12.3)),
    ):
        for method, count in zip(("B2", "B3", "H-paced", "T2"), counts):
            r = one(d["rows"], mode=mode, method=method, budget=50)
            assert (r["current"], r["current_total"]) == (count, 600)
            assert r["verification_attempts"] == (0 if method == "B2" else 250)
        assert interval(one(d["contrasts"], mode=mode, left="T2", right="H-paced", budget=50)) == bounds
    for method, stale, helpful in (("T2", 94, 122), ("H-paced", 70, 85)):
        assert one(d["rows"], mode="fixed", method=method, budget=50)["stale_targets"] == stale
        assert one(d["rows"], mode="closed-loop", method=method, budget=50)["helpful_verifications"] == helpful
    for method in ("B3", "T2", "H-paced"):
        r = one(d["rows"], mode="closed-loop", method=method, budget=100)
        assert (r["current"], r["verification_attempts"]) == (598, 500)
    for budget in (10, 25):
        a, b = [one(d["rows"], mode="closed-loop", method=m, budget=budget) for m in ("B3", "T2")]
        assert a["current"] > b["current"] and a["verification_attempts"] == b["verification_attempts"]
    assert d["oracle"]["current"] == 600
    assert [d["oracle"]["qa"][k]["correct"] for k in ("short", "reasoning")] == [5, 10]
    assert sum(r["deletion_total"] * r["seeds"] for r in d["rows"]) == 28000
    assert all(r["deletion"] == r["authorized_deletion"] == r["deletion_total"] for r in d["rows"])
    v = d["resources"]["verifier"]
    assert (v["attempts"], v["attempts"] + v["cache_hits"]) == (814, 16489)
    assert (v["input_tokens"], v["output_tokens"], round(v["latency_ms"] / 1000, 1)) == (233459, 9537, 730.4)
    assert round(d["resources"]["wall_seconds"]) == 1021


def followup():
    d = load("docs/step31_artifacts/aggregate.json")
    for horizon, bounds in ((100, (3.7, -1.7, 9.0)), (200, (-9.7, -16.3, -3.2))):
        assert interval(one(d["contrasts"], budget=50, mode="closed-loop", contrast="T2 minus B3", horizon=horizon)) == bounds
    r = one(d["rows"], mode="closed-loop", method="T2", budget=50, horizon=200)
    assert (r["verification_attempts"], r["accuracy"]) == (211, 0.59)
    for m, n, h in (("T2", 7, 100), ("B3", 6, None), ("H-paced", 12, 100)):
        qa = one(d["rows"], mode="closed-loop", method=m, budget=50, horizon=h)["qa"]["short"]
        assert (qa["correct"], qa["total"]) == (n, 30)
    m = load("docs/memora_step24_artifacts/aggregate.json")
    assert (m["judge"]["scored"], m["judge"]["rows"]) == (2184, 2400)
    assert all(r["macro_fama_seed_mean"] == 0 for r in m["curves"])
    e = load("docs/step32_artifacts/aggregate.json")
    for method, n in (("BM25", 3), ("MiniLM", 2), ("oracle", 6)):
        assert (e["methods"][method]["completed"], e["methods"][method]["correct"]) == (14, n)
    assert all(r == {"cases": 1, "correct": 0} for r in e["common_with_managed"].values())
    a = load("docs/step33_artifacts/metrics.json")["validation"]
    assert not a["extraction_gate"]["recall"]
    for method, facts, answers in (("original", 22, 27), ("candidate", 50, 24)):
        arm = a["arms"][method]
        assert (arm["extraction"]["correct"], arm["extraction"]["expected"]) == (facts, 100)
        assert arm["reader"]["correct"] == answers and arm["reader"]["accuracy"] == answers / 30


def workspace():
    d = load("research/workspace42/results.json")
    assert len(d["rows"]) == 54 and max(r["prompt"] for r in d["rows"]) == 1030
    for mode, expected in (
        ("standard", (0, 0, 0, 24, 16002, 36, 0)),
        ("rag", (6, 12, 24, 24, 16794, 42, 0)),
        ("trace", (18, 24, 30, 24, 5718, 18, 12)),
    ):
        rows = [r for r in d["rows"] if r["mode"] == mode]
        assert len(rows) == 18 and len({r["length"] for r in rows}) == 6
        assert (sum(r["correct"] for r in rows), sum(r["hits"] for r in rows),
                sum(len(r["values"]) for r in rows), sum(r["required"] for r in rows),
                sum(r["prompt"] for r in rows), sum(r["output"] for r in rows),
                sum(r["direct"] for r in rows)) == expected
        assert sum(r["correct"] for r in rows if r["kind"] == "reason") == (0 if mode == "standard" else 6)
    assert d["paraphrases"] == [[None, None], [None, None], [None, "education"], [None, None]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("Run with assertions enabled")
    primary()
    followup()
    workspace()
    if args.local:
        groups = load("results/updateset-v3-final/report.json")["groups"]
        assert sum(v["histories"] for v in groups.values()) == 200
        assert sum(v["families"] for v in groups.values()) == 40
        assert [groups[k]["positive"] + groups[k]["negative"] for k in ("train", "calibration", "evaluation")] == [112, 63, 37]
    print("Manuscript numerical checks passed.")
