import json
import unittest

from scripts.collect_updateset_v3_final import audit, collect, dataset_files
from trace_mem.data.updateset_v3 import cases as pilot_cases
from trace_mem.data.updateset_v3_final import SIZES, generate
from trace_mem.features_v3 import V3Features
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.providers import ProviderError
from trace_mem.semantic import NLIScores


class FinalUpdateSetTest(unittest.TestCase):
    def test_disjoint_families_gold_and_blind_packets(self):
        records = generate()
        self.assertEqual(records, generate())
        self.assertEqual(len(records), 200)
        self.assertEqual(sum(len(item["turns"]) for item in records), 600)
        family_sets = [{item["family"] for item in records if item["split"] == split}
                       for split in SIZES]
        self.assertEqual(list(map(len, family_sets)), [20, 10, 10])
        self.assertEqual(len(set.union(*family_sets)), 40)
        pilot = {t["text"].casefold() for item in pilot_cases() for t in item["transcript"]}
        seen = {}
        for item in records:
            for turn in item["turns"]:
                text = turn["message"].casefold()
                self.assertNotIn(text, pilot)
                self.assertEqual(seen.setdefault(text, item["split"]), item["split"])
                self.assertNotIn("trace-v3", text)
        reviews = [json.loads(line) for line in dataset_files()["pending-review.jsonl"].splitlines()]
        self.assertEqual(len(reviews), 65)
        self.assertTrue(all(len(item["timeline"]) == item["turn"] for item in reviews))
        self.assertTrue(all("gold" not in turn for item in reviews for turn in item["timeline"]))

    def test_causal_budget_and_b2_prefix_are_preserved(self):
        case = generate()[0] | {"cap": 2}
        seen = []
        value = "Replacement Clinic"

        def reply(task, payload):
            parsed = json.loads(payload)
            seen.append((task, parsed))
            if task == "extract-v1":
                return json.dumps([{"predicate": "job", "value": value, "intent": "assert"}])
            return '{"verdict":"update"}'

        result = collect(case, LLMTasks(MockProvider(reply), verification_mode="direct-v2"),
                         V3Features(lambda _: [[1, 0], [0, 1]], lambda *_: NLIScores(0.8, 0.1, 0.1)))
        first, second, third = [step["candidates"][0] for step in result["steps"]]
        self.assertEqual(result["attempts"], 2)
        self.assertEqual([first["features"][-1], second["features"][-1]], [1.0, 0.5])
        self.assertEqual(third["status"], "budget_exhausted")
        self.assertNotIn("features", third)
        self.assertEqual(first["unverified"], second["unverified"])
        self.assertEqual(first["target"]["value"], second["target"]["value"])
        self.assertNotIn("trace-v3", repr(seen))
        self.assertNotIn('"gold"', repr(seen))
        verified = [payload for task, payload in seen if task.startswith("verify-")]
        self.assertEqual([len(payload["conversation"]) for payload in verified], [3, 5])
        self.assertEqual(audit([result])["train"]["unique_vectors"], 2)

    def test_extraction_and_verification_failures_are_kept(self):
        case = generate()[0] | {"cap": 1}

        def reply(task, payload):
            if task != "extract-v1" or "2026-05-12" in payload:
                raise ProviderError("fixture failure")
            return '[{"predicate":"job","value":"New Place","intent":"assert"}]'

        result = collect(case, LLMTasks(MockProvider(reply), verification_mode="direct-v2"),
                         V3Features(lambda _: [[1], [1]], lambda *_: NLIScores(0.8, 0.1, 0.1)))
        self.assertEqual(result["steps"][0]["status"], "extraction_failure")
        self.assertEqual(result["steps"][1]["candidates"][0]["status"], "verification_failure")
        self.assertIsNone(result["steps"][1]["candidates"][0]["helpful"])
        self.assertEqual(result["steps"][2]["candidates"][0]["status"], "budget_exhausted")
