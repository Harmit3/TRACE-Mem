"""Verify historical publication files from offline rendering outputs."""

import csv
from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess
import sys

from scripts.render_memora_controlled import plot
from scripts.summarize_authorized_evidence import publish
from scripts.summarize_memora_failure_isolation import render as render25
from scripts.summarize_reader_safety import render as render26


def main(out):
    if Path("results").resolve() not in out.resolve().parents:
        raise ValueError("Use a new ignored results directory")
    out.mkdir(parents=True, exist_ok=False)
    checks = []

    def module(name, *args):
        subprocess.run([sys.executable, "-m", name, *map(str, args)], check=True)

    def same(public, reproduced):
        public, reproduced = Path(public), Path(reproduced)
        if public.read_bytes() != reproduced.read_bytes():
            raise ValueError(f"Regeneration differs for {public}")
        checks.append([public.as_posix(), "byte-identical"])

    step22 = out / "step22.svg"
    plot(json.loads(Path("results/memora-step22/report.json").read_bytes()), step22)
    same("docs/memora_step22_budget.svg", step22)
    module("scripts.render_t2_development", "results/t2-step23/report.json",
           "--aggregate", out / "step23.json", "--plot", out / "step23.svg")
    same("docs/t2_step23_aggregate.json", out / "step23.json")
    same("docs/t2_step23_budget.svg", out / "step23.svg")
    module("scripts.render_memora_full", "results/memora-step24-final", out / "step24")
    for n, render, base in [(25, render25, "memora-step25"), (26, render26, "memora-step26")]:
        path = out / f"step{n}"
        path.mkdir()
        render(Path("results") / base, path)
    p29 = out / "step29"
    p29.mkdir()
    publish(Path("results/memora-step29"), Path("results/memora-step26/scored.json"), p29)
    for n in (24, 25, 26, 29):
        for f in sorted((out / f"step{n}").iterdir()):
            same(Path(f"docs/memora_step{n}_artifacts") / f.name, f)
    for n, script, args in [
        (30, "summarize_step30", ["results/step30/report.json"]),
        (31, "summarize_step31", ["results/step31/report.json"]),
        (32, "summarize_longmemeval", ["results/step32/safe-report.json"]),
        (33, "summarize_step33", ["results/step33"]),
    ]:
        folder = out / f"step{n}"
        module(f"scripts.{script}", *args, folder)
        for f in sorted(folder.iterdir()):
            same(Path(f"docs/step{n}_artifacts") / f.name, f)
    t1 = out / "step18"
    module("scripts.train_t1_v3", "evaluate", "data/updateset-v3-final",
           "results/updateset-v3-final", "results/updateset-v3-final-no-nli",
           "results/t1-v3-fit", "--output", t1)
    for f in sorted(t1.iterdir()):
        same(Path("docs/t1_v3_artifacts") / f.name, f)

    for public, original in [
        ("docs/memora_step21_aggregate.json", "results/memora-step21-validation/report.json"),
        ("docs/memora_step27_aggregate.json", "results/memora-step27/report.json"),
        ("docs/step30_artifacts/run-manifest.json", "results/step30/freeze.json"),
    ]:
        archived = json.loads(Path(original).read_bytes())
        if "step21" in public:
            for method in archived["methods"].values():
                del method["by_case"]
        if json.loads(Path(public).read_bytes()) != archived:
            raise ValueError(f"Archived values differ for {public}")
        checks.append([public, "identical JSON values"])
    with Path("research/tables/artifact-verification.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["artifact", "verification"])
        writer.writerows(sorted(checks))
    print(f"Verified {len(checks)} published files.")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    main(parser.parse_args().output)
