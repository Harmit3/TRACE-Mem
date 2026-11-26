"""Loopback-only, offline browser demo. All scenario claims and verdicts are fictional."""

from argparse import ArgumentParser
from datetime import date
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim
from trace_mem.data.memora import Event
from trace_mem.memora_benchmark import run_suite
from trace_mem.memory import Source


ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).with_name("demo_web")
POLICIES = ("B2", "B3", "B5")
TIMELINE = (
    ("Initial office", "office", "Cedar Hall", "assert"),
    ("Private routing note recorded", "routing note", "Blue envelope", "assert"),
    ("Permanent office correction", "office", "Maple Studio", "assert"),
    ("Possible future move", "office", "Harbor Annex", "uncertain"),
    ("Routing note deleted", "routing note", "Blue envelope", "delete"),
)
STATIC = {
    "/": (WEB / "index.html", "text/html"),
    "/style.css": (WEB / "style.css", "text/css"),
    "/app.js": (WEB / "app.js", "text/javascript"),
    "/horizon.png": (ROOT / "docs/step31_artifacts/horizon.png", "image/png"),
    "/paired.png": (ROOT / "docs/step30_artifacts/paired-intervals.png", "image/png"),
}


class FictionalVerifier:
    def verify(self, claim, target, *, conversation):
        return "update" if claim.value == "Maple Studio" else "insufficient_evidence"


def sample(policy, cap, step, query):
    if (policy not in POLICIES or cap not in (0, 1, 2) or not 1 <= query <= step <= len(TIMELINE)):
        raise ValueError("Unknown policy, budget, replay step or query day")
    events, claims = [], []
    for i, (label, predicate, value, intent) in enumerate(TIMELINE[:step], 1):
        day = date(2025, 1, i)
        events.append(Event(day, i, 1, "user", label))
        claims.append(PreparedClaim(Claim(predicate, value, intent, day), Source(day, f"{i}/1", "direct"), f"e{i}"))
    state, metrics = run_suite(
        events, claims, FictionalVerifier(), entity="fictional-subject", models={}, builders={},
        mode="closed-loop", cap=cap, seed=23, methods=(policy,))[policy]
    facts = state.retrieve("fictional-subject", None, as_of=date(2025, 1, query))
    stats = {"calls": metrics["verification_attempts"], "eligible": metrics["eligible_candidates"],
             "allowance": cap if policy != "B2" else 0}
    return {
        "fictional": True, "policy": policy, "query": query, "step": step, "stats": stats,
        "facts": [{"slot": f.predicate, "value": f.value, "source": f.source.reference,
                   "valid_from": f.valid_from.isoformat(), "valid_to": f.valid_to.isoformat() if f.valid_to else None}
                  for f in facts],
        "timeline": [{"day": i, "label": label, "operations": [t.operation for t in state.trace
                     if t.source.reference == f"{i}/1"]}
                     for i, (label, *_rest) in enumerate(TIMELINE[:step], 1)],
    }


@lru_cache(maxsize=1)
def archive():
    def load(step, filename):
        return json.loads((ROOT / f"docs/step{step}_artifacts/{filename}.json").read_bytes())
    a, b, c, d = (load(n, "metrics" if n == 33 else "aggregate") for n in (30, 31, 32, 33))
    return {"cohort": {"histories": a["histories"], "families": a["families"]},
            "performance": [{k: r[k] for k in ("mode", "budget", "method", "current_accuracy",
                                               "historical_accuracy", "harmful_adoptions",
                                               "verification_attempts", "budget_cap")} for r in a["rows"]],
            "contrasts": a["contrasts"], "resources": a["resources"],
            "horizon": [{k: r[k] for k in ("budget", "method", "horizon", "accuracy",
                                          "verification_attempts", "budget_cap")} for r in b["rows"]
                        if r["mode"] == "closed-loop" and r["method"] in ("T2", "B3", "H-paced")],
            "external": {k: {x: c["methods"][k][x] for x in (
                "correct", "completed", "judged", "invalid_reader", "invalid_judge", "session_recall", "turn_recall")}
                for k in ("BM25", "MiniLM", "oracle", "T2-2")},
            "validation": d["validation"]["arms"]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_error(403)
            return
        parts = urlsplit(self.path)
        if parts.path in STATIC and not parts.query:
            file, kind = STATIC[parts.path]
            self.respond(file.read_bytes(), kind)
            return
        try:
            if parts.path == "/api/archive" and not parts.query:
                data = archive()
            elif parts.path == "/api/replay":
                q = parse_qs(parts.query, strict_parsing=True, max_num_fields=4)
                if set(q) != {"policy", "cap", "step", "query"} or any(len(x) != 1 for x in q.values()):
                    raise ValueError("Expected one value for each replay control")
                data = sample(q["policy"][0], int(q["cap"][0]), int(q["step"][0]), int(q["query"][0]))
            else:
                self.send_error(404)
                return
        except (ValueError, KeyError):
            self.send_error(400, "Invalid demonstration controls")
            return
        self.respond(json.dumps(data, allow_nan=False).encode(), "application/json")

    def respond(self, body, kind):
        self.send_response(200)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind != "image/png" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    config = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", config.port), Handler) as server:
        print(f"TRACE-Mem offline demo: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
