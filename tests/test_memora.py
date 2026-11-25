from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from trace_mem.data.memora import Event, replay


class MemoraReplayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.history = Path(temporary.name) / "synthetic"
        (self.history / "conversations").mkdir(parents=True)

    def session(self, session_id, day, turns):
        record = {
            "session_id": session_id,
            "persona": self.history.name,
            "date": day,
            "operation": "scorer-only sentinel",
            "conversation": turns,
        }
        path = self.history / "conversations" / f"session_{session_id}.json"
        path.write_text(json.dumps(record), encoding="utf-8")

    def test_replay_orders_numerically_and_includes_cutoff_day(self):
        day = date(2026, 1, 1)
        self.session(10, str(day), [{"turn": 1, "speaker": "ai_agent", "message": "third"}])
        self.session(2, str(day), [
            {"turn": 1, "speaker": "user_agent", "message": "first", "share_memory": True},
            {"turn": 2, "speaker": "ai_agent", "message": "second"},
        ])
        self.session(11, "2026-01-02", [{"turn": 1, "speaker": "user_agent", "message": "later"}])
        (self.history / "evaluation_questions_synthetic.json").write_text("invalid JSON")
        self.assertEqual(list(replay(self.history, day)), [
            Event(day, 2, 1, "user", "first"),
            Event(day, 2, 2, "assistant", "second"),
            Event(day, 10, 1, "assistant", "third"),
        ])

    def test_malformed_history_fails_before_emitting_events(self):
        self.session(1, "2026-01-01", [{"turn": 1, "speaker": "user_agent", "message": "first"}])
        self.session(2, "2026-01-01", [{"turn": 1, "speaker": "unknown", "message": "bad role"}])
        with self.assertRaisesRegex(ValueError, "session_2.json"):
            next(replay(self.history))
