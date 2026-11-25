"""Check the frozen local verifier on synthetic development cases."""

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from trace_mem.claims import Claim
from trace_mem.llm_tasks import LLMTasks, RESPONSE_SCHEMAS, VERIFY_PROMPT
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError


MODEL = "llama3.2:3b"
DIGEST = "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72"
ORIGIN = "http://127.0.0.1:11434"
OLLAMA_VERSION = "0.40.13"
# The expected column is used only after the verifier returns. Evaluation is
# update versus no update because that is what the paired collector applies.
CASES = (
    ("u1", "commute", "Route 14", "Route 27", "correct",
     "I stopped commuting on route 14. Starting today I use route 27 instead.", True),
    ("u2", "residence", "Juniper Court", "Basin Flats", "correct",
     "The move is complete. Basin Flats is my permanent home now.", True),
    ("u3", "subscription", "Paper Digest", "Audio Digest", "correct",
     "I canceled Paper Digest and replaced it today with Audio Digest.", True),
    ("u4", "worksite", "Mint Wharf", "Amber Pier", "correct",
     "My permanent assignment moved today from Mint Wharf to Amber Pier.", True),
    ("u5", "membership", "Chess Circle", "Bridge Circle", "assert",
     "I resigned from the Chess Circle. My only club membership is now the Bridge Circle.", True),
    ("n1", "subscription", "News Basic", "News Plus", "uncertain",
     "My renewal email advertises News Plus. I have not changed my plan.", False),
    ("n2", "residence", "Hearth Lane", "Delta Court", "assert",
     "Delta Court is where I am staying for a wedding this weekend. Hearth Lane remains my home.", False),
    ("n3", "worksite", "South Warehouse", "River Warehouse", "assert",
     "I trained at River Warehouse last winter, before I joined South Warehouse.", False),
    ("n4", "commute", "Tram Five", "Bus Nine", "assert",
     "I saw someone take Bus Nine. My own commute is still Tram Five.", False),
    ("n5", "membership", "Star Theater", "Moon Theater", "uncertain",
     "If the schedule works out I might move to Moon Theater, but I haven't decided.", False),
    ("n6", "subscription", "Garden Standard", "Garden Standard Monthly", "assert",
     "Garden Standard Monthly is the full name of my existing Garden Standard plan.", False),
    ("n7", "worksite", "Birch Shed", "North Barn", "assert",
     "My manager says somebody needs to transfer to North Barn, but nobody has been assigned.", False),
)


def runtime() -> dict:
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"{ORIGIN}/api/version", timeout=5) as response:
        version = json.load(response)["version"]
    with opener.open(f"{ORIGIN}/api/tags", timeout=5) as response:
        models = json.load(response)["models"]
    if version != OLLAMA_VERSION:
        raise ValueError("Ollama version differs from the frozen configuration")
    if not any(item["name"] == MODEL and item["digest"] == DIGEST for item in models):
        raise ValueError("Installed model digest differs from the frozen configuration")
    return {"ollama_version": version, "model": MODEL, "digest": DIGEST}


def configuration() -> dict:
    return {
        "prompt_schema_sha256": hashlib.sha256(json.dumps(
            [VERIFY_PROMPT, RESPONSE_SCHEMAS["verify-v1"]], sort_keys=True,
        ).encode()).hexdigest(),
        "development_cases_sha256": hashlib.sha256(json.dumps(CASES).encode()).hexdigest(),
        "temperature": 0, "seed": 23, "timeout": 120,
        "retries": 0, "max_input_tokens": 4096, "max_output_tokens": 256,
    }


def verdict_gate(correct: int, false_updates: int, failures: int) -> bool:
    return correct >= 10 and false_updates == 0 and failures == 0


def validate(output: Path) -> dict:
    if not output.resolve().is_relative_to(Path("results").resolve()) or output.resolve() == Path("results").resolve():
        raise ValueError("Use a fresh directory under results/")
    if output.exists():
        raise FileExistsError(output)
    identity = runtime()
    config = configuration()
    provider = ChatProvider(ProviderConfig(
        "ollama", MODEL, len(CASES), timeout=config["timeout"], seed=config["seed"],
        retries=config["retries"], max_input_tokens=config["max_input_tokens"],
        max_output_tokens=config["max_output_tokens"],
    ), output / "responses.sqlite")
    tasks = LLMTasks(provider)
    today = date(2026, 2, 15)
    old_day = today - timedelta(days=20)
    scores = Counter()
    details = []
    for identifier, predicate, previous, new, message_intent, message, expected in CASES:
        old = Fact("old", "fictional", predicate, previous, Source(old_day, "source/1"), old_day)
        claim = Claim(predicate, new, message_intent, today)
        try:
            verdict = tasks.verify(claim, old, conversation=(message,))
        except ProviderError:
            scores["failures"] += 1
            details.append({"case": identifier, "verdict": None, "expected_update": expected})
            continue
        update = verdict == "update"
        scores["correct"] += update == expected
        scores["false_updates"] += update and not expected
        scores["missed_updates"] += expected and not update
        details.append({"case": identifier, "verdict": verdict, "expected_update": expected})
    report = {
        **identity, **config, "cases": len(CASES),
        "correct": scores["correct"], "false_updates": scores["false_updates"],
        "missed_updates": scores["missed_updates"], "failures": scores["failures"],
        "passed": verdict_gate(scores["correct"], scores["false_updates"], scores["failures"]),
        "usage": provider.stats(), "details": details,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.output) if args.output else {**runtime(), **configuration()}
    print(json.dumps(report, sort_keys=True))
    return int(report.get("passed") is False)


if __name__ == "__main__":
    raise SystemExit(main())
