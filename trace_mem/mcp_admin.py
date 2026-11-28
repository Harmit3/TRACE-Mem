"""Human-operated local CLI. Never registered as an MCP tool."""
import argparse
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trace_mem.mcp_store import Practice, bind, initialize


def advise(store, key, model):
    from trace_mem.baselines import _eligible_target
    from trace_mem.claims import Claim
    from trace_mem.llm_tasks import LLMTasks
    from trace_mem.memory import Fact, Source, TemporalMemory
    from trace_mem.providers import ChatProvider, ProviderConfig
    from trace_mem.verification import Budget

    with store.transaction() as db:
        p = db.execute("SELECT * FROM proposals WHERE id=? AND state='pending' AND action='correct' "
                       "AND kind='permanent'", (key,)).fetchone()
        if not p:
            return "ineligible"
        old = db.execute("SELECT * FROM facts WHERE label=? ORDER BY start DESC LIMIT 1",
                         (p["label"],)).fetchone()
        if not old:
            return "ineligible"
        memory = TemporalMemory()
        memory.accept(Fact(old["id"], "practice", p["label"], old["value"],
                           Source(date.fromisoformat(old["observed"]), old["source"], "reported"),
                           date.fromisoformat(old["start"]), date.fromisoformat(old["end"]) if old["end"] else None))
        claim = Claim(p["label"], p["value"], "correct", date.fromisoformat(p["start"]))
        target = _eligible_target(memory, "practice", claim)
        if target is None:
            return "ineligible"
        config = ProviderConfig("ollama", model, max_requests=1, context_tokens=2048,
                                max_input_tokens=1800, max_output_tokens=48, timeout=30)
        with TemporaryDirectory() as scratch:
            provider = ChatProvider(config, Path(scratch) / "once.sqlite3")
            tasks = LLMTasks(provider, verification_mode="direct-v2")
            budget = Budget(1)
            verdict = budget.call(tasks.verify, claim, target)
            return {"advisory": verdict, "failures": budget.failures, "usage": provider.stats()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init")
    commands.add_parser("pending")
    commands.add_parser("bind").add_argument("agent")
    grant = commands.add_parser("grant")
    grant.add_argument("agent")
    grant.add_argument("label")
    for name in ("read", "history", "propose"):
        grant.add_argument("--" + name, action="store_true")
    for command in ("approve", "reject", "advise"):
        sub = commands.add_parser(command)
        sub.add_argument("ticket")
        if command == "advise":
            sub.add_argument("--model", required=True)
    a = parser.parse_args()
    if a.action == "init":
        initialize(a.profile)
        return
    store = Practice(a.profile)
    if a.action == "bind":
        bind(a.profile, a.agent)
    elif a.action == "grant":
        store.grant(a.agent, a.label, a.read, a.history, a.propose)
    elif a.action == "pending":
        print(json.dumps(store.pending(), indent=2, ensure_ascii=True))
    elif a.action == "advise":
        print(json.dumps(advise(store, a.ticket, a.model)))
    else:
        print(store.decide(a.ticket, a.action == "approve"))


if __name__ == "__main__":
    main()
