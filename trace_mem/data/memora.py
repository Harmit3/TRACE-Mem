"""Load one Memora history without opening its scoring rubric."""

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class Event:
    observed_on: date
    session_id: int
    turn: int
    role: str
    message: str


_ROLES = {"user_agent": "user", "ai_agent": "assistant"}


def replay(history: Path, through: date | None = None) -> Iterator[Event]:
    """Yield date-, session-, and turn-ordered events through the cutoff day."""
    sessions = {}
    directory = history / "conversations"
    paths = sorted(directory.glob("session_*.json"))
    if not paths:
        raise ValueError(f"No Memora sessions found in {directory}")

    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            observed_on = date.fromisoformat(record["date"])
            session_id = record["session_id"]
            if type(session_id) is not int or session_id != int(path.stem[8:]):
                raise ValueError("session ID does not match filename")
            if session_id in sessions or record["persona"] != history.name:
                raise ValueError("duplicate session ID or mismatched persona")
            turns = []
            previous = 0
            for row in record["conversation"]:
                turn = row["turn"]
                message = row["message"]
                if type(turn) is not int or turn <= previous:
                    raise ValueError("turn numbers must increase")
                if not isinstance(message, str):
                    raise ValueError("message must be text")
                turns.append(Event(observed_on, session_id, turn, _ROLES[row["speaker"]], message))
                previous = turn
            sessions[session_id] = observed_on, turns
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid Memora session file: {path.name}") from exc

    for observed_on, session_id in sorted((day, sid) for sid, (day, _) in sessions.items()):
        if through is not None and observed_on > through:
            break
        yield from sessions[session_id][1]
