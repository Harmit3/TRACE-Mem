from datetime import date
import json
import unittest

from scripts.updateset_v3_pilot import collect
from trace_mem.baselines import run_t1
from trace_mem.claims import Claim, parse_claims
from trace_mem.controller import LogisticController
from trace_mem.data.memora import Event
from trace_mem.data.updateset_v3 import cases
from trace_mem.features_v3 import V3Features
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memory import Fact, Source
from trace_mem.semantic import NLIScores
from trace_mem.verification import Budget


class UpdateSetV3Test(unittest.TestCase):
    def test_partitions_have_disjoint_families_and_no_ids_in_text(self):
        rows = cases()
        family_sets = [{row["family"] for row in rows if row["split"] == split}
                       for split in ("train", "calibration", "evaluation")]
        self.assertEqual(len(rows), 24)
        self.assertEqual(len(set.union(*family_sets)), 12)
        self.assertEqual(sum(row["gold"] is None for row in rows), 3)
        self.assertTrue(all("trace-v3" not in turn["text"] for row in rows for turn in row["transcript"]))

    def test_feature_builder_uses_dates_sources_and_budget(self):
        day = date(2026, 4, 24)
        old = Fact("old", "person", "job", "Old Lab", Source(date(2026, 3, 1), "old", "reported"),
                   date(2026, 3, 1))
        claim, = parse_claims('[{"predicate":"job","value":"New Lab","intent":"assert",'
                              '"effective_on":"2026-04-24"}]', day)
        embed = lambda texts: [[1, 0], [0, 1]]
        kwargs = dict(entity="person", source=Source(day, "new", "dated_record"),
                      budget_remaining_fraction=0.625)
        self.assertEqual(V3Features(embed)(claim, old, **kwargs),
                         (0.0, None, 1.0, 1.0, 54.0, 0.5, 0.5, 0.625))
        self.assertEqual(V3Features(embed, lambda *_: NLIScores(0.2, 0.3, 0.5))(
            claim, old, **kwargs)[1], 0.2)
        with self.assertRaisesRegex(ValueError, "exact entity"):
            V3Features(embed)(claim, old, **(kwargs | {"entity": "different"}))

    def test_collection_uses_actual_budget_and_never_passes_gold(self):
        records = [row for row in cases() if row["split"] == "train"][:2]
        budget = Budget(2)
        seen = []

        def respond(task, payload):
            seen.append(payload)
            if task == "extract-v1":
                return json.dumps([dict(predicate="residence", value="Different Residence", intent="assert")])
            return '{"verdict":"insufficient_evidence"}'

        tasks = LLMTasks(MockProvider(respond), verification_mode="direct-v2")
        features = V3Features(lambda _: [[1, 0], [1, 0]])
        rows = [collect(record, tasks, features, budget) for record in records]
        self.assertEqual([row["features"][-1] for row in rows], [1.0, 0.5])
        self.assertEqual(budget.remaining, 0)
        self.assertNotIn('"gold"', repr(seen))
        self.assertNotIn("trace-v3", repr(seen))

    def test_live_v3_replay_uses_same_builder_and_requires_nli(self):
        events = [Event(date(2026, 4, day), day, 1, "user", value, provenance)
                  for day, value, provenance in ((1, "Old", "direct"), (2, "New", "reported"))]
        controller = LogisticController((0,) * 8, (1,) * 8, (0,) * 8, 0)
        embed = lambda _: [[1, 0], [0, 1]]

        def extract(prompt, payload):
            return json.dumps([dict(predicate="job", value=json.loads(payload)["message"], intent="assert")])

        kwargs = dict(entity="p", controller=controller, threshold=0.5, calls=1,
                      verify=lambda *_: "update")
        with self.assertRaisesRegex(ValueError, "complete feature"):
            run_t1(events, extract, feature_builder=V3Features(embed), **kwargs)
        result = run_t1(events, extract, feature_builder=V3Features(
            embed, lambda *_: NLIScores(0.8, 0.1, 0.1)), **kwargs)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.memory.trace[-1].source.kind, "reported")
