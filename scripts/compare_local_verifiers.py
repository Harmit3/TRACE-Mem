"""Compare pinned local models on a frozen synthetic development set."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from scripts.validate_ollama_verifier import DIGEST, MODEL, OLLAMA_VERSION, ORIGIN
from scripts.validate_ollama_verifier_v2 import evaluate
from trace_mem.llm_tasks import DIRECT_V2_PROMPT, RESPONSE_SCHEMAS
from trace_mem.providers import ChatProvider, ProviderConfig


QWEN = "qwen2.5:7b-instruct-q4_K_M"
SETTINGS = dict(seed=23, timeout=120, retries=0, max_input_tokens=4096,
                max_output_tokens=256, context_tokens=4096)
MODE = "direct-v2"
# This release uses fresh values, predicates and surface forms. Only the
# evaluator sees the final boolean. There are 16 updates and 24 no-updates.
CASES = (
    ("replacement", "gym", "Eight Bells", "Birch Fitness", "correct", "I canceled Eight Bells. Birch Fitness has been my gym since yesterday.", True),
    ("replacement", "office", "Suite 18", "Suite 44", "assert", "Facilities finished our move this morning. Suite 44 is my permanent office.", True),
    ("replacement", "insurance", "Meadow Cover", "Granite Cover", "correct", "Granite Cover is in force now. The previous Meadow Cover contract ended.", True),
    ("replacement", "mailbox", "Box 15", "Box 28", "assert", "My keys for Box 15 were returned. From today my mailbox is Box 28.", True),
    ("replacement", "vehicle", "Sedan A", "Wagon B", "correct", "I traded in Sedan A and took ownership of Wagon B. It is now my only car.", True),
    ("replacement", "shift", "Night", "Early", "assert", "The schedule switch took effect on Monday. Early is my regular shift now.", True),
    ("replacement", "library", "Harbor Branch", "Larch Branch", "correct", "Please update my default library to Larch Branch. I switched it in my account yesterday.", True),
    ("replacement", "residence", "Willow Row", "Fern Rise", "assert", "My boxes are unpacked and I have handed back the old keys. I live at Fern Rise now.", True),
    ("replacement", "subscription", "Monthly Films", "Weekly Films", "correct", "I completed the switch from Monthly Films to Weekly Films. The latter is active today.", True),
    ("replacement", "contact_method", "voice call", "text message", "correct", "Going forward please text me instead of calling. This is my new contact preference.", True),
    ("replacement", "project", "North Array", "East Array", "assert", "I finished the handover and now work exclusively on East Array.", True),
    ("replacement", "courier", "Orange Dispatch", "Silver Dispatch", "assert", "Our new signed courier arrangement started on Tuesday. We now use Silver Dispatch exclusively.", True),
    ("replacement", "allergy", "no known pollen allergy", "birch pollen", "correct", "I confirmed that I'm allergic to birch pollen. My old record saying no known pollen allergy is outdated.", True),
    ("replacement", "course_section", "Section 2", "Section 6", "assert", "The registrar completed my transfer. I'm enrolled in Section 6, not Section 2.", True),
    ("replacement", "timezone", "UTC+2", "UTC+1", "correct", "My account timezone has been corrected to UTC+1. Please replace the UTC+2 entry.", True),
    ("replacement", "billing_address", "12 Stone Way", "5 Ash Avenue", "assert", "The billing address update finished. Use 5 Ash Avenue as my sole billing address from today.", True),
    ("temporary", "office", "Suite 7", "Suite 9", "assert", "I'm borrowing Suite 9 while my office is painted. I return to Suite 7 tomorrow.", False),
    ("temporary", "vehicle", "Hatchback", "Pickup", "assert", "I rented the pickup to move a chair, and will return it tonight.", False),
    ("temporary", "shift", "Morning", "Evening", "assert", "I agreed to cover the evening shift once. My regular morning schedule is unchanged.", False),
    ("temporary", "residence", "Birch Lane", "Dune Inn", "assert", "I'm at Dune Inn for the conference. I go back home to Birch Lane on Sunday.", False),
    ("historical", "gym", "Gray Fitness", "Oak Fitness", "assert", "I trained at Oak Fitness before I joined Gray Fitness two years ago.", False),
    ("historical", "insurance", "River Shield", "Brook Shield", "assert", "The records for my former Brook Shield policy showed up. That expired last winter.", False),
    ("historical", "mailbox", "Box 70", "Box 19", "assert", "Box 19 is the number printed on a letter from my previous apartment.", False),
    ("historical", "course_section", "Section D", "Section B", "assert", "Last semester I was in Section B. Section D is my current course section.", False),
    ("hypothetical", "courier", "Cedar Express", "Aspen Express", "assert", "Suppose we hired Aspen Express. What would it cost? We are pricing alternatives.", False),
    ("hypothetical", "contact_method", "phone", "email", "uncertain", "If I leave the country, emailing might work better than calling.", False),
    ("hypothetical", "vehicle", "Blue Sedan", "White Sedan", "assert", "If I won the raffle I'd drive the white sedan. I haven't entered yet.", False),
    ("hypothetical", "workspace", "Desk 3", "Desk 10", "uncertain", "I would take Desk 10 if it were open, but I haven't requested a move.", False),
    ("future", "subscription", "Archive Plus", "Archive Pro", "assert", "My upgrade to Archive Pro is scheduled for next month. Archive Plus remains active today.", False),
    ("future", "gym", "Hill Fitness", "Vista Fitness", "correct", "Vista Fitness approved my application. The membership starts in January, and I am still with Hill Fitness.", False),
    ("uncertain", "project", "Unit Amber", "Unit Green", "uncertain", "The assignment might be Unit Green. My supervisor has not decided.", False),
    ("uncertain", "office", "Room 12", "Room 23", "assert", "I saw Room 23 on the draft chart, but no one has told me my office changed.", False),
    ("other_subject", "vehicle", "Van T", "Car K", "assert", "My neighbor just purchased Car K; my van is still running.", False),
    ("other_subject", "shift", "Day", "Overnight", "assert", "My replacement on the weekend team started working overnight. I still work days.", False),
    ("unrelated", "billing_address", "9 Elm Walk", "42 Lime Walk", "assert", "I delivered a parcel to 42 Lime Walk this morning.", False),
    ("unrelated", "primary_language", "English", "Portuguese", "assert", "The workshop I attended offered a Portuguese handout.", False),
    ("unchanged_or_alias", "gym", "Cross Street Gym", "CSG", "assert", "CSG is the abbreviation on the card for my existing Cross Street Gym.", False),
    ("unchanged_or_alias", "insurance", "Town Mutual", "Town Mutual Standard", "assert", "The insurer added Standard to the printed plan name, without changing my existing policy.", False),
    ("negated", "timezone", "UTC-4", "UTC-7", "assert", "Do not change the timezone to UTC-7. Leave it at UTC-4.", False),
    ("conflicting", "project", "Lab Panel", "Bench Panel", "assert", "One spreadsheet says Bench Panel and another says Lab Panel. I need to confirm before changing the record.", False),
)


def local_json(path: str) -> dict:
    with build_opener(ProxyHandler({})).open(ORIGIN + path, timeout=5) as response:
        return json.load(response)


def checksum(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def freeze(qwen_digest: str) -> dict:
    tags = {item["name"]: item["digest"] for item in local_json("/api/tags")["models"]}
    version = local_json("/api/version")["version"]
    if version != OLLAMA_VERSION or tags.get(MODEL) != DIGEST or tags.get(QWEN) != qwen_digest:
        raise ValueError("Installed server or model does not match frozen comparison")
    return {
        "ollama_version": version, "models": {MODEL: DIGEST, QWEN: qwen_digest},
        "cases_sha256": checksum(CASES), "configuration": SETTINGS | {"temperature": 0},
        "prompt_schema_sha256": checksum([DIRECT_V2_PROMPT, RESPONSE_SCHEMAS["verify-direct-v2"]]),
        "mode": MODE, "gate": {"correct": 34, "false_updates": 0, "failures": 0, "recall": 0.8},
    }


def compare(qwen_digest: str, output: Path) -> dict:
    if Path("results").resolve() not in output.resolve().parents:
        raise ValueError("Use a fresh directory under results/")
    run = {"freeze": freeze(qwen_digest), "variants": {}}
    output.mkdir(parents=True, exist_ok=False)
    (output / "freeze.json").write_text(json.dumps(run["freeze"], indent=2), encoding="utf-8")
    for index, model in enumerate((MODEL, QWEN)):
        provider = ChatProvider(ProviderConfig("ollama", model, len(CASES), **SETTINGS),
                                output / f"model-{index}.sqlite")
        result = evaluate(provider, MODE, CASES)
        result["resident"] = [
            {key: item.get(key) for key in ("name", "digest", "size", "size_vram", "context_length")}
            for item in local_json("/api/ps")["models"] if item["name"] == model
        ]
        run["variants"][model] = result
        (output / "report.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
        print(json.dumps({"model": model, **{k: v for k, v in result.items() if k != "details"}}),
              flush=True)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qwen-digest", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        print(json.dumps(freeze(args.qwen_digest), sort_keys=True))
    else:
        result = compare(args.qwen_digest, args.output)
        raise SystemExit(int(not result["variants"][QWEN]["passed"]))
