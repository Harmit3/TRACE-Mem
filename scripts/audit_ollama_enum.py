"""Probe schema enum ordering on already-used verifier diagnostic cases."""

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path

from scripts.validate_ollama_verifier import CASES, MODEL, runtime
from trace_mem.claims import Claim
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, ProviderConfig


class DiagnosticProvider(ChatProvider):
    def __init__(self, *args, reverse=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reverse = reverse
        self.kinds = []

    def _request(self, task, system, payload):
        url, headers, body = super()._request(task, system, payload)
        if self.reverse and task == "verify-evidence-v2":
            body = deepcopy(body)
            body["format"]["properties"]["kind"]["enum"].reverse()
        return url, headers, body

    def generate(self, task, system, payload, validate):
        text = super().generate(task, system, payload, validate)
        if task == "verify-evidence-v2":
            self.kinds.append(json.loads(text)["kind"])
        return text


def main():
    runtime()
    output = Path("results/ollama-enum-diagnostic")
    output.mkdir(parents=True, exist_ok=False)
    ids = {"u1", "n2", "n3", "n4", "n6", "n7"}
    cases = [row for row in CASES if row[0] in ids]
    observed = date(2026, 2, 15)
    old_day = observed - timedelta(days=20)
    for reverse in (False, True):
        provider = DiagnosticProvider(
            ProviderConfig("ollama", MODEL, 2 * len(cases), seed=23, context_tokens=4096),
            output / f"{int(reverse)}.sqlite", reverse=reverse,
        )
        tasks = LLMTasks(provider, verification_mode="evidence-v2")
        verdicts = []
        for case_id, predicate, old, new, intent, message, _ in cases:
            fact = Fact("old", "fictional", predicate, old, Source(old_day, "source/1"), old_day)
            verdict = tasks.verify(Claim(predicate, new, intent, observed), fact,
                                   conversation=(message,))
            verdicts.append({"case": case_id, "kind": provider.kinds[-1], "verdict": verdict})
        print(json.dumps({"reversed_kind_enum": reverse, "cases": verdicts, "usage": provider.stats()}))


if __name__ == "__main__":
    main()
