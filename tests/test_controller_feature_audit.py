from datetime import date
import unittest

from scripts.audit_controller_features import statistics_for
from trace_mem.claims import Claim
from trace_mem.controller import semantic_pair
from trace_mem.memory import Fact, Source


class ControllerFeatureAuditTest(unittest.TestCase):
    def test_correlation_omits_constant_columns_and_counts_vector_classes(self):
        report = statistics_for([
            ("family-a", [0.2, 0.75, 1, 1, 21, 1, 0.5, 1], True),
            ("family-a", [0.2, 0.75, 1, 1, 21, 1, 0.5, 1], False),
            ("family-b", [0.5, 0.5, 1, 1, 21, 1, 1, 1], None),
        ])
        self.assertEqual(report["unique_vectors"], 2)
        self.assertEqual(report["positive_vectors"], 1)
        self.assertEqual(report["negative_vectors"], 1)
        self.assertEqual(report["families"], {"family-a": 2, "family-b": 1})
        self.assertEqual(report["variance"]["entity_match"], 0)
        self.assertAlmostEqual(report["pearson_nonconstant"]["contradiction_score:uncertainty"], -1)
        self.assertFalse(any("entity_match" in key for key in report["pearson_nonconstant"]))

    def test_semantic_rendering_hides_ids_but_preserves_entity_relation(self):
        today = date(2026, 1, 1)
        fact = Fact("trace/validation/12/fact", "trace/validation/12/persona", "job", "Old Lab",
                    Source(today, "trace/validation/12/source"), today)
        claim = Claim("job", "New Lab", "assert", today)
        self.assertEqual(semantic_pair(claim, fact, fact.entity),
                         ("subject A | job | Old Lab", "subject A | job | New Lab"))
        self.assertEqual(semantic_pair(claim, fact, "trace/train/44/persona")[1],
                         "subject B | job | New Lab")
