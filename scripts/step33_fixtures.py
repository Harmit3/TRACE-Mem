"""Deterministic fictional outcomes authored independently of model predictions."""

NAMES = ("Alden", "Bram", "Celia", "Dara", "Emil", "Faye", "Gio", "Hana", "Ivo", "Juno")


def extraction():
    for i, name in enumerate(NAMES):
        date = f"2026-02-{i + 11}"
        place, task = f"{name} Hall", f"catalog {name} prints"
        noise = "Hello. Thank you for the explanation. " * 105
        scenarios = (
            ("long", "user", noise + f"I prefer {name} tea. My appointment is at {place} on {date}.",
             [(f"{name} tea", "assert"), (place, "assert")]),
            ("multiple", "user", f"My task is to {task}. The exhibit invitation recipient is {name} Studio.",
             [(task, "assert"), (f"{name} Studio", "assert")]),
            ("assistant", "assistant", f"I recommend {place} as a venue. I have recorded {i + 12} steps in the simulated log.",
             [(place, "assert"), (f"{i + 12} steps", "assert")]),
            ("repeat", "user", f"On {date} I measured {i + 21} cm. The following day I measured {i + 35} cm.",
             [(f"{i + 21} cm", "assert"), (f"{i + 35} cm", "assert")]),
            ("ambiguous", "user", f"I might move to {place}, but I have not decided.",
             [(place, "uncertain")]),
            ("delete", "user", f"Please forget my note about {task}. Keep my existing unrelated notes.",
             [(task, "delete")]),
            ("irrelevant", "user", f"Thanks. Could you explain how calendars work, {name}?",
             []),
        )
        for kind, role, message, expected in scenarios:
            yield {"id": f"{kind}-{i}", "role": role, "message": message, "expected": expected}


def reader():
    for i, name in enumerate(NAMES[:6]):
        scenarios = (
            ("lookup", "Which room is confirmed?", [f"The booking is confirmed in {name} Hall.", "The catering is pending."], [0]),
            ("multi", "Where is the booking and who is the host?",
             [f"Booking location: {name} Hall.", f"Host: {name} Studio.", "The booking is confirmed."], [0, 1]),
            ("negation", "Did the group approve the venue?",
             [f"The group did not approve {name} Hall.", "The group approved the catering."], [0]),
            ("insufficient", "Which room was confirmed?",
             [f"The group might book {name} Hall.", "No booking is confirmed."], []),
            ("conflict", "Which venue is currently confirmed?",
             [f"The venue is {name} Hall.", "The venue is Cedar Hall."], []),
        )
        for kind, question, facts, expected in scenarios:
            yield {"id": f"{kind}-{i}", "question": question, "facts": facts, "expected": expected}
