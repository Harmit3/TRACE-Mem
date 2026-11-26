"""Build the reviewed numeric projection from local fictional checkpoints."""

import gzip
import json
from pathlib import Path

from reproducibility.reproduce import FIELDS, aggregate, collect, digest, read_json


ROOT = Path("reproducibility")
FILES = ("README.md", "reviewer-guide.md", "independent-review-checklist.md", "manifest.json",
         "reproduce.py", "figures.py", "requirements.txt", "data/history.jsonl.gz",
         "data/family.jsonl.gz", "data/frozen-reference.json")


def write(path, data):
    (ROOT / path).write_bytes((json.dumps(data, indent=2) + "\n").encode())


def records(path, items):
    body = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in items)
    (ROOT / path).write_bytes(gzip.compress(body.encode(), mtime=0))


def export():
    f30, f31 = (read_json(f"docs/step{s}_freeze.json") for s in (30, 31))
    reports = {s: read_json(f"results/step{s}/report.json") for s in (30, 31)}
    published = {s: read_json(f"docs/step{s}_artifacts/aggregate.json") for s in (30, 31)}
    labels = [
        ("T2", "B3"), ("T2", "H-paced"), ("T2", "T1"), ("T2", "T2-no-NLI"),
        ("T1", "T1-no-NLI"),
    ]
    config = {
        "budgets": f30["budget_percents"], "horizons": f31["horizon_percent"],
        "primary_seed": f31["seed"], "b4_seeds": f30["seeds"],
        "bootstrap_seed": f30["bootstrap"]["seed"], "bootstrap_draws": f30["bootstrap"]["replicates"],
        "step30_methods": sorted({r["method"] for r in published[30]["rows"]}),
        "step31_fixed": f31["baselines"] + f31["adaptive"],
        "step31_baselines": f31["baselines"], "step31_paced": f31["adaptive"],
        "contrasts30": {f"{a} minus {b}": {a: 1, b: -1} for a, b in (
            ("T2", "H-paced"), ("T1", "T1-no-NLI"), ("T2", "B4"), ("T1", "B5"))},
        "contrasts31": {f"{a} minus {b}": {a: 1, b: -1} for a, b in labels} | {
            "Score by pacing interaction": {"T2": 1, "T2-no-NLI": -1, "T1": -1, "T1-no-NLI": 1}},
    }
    identities, family_names = {}, {}
    rows = []
    for step, report in reports.items():
        folder = Path(f"results/step{step}/histories")
        checkpoints = [read_json(p) for p in sorted(folder.glob("*.json"))]
        if checkpoints != report["histories"]:
            raise ValueError(f"Step {step} checkpoint/report mismatch")
        for h in checkpoints:
            src, family = h["history"], h["family"]
            if step == 30:
                identities[src] = (f"H{len(identities)+1:03}", family)
                family_names.setdefault(family, f"F{len(family_names)+1:02}")
            key, old_family = identities[src]
            if old_family != family:
                raise ValueError("Source history family changed")
            for r in h["rows"]:
                rows.append({"step": step, "mode": r["mode"], "budget": r["budget"],
                             "horizon": r.get("horizon"), "method": r["method"],
                             "seed": r.get("seed", f31["seed"]), "history": key,
                             "family": family_names[family],
                             "metrics": {name: r[name] for name in FIELDS[step]}, "qa": r.get("qa", {})})
    _, family_rows, _ = aggregate(collect(rows, config))
    reference = {"summaries": [], "intervals": []}
    for step, report in published.items():
        reference["summaries"].extend({"step": step, "horizon": None} | r for r in report["rows"])
        reference["intervals"].extend({"step": step} | r for r in report["contrasts"])
    records("data/history.jsonl.gz", rows)
    records("data/family.jsonl.gz", family_rows)
    write("data/frozen-reference.json", reference)
    sources = {
        f"step{s}": {"report_sha256": digest(Path(f"results/step{s}/report.json")),
                     "config_sha256": digest(Path(f"docs/step{s}_freeze.json")),
                     "published_aggregate_sha256": digest(Path(f"docs/step{s}_artifacts/aggregate.json"))}
        for s in (30, 31)
    }
    spending = {}
    for s, report in reports.items():
        verifier = report["verifier"]
        items = [r["metrics"] for r in rows if r["step"] == s]
        spending[str(s)] = {"logical_calls": sum(r["verification_attempts"] for r in items),
                           "fresh_verifier_calls": verifier["attempts"],
                           "fresh_input_tokens": verifier["input_tokens"],
                           "fresh_output_tokens": verifier["output_tokens"],
                           "logical_input_tokens": sum(r["logical_input_tokens"] for r in items) if s == 31 else None,
                           "logical_output_tokens": sum(r["logical_output_tokens"] for r in items) if s == 31 else None,
                           "exact_cached_verdict_uses": (report["prior_verifier_uses"] if s == 31
                                                        else verifier["cache_hits"])}
    models = reports[31]["manifest"]
    write("manifest.json", {
        "schema": 1, "source_commit": "43a80f9", "analysis": config,
        "provenance": {"sources": sources, "spending": spending,
                       "cohort_sha256": f30["dataset_sha256"], "generator_seed": f30["seed"],
                       "controller_sha256": models["artifacts"],
                       "inference_model_ids": {k: models[k] for k in ("qwen", "minilm", "nli")},
                       "settings": models["settings"],
                       "controller_fit_manifest_sha256": digest(Path("docs/t1_v3_artifacts/fit-freeze.json")),
                       "step34_figure_sha256": {p.name: digest(p) for p in sorted(Path("research/figures").glob("*"))
                                               if p.suffix in {".pdf", ".svg"}}},
    })
    (ROOT / "checksums.sha256").write_bytes("".join(
        f"{digest(ROOT / name)}  {name}\n" for name in sorted(FILES)).encode())


if __name__ == "__main__":
    export()
