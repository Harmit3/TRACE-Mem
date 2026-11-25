"""Collect real verifier decisions for a validated TRACE-UpdateSet release."""

import argparse
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path

from trace_mem.llm_tasks import LLMTasks
from trace_mem.providers import ChatProvider, ProviderConfig, ProviderError
from trace_mem.training import DecisionInput, collect_pairs, eligible_case


def _update_decision(case: DecisionInput, confirmed: bool) -> dict:
    if not eligible_case(case):
        raise ValueError("Expected a replay-eligible verifier case")
    return {"operation": "supersede", "target_id": case.old.fact_id} if confirmed else {
        "operation": "defer", "target_id": None,
    }


def collect_with_verifier(dataset: Path, output: Path, tasks: LLMTasks, *, reference: str,
                          origin: str = "recorded_verifier") -> dict:
    """Compare B2 with the same transition rule gated by a verifier verdict."""
    def unverified(case):
        return _update_decision(case, case.new.intent == "correct")

    def verified(case):
        verdict = tasks.verify(case.new, case.old, conversation=case.conversation)
        return _update_decision(case, verdict == "update")

    return collect_pairs(dataset, output, unverified=unverified, verified=verified,
                         reference=reference, origin=origin, eligible_only=True)


def _ignored(path: Path) -> Path:
    path = path.resolve()
    if not any(path.is_relative_to(Path(root).resolve()) and path != Path(root).resolve()
               for root in ("data", "results")):
        raise ValueError("Keep collection output and provider state under data/ or results/")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backend", choices=("ollama", "openai", "openrouter"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--max-spend", type=Decimal, default=Decimal(0))
    parser.add_argument("--input-price", type=Decimal, default=Decimal(0))
    parser.add_argument("--output-price", type=Decimal, default=Decimal(0))
    args = parser.parse_args()
    try:
        config = ProviderConfig(
            args.backend, args.model, args.max_requests, timeout=args.timeout,
            retries=args.retries, max_input_tokens=args.max_input_tokens,
            max_output_tokens=args.max_output_tokens, seed=args.seed,
            ollama_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
            api_key=os.environ.get(f"{args.backend.upper()}_API_KEY"),
            allow_paid=args.allow_paid, max_spend=args.max_spend,
            input_price=args.input_price, output_price=args.output_price,
        )
        provider = ChatProvider(config, _ignored(args.database))
        try:
            release = collect_with_verifier(args.dataset, _ignored(args.output), LLMTasks(provider),
                                            reference=args.reference)
        finally:
            print(json.dumps({"provider": args.backend, "model": args.model,
                              "seed": args.seed, "usage": provider.stats()}, sort_keys=True))
        print(json.dumps({"distribution": release["distribution"],
                          "files": release["files"]}, sort_keys=True))
    except (OSError, ProviderError, TypeError, ValueError, InvalidOperation) as error:
        if isinstance(error, ProviderError):
            parser.error(str(error))
        parser.error(f"Collection stopped ({type(error).__name__}). Check settings and input paths.")


if __name__ == "__main__":
    main()
