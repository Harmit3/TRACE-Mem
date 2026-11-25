"""Compare frozen local verifier variants on fresh synthetic development cases."""

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import time

from scripts.validate_ollama_verifier import MODEL, runtime
from trace_mem.claims import Claim
from trace_mem.llm_tasks import (
    DIRECT_V2_PROMPT, EVIDENCE_PROMPT, EVIDENCE_VERDICT_PROMPT,
    LLMTasks, RESPONSE_SCHEMAS, VERIFY_PROMPT,
)
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError


# category, predicate, old value, candidate, intent, user evidence, expected update
CASES = (
    ("replacement", "job", "Granite Clinic", "Mosaic Clinic", "correct", "I resigned from Granite Clinic in May. Mosaic Clinic employs me now.", True),
    ("replacement", "residence", "Quarry Village", "Dune Village", "assert", "My lease at Quarry Village ended and I moved permanently to Dune Village last week.", True),
    ("replacement", "membership", "Map Club", "Compass Club", "correct", "My active membership is Compass Club now. I left Map Club.", True),
    ("replacement", "commute", "Bus 41", "Ferry Blue", "assert", "I no longer take Bus 41 to my office. Ferry Blue is my regular commute.", True),
    ("replacement", "worksite", "West Hangar", "East Hangar", "correct", "Starting this morning my permanent duty station is East Hangar.", True),
    ("replacement", "phone", "ending 0712", "ending 0824", "assert", "My phone number changed. The only line where you can reach me now ends in 0824.", True),
    ("replacement", "subscription", "Copper Stream", "Quartz Stream", "correct", "Copper Stream has been canceled. I activated Quartz Stream as its replacement yesterday.", True),
    ("replacement", "preferred_contact", "mail", "email", "correct", "Please replace mail with email as my ongoing contact preference.", True),
    ("replacement", "parking", "Zone C", "Zone F", "assert", "Management made the changes yesterday. Zone F is my assigned parking zone from now on.", True),
    ("replacement", "carrier", "Sun Cellular", "Lake Cellular", "correct", "The transfer completed this morning. Lake Cellular is my carrier now.", True),
    ("replacement", "class", "Evening Ceramics", "Morning Woodwork", "assert", "I finished the enrollment switch. Morning Woodwork is my only current class.", True),
    ("replacement", "workspace", "Desk Maple", "Desk Indigo", "correct", "My manager permanently reassigned me to Desk Indigo last week.", True),
    ("replacement", "supplier", "Orchid Paper", "Tulip Paper", "assert", "For my studio orders, I switched suppliers to Tulip Paper. The new arrangement has already started.", True),
    ("replacement", "delivery_address", "8 Highland Crescent", "32 Market Mews", "correct", "I updated my regular delivery address to 32 Market Mews this afternoon and it is effective now.", True),
    ("replacement", "shoe_size", "size 8", "size 9", "correct", "I checked the current measurement again. My correct shoe size is 9; size 8 was a recording mistake.", True),
    ("replacement", "primary_language", "French", "English", "correct", "For this account, change my primary language to English going forward.", True),
    ("temporary", "residence", "Linden Walk", "Cobalt Hotel", "assert", "I am spending tonight at the Cobalt Hotel because my flight was canceled.", False),
    ("temporary", "worksite", "Copper Mill", "Slate Forge", "assert", "I'm covering one afternoon at Slate Forge for a coworker.", False),
    ("temporary", "commute", "Bus 8", "Metro West", "assert", "Bus 8 has a one-day detour. I will take Metro West just for today.", False),
    ("temporary", "workspace", "Desk Gray", "Desk Blue", "assert", "I borrowed Desk Blue for the morning while my keyboard was fixed.", False),
    ("historical", "residence", "Beech Square", "Tern Villas", "assert", "A package from my years at Tern Villas just turned up. That was two addresses ago.", False),
    ("historical", "carrier", "Amber Wireless", "Violet Wireless", "assert", "I first used Violet Wireless in college; that old account has been closed for years.", False),
    ("historical", "parking", "Lot Green", "Lot Yellow", "assert", "I found a photo of the Lot Yellow permit I had before my current assignment.", False),
    ("historical", "job", "Ivory Museum", "Canyon Library", "assert", "Before I took the museum job I worked at Canyon Library.", False),
    ("hypothetical", "membership", "Stone Choir", "Grove Choir", "uncertain", "If I ever leave Stone Choir, I would consider Grove Choir.", False),
    ("hypothetical", "supplier", "Fox Linen", "Owl Linen", "assert", "Imagine we switched to Owl Linen. Would their invoices be easier to reconcile?", False),
    ("hypothetical", "residence", "Maple Rise", "Palm Terrace", "assert", "Palm Terrace would be my new home if the offer were accepted, but I haven't made one.", False),
    ("hypothetical", "commute", "Tram 2", "Tram 7", "uncertain", "I could use Tram 7 if they extend the track to my neighborhood.", False),
    ("future", "worksite", "Mint Yard", "Pearl Yard", "assert", "My permanent transfer to Pearl Yard starts in three months. Until then I am based at Mint Yard.", False),
    ("future", "subscription", "Atlas Weekly", "Atlas Audio", "assert", "My subscription changes to Atlas Audio at the start of next quarter.", False),
    ("uncertain", "job", "Star Lab", "Horizon Lab", "uncertain", "I interviewed at Horizon Lab. I haven't been offered the position.", False),
    ("uncertain", "class", "Drawing I", "Drawing II", "assert", "I thought I had been enrolled in Drawing II, but the confirmation has not arrived and I don't know which class I'm in.", False),
    ("other_subject", "job", "Lotus Studio", "Poppy Studio", "assert", "My cousin recently began working at Poppy Studio.", False),
    ("other_subject", "parking", "Zone L", "Zone M", "assert", "My landlord was assigned Zone M this week.", False),
    ("unrelated", "residence", "Apple Court", "Plum Court", "assert", "I picked up a prescription near Plum Court. My address is unchanged.", False),
    ("unrelated", "supplier", "North Goods", "South Goods", "assert", "South Goods makes the paint sample I saw at the exhibition; I was only looking.", False),
    ("unchanged_or_alias", "worksite", "Harbor Annex", "HA Building", "assert", "We call the Harbor Annex the HA Building. It is the same office.", False),
    ("unchanged_or_alias", "subscription", "Civic Standard", "Civic Standard Annual", "assert", "Civic Standard Annual is what the bill calls my unchanged Civic Standard plan.", False),
    ("negated", "phone", "ending 3101", "ending 4220", "assert", "Please don't replace my number with the one ending 4220; that phone is disconnected.", False),
    ("conflicting", "class", "Piano A", "Piano B", "assert", "The counselor said Piano B, but my registration still says Piano A. Please wait until they confirm.", False),
)
MODES = ("original", "direct-v2", "evidence-v2")
SETTINGS = {"seed": 23, "temperature": 0, "timeout": 120, "retries": 0,
            "max_input_tokens": 4096, "max_output_tokens": 256}


