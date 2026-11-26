"""Execution entry point for a future independently approved validation cohort."""

from argparse import ArgumentParser
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path

from scripts.run_memora import write
from trace_mem.baselines import PreparedClaim
from trace_mem.claims import Claim
from trace_mem.memory import Source
from trace_mem.validation_adapters_v1 import asset_check, bind, sha
from trace_mem.validation_v2 import (Check, Episode, ExactLedger, ExecutionPaused, Gold, check_reviewed,
                                    code_fingerprint, run_reviewed, signature)

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "research/execution_preflight.json"


def fields(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys.split()):
        raise ValueError(f"Unexpected input fields. Expected {keys}")


def parse_episode(obj):
    fields(obj, "identity family opening closing events permitted restricted_values support")
    entries = []
    for row in obj["events"]:
        fields(row, "claim source fact_id")
        c, s = row["claim"], row["source"]
        fields(c, "predicate value intent effective_on expires_on explicit_effective_date")
        fields(s, "observed_on reference kind")
        if (c["intent"] not in ("assert", "correct", "uncertain", "delete") or not c["predicate"].strip()
                or not c["value"].strip() or type(c["explicit_effective_date"]) is not bool
                or s["kind"] not in ("direct", "dated_record", "reported", "conflicting", "unknown")):
            raise ValueError("Unsupported prepared claim")
        start = date.fromisoformat(c["effective_on"])
        end = date.fromisoformat(c["expires_on"]) if c["expires_on"] is not None else None
        if end is not None and end <= start:
            raise ValueError("Invalid claim interval")
        entries.append(PreparedClaim(Claim(**(c | {"effective_on": start, "expires_on": end})),
                                     Source(**(s | {"observed_on": date.fromisoformat(s["observed_on"])})),
                                     row["fact_id"]))
    return Episode(obj["identity"], obj["family"], date.fromisoformat(obj["opening"]),
                   date.fromisoformat(obj["closing"]), tuple(entries), frozenset(obj["permitted"]),
                   tuple(obj["restricted_values"]), tuple(tuple(s) for s in obj["support"]))


def parse_cases(content):
    cases = []
    for row in content:
        fields(row, "episode gold question")
        gold = row["gold"]
        fields(gold, "checks answerable answers harmful")
        checks = []
        for c in gold["checks"]:
            fields(c, "observed effective predicate values type")
            checks.append(Check(date.fromisoformat(c["observed"]), date.fromisoformat(c["effective"]),
                                c["predicate"], tuple(c["values"]), c["type"]))
        cases.append((parse_episode(row["episode"]), Gold(tuple(checks), gold["answerable"],
                      tuple(gold["answers"]), frozenset(gold["harmful"])), row["question"]))
    return cases


def fingerprint(config, stage):
    return signature([config["version"], config["pins"], config["stages"][stage],
                      sha(Path(__file__)), sha(ROOT / "trace_mem/validation_adapters_v1.py"),
                      {name: sha(ROOT / "trace_mem" / name) for name in (
                          "features_v3.py", "reader_v2.py", "llm_tasks.py", "providers.py",
                          "retrieval_diagnostic.py", "semantic.py", "controller.py", "training.py")} ])


def approved(config, stage, cohort, receipt_path, protocol):
    if not all(isinstance(p, Path) and p.is_file() for p in (cohort, receipt_path, protocol)):
        raise ValueError("Blocked: supply the approved cohort, reviewed protocol and signed-off receipt")
    receipt = json.loads(receipt_path.read_bytes())
    if any(not receipt.get(k) for k in config["required"]):
        raise ValueError("Blocked: approval receipt has missing fields")
    if (receipt["status"] != "approved" or receipt["stage"] != stage
            or receipt["protocol_sha256"] != sha(protocol)
            or receipt["cohort_file_sha256"] != sha(cohort)
            or receipt["backend_fingerprint"] != fingerprint(config, stage)):
        raise ValueError("Blocked: approved stage, input or adapter fingerprint differs")
    cases = parse_cases(json.loads(cohort.read_bytes()))
    return check_reviewed(cases, receipt), receipt


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify-assets", "fingerprints", "preflight", "run"))
    parser.add_argument("--stage", choices=("primary", "secondary", "fixed"), default="primary")
    for arg in ("cohort", "receipt", "protocol", "nli", "outcomes", "output"):
        parser.add_argument("--" + arg, type=Path)
    args = parser.parse_args()
    config = json.loads(PREFLIGHT.read_bytes())
    try:
        if args.command == "fingerprints":
            summary = {"backend_fingerprint": fingerprint(config, args.stage),
                       "code_sha256": code_fingerprint()}
            if args.protocol:
                summary["protocol_sha256"] = sha(args.protocol)
            if args.cohort:
                summary["cohort_file_sha256"] = sha(args.cohort)
                cases = sorted(parse_cases(json.loads(args.cohort.read_bytes())),
                               key=lambda c: (c[0].family, c[0].identity))
                summary["cohort_sha256"] = signature([(asdict(e), asdict(g), q) for e,g,q in cases])
            print(json.dumps(summary))
            return 0
        if args.command != "verify-assets":
            cases, receipt = approved(config, args.stage, args.cohort, args.receipt, args.protocol)
        if not isinstance(args.nli, Path) or not isinstance(args.outcomes, Path):
            raise ValueError("Provide local --nli and --outcomes paths")
        checked = asset_check(config["pins"], args.nli, args.outcomes)
        if args.command != "run":
            print(json.dumps(checked))
            return 0
        if args.output is None or (ROOT / "results").resolve() not in args.output.resolve().parents:
            raise ValueError("Choose an ignored --output directory")
        limits = config["stages"][args.stage]
        # Bind only after independent approval, cohort validation and offline asset checks.
        rules, features, verifier, reader, meter = bind(config["pins"], args.nli, args.outcomes,
                                                        args.output, limits["reader_physical_cap"])
        rows, intervals = run_reviewed(cases, receipt, args.output, rules=rules, feature=features,
                                       provider=verifier, reader=reader, stage=args.stage,
                                       verifier_limit=limits["verifier_physical_cap"])
        write(args.output / "report.json", {"stage": args.stage, "conditions": rows, "intervals": intervals,
                                          "assets": checked, "reader_physical": meter.stats(),
                                          "verifier_physical": ExactLedger(args.output / "verifier.sqlite",
                                              receipt["backend_fingerprint"]).stats()})
    except (OSError, ValueError, KeyError, TypeError, ExecutionPaused) as error:
        parser.exit(2, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
