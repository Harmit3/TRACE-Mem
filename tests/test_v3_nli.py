from contextlib import closing
from datetime import date
import json
import sqlite3
import unittest

from scripts.validate_v3_nli import CASES, ExtractionTape, feature_audit, reconstruct
from trace_mem.claims import EXTRACTION_PROMPT, Claim
from trace_mem.data.updateset_v3 import cases
from trace_mem.features_v3 import nli_pair
from trace_mem.llm_tasks import LLMTasks, VERIFY_PROMPT
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider


class V3NliTest(unittest.TestCase):
    def test_renderer_preserves_uncertainty_and_uses_no_opaque_identifiers(self):
        day = date(2026, 4, 24)
        claim = Claim("residence", "Pine House", "uncertain", day)
        fact = Fact("private-id", "split-id", "residence", "Oak House",
                    Source(day, "private-source"), day)
        premise, hypothesis = nli_pair(claim, fact)
        self.assertEqual(premise, "On 2026-04-24, the person lives at Oak House.")
        self.assertEqual(hypothesis, "On 2026-04-24, the person might live at Pine House.")

    def test_reconstruction_uses_extraction_key_and_rejects_verifier_queries(self):
        case = cases()[0]
        payload = json.dumps({"observed_on": case["observed_on"],
                              "message": case["transcript"][-1]["text"]})
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE response(key TEXT PRIMARY KEY, text TEXT)")
            tape = ExtractionTape(db)
            url, _, request = ChatProvider.request_for(tape.settings, "extract-v1", EXTRACTION_PROMPT, payload)
            cache_key = ChatProvider.cache_key("extract-v1", url, request)
            db.execute("INSERT INTO response VALUES (?,?)", (cache_key, json.dumps([
                {"predicate": "residence", "value": "Birch Court", "intent": "assert"},
            ])))
            claim, fact, source = reconstruct(case, LLMTasks(tape))
            self.assertEqual((claim.value, fact.value, source.kind),
                             ("Birch Court", "Wren Apartments", "dated_record"))
            with self.assertRaisesRegex(ValueError, "Only frozen extraction"):
                tape.generate("verify-v1", VERIFY_PROMPT, payload, lambda *_: None)

    def test_label_balance_and_feature_audit(self):
        self.assertEqual(len(CASES), 24)
        for label in ("contradiction", "entailment", "neutral"):
            self.assertEqual(sum(case[0] == label for case in CASES), 8)
        report = feature_audit([{"features": [0.2, 0.8, 1, 1, 20, 0.5, 1, 1]},
                                {"features": [0.5, 0.1, 1, 1, 20, 0.5, 1, 1]}])
        self.assertEqual(report["unique_vectors"], 2)
        self.assertEqual(report["features"]["entity_match"]["variance"], 0)
        self.assertAlmostEqual(report["pearson_nonconstant"]["semantic_similarity:contradiction_score"], -1)
