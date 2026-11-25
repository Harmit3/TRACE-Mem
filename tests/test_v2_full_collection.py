import json
import unittest

from scripts.audit_v2_full_release import _verify_candidate
from scripts.collect_updateset_v2 import _encode, audit, collect_case
from trace_mem.controller import FEATURE_NAMES
from trace_mem.data.updateset_v2 import generate
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.providers import ProviderError


class FullCandidateCollectionTest(unittest.TestCase):
    def setUp(self):
        cases, _ = generate()
        self.case = next(row for row in cases if row["family"] == "train/implicit")

    def run_case(self, *, case=None, intent="assert", verdict="update", predicate="job",
                 pilot=False, fail=None, multi=False):
        case = case or self.case
        new = self.case["gold"]["current_value"]
        prompts = []

        def respond(task, payload):
            prompts.append((task, json.loads(payload)))
            if task == fail:
                raise ProviderError("fixture failure")
            if task == "extract-v1":
                claims = [{"predicate": predicate, "value": new, "intent": intent}]
                if multi:
                    claims.append({"predicate": predicate, "value": "Third Lab", "intent": "assert"})
                return json.dumps(claims)
            return json.dumps({"verdict": verdict})

        result = collect_case(case, LLMTasks(MockProvider(respond), verification_mode="direct-v2"),
                              pilot=pilot)
        return result, prompts

    def test_independent_candidate_prefixes_and_preverification_features(self):
        result, prompts = self.run_case(multi=True)
        first, second = result["candidates"]
        self.assertEqual(len(first["features"]), len(FEATURE_NAMES))
        self.assertTrue(first["helpful"])
        self.assertFalse(second["helpful"])
        self.assertEqual(second["prefix_trace"][-1]["operation"], "defer")
        self.assertEqual(first["unverified"], second["unverified"])
        self.assertEqual(len(prompts), 3)
        self.assertEqual(set(prompts[0][1]), {"message", "observed_on"})
        for _, payload in prompts[1:]:
            self.assertEqual(set(payload), {"existing", "proposed", "conversation"})
        pending, _ = self.run_case(case={**self.case, "gold": None})
        self.assertEqual(pending["candidates"][0]["features"], first["features"])
        self.assertIsNone(pending["candidates"][0]["helpful"])

    def test_negative_outcomes_ineligibility_and_failures_are_retained(self):
        harmful, _ = self.run_case(intent="correct", verdict="insufficient_evidence")
        self.assertTrue(harmful["candidates"][0]["harmful"])
        self.assertFalse(harmful["candidates"][0]["helpful"])
        ineligible, prompts = self.run_case(predicate="visit")
        self.assertEqual(ineligible["candidates"][0]["status"], "ineligible")
        self.assertEqual(len(prompts), 1)
        bad_extract, _ = self.run_case(fail="extract-v1")
        self.assertEqual(bad_extract["status"], "extraction_failure")
        bad_verify, _ = self.run_case(fail="verify-direct-v2")
        self.assertEqual(bad_verify["candidates"][0]["status"], "verification_failure")
        self.assertIsNone(bad_verify["candidates"][0]["helpful"])

    def test_audit_keeps_pilot_partition_separate(self):
        pilot, _ = self.run_case(pilot=True)
        other, _ = self.run_case(intent="correct")
        report = audit([pilot, other])
        self.assertEqual(report["train/pilot"]["positive"], 1)
        self.assertEqual(report["train/nonpilot"]["negative"], 1)
        self.assertEqual(report["train/nonpilot"]["missing_feature_rows"], 0)
        self.assertEqual(report["train/pilot"]["features"]["budget_remaining_fraction"]["min"], 1)

    def test_release_audit_recomputes_features_and_labels(self):
        result, _ = self.run_case()
        item = json.loads(_encode(result))["candidates"][0]
        _verify_candidate(item, self.case)
        with self.assertRaisesRegex(ValueError, "Stored label"):
            _verify_candidate({**item, "helpful": False}, self.case)
        with self.assertRaisesRegex(ValueError, "Candidate features"):
            _verify_candidate({**item, "features": [0] * len(FEATURE_NAMES)}, self.case)