def gate(correct: int, false_updates: int, failures: int, recall: float) -> bool:
    return correct >= 34 and false_updates == 0 and failures == 0 and recall >= 0.8


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def freeze() -> dict:
    return {
        **runtime(), **SETTINGS,
        "cases_sha256": _sha(CASES),
        "prompts_and_schemas_sha256": _sha([
            VERIFY_PROMPT, DIRECT_V2_PROMPT, EVIDENCE_PROMPT, EVIDENCE_VERDICT_PROMPT,
            {key: value for key, value in RESPONSE_SCHEMAS.items() if key.startswith("verify")},
        ]),
        "acceptance": {"minimum_correct": 34, "max_false_updates": 0, "max_failures": 0,
                       "minimum_update_recall": 0.8},
    }


def compare(output: Path) -> dict:
    root = Path("results").resolve()
    if not output.resolve().is_relative_to(root) or output.resolve() == root:
        raise ValueError("Use a fresh directory under results/")
    frozen = freeze()
    output.mkdir(parents=True, exist_ok=False)
    (output / "freeze.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    report = {"freeze": frozen, "cases": len(CASES), "variants": {}}
    today = date(2026, 2, 15)
    first_day = today - timedelta(days=20)
    for mode in MODES:
        provider = ChatProvider(ProviderConfig(
            "ollama", MODEL, len(CASES) * (2 if mode == "evidence-v2" else 1),
            seed=SETTINGS["seed"], timeout=SETTINGS["timeout"], retries=SETTINGS["retries"],
            max_input_tokens=SETTINGS["max_input_tokens"],
            max_output_tokens=SETTINGS["max_output_tokens"],
        ), output / f"{mode}.sqlite")
        tasks = LLMTasks(provider, verification_mode=mode)
        counts = Counter()
        details = []
        for index, (category, predicate, old, new, intent, message, expected) in enumerate(CASES, 1):
            fact = Fact("prior", "fictional", predicate, old, Source(first_day, "input/1"), first_day)
            claim = Claim(predicate, new, intent, today)
            started = time.perf_counter()
            try:
                result = tasks.verify(claim, fact, conversation=(message,))
            except ProviderError:
                result = None
            elapsed_ms = (time.perf_counter() - started) * 1000
            if result is None:
                counts["failure"] += 1
            elif result == "update":
                counts["tp" if expected else "fp"] += 1
            else:
                counts["fn" if expected else "tn"] += 1
            details.append(dict(case=index, category=category, expected_update=expected,
                                verdict=result, elapsed_ms=elapsed_ms))
        usage = provider.stats()
        tp, tn, fp, fn, failures = (counts[key] for key in ("tp", "tn", "fp", "fn", "failure"))
        positives = sum(row[-1] for row in CASES)
        negatives = len(CASES) - positives
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / positives
        expected_calls = len(CASES) * (2 if mode == "evidence-v2" else 1)
        report["variants"][mode] = {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn, "failures": failures,
            "accuracy": (tp + tn) / len(CASES), "false_update_rate": fp / negatives,
            "precision": precision, "recall": recall,
            "schema_compliance": usage["statuses"].get("ok", 0) / usage["attempts"],
            "expected_model_calls": expected_calls,
            "mean_case_latency_ms": sum(row["elapsed_ms"] for row in details) / len(CASES),
            "passed": gate(tp + tn, fp, failures, recall),
            "usage": usage, "details": details,
        }
        print(json.dumps({"mode": mode, **{k: v for k, v in report["variants"][mode].items()
                                         if k != "details"}}, sort_keys=True), flush=True)
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        print(json.dumps(freeze(), sort_keys=True))
    else:
        result = compare(args.output)
        raise SystemExit(int(not any(result["variants"][mode]["passed"] for mode in MODES[1:])))
