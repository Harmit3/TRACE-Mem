"""Independent chronological source-authored histories for controller reevaluation."""

from dataclasses import replace
from datetime import date, timedelta
from itertools import product
import random

from scripts.run_memora_controlled import source_claim
from trace_mem.data.memora import Event


CODES = ("Alder", "Bramble", "Cobalt", "Dune", "Elm", "Fable", "Grove", "Harbor", "Iris",
         "Juniper", "Kite", "Larch", "Maple", "Nettle", "Orchid", "Pine", "Quill", "Reed",
         "Sable", "Teal", "Umber", "Violet", "Willow", "Yarrow", "Zinc")
MARKS = ("Leaf", "Bell", "Crown", "Drum", "Ember", "Fern", "Glass", "Hill", "Ivory", "Key",
         "Lantern", "Moon", "Nest", "Oar", "Pearl", "Quartz", "Ribbon", "Shell", "Thimble",
         "Urn", "Vale", "Wheel", "Yoke", "Acorn", "Brook", "Cairn", "Dawn", "Flute", "Gate", "Hearth", "Loom", "Moss", "Spire")
PATTERNS = ("correct", "implicit", "misleading", "uncertain", "historical")


def generate(config):
    rng = random.Random(config["seed"])
    codes = [f"{a} {b}" for a, b in product(CODES, MARKS)]
    rng.shuffle(codes)
    sequence = iter(codes)
    for family, predicate, setting in config["families"]:
        for member in range(config["histories_per_family"]):
            yield build(family, predicate, setting, member, rng, sequence)


def build(family, pred, setting, member, rng, sequence):
    anchor = date(2025, 7, 1) + timedelta(days=member)
    events, prepared, decisions = [], [], {}
    initial = next(sequence)
    value = initial

    def append(day, text, predicate=None, proposed=None, intent="assert", source="unknown", explicit=False):
        idx = len(events) + 1
        event = Event(day, idx, 1, "user", text, source)
        events.append(event)
        if predicate:
            item = source_claim(event, predicate, proposed, intent)
            prepared.append(replace(item, claim=replace(item.claim, explicit_effective_date=explicit)))
            return prepared[-1].fact_id
        return None

    append(anchor, f"For the {setting}, the current {pred} is {initial}.", pred, initial, source="direct")
    secret = f"Private note {next(sequence)}"
    append(anchor, f"Remember this private routing note: {secret}.", "private note", secret)
    cost1, cost2 = rng.randint(3, 19), rng.randint(2, 17)
    append(anchor, f"We paid ${cost1}.00 for the first set of supplies.", "recorded cost",
           f"We paid ${cost1}.00 for the first set of supplies.")
    order = list(PATTERNS)
    rng.shuffle(order)
    day = anchor
    for n, pattern in enumerate(order):
        day += timedelta(days=rng.choice((1, 3, 11, 40, 97)))
        proposed = next(sequence)
        before = value
        explicit = False
        if pattern == "correct":
            text = f"The {setting} switched the {pred} to {proposed} on {day.isoformat()}; the change is now in force."
            intent, value, explicit = "correct", proposed, True
        elif pattern == "implicit":
            text = f"The {setting} now uses {proposed} as its sole {pred}. The prior selection was retired."
            intent, value = "assert", proposed
        elif pattern == "misleading":
            text = (f"The rehearsal card suggests replacing the {pred} with {proposed}, but it was only a mock-up. "
                    f"The official {pred} is unchanged.")
            intent = "correct"
        elif pattern == "uncertain":
            text = f"The {setting} might use {proposed} for the {pred} next month. No decision has been made."
            intent = "uncertain"
        else:
            text = f"An old exhibit brochure lists {proposed} as the {pred} for a past season. This is an archival reference only."
            intent = "assert"
        identifier = append(day, text, pred, proposed, intent, ("direct", "reported", "unknown")[n % 3],
                            explicit)
        decisions[identifier] = {"day": day, "expected": value, "proposal": proposed, "kind": pattern,
                                 "changed": value != before}
        if n == 2:
            append(day, "A visitor asked how many benches are usually near a gallery entrance.")
    final = day + timedelta(days=1)
    append(final, f"We paid ${cost2}.00 for the final materials.", "recorded cost",
           f"We paid ${cost2}.00 for the final materials.")
    # Give the second event its own predicate so the single-slot baseline can retain both expenses.
    last = prepared[-1]
    prepared[-1] = replace(last, claim=replace(last.claim, predicate="second recorded cost"))
    append(final, f"Please forget this private routing note: {secret}.", "private note", secret, "delete")
    return {"id": f"{family}/{member}", "family": family, "member": member, "predicate": pred,
            "events": tuple(events), "claims": tuple(prepared), "decisions": decisions,
            "initial": initial, "start": anchor, "final": final, "current": value,
            "private": secret, "cost": cost1 + cost2}
