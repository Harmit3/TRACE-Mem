"""Recompute TRACE-Mem Steps 30 and 31 with public numeric checkpoints only."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import random
import re
from statistics import fmean
import sys


ROOT = Path(__file__).resolve().parent
COMMON = tuple("current current_total historical historical_total deletion deletion_total authorized_deletion "
               "harmful_adoptions eligible_candidates verification_attempts verification_failures budget_cap "
               "stale_targets".split())
FIELDS = {
    30: COMMON + ("helpful_verifications", "harmful_verifications", "reference_candidates"),
    31: COMMON + tuple("live_eligible positions_total logical_input_tokens logical_output_tokens "
                       "unmetered_calls helpful harmful".split()),
}
MODES = ("fixed", "closed-loop")
QUESTIONS = ("short", "reasoning")
Q30 = ("correct", "abstained", "error")
Q31 = ("correct", "incorrect", "abstained", "invalid", "contradictory")


class ReleaseError(ValueError):
    pass


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def verify(root):
    paths = {}
    for line in (root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        checksum, sep, name = line.partition("  ")
        if (not sep or not re.fullmatch(r"[a-f0-9]{64}", checksum)
                or not re.fullmatch(r"(?:data/)?[a-zA-Z0-9._-]+", name)
                or name in paths or name in (".", "..", "data/.", "data/..")):
            raise ReleaseError("Malformed or unsafe checksum entry")
        paths[name] = checksum
    required = {"manifest.json", "reproduce.py", "figures.py", "requirements.txt", "README.md",
                "reviewer-guide.md", "independent-review-checklist.md", "data/history.jsonl.gz",
                "data/family.jsonl.gz", "data/frozen-reference.json"}
    if paths.keys() != required:
        raise ReleaseError("Checksum list does not cover exactly the public files")
    for name, expected in paths.items():
        candidate = root / name
        if not candidate.is_file():
            raise ReleaseError(f"Missing release file: {name}")
        if digest(candidate) != expected:
            raise ReleaseError(f"SHA-256 mismatch: {name}")
    manifest = read_json(root / "manifest.json")
    if manifest.get("schema") != 1:
        raise ReleaseError("Unsupported manifest version")
    return manifest


def load_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def condition(row):
    return row["step"], row["mode"], row["budget"], row.get("horizon"), row["method"]


def named(key):
    return dict(zip(("step", "mode", "budget", "horizon", "method"), key, strict=True))


def check_row(row, metrics):
    if set(row) != {"step", "mode", "budget", "horizon", "method", "seed",
                    "history", "family", "metrics", "qa"}:
        raise ReleaseError("Unexpected history fields")
    if not re.fullmatch(r"H\d{3}", row["history"]) or not re.fullmatch(r"F\d{2}", row["family"]):
        raise ReleaseError("Invalid anonymous history or family ID")
    if any(type(row[k]) is not int for k in ("step", "budget", "seed")) or (
            row["horizon"] is not None and type(row["horizon"]) is not int):
        raise ReleaseError("Invalid condition coordinates")
    if (set(metrics) != set(FIELDS[row["step"]])
            or any(type(v) is not int or v < 0 for v in metrics.values())):
        raise ReleaseError("Invalid metric fields or non-integer history count")
    for numerator, denominator in (("current", "current_total"), ("historical", "historical_total"),
                                   ("deletion", "deletion_total"), ("stale_targets", "verification_attempts"),
                                   ("verification_failures", "verification_attempts"),
                                   ("verification_attempts", "budget_cap")):
        if metrics[numerator] > metrics[denominator]:
            raise ReleaseError(f"Out-of-range count: {numerator}")
    if row["mode"] == "fixed" and metrics["verification_attempts"] != metrics["budget_cap"]:
        raise ReleaseError("Fixed stream must spend the exact quota")
    if metrics["authorized_deletion"] != metrics["deletion_total"] or metrics.get("unmetered_calls", 0):
        raise ReleaseError("Authorization or token-accounting invariant failed")
    if [metrics["current_total"], metrics["historical_total"], metrics["deletion_total"]] != [6, 5, 2]:
        raise ReleaseError("Unexpected evaluation denominator")
    qa = row["qa"]
    if qa:
        if set(qa) != set(QUESTIONS):
            raise ReleaseError("Invalid QA questions")
        for outcome in qa.values():
            if row["step"] == 30:
                if (set(outcome) != set(Q30) or any(type(v) is not bool for v in outcome.values())
                        or sum(outcome.values()) > 1):
                    raise ReleaseError("Invalid Step 30 QA counts")
            elif outcome not in Q31:
                raise ReleaseError("Invalid Step 31 QA status")


def collect(rows, config):
    grouped, cohort = defaultdict(lambda: defaultdict(list)), {}
    observed = set()
    expected = set()
    for budget in config["budgets"]:
        for mode in MODES:
            for method in config["step30_methods"]:
                expected.add((30, mode, budget, None, method))
        for method in config["step31_fixed"]:
            expected.add((31, "fixed", budget, None, method))
        for method in config["step31_baselines"]:
            expected.add((31, "closed-loop", budget, None, method))
        for horizon in config["horizons"]:
            for method in config["step31_paced"]:
                expected.add((31, "closed-loop", budget, horizon, method))
    for row in rows:
        key, history, family, seed = condition(row), row["history"], row["family"], row["seed"]
        if key not in expected or (*key, history, seed) in observed:
            raise ReleaseError("Unknown or duplicate policy condition")
        observed.add((*key, history, seed))
        if cohort.setdefault(history, family) != family:
            raise ReleaseError("Inconsistent family assignment across steps")
        check_row(row, row["metrics"])
        grouped[key][history].append(row)
    families = Counter(cohort.values())
    if len(families) != 10 or set(families.values()) != {10} or set(grouped) != expected:
        raise ReleaseError("Incomplete condition grid or incorrect family sizes")
    for key, histories in grouped.items():
        seeds = config["b4_seeds"] if key[0] == 30 and key[-1] == "B4" else [config["primary_seed"]]
        if histories.keys() != cohort.keys() or any(sorted(r["seed"] for r in series) != sorted(seeds)
                                                    for series in histories.values()):
            raise ReleaseError("Missing histories or seeds in a condition")
    return grouped


def qa_counts(step, histories):
    result = defaultdict(Counter)
    for repetitions in histories.values():
        answers = [r["qa"] for r in repetitions if r["qa"]]
        if not answers:
            continue
        for q in QUESTIONS:
            result[q]["total"] += 1
            if step == 30:
                result[q].update({k: fmean(a[q][k] for a in answers) for k in Q30})
            else:
                for answer in answers:
                    result[q][answer[q]] += 1
    if step == 30:
        return {q: {k: result[q][k] for k in (*Q30, "total")} for q in QUESTIONS}
    return {q: {k: rr[k] for k in (*Q31, "total")} for q, rr in result.items()}


def aggregate(grouped):
    summaries, family_rows, scores = {}, [], {}
    for key, histories in sorted(grouped.items(), key=lambda item: repr(item[0])):
        step = key[0]
        family_totals = defaultdict(Counter)
        scores[key] = {}
        totals = Counter()
        for history, series in histories.items():
            family = series[0]["family"]
            means = {name: fmean(r["metrics"][name] for r in series) for name in FIELDS[step]}
            scores[key][history] = family, means["current"] / means["current_total"]
            totals.update(means)
            family_totals[family].update(means | {"histories": 1})
        for family, counts in sorted(family_totals.items()):
            family_rows.append(named(key) | {"family": family, "metrics": dict(counts)})
        calls, cap = totals["verification_attempts"], totals["budget_cap"]
        derived = {"historical_accuracy": totals["historical"] / totals["historical_total"]}
        accuracy = totals["current"] / totals["current_total"]
        if step == 30:
            derived.update(current_accuracy=accuracy, seeds=len(next(iter(histories.values()))),
                           achieved_reference_coverage=calls / totals["reference_candidates"],
                           budget_utilization=calls / cap if cap else None)
        else:
            derived.update(accuracy=accuracy, utilization=calls / cap if cap else None,
                           mean_position=totals["positions_total"] / calls if calls else None)
        summaries[key] = dict(totals) | derived | {"histories": len(histories), "qa": qa_counts(step, histories)}
    return summaries, family_rows, scores


def quantile(ordered, p):
    index, fraction = divmod((len(ordered) - 1) * p, 1)
    k = int(index)
    return ordered[k] + (ordered[k + 1] - ordered[k]) * fraction


def bootstrap(means, config):
    rng = random.Random(config["bootstrap_seed"])
    draws = sorted(fmean(rng.choices(means, k=len(means))) for _ in range(config["bootstrap_draws"]))
    return {"difference": fmean(means), "lower": quantile(draws, .025),
            "upper": quantile(draws, .975), "families": len(means)}


def intervals(scores, config):
    results = []
    for step in (30, 31):
        for budget in config["budgets"]:
            if step == 31 and not budget:
                continue
            modes = [(m, None) for m in MODES] if step == 30 else [
                ("fixed", None), *(("closed-loop", h) for h in config["horizons"])]
            for mode, horizon in modes:
                contrasts = config[f"contrasts{step}"]
                for label, weights in contrasts.items():
                    arms = {m: scores[step, mode, budget, horizon if m in config["step31_paced"] else None, m]
                            for m in weights}
                    paired = defaultdict(list)
                    for h, (family, _) in next(iter(arms.values())).items():
                        paired[family].append(sum(w * arms[m][h][1] for m, w in weights.items()))
                    stats = bootstrap([fmean(paired[f]) for f in sorted(paired)], config)
                    meta = ({"left": next(iter(weights)), "right": next(reversed(weights)), "histories": 100}
                            if step == 30 else {"horizon": horizon, "contrast": label})
                    results.append({"step": step, "mode": mode, "budget": budget} | meta | stats)
    return results


def compare(actual, frozen, path):
    if isinstance(actual, dict) and isinstance(frozen, dict) and actual.keys() == frozen.keys():
        for key in actual:
            compare(actual[key], frozen[key], f"{path}.{key}")
    elif (type(actual) in (int, float) and type(frozen) in (int, float)
          and isclose(actual, frozen, rel_tol=0, abs_tol=1e-12)):
        return
    elif actual != frozen:
        raise ReleaseError(f"Recomputed value differs from frozen reference: {path}")


def contrast_key(row):
    label = row.get("contrast") or f"{row['left']} minus {row['right']}"
    return row["step"], row["mode"], row["budget"], row.get("horizon"), label


def run(root=ROOT):
    manifest = verify(root)
    config = manifest["analysis"]
    rows = load_rows(root / "data/history.jsonl.gz")
    reports = read_json(root / "data/frozen-reference.json")
    summary, families, scores = aggregate(collect(rows, config))
    checks = intervals(scores, config)
    scoring = {contrast_key(row): row for row in checks}
    for row in reports["summaries"]:
        compare(summary[condition(row)], {k: v for k, v in row.items() if k not in named(condition(row))},
                f"condition {condition(row)}")
    for row in reports["intervals"]:
        compare(scoring[contrast_key(row)], row, f"interval {contrast_key(row)}")
    if (len(summary) != len(reports["summaries"])
            or len(summary) != len({condition(row) for row in reports["summaries"]})
            or len(scoring) != len(reports["intervals"])
            or len(scoring) != len({contrast_key(row) for row in reports["intervals"]})):
        raise ReleaseError("Frozen reference does not span the experiment grid")
    family_keys = lambda row: (*condition(row), row["family"])
    saved_families = load_rows(root / "data/family.jsonl.gz")
    if len(saved_families) != len(families):
        raise ReleaseError("Incorrect number of family rows")
    compare({family_keys(r): r["metrics"] for r in families},
            {family_keys(r): r["metrics"] for r in saved_families}, "family")
    physical = manifest["provenance"]["spending"]
    for step in (30, 31):
        raw = [r["metrics"] for r in rows if r["step"] == step]
        budget = physical[str(step)]
        if sum(r["verification_attempts"] for r in raw) != budget["logical_calls"]:
            raise ReleaseError("Logical spending disagrees with archive totals")
        for key in ("logical_input_tokens", "logical_output_tokens"):
            if step == 31 and sum(r[key] for r in raw) != budget[key]:
                raise ReleaseError("Logical token usage disagrees with archive totals")
    return summary, checks, len(rows), len(families)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reproduced"))
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    try:
        if args.output.resolve() == ROOT or ROOT / "data" in (args.output.resolve(), *args.output.resolve().parents):
            raise ReleaseError("Choose an output directory outside the released inputs")
        summary, checks, histories, families = run()
        args.output.mkdir(parents=True, exist_ok=True)
        derived = [named(k) | v for k, v in summary.items()]
        (args.output / "reproduced.json").write_text(json.dumps(
            {"conditions": derived, "intervals": checks}, indent=2) + "\n", encoding="utf-8")
        if args.figures:
            from figures import render
            render(derived, checks, args.output)
        print(f"Verified {histories:,} history rows, {families:,} family rows, "
              f"{len(summary)} summaries and {len(checks)} paired intervals.")
    except (OSError, ImportError, ValueError, KeyError, TypeError) as error:
        print(f"Release verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
