"""Run a small real TRACE-Mem smoke check on an already-installed local model."""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import time

from trace_mem.claims import Claim
from trace_mem.data.memora import Event
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(Path("results").resolve()) or output == Path("results").resolve():
        parser.error("Use a fresh directory below results/")
    output.mkdir(parents=True, exist_ok=False)
    observed = date(2026, 1, 12)
    fact = Fact("old", "fictional", "job", "Alder Lab",
                Source(observed - timedelta(days=10), "session/1"),
                observed - timedelta(days=10))
    cases = (
        ("correction", "I now work at Birch Lab instead of Alder Lab.",
         Claim("job", "Birch Lab", "correct", observed)),
        ("uncertain", "I might take a job at Cedar Lab, but nothing has changed.",
         Claim("job", "Cedar Lab", "uncertain", observed)),
    )
    failures = 0
    for repetition in range(1, 3):
        provider = ChatProvider(ProviderConfig("ollama", args.model, 4, timeout=120, seed=23),
                                output / f"pass-{repetition}.sqlite")
        tasks = LLMTasks(provider)
        for index, (name, message, claim) in enumerate(cases, 1):
            operations = {
                "extract": lambda: [(c.predicate, c.value, c.intent) for c in tasks.extract(
                    Event(observed, index, 1, "user", message))],
                "verify": lambda: tasks.verify(claim, fact, conversation=(message,)),
            }
            for task, invoke in operations.items():
                started = time.perf_counter()
                result = {"pass": repetition, "case": name, "task": task}
                try:
                    result.update(valid=True, result=invoke())
                except ProviderError as error:
                    failures += 1
                    result.update(valid=False, result=None, error=str(error))
                result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
                print(json.dumps(result), flush=True)
        print(json.dumps({"pass": repetition, "usage": provider.stats()}), flush=True)
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
