"""Sequential, resumable original TRACE-Mem extraction for LongMemEval."""

from argparse import ArgumentParser
from dataclasses import asdict
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.longmemeval_inputs import DESIGN, events
from scripts.run_memora import ROOT, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from trace_mem.claims import EXTRACTION_PROMPT
from trace_mem.llm_tasks import LLMTasks, RESPONSE_SCHEMAS
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


def extract_all(root):
    if (ROOT / "results").resolve() not in root.resolve().parents:
        raise ValueError("Use ignored local result paths")
    design = json.loads(DESIGN.read_bytes())
    inputs = root / "inputs.json"
    if {r["name"]: r["digest"] for r in local_json("/api/tags")["models"]}.get(QWEN) != QWEN_DIGEST:
        raise ValueError("Pinned Qwen digest unavailable")
    manifest = {"design": sha(DESIGN), "inputs": sha(inputs), "model": QWEN_DIGEST, "settings": SETTINGS,
                "prompt": EXTRACTION_PROMPT, "schema": RESPONSE_SCHEMAS["extract-v1"]}
    lock = root / "extraction-freeze.json"
    if lock.exists() and json.loads(lock.read_bytes()) != manifest:
        raise ValueError("Extraction configuration changed")
    write(lock, manifest)
    start = time.perf_counter()
    provider = ChatProvider(ProviderConfig("ollama", QWEN, design["extract_limit"], **SETTINGS),
                            root / "extract.sqlite")
    model = LLMTasks(provider)
    (root / "extraction").mkdir(exist_ok=True)
    summaries = []
    for case in json.loads(inputs.read_bytes()):
        case_name = case["case"]
        path = root / "extraction" / f"{case_name}.json"
        user_turns = tuple(e for e in events(case) if e.role == "user")
        rows = json.loads(path.read_bytes()) if path.exists() else []
        stopped = None
        for event in user_turns[len(rows):]:
            try:
                claims = model.extract(event)
                row = {"claims": [asdict(c) | {"effective_on": c.effective_on.isoformat(),
                    "expires_on": c.expires_on.isoformat() if c.expires_on else None} for c in claims]}
            except LimitExceeded as exc:
                if str(exc) != "Input exceeds conservative preflight ceiling":
                    stopped = str(exc)
                    break
                row = {"error": str(exc), "claims": []}
            except ProviderError as exc:
                if exc.retryable:
                    stopped = str(exc)
                    break
                row = {"error": str(exc), "claims": []}
            rows.append(row | {"source": f"{event.session_id}/{event.turn}"})
            write(path, rows)
            if len(rows) % 50 == 0:
                print(case_name, len(rows), "of", len(user_turns), flush=True)
        failures = sum("error" in row for row in rows)
        summaries.append({"case": case_name, "user_turns": len(user_turns), "processed": len(rows),
                          "errors": failures, "claims": sum(len(r["claims"]) for r in rows),
                          "turns_with_claims": sum(bool(r["claims"]) for r in rows),
                          "complete": len(rows) == len(user_turns) and not failures,
                          "stopped": stopped})
        print(json.dumps(summaries[-1]), flush=True)
    write(root / "extraction-report.json", {"cases": summaries, "usage": provider.stats(),
                                           "wall_seconds": time.perf_counter() - start})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    extract_all(parser.parse_args().output)
