"""Hand-authored, model-independent v3 pilot cases."""

from datetime import date, timedelta


OBSERVED = date(2026, 4, 24)
# Each pair belongs to its own family. Case values are natural and contain no IDs.
# predicate, prior, proposed, gap days, old/new provenance, context, focal, gold
FAMILIES = {
    "train": {
        "lease_handover": (
            ("residence", "Wren Apartments", "Birch Court", 73, "direct", "dated_record",
             "The signed lease and handover receipt both start April 20.",
             "I moved to Birch Court on 2026-04-20. That's my permanent home now.", "new"),
            ("residence", "Linden Terrace", "Oak View", 9, "dated_record", "direct",
             "You are staying with friends while the plumbing is repaired.",
             "I am at Oak View for the week, then I'll move back home to Linden Terrace.", "old"),
        ),
        "payroll_transfer": (
            ("job", "Aster Press", "Maple Studio", 63, "direct", "direct",
             "The last payslip from Aster Press is marked final.",
             "Maple Studio now pays my salary. I started there after leaving the press.", "new"),
            ("job", "Rowan Café", "Lake Bistro", 19, "direct", "reported",
             "The rota for Lake Bistro was forwarded from your roommate.",
             "My roommate works at Lake Bistro; I still work at Rowan Café.", "old"),
        ),
        "directory_dispute": (
            ("job", "River Library", "Cove Archive", 36, "dated_record", "conflicting",
             "The directory lists one employer and the contract another.",
             "It lists Cove Archive, but that entry is a mistake. River Library still employs me.", "old"),
            ("job", "Slate Museum", "Elm Gallery", 6, "reported", "conflicting",
             "The roster and HR message conflict.",
             "The roster says Elm Gallery, but I haven't confirmed where I will be employed.", None),
        ),
        "mail_reassignment": (
            ("residence", "Sparrow Lane", "Willow Mews", 105, "reported", "direct",
             "The old forwarding notice just expired.",
             "Address my mail to Willow Mews. I live there now and have returned the old keys.", "new"),
            ("residence", "Orchard Walk", "Pine Lodge", 56, "direct", "reported",
             "You found an old return label for Pine Lodge.",
             "I lived at Pine Lodge back in college. My present home is still Orchard Walk.", "old"),
        ),
    },
    "calibration": {
        "orientation_date": (
            ("job", "Cedar Bakery", "Harbor Kitchen", 44, "dated_record", "dated_record",
             "The contract lists the new start date and confirms the old contract ended.",
             "I have worked for Harbor Kitchen since 2026-04-16, when I left Cedar Bakery.", "new"),
            ("job", "Dune Gardens", "Fern Nursery", 16, "direct", "direct",
             "Your offer letter has a future start date.",
             "I'm still employed by Dune Gardens. I don't start at Fern Nursery until 2026-05-01.", "old"),
        ),
        "utility_account": (
            ("residence", "Hill House", "Birch Landing", 88, "dated_record", "direct",
             "Is the address on the new utility bill your current home?",
             "Birch Landing is where I live now. I handed the keys for Hill House back last month.", "new"),
            ("residence", "Peach Square", "Ash Terrace", 27, "direct", "reported",
             "The utility bill you forwarded belongs to your sister.",
             "She lives at Ash Terrace. My own address is Peach Square.", "old"),
        ),
        "temporary_cover": (
            ("job", "Quartz Lab", "Copper Lab", 53, "reported", "direct",
             "A temporary placement is different from a new permanent job.",
             "I am covering a shift at Copper Lab tonight, but my employer is Quartz Lab.", "old"),
            ("job", "Amber Depot", "Cobalt Yard", 24, "dated_record", "direct",
             "The transfer form states the arrangement is permanent.",
             "My old employment at Amber Depot ended. Cobalt Yard employs me now.", "new"),
        ),
        "forwarding_uncertainty": (
            ("residence", "Meadow Gate", "Clover Place", 12, "reported", "conflicting",
             "The forwarding form was submitted but the move was delayed.",
             "The form says Clover Place. I don't know whether the move will go ahead.", None),
            ("residence", "Bramble Rise", "Moss Grove", 38, "direct", "direct",
             "The forwarding form has not been sent.",
             "I considered Moss Grove, but I never moved and I still live at Bramble Rise.", "old"),
        ),
    },
    "evaluation": {
        "professional_register": (
            ("job", "Cloud Clinic", "Rain Clinic", 98, "dated_record", "direct",
             "The old employment listing was withdrawn.",
             "Update the register to Rain Clinic. They are my only employer and I started yesterday.", "new"),
            ("job", "Ivy Health", "Holly Health", 14, "direct", "reported",
             "The professional register groups the two names together.",
             "Holly Health is just Ivy Health's trading name. My employment did not change.", "old"),
        ),
        "residence_inspection": (
            ("residence", "Daisy Court", "Poppy Lane", 120, "direct", "dated_record",
             "The inspector's handover receipt is dated April 22.",
             "Poppy Lane became my home on 2026-04-22. I no longer live at Daisy Court.", "new"),
            ("residence", "Heron Court", "Crane Inn", 3, "direct", "direct",
             "Your current booking is only for the weekend.",
             "I'm visiting Crane Inn until Sunday, then going back home to Heron Court.", "old"),
        ),
        "employee_reference": (
            ("job", "Owl Books", "Robin News", 67, "reported", "reported",
             "The reference names an employer from several years ago.",
             "Robin News employed me long ago. I currently work for Owl Books.", "old"),
            ("job", "Dove Paper", "Swift Media", 31, "direct", "conflicting",
             "The recommendation letter and training schedule disagree.",
             "One note says Swift Media and one says Dove Paper. I can't confirm my assignment.", None),
        ),
        "household_move": (
            ("residence", "Chalk Row", "Flint Terrace", 46, "reported", "direct",
             "Your household finished unpacking at the new address.",
             "Flint Terrace is where I live now. Chalk Row was the previous address.", "new"),
            ("residence", "Garden End", "Fountain Row", 22, "dated_record", "reported",
             "The photo shows a family member's new apartment.",
             "My cousin moved to Fountain Row. I have not moved from Garden End.", "old"),
        ),
    },
}


def cases() -> list[dict]:
    records = []
    for split, families in FAMILIES.items():
        for family, examples in families.items():
            for index, (predicate, old, new, gap, old_kind, kind, context, message, gold) in enumerate(examples):
                case_id = f"trace-v3/{split}/{family}/{index + 1}"
                initial = f"My {'employer' if predicate == 'job' else 'home'} is {old}."
                records.append({
                    "id": case_id, "split": split, "family": family,
                    "old": {"predicate": predicate, "value": old,
                            "observed_on": (OBSERVED - timedelta(days=gap)).isoformat(), "kind": old_kind},
                    "observed_on": OBSERVED.isoformat(), "kind": kind,
                    "transcript": [{"role": "user", "text": initial},
                                   {"role": "assistant", "text": context},
                                   {"role": "user", "text": message}],
                    "gold": {"current": new if gold == "new" else old, "prior": old} if gold else None,
                })
    return records
