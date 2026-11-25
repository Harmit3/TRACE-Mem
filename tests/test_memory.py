from datetime import date
import unittest

from trace_mem.memory import Fact, Source, TemporalMemory


def day(number):
    return date(2026, 3, number)


def fact(fact_id, predicate, value, start, end=None):
    return Fact(fact_id, "person", predicate, value, Source(day(start), fact_id),
                day(start), day(end) if end is not None else None)


class TemporalMemoryTest(unittest.TestCase):
    def test_correction_preserves_history_and_provenance(self):
        memory = TemporalMemory()
        memory.accept(fact("a", "job", "Alder Labs", 1))
        memory.accept(fact("b", "job", "Birch Labs", 5), replaces="a")
        past, = memory.retrieve("person", "job", as_of=day(3))
        current, = memory.retrieve("person", "job", as_of=day(5))
        self.assertEqual((past.value, past.valid_to), ("Alder Labs", day(5)))
        self.assertEqual((current.value, current.supersedes), ("Birch Labs", "a"))
        self.assertEqual(memory.trace[-1].source, Source(day(5), "b"))

    def test_visit_expires_without_affecting_residence(self):
        memory = TemporalMemory()
        memory.accept(fact("a", "residence", "Oak City", 1))
        memory.accept(fact("b", "visit", "Pine City", 3, 5))
        home, = memory.retrieve("person", "residence", as_of=day(4))
        self.assertEqual(home.value, "Oak City")
        self.assertEqual(len(memory.retrieve("person", "visit", as_of=day(4))), 1)
        self.assertEqual(memory.retrieve("person", "visit", as_of=day(5)), ())

    def test_deletion_removes_historical_fact_and_rejects_id_reuse(self):
        memory = TemporalMemory()
        memory.accept(fact("a", "job", "Alder Labs", 1))
        memory.accept(fact("b", "job", "Birch Labs", 5), replaces="a")
        memory.delete("a", Source(day(6), "remove"))
        self.assertEqual(memory.retrieve("person", "job", as_of=day(3)), ())
        self.assertNotIn("Alder Labs", repr(memory.trace))
        with self.assertRaisesRegex(ValueError, "already been used"):
            memory.accept(fact("a", "job", "Alder Labs", 7))

    def test_deferral_and_invalid_replacement_leave_store_intact(self):
        memory = TemporalMemory()
        original = fact("a", "job", "Alder Labs", 1)
        memory.accept(original)
        memory.defer("b", Source(day(3), "maybe"))
        with self.assertRaisesRegex(ValueError, "same entity and predicate"):
            memory.accept(fact("c", "visit", "Pine City", 4), replaces="a")
        self.assertEqual(memory.retrieve("person", "job", as_of=day(4)), (original,))
        self.assertEqual([entry.operation for entry in memory.trace], ["add", "defer"])
