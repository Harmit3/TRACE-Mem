from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.updateset_v2_pilot import paired_case, summarize
from trace_mem.data.updateset_v2 import generate, read_release, write_release
from trace_mem.llm_tasks import LLMTasks, MockProvider


class UpdateSetV2Test(unittest.TestCase):
    def test_release_is_independent_and_stratified(self):
        cases, manifest = generate()
        self.assertEqual((cases, manifest), generate())
        self.assertEqual(Counter(case["split"] for case in cases), {"train": 350, "validation": 150})
        self.assertEqual(len({case["persona"] for case in cases}), 500)
        self.assertEqual(len({case["history"] for case in cases}), 500)
        selected = set(manifest["pilot_ids"])
        self.assertEqual(len(selected), 44)
        self.assertEqual(set(Counter(case["family"] for case in cases
                                     if case["case_id"] in selected).values()), {2})
        self.assertTrue(all("new_claim" not in case for case in cases))
        self.assertFalse(manifest["benchmark_inputs"])
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "v2"
            saved = write_release(root)
            self.assertEqual(read_release(root), (cases, saved))
            pending = [json.loads(line) for line in (root / "pending-review.jsonl").read_bytes().splitlines()]
            self.assertEqual(len(pending), 45)
            self.assertTrue(all("gold" not in case for case in pending))
            (root / "cases.jsonl").write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "frozen"):
                read_release(root)

    def test_pair_uses_real_b2_operations_and_gold_blind_model_inputs(self):
        cases, _ = generate()
        implicit = next(case for case in cases if case["family"] == "train/implicit")
        new = implicit["gold"]["current_value"]
        old = implicit["old_fact"]["value"]

        def run(case, intent, verdict):
            prompts = []

            def response(task, payload):
                prompts.append((task, json.loads(payload)))
                if task == "extract-v1":
                    return json.dumps([{"predicate": "job", "value": new, "intent": intent}])
                return json.dumps({"verdict": verdict})

            result = paired_case(case, LLMTasks(MockProvider(response), verification_mode="direct-v2"))
            self.assertEqual([task for task, _ in prompts], ["extract-v1", "verify-direct-v2"])
            self.assertEqual(set(prompts[0][1]), {"observed_on", "message"})
            self.assertEqual(set(prompts[1][1]), {"existing", "proposed", "conversation"})
            return result

        changed = run(implicit, "assert", "update")
        self.assertEqual(changed["unverified_operations"], ["defer"])
        self.assertEqual(changed["verified_operations"], ["supersede"])
        self.assertIs(changed["verification_helpful"], True)
        unchanged = run(implicit, "correct", "update")
        self.assertEqual(unchanged["unverified_operations"], ["supersede"])
        self.assertTrue(unchanged["unchanged_trace"])
        self.assertIs(unchanged["verification_helpful"], False)
        preserve = {**implicit, "gold": {**implicit["gold"], "current_value": old}}
        harmful = run(preserve, "assert", "update")
        self.assertTrue(harmful["harmful"])
        self.assertEqual(summarize([changed, unchanged, harmful])["train"]["negative"], 2)
        pending = run({**implicit, "gold": None}, "assert", "update")
        self.assertIsNone(pending["verification_helpful"])
