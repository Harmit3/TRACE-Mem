"""Resumable original extraction for the frozen full Memora development diagnostic."""

from argparse import ArgumentParser
from collections import Counter
from dataclasses import asdict
from datetime import date
import json
from itertools import groupby
from pathlib import Path
import sqlite3
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.run_memora import PROTOCOL, ROOT, audit_checkout, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim, EXTRACTION_PROMPT
from trace_mem.data.memora import replay
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Source
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


DESIGN = ROOT / "docs/memora_step24_freeze.json"


def input_history(repository):
    design = json.loads(DESIGN.read_bytes())
    official = json.loads(PROTOCOL.read_bytes())
    revision = audit_checkout(repository, official)
    path = repository / official["development"]["path"]
    if path.name != design["development_persona"] or path.parent.name != design["period"]:
        raise ValueError("Frozen development persona does not match the audited path")
    return design, path, revision


def checkpoint_value(item):
    fields = asdict(item)
    for group, key in (("claim", "effective_on"), ("claim", "expires_on"), ("source", "observed_on")):
        if fields[group][key] is not None:
            fields[group][key] = fields[group][key].isoformat()
    return fields


def restore(row):
    claim, source = dict(row["claim"]), dict(row["source"])
    for key in ("effective_on", "expires_on"):
        if claim[key] is not None:
            claim[key] = date.fromisoformat(claim[key])
    source["observed_on"] = date.fromisoformat(source["observed_on"])
    return PreparedClaim(Claim(**claim), Source(**source), row["fact_id"])


def seed_cache(database, supplied):
    """Import successful keyed responses only, leaving old ledgers and caches untouched."""
    if supplied:
        with sqlite3.connect(database) as db:
            db.execute("ATTACH DATABASE ? AS previous", (supplied.resolve().as_uri() + "?mode=ro",))
            db.execute("INSERT OR IGNORE INTO response SELECT key, text FROM previous.response")


def run(repository, output, reuse):
    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results subdirectory")
    design, history, revision = input_history(repository)
    tags = {row["name"]: row["digest"] for row in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Original extraction requires the pinned local Qwen")
    output.mkdir(parents=True, exist_ok=True)
    freeze = {"protocol_sha256": sha(DESIGN), "revision": revision,
              "qwen": QWEN_DIGEST, "provider_settings": SETTINGS,
              "extractor_sha256": sha(ROOT / "trace_mem/claims.py"),
              "extraction_runner_sha256": sha(Path(__file__)),
              "ollama": local_json("/api/version")["version"]}
    freeze_path = output / "extraction-freeze.json"
    if freeze_path.exists() and json.loads(freeze_path.read_bytes()) != freeze:
        raise ValueError("Extraction freeze changed; create a new run directory")
    write(freeze_path, freeze)
    directory = output / "sessions"
    directory.mkdir(exist_ok=True)
    provider = ChatProvider(ProviderConfig("ollama", QWEN, design["max_extraction_requests"], **SETTINGS),
                            output / "extraction.sqlite")
    seed_cache(provider.database, reuse)
    tasks = LLMTasks(provider)
    started = time.perf_counter()
    total = Counter()
    for n, (session, events) in enumerate(groupby(replay(history), key=lambda e: e.session_id), 1):
        events = tuple(events)
        path = directory / f"{session:04d}.json"
        if path.exists():
            saved = json.loads(path.read_bytes())
        else:
            saved = {"session": session, "stats": Counter(), "claims": []}
            counts = saved["stats"]
            for event in events:
                counts["events"] += 1
                if event.role != "user":
                    continue
                counts["user_turns"] += 1
                prompt = json.dumps({"observed_on": event.observed_on.isoformat(), "message": event.message})
                if len((EXTRACTION_PROMPT + prompt).encode()) + 128 > (
                        SETTINGS["context_tokens"] - SETTINGS["max_output_tokens"]):
                    counts["overlong_turns"] += 1
                    continue
                try:
                    claims = tasks.extract(event)
                except LimitExceeded:
                    raise
                except ProviderError:
                    counts["failed_turns"] += 1
                    continue
                counts["claim_turns"] += bool(claims)
                counts["claims"] += len(claims)
                source = Source(event.observed_on, f"{session}/{event.turn}", event.source_kind)
                for i, claim in enumerate(claims):
                    counts[f"intent_{claim.intent}"] += 1
                    saved["claims"].append(checkpoint_value(PreparedClaim(
                        claim, source, f"{source.reference}/{i}")))
            write(path, saved)
        total.update(saved["stats"])
        if n % 10 == 0:
            print(json.dumps({"sessions_complete": n, **total}), flush=True)
    report = {"sessions": n, **total, "provider": provider.stats(),
              "invocation_wall_seconds": time.perf_counter() - started}
    write(output / "extraction-report.json", report)
    return report


if __name__ == "__main__":
    p = ArgumentParser(description=__doc__)
    p.add_argument("memora", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--reuse", type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.memora, a.output, a.reuse), sort_keys=True))
