from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.check_staged import forbidden
from trace_mem.collect_labels import collect_with_verifier
from trace_mem.data.memora import Event
from trace_mem.data.updateset import generate, read_release, write_release
from trace_mem.llm_tasks import LLMTasks, MockProvider
from trace_mem.memory import Fact, Source, TemporalMemory
from trace_mem.providers import ChatProvider, LimitExceeded, ProviderConfig, ProviderError


def ollama(text, *, tokens=3):
    return {"message": {"content": text}, "done": True, "done_reason": "stop",
            "prompt_eval_count": tokens, "eval_count": 2, "model": "local-fixture"}


def chat(text):
    return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2}, "model": "remote-fixture"}


class ProviderTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "ledger.sqlite"

    def remote(self, backend, **changes):
        config = dict(backend=backend, model="fixture", max_requests=2, api_key="fixture-value",
                      allow_paid=True, max_spend=Decimal("0.05"),
                      input_price=Decimal("1"), output_price=Decimal("2"))
        return ProviderConfig(**(config | changes))

    def test_remote_adapters_account_usage_and_cache_without_leaking_key(self):
        for backend, url, cap_field in (
            ("openai", "https://api.openai.com/v1/chat/completions", "max_completion_tokens"),
            ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "max_tokens"),
        ):
            with self.subTest(backend=backend):
                calls = []

                def transport(endpoint, headers, body, timeout):
                    calls.append(body)
                    self.assertEqual(endpoint, url)
                    self.assertEqual(timeout, 12)
                    self.assertEqual(headers["Authorization"], "Bearer fixture-value")
                    self.assertEqual(body[cap_field], 256)
                    return chat("[]")

                config = self.remote(backend, timeout=12)
                db = self.root / f"{backend}.sqlite"
                event = Event(date(2026, 3, 1), 1, 1, "user", "test")
                provider = ChatProvider(config, db, transport=transport)
                self.assertEqual(LLMTasks(provider).extract(event), ())
                resumed = ChatProvider(config, db, transport=transport)
                self.assertEqual(LLMTasks(resumed).extract(event), ())
                self.assertEqual(len(calls), 1)
                report = resumed.stats()
                self.assertEqual((report["attempts"], report["input_tokens"], report["output_tokens"],
                                  report["cache_hits"], report["cost_usd"]), (1, 3, 2, 1, "0.000007"))
                self.assertGreaterEqual(report["latency_ms"], 0)
                self.assertNotIn(b"fixture-value", db.read_bytes())
                self.assertNotIn("fixture-value", repr(config))

    def test_budget_reserves_unknown_cost_and_retry_stops_at_cap(self):
        def timeout(*args):
            raise ProviderError("timeout", retryable=True)

        config = self.remote("openai", retries=3, max_spend=Decimal("0.005"))
        provider = ChatProvider(config, self.db, transport=timeout, sleep=lambda _: None)
        with self.assertRaisesRegex(LimitExceeded, "Spending"):
            provider.generate("fixture", "system", "data", json.loads)
        self.assertEqual(provider.stats()["statuses"], {"unknown": 1})
        self.assertEqual(provider.stats()["cost_usd"], "0.004608")
        with self.assertRaises(LimitExceeded):
            ChatProvider(config, self.db, transport=timeout).generate("next", "system", "x", json.loads)

    def test_invalid_schema_is_not_cached_and_failures_consume_attempts(self):
        replies = iter((ollama("not-json"), ollama("[]")))
        config = ProviderConfig("ollama", "fixture", 2)
        provider = ChatProvider(config, self.db, transport=lambda *_: next(replies))
        tasks = LLMTasks(provider)
        event = Event(date(2026, 3, 1), 1, 1, "user", "test")
        with self.assertRaisesRegex(ProviderError, "task schema"):
            tasks.extract(event)
        self.assertEqual(tasks.extract(event), ())
        with self.assertRaisesRegex(LimitExceeded, "Request limit"):
            tasks.extract(Event(event.observed_on, 2, 1, "user", "other"))
        self.assertEqual(provider.stats()["statuses"], {"invalid": 1, "ok": 1})

    def test_requires_paid_opt_in_and_rejects_nonlocal_ollama(self):
        with self.assertRaisesRegex(ValueError, "paid approval"):
            self.remote("openai", allow_paid=False)
        with self.assertRaisesRegex(ValueError, "loopback"):
            ProviderConfig("ollama", "fixture", 1, ollama_url="http://example.com")
        with self.assertRaisesRegex(ValueError, "locally"):
            ProviderConfig("ollama", "fixture:cloud", 1)

    def test_reported_token_overrun_prevents_future_calls(self):
        provider = ChatProvider(ProviderConfig("ollama", "fixture", 3, max_input_tokens=200),
                                self.db, transport=lambda *_: ollama("[]", tokens=201))
        with self.assertRaisesRegex(LimitExceeded, "usage exceeded"):
            provider.generate("fixture", "system", "data", json.loads)
        with self.assertRaisesRegex(LimitExceeded, "billing ceiling"):
            provider.generate("fixture", "system", "data", json.loads)

    def test_collection_resumes_from_cache_and_skips_test_and_ineligible_cases(self):
        raw, output = self.root / "raw", self.root / "paired"
        settings = dict(seed=23, sizes=dict(train=7, validation=7, test=7))
        write_release(raw, generate(**settings), **settings)
        calls = []

        def transport(url, headers, body, timeout):
            self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
            self.assertNotIn("Authorization", headers)
            self.assertEqual(body["options"]["seed"], 7)
            payload = json.loads(body["messages"][1]["content"])
            self.assertEqual(set(payload), {"existing", "proposed", "conversation"})
            calls.append(payload)
            return ollama('{"verdict":"update"}')

        def provider(cap):
            return ChatProvider(ProviderConfig("ollama", "fixture", cap, seed=7), self.db,
                                transport=transport)

        with self.assertRaises(LimitExceeded):
            collect_with_verifier(raw, output, LLMTasks(provider(1)), reference="test mock",
                                  origin="synthetic_mock")
        self.assertFalse(output.exists())
        resumed = provider(6)
        collect_with_verifier(raw, output, LLMTasks(resumed), reference="test mock",
                              origin="synthetic_mock")
        self.assertEqual(len(calls), 6)
        self.assertEqual(resumed.stats()["cache_hits"], 1)
        rows, manifest = read_release(output)
        self.assertTrue(all(row["outcomes"] is None for row in rows if row["split"] == "test"))
        self.assertEqual(manifest["distribution"]["train"]["synthetic_mock"], 3)
        self.assertEqual(manifest["distribution"]["validation"]["synthetic_mock"], 3)

    def test_answer_uses_eligible_facts_and_validates_citations(self):
        observed = []
        day = date(2026, 3, 1)
        memory = TemporalMemory()
        memory.accept(Fact("a", "p", "job", "Alder", Source(day, "s1"), day))
        memory.accept(Fact("b", "p", "job", "Deleted", Source(day, "s2"), day))
        memory.delete("b", Source(day, "d"))

        def respond(task, payload):
            observed.append((task, payload))
            return '{"answer":"Alder","citations":["a"]}'

        task = LLMTasks(MockProvider(respond))
        self.assertEqual(task.answer("Where?", memory, entity="p", as_of=day).citations, ("a",))
        self.assertNotIn("Deleted", observed[0][1])
        self.assertIsNone(task.answer("Where?", memory, entity="q", as_of=day).text)
        invalid = LLMTasks(MockProvider(lambda *_: '{"answer":"Deleted","citations":["b"]}'))
        with self.assertRaises(ValueError):
            invalid.answer("Where?", memory, entity="p", as_of=day)

    def test_staged_guard_rejects_private_paths_and_recognizable_secrets(self):
        self.assertTrue(forbidden("data/run.jsonl", b"x"))
        self.assertTrue(forbidden("p/model.sqlite", b"x"))
        self.assertTrue(forbidden("p/.env", b"x"))
        self.assertTrue(forbidden("notes.md", b"sk-" + b"example" * 5))
        self.assertTrue(forbidden(".env.example", b"OPENAI_API_" + b"KEY=value"))
        self.assertFalse(forbidden(".env.example", b"OPENAI_API_KEY\n"))
