from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from trace_mem.baselines import run_matched_baselines, run_t1
from trace_mem.claims import Claim
from trace_mem.controller import LogisticController, features_for
from trace_mem.data.memora import replay
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.semantic import (
    NLIScores, SemanticEvidence, SentenceTransformerProvider, TransformersNLIProvider,
    retrieve_semantic,
)


def day(index):
    return date(2026, 3, index)


class SemanticRetrievalTest(unittest.TestCase):
    def test_rank_filters_entity_time_predicate_and_deletion_before_embedding(self):
        memory = TemporalMemory()
        old = Fact("old", "p", "job", "Alder", Source(day(1), "s1"), day(1))
        updated = Fact("new", "p", "job", "Birch", Source(day(3), "s2"), day(3))
        memory.accept(old)
        memory.accept(updated, replaces="old")
        memory.accept(Fact("visit", "p", "visit", "Cedar", Source(day(3), "s3"), day(3), day(4)))
        memory.accept(Fact("other", "q", "job", "Dogwood", Source(day(3), "s4"), day(3)))
        memory.accept(Fact("future", "p", "job", "Elm", Source(day(3), "s5"), day(6)))
        seen = []

        def embed(texts):
            seen.append(tuple(texts))
            return [[0, 1] if "Cedar" in text else [2, 0] for text in texts]

        query = dict(entity="p", k=1, embed=embed)
        historical, = retrieve_semantic(memory, "workplace", as_of=day(2), **query)
        self.assertEqual(historical.fact.source, old.source)
        current, = retrieve_semantic(memory, "workplace", as_of=day(3), **query)
        self.assertEqual((current.fact.fact_id, current.fact.supersedes, current.similarity),
                         ("new", "old", 1.0))
        self.assertEqual(seen[-1], ("workplace", "p | visit | Cedar", "p | job | Birch"))
        retrieve_semantic(memory, "workplace", as_of=day(3), predicate="job", **query)
        self.assertEqual(seen[-1], ("workplace", "p | job | Birch"))
        memory.delete("old", Source(day(4), "s6"))
        self.assertEqual(retrieve_semantic(memory, "workplace", as_of=day(2), **query), ())
        retrieve_semantic(memory, "workplace", as_of=day(4), **query)
        self.assertEqual(seen[-1], ("workplace", "p | job | Birch"))
        self.assertNotIn("Alder", repr(seen[1:]))
        self.assertNotIn("Dogwood", repr(seen))
        self.assertNotIn("Elm", repr(seen))

    def test_ties_k_and_invalid_embeddings(self):
        memory = TemporalMemory()
        for name in ("z", "a"):
            memory.accept(Fact(name, "p", "job", name, Source(day(1), name), day(1)))
        hits = retrieve_semantic(memory, "job", entity="p", as_of=day(1), k=2,
                                 embed=lambda texts: [[1, 0]] * len(texts))
        self.assertEqual([hit.fact.fact_id for hit in hits], ["a", "z"])
        never = MagicMock(side_effect=AssertionError("Provider should not be called"))
        self.assertEqual(retrieve_semantic(memory, "job", entity="p", as_of=day(1), k=0,
                                           embed=never), ())
        for k in (-1, True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                retrieve_semantic(memory, "job", entity="p", as_of=day(1), k=k, embed=never)
        for bad in ([[1]], [[1], [1, 2], [1]], [[1], [0], [1]], [[1], [float("nan")], [1]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                retrieve_semantic(memory, "job", entity="p", as_of=day(1), k=2,
                                  embed=lambda texts: bad)

    def test_nli_direction_and_model_feature_replacement(self):
        target = Fact("a", "p", "job", "Alder", Source(day(1), "s1"), day(1))
        claim = Claim("job", "Birch", "uncertain", day(2))
        infer = MagicMock(return_value=NLIScores(0.8, 0.1, 0.1))
        semantic = SemanticEvidence(lambda texts: [[3, 0], [-2, 0]], infer)
        kwargs = dict(entity="p", source=Source(day(2), "s2"), budget_remaining_fraction=1)
        values = features_for(claim, target, semantic=semantic, **kwargs)
        self.assertEqual(values[:2], (-1.0, 0.8))
        self.assertEqual(values[2:], features_for(claim, target, **kwargs)[2:])
        infer.assert_called_once_with("p | job | Alder", "p | job | Birch")
        self.assertEqual(infer.return_value.label, "contradiction")
        self.assertEqual(NLIScores(0.1, 0.8, 0.1).label, "entailment")
        self.assertEqual(NLIScores(0.5, 0.0, 0.5).label, "neutral")
        with self.assertRaises(ValueError):
            NLIScores(0.8, 0.5, 0.1)


class LocalProviderTest(unittest.TestCase):
    def test_embedding_loader_pins_revision_and_encodes_locally(self):
        loader = MagicMock()
        loader.return_value.encode.return_value.tolist.return_value = [[1.0]]
        with patch.dict("sys.modules", {"sentence_transformers": SimpleNamespace(SentenceTransformer=loader)}):
            provider = SentenceTransformerProvider("embedding", revision="pinned")
            self.assertEqual(provider(("work",)), [[1.0]])
        self.assertEqual(loader.call_args.kwargs["revision"], "pinned")
        self.assertTrue(loader.call_args.kwargs["local_files_only"])
        self.assertFalse(loader.call_args.kwargs["token"])
        loader.return_value.encode.assert_called_once_with(
            ["work"], convert_to_numpy=True, show_progress_bar=False)

    def test_nli_uses_checkpoint_labels_and_inference_mode(self):
        torch = MagicMock()
        tokenizer_loader = MagicMock()
        model_loader = MagicMock()
        model = model_loader.from_pretrained.return_value.to.return_value.eval.return_value
        model.config.id2label = {0: "ENTAILMENT", 1: "neutral", 2: "contradiction"}
        model.return_value.logits[0].float.return_value.softmax.return_value.tolist.return_value = [
            0.7, 0.1, 0.2,
        ]
        modules = {"torch": torch, "transformers": SimpleNamespace(
            AutoTokenizer=tokenizer_loader, AutoModelForSequenceClassification=model_loader)}
        with patch.dict("sys.modules", modules):
            provider = TransformersNLIProvider("nli", revision="pinned", max_length=64)
            self.assertEqual(provider("old", "new"), NLIScores(0.2, 0.7, 0.1))
            model.config.id2label = {0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"}
            with self.assertRaisesRegex(ValueError, "explicitly"):
                TransformersNLIProvider("nli")
        tokenizer_loader.from_pretrained.return_value.assert_called_once_with(
            "old", "new", return_tensors="pt", truncation=True, max_length=64)
        torch.inference_mode.assert_called_once()
        self.assertTrue(model_loader.from_pretrained.call_args.kwargs["use_safetensors"])


class SemanticReplayTest(unittest.TestCase):
    def test_semantic_feature_selects_conflict_without_exposing_rubric(self):
        observed_inputs = []

        def embed(texts):
            observed_inputs.extend(texts)
            return [[1.0, 0.0] for _ in texts]

        def infer(premise, hypothesis):
            observed_inputs.extend((premise, hypothesis))
            return (NLIScores(0.9, 0.05, 0.05) if "Cedar" in hypothesis
                    else NLIScores(0.1, 0.8, 0.1))

        def extract(prompt, payload):
            observed_inputs.append(payload)
            value = json.loads(payload)["message"]
            intent = "assert" if value == "Alder" else "uncertain"
            return json.dumps([dict(predicate="job", value=value, intent=intent)])

        semantic = SemanticEvidence(embed, infer)
        controller = LogisticController((0,) * 8, (1,) * 8, (0, 4, 0, 0, 0, 0, 0, 0), -2)
        verify = MagicMock(return_value="update")
        with TemporaryDirectory() as temporary:
            history = Path(temporary) / "p"
            directory = history / "conversations"
            directory.mkdir(parents=True)
            for i, value in enumerate(("Alder", "Birch", "Cedar"), 1):
                record = dict(session_id=i, date=day(i).isoformat(), persona="p",
                              operation_details="RUBRIC_SENTINEL",
                              conversation=[dict(turn=1, speaker="user_agent", message=value)])
                (directory / f"session_{i:04}.json").write_text(json.dumps(record))
            rubric = history / "evaluation_questions_p.json"
            rubric.write_text("RUBRIC_SENTINEL")
            kwargs = dict(entity="p", controller=controller, semantic=semantic, calls=1, verify=verify)
            paired = run_matched_baselines(replay(history), extract, seed=2, **kwargs)
            self.assertEqual({key: run.attempts for key, run in paired.items()},
                             {"B4": 1, "B5": 1, "T1": 1})
            self.assertEqual(paired["T1"].selected_ids, ("3/1/0",))
            verify.reset_mock()
            online = run_t1(replay(history), extract, threshold=0.5, **kwargs)
            self.assertEqual(online.selected_ids, ("3/1/0",))
            self.assertEqual(verify.call_count, 1)
            hit, = retrieve_semantic(online.memory, "Where do I work?", entity="p",
                                     as_of=day(3), k=1, embed=embed)
            self.assertEqual((hit.fact.value, hit.fact.source.reference), ("Cedar", "3/1"))
        self.assertNotIn("RUBRIC_SENTINEL", repr(observed_inputs))
