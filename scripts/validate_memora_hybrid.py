"""Frozen fictional comparison of three extractors plus independent local Llama."""

from argparse import ArgumentParser
from collections import Counter
from datetime import date
import json
from pathlib import Path
import time

from scripts.compare_local_verifiers import QWEN, SETTINGS, local_json
from scripts.run_memora import ARTIFACTS, ROOT, sha, write
from scripts.updateset_v2_pilot import QWEN_DIGEST
from scripts.validate_memora_quality import key, metrics
from scripts.validate_ollama_verifier import DIGEST as LLAMA_DIGEST, MODEL as LLAMA
from trace_mem.context_extraction import extract_event
from trace_mem.data.memora import Event
from trace_mem.features_v3 import CachedMiniLM, V3Features, pinned_nli
from trace_mem.hybrid_extraction import EvidenceMemory, normalize
from trace_mem.llm_tasks import LLMTasks
from trace_mem.memory import Fact, Source
from trace_mem.providers import ChatProvider, ProviderError, ProviderConfig
from trace_mem.training import load_model


PROTOCOL = ROOT / "docs/memora_step21_validation.json"
OBSERVED = date(2025, 3, 4)
BASELINE_DAY = date(2024, 1, 1)


def evaluated(extractor, cases, aliases, features, model, embed, provider):
    exact_rows, semantic_rows, vectors = [], [], []
    failures = Counter()
    per_case = {}
    summary = Counter()
    for ident, recent, prior, message, expected in cases:
        event = Event(OBSERVED, 1, len(recent) + 1, "user", message)
        source = Source(OBSERVED, "focal", "direct")
        target = Fact("prior", "fictional", prior[0], prior[1],
                      Source(BASELINE_DAY, "prior", "direct"), BASELINE_DAY) if prior else None
        memory = EvidenceMemory("fictional")
        if target:
            memory.memory.accept(target)
            memory.targets[target.fact_id] = target
        try:
            claims, grounded = extractor(event, tuple(recent), (target,) if target else ())
        except ProviderError:
            failures["invalid_or_failed_response"] += 1
            claims, grounded = (), ()
        expected_set = {key(*expected)} if expected else set()
        predictions = {key(c.predicate, c.value, c.intent) for c in claims}
        exact_rows.append((predictions, expected_set))

        def equivalent(rows):
            return {(aliases.get(p, p), value, intent) for p, value, intent in rows}

        semantic_rows.append((equivalent(predictions), equivalent(expected_set)))
        per_case[ident] = sorted(predictions)
        source_text = "\n".join((*recent, message)).casefold()
        allowed_value = lambda c: (c.value.casefold() in source_text or (
            c.intent == "delete" and target and c.value.casefold() == target.value.casefold()))
        summary["source_value_matches"] += sum(bool(allowed_value(c)) for c in claims)
        summary["emitted"] += len(claims)
        summary["cited_claims"] += len(grounded)
        if expected:
            summary["source_grounded_semantic_matches"] += sum(
                bool(allowed_value(c)) and
                (aliases.get(c.predicate, c.predicate), key(c.predicate, c.value, c.intent)[1], c.intent)
                in equivalent(expected_set) for c in claims)
        for i, item in enumerate(grounded):
            memory.apply(item, source, f"normalized/{i}")
            if item.claim.intent == "delete":
                summary["applied_deletions"] += not memory.evidence("old information", BASELINE_DAY, 4, embed)
        summary["quote_bytes"] += sum(len(quote.encode()) for _, quote in memory.evidence(
            message, OBSERVED, 4, embed))
        for c in claims:
            if (target and c.intent != "delete" and c.predicate == target.predicate
                    and c.value.casefold() != target.value.casefold() and c.effective_on > target.valid_from):
                vector = features(c, target, entity="fictional", source=source,
                                  budget_remaining_fraction=1)
                vectors.append(vector)
    exact, semantic = metrics(exact_rows), metrics(semantic_rows)
    scores = [model.controller.score(vector) for vector in vectors]
    if not scores:
        features_summary = {"candidates": 0}
    else:
        features_summary = {"candidates": len(scores), "average_features": [sum(x) / len(x) for x in zip(*vectors)],
                            "mean_frozen_score": sum(scores) / len(scores),
                            "above_frozen_threshold": sum(score >= model.threshold for score in scores)}
    return {"exact": exact, "alias_semantic": semantic, "source": dict(summary),
            "grounding_precision": summary["source_grounded_semantic_matches"] / summary["emitted"]
                                    if summary["emitted"] else 0.0,
            "unsupported_values": summary["emitted"] - summary["source_value_matches"],
            "feature_shift": features_summary, "failures": dict(failures),
            "provider": provider.stats(), "by_case": per_case}


def run(nli, output):
    import torch

    if (ROOT / "results").resolve() not in output.resolve().parents:
        raise ValueError("Use an ignored results directory")
    config = json.loads(PROTOCOL.read_bytes())
    tags = {item["name"]: item["digest"] for item in local_json("/api/tags")["models"]}
    if tags.get(QWEN) != QWEN_DIGEST or tags.get(LLAMA) != LLAMA_DIGEST:
        raise ValueError("Pinned Qwen and Llama are required")
    fit = json.loads((ARTIFACTS / "fit-freeze.json").read_bytes())
    if sha(ARTIFACTS / "full.json") != fit["artifacts_sha256"]["full.json"]:
        raise ValueError("Frozen T1 artifact was modified")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    torch.set_num_threads(4)
    embed = CachedMiniLM()
    features = V3Features(embed, pinned_nli(nli))
    model = load_model(ARTIFACTS / "full.json")
    methods = {}
    for name, tag in (("original", QWEN), ("contextual", QWEN),
                      ("hybrid", QWEN), ("hybrid_llama", LLAMA)):
        provider = ChatProvider(ProviderConfig("ollama", tag, 100, **SETTINGS), output / f"{name}.sqlite")
        tasks = LLMTasks(provider)

        def extractor(event, recent, targets):
            if name in {"original", "contextual"}:
                return extract_event(tasks, event, recent, improved=name == "contextual"), ()
            normalized = normalize(provider, event, recent, targets)
            return tuple(item.claim for item in normalized), normalized

        methods[name] = evaluated(extractor, config["cases"], config["aliases"],
                                  features, model, embed, provider)
    hybrid, original, contextual = (methods[x] for x in ("hybrid", "original", "contextual"))
    g = config["gate"]
    passes = (hybrid["alias_semantic"]["precision"] >= g["semantic_precision"]
              and hybrid["alias_semantic"]["recall"] >= g["semantic_recall"]
              and hybrid["exact"]["f1"] - max(original["exact"]["f1"], contextual["exact"]["f1"]) >= g["exact_f1_gain"]
              and hybrid["exact"]["matched_deletions"] >= g["deletions"]
              and hybrid["grounding_precision"] >= g["grounding_precision"])
    report = {"protocol_sha256": sha(PROTOCOL), "settings": SETTINGS, "qwen": QWEN_DIGEST,
              "llama": LLAMA_DIGEST, "t1_sha256": sha(ARTIFACTS / "full.json"),
              "hybrid_passes": passes, "methods": methods, "wall_seconds": time.perf_counter() - started}
    write(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--nli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.nli, args.output)
    for method in report["methods"].values():
        del method["by_case"]
    print(json.dumps(report, sort_keys=True))
