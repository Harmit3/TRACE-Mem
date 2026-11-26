"""Read-only Step 32 audit with a new ledger for nine exact-request forensic replays."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
import json
from pathlib import Path
import random

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.run_memora import ROOT, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.claims import EXTRACTION_PROMPT, parse_claims
from trace_mem.data.memora import Event
from trace_mem.llm_tasks import LLMTasks
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError, http_transport


REVIEW = (
    "missed", "missed", "missed", "non-memory", "missed", "ambiguous",
    "non-memory", "missed", "missed", "ambiguous", "non-memory", "non-memory",
    "non-memory", "ambiguous", "non-memory", "missed", "non-memory", "non-memory",
    "non-memory", "non-memory", "non-memory", "non-memory", "missed", "non-memory",
)


def rejection(raw, day):
    if raw is None:
        return "transport-no-response"
    if raw.get("done_reason") != "stop":
        return "terminal-" + str(raw.get("done_reason", "unknown"))
    body = raw.get("message", {}).get("content", "")
    try:
        value = json.loads(body)
    except ValueError:
        return "malformed-json"
    if not isinstance(value, list):
        return "top-level-not-array"
    try:
        parse_claims(body, day)
    except (ValueError, TypeError, KeyError) as error:
        reason = str(error)
        if reason.startswith(("Unknown claim intent", "Claim expiry", "Claim predicate",
                              "Each claim", "Invalid isoformat string")):
            return reason.split(":")[0]
        return "invalid-claim-fields"
    return "valid-on-replay"


def audit(previous, output):
    if ((ROOT / "results").resolve() not in output.resolve().parents
            or previous.resolve() == output.resolve()):
        raise ValueError("Use separate ignored result directories")
    if {r["name"]: r["digest"] for r in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned Qwen unavailable")
    inputs = json.loads((previous / "inputs.json").read_bytes())
    paths = [previous / filename for filename in (
        "blind-predictions.json", "safe-report.json", "human-review.json", "extraction-report.json")]
    originals = {p.name: sha(p) for p in paths}
    output.mkdir(parents=True, exist_ok=True)
    current = None

    def transport(*args):
        nonlocal current
        current = http_transport(*args)
        return current

    provider = ChatProvider(ProviderConfig("ollama", QWEN, 9, **SETTINGS),
                            output / "step32-forensics.sqlite", transport=transport)
    task = LLMTasks(provider)
    failures, empty = [], []
    checkpoint = output / "step32-audit-progress.json"
    saved = json.loads(checkpoint.read_bytes()) if checkpoint.exists() else {}
    for case in inputs:
        original = previous / "extraction" / f"{case['case']}.json"
        if not original.exists():
            continue
        turns = {f"{s}/{n}": Event(date.fromisoformat(day), s, n, role, message)
                 for day, s, n, role, message in case["turns"]}
        for row in json.loads(original.read_bytes()):
            ref = row["source"]
            if "error" not in row:
                if not row["claims"]:
                    empty.append((case["case"], ref))
                continue
            event = turns[ref]
            identity = f"{case['case']}/{ref}"
            payload = json.dumps({"observed_on": event.observed_on.isoformat(), "message": event.message})
            charge = len((EXTRACTION_PROMPT + payload).encode()) + 128
            kind = "preflight-oversized"
            if "preflight" not in row["error"]:
                if identity not in saved:
                    current = None
                    try:
                        task.extract(event)
                    except ProviderError:
                        pass
                    saved[identity] = rejection(current, event.observed_on)
                    write(checkpoint, saved)
                kind = saved[identity]
            failures.append({"case": case["case"], "source": ref, "original": row["error"],
                             "replay_diagnosis": kind, "preflight_bytes": charge})
    review = [dict(case=case, source=source, assessment=label) for (case, source), label in
              zip(random.Random(3318).sample(empty, 24), REVIEW, strict=True)]
    readers = json.loads(paths[1].read_bytes())["rows"]
    reader_audit = {}
    for method in ("BM25", "MiniLM", "oracle"):
        subset = [r["methods"][method] for r in readers]
        reader_audit[method] = dict(Counter(
            f"{r['status']}|{r['judge']}|{'all-tagged-turns' if r['turn_recall'] and r['turn_recall'][0] == r['turn_recall'][1] else 'other'}"
            for r in subset))
    if originals != {p.name: sha(p) for p in paths}:
        raise ValueError("Step 32 state changed")
    report = {"protected_sha256": originals, "failures": failures, "empty_population": len(empty),
              "empty_sample": review, "usage": provider.stats(), "reader_audit": reader_audit}
    write(output / "step32-audit.json", report)
    print(json.dumps({"failure_diagnoses": Counter(r["replay_diagnosis"] for r in failures),
                      "empty_sample": Counter(REVIEW), "usage": report["usage"]}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audit(args.previous, args.output)
