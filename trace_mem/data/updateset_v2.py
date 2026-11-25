"""Independent synthetic paired-decision cases with raw focal user turns."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import random


SEED = 2407
SIZES = {"train": 350, "validation": 150}
PILOT_PER_FAMILY = 2
OBSERVED = "2026-02-15"
OLD_DATE = "2026-01-25"

# category, anchor predicate, old/new names, preceding context, focal user
# message and gold state ("old", "new", or None for human review).
FAMILIES = {
    "train": (
        ("implicit", "job", "Cedar Clinic", "Marble Clinic", "Which workplace should be on the emergency contact form?",
         "Put {new} on the form. That's where I work now.", "new"),
        ("indirect", "residence", "Harrow Court", "Basin Lane", "Do I still need to forward mail from the old apartment?",
         "The mail goes to {new} now. That's my permanent home and the forwarding has ended.", "new"),
        ("paraphrase", "job", "Sundial Press", "Solstice Press", "Are those two employers or one?",
         "They're the same. {new} is just the new sign on the building at {old}.", "old"),
        ("temporary", "residence", "Violet Walk", "Terrace Inn", "Are you home this week?",
         "I am at {new} until Tuesday. I'll be back at {old} right after the conference.", "old"),
        ("historical", "job", "Cliff Library", "Garden Library", "Tell me where you worked before your current role.",
         "That used to be {new}. Today I'm still employed by {old}.", "old"),
        ("future", "job", "Signal Depot", "Relay Depot", "Does the signed offer mean you have started?",
         "I accepted the offer from {new}, but I start next month. I still work at {old}.", "old"),
        ("contradictory", "residence", "Oak Mews", "Redwood Court", "The two addresses on file don't agree.",
         "The form says I moved to {new}, but that's an error. I have not left {old}.", "old"),
        ("other_subject", "job", "Mint Foods", "Basil Foods", "Was it you or your roommate who got hired?",
         "My roommate works at {new}. I work at {old}.", "old"),
        ("context_reference", "job", "Slate Records", "Quartz Records", "The new employer on the confirmed contract is {new}. Where do you work now?",
         "The new one. My first day there was yesterday.", "new"),
        ("uncertain", "residence", "Park Homes", "River Homes", "Did the landlord approve the move?",
         "I put {new} on one form, but the lease and my plans are still up in the air.", None),
        ("explicit", "job", "Ferry School", "Harbor School", "Is your replacement assignment permanent?",
         "I left {old}. I'm permanently employed by {new} now.", "new"),
    ),
    "validation": (
        ("implicit", "residence", "Kiln Square", "Wren Terrace", "Where do you consider home these days?",
         "I live at {new}. My keys to {old} went back to the landlord last night.", "new"),
        ("indirect", "job", "Glass Museum", "Copper Gallery", "Tell me which organization issues your current payslips.",
         "My active employer is {new}. The older payslip from {old} is just a record.", "new"),
        ("paraphrase", "residence", "Eastbank Apartments", "Eastbank Flats", "Have you had to register a change of address?",
         "No. {new} is the building's other name. My address at {old} hasn't changed.", "old"),
        ("temporary", "job", "Seam Studio", "Thread House", "Does covering the shift replace your own job?",
         "I only have a one-day cover shift at {new}; my employer remains {old}.", "old"),
        ("historical", "residence", "Moss Garden", "Pine Crescent", "Which address did you live at in college?",
         "{new} was my college address, before I settled at {old}.", "old"),
        ("future", "residence", "Aster Place", "Clover Place", "When do you hand over the current keys?",
         "The handover and move to {new} are scheduled for next spring. {old} is home until then.", "old"),
        ("contradictory", "job", "Beacon Workshop", "Lantern Works", "One entry names a different employer.",
         "Someone entered {new} in the directory. They have no role in my employment at {old}.", "old"),
        ("other_subject", "residence", "Osprey Steps", "Kestrel Steps", "Who is listed on that moving van receipt?",
         "My brother moved to {new}; I had only helped him unload. My home is {old}.", "old"),
        ("context_reference", "residence", "Creek Corner", "Delta Place", "Your new confirmed home address is {new}. Has the move happened?",
         "Yes, I've moved in there and no longer live at the previous place.", "new"),
        ("uncertain", "job", "Fern Center", "Juniper Hall", "Has the employment decision come through?",
         "HR listed {new} in one note, though the confirmed assignment hasn't arrived.", None),
        ("explicit", "residence", "Copper Steps", "Bronze Gate", "Please confirm which residence I should keep.",
         "Replace {old} with {new}. I moved and {new} is my permanent residence.", "new"),
    ),
}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate() -> tuple[list[dict], dict]:
    rng = random.Random(SEED)
    cases = []
    pilot = []
    for split, size in SIZES.items():
        families = FAMILIES[split]
        order = list(range(len(families)))
        rng.shuffle(order)
        groups = {index: [] for index in order}
        for ordinal in range(size):
            family = order[ordinal % len(order)]
            name, predicate, old_base, new_base, context, message, gold = families[family]
            suffix = f" {split[0].upper()}{ordinal + 1:03}"
            old, new = old_base + suffix, new_base + suffix
            case_id = f"trace-v2/{split}/{ordinal:03}"
            fact_id = f"{case_id}/prior"
            cases.append({
                "case_id": case_id, "split": split, "family": f"{split}/{name}",
                "persona": f"{case_id}/persona", "history": f"{case_id}/history",
                "observed_on": OBSERVED,
                "old_fact": {"id": fact_id, "value": old, "predicate": predicate,
                             "observed_on": OLD_DATE, "reference": f"{case_id}/source/1"},
                "conversation": [
                    {"role": "user", "text": f"My {'employer' if predicate == 'job' else 'home'} has been {old}."},
                    {"role": "assistant", "text": context.format(old=old, new=new)},
                    {"role": "user", "text": message.format(old=old, new=new)},
                ],
                "gold": (None if gold is None else {
                    "origin": "synthetic_rule", "reference": f"v2/{split}/{name}",
                    "current_value": new if gold == "new" else old,
                    "preserve_prior_value": old,
                }),
            })
            groups[family].append(case_id)
        for family in sorted(groups):
            pilot.extend(rng.sample(groups[family], PILOT_PER_FAMILY))
    distribution = {split: dict(Counter(case["family"] for case in cases if case["split"] == split))
                    for split in SIZES}
    manifest = {
        "schema_version": 2, "seed": SEED, "sizes": SIZES, "pilot_per_family": PILOT_PER_FAMILY,
        "pilot_ids": sorted(pilot), "families": distribution, "origin": "trace_synthetic",
        "benchmark_inputs": [],
    }
    return cases, manifest


def rows_bytes(rows: list[dict]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def write_release(output: Path) -> dict:
    cases, manifest = generate()
    pending = [{key: value for key, value in case.items() if key != "gold"}
               for case in cases if case["gold"] is None]
    artifacts = {"cases.jsonl": rows_bytes(cases), "pending-review.jsonl": rows_bytes(pending)}
    manifest["files"] = {name: sha(data) for name, data in artifacts.items()}
    manifest["pending_gold"] = dict(Counter(case["split"] for case in pending))
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    (output / "manifest.json").write_bytes(canonical(manifest) + b"\n")
    return manifest


def read_release(output: Path) -> tuple[list[dict], dict]:
    manifest = json.loads((output / "manifest.json").read_bytes())
    cases, expected = generate()
    data = (output / "cases.jsonl").read_bytes()
    pending = [{key: value for key, value in case.items() if key != "gold"}
               for case in cases if case["gold"] is None]
    expected["files"] = {"cases.jsonl": sha(rows_bytes(cases)),
                         "pending-review.jsonl": sha(rows_bytes(pending))}
    expected["pending_gold"] = dict(Counter(case["split"] for case in pending))
    if (manifest != expected or sha(data) != expected["files"]["cases.jsonl"]
            or sha((output / "pending-review.jsonl").read_bytes()) != expected["files"]["pending-review.jsonl"]):
        raise ValueError("V2 release differs from frozen independent generation")
    return cases, manifest
