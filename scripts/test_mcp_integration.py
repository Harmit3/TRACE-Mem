"""Bounded two-client stdio rehearsal with entirely fictional data and scripted local review."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trace_mem.mcp_store import Practice, initialize


@asynccontextmanager
async def client(root, agent):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[
        "-I", str(ROOT / "scripts/serve_mcp.py"), "--binding", str(root / "bindings" / (agent + ".json"))])
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        init = await session.initialize()
        assert init.serverInfo.name == "trace-mem-practice"
        yield session


async def call(session, name, **args):
    response = await session.call_tool("memory_" + name, args)
    assert not response.isError, response.content
    assert response.structuredContent["untrusted_data"] is True
    return response.structuredContent


async def scenario(root):
    initialize(root)
    store = Practice(root)
    label = "project budget"
    slot = {"label": label}
    initial = dict(**slot, value="$500", effective="2025-01-01", source="fiction:budget")
    corrected = dict(initial, value="$800", effective="2025-02-01", source="fiction:revision")
    async with client(root, "agent-a") as a, client(root, "agent-b") as b:
        discovered = (await a.list_tools()).tools
        assert {t.name for t in discovered} == {"memory_" + name for name in (
            "status", "search", "recall", "history", "propose", "propose_correction",
            "propose_forgetting", "proposal_status")}
        assert all(t.inputSchema["additionalProperties"] is False and t.outputSchema for t in discovered)
        assert (await call(a, "propose", **initial))["status"] == "denied"
        store.grant("agent-a", label, read=True, propose=True)
        store.grant("agent-b", label, read=True, history=True)
        for bad in (dict(initial, agent="agent-b"), dict(initial, value="x"*241),
                    dict(initial, effective="2025-02-31"), dict(initial, value=500)):
            assert (await a.call_tool("memory_propose", bad)).isError
        assert (await call(b, "propose", **initial))["status"] == "denied"
        ticket = (await call(a, "propose", **initial))["proposal_id"]
        assert (await call(b, "proposal_status", proposal_id=ticket))["status"] == "unavailable"
        assert (await call(b, "recall", **slot))["status"] == "abstain"
        assert store.decide(ticket, True) == "approved"
        assert (await call(a, "proposal_status", proposal_id=ticket))["status"] == "approved"
        assert (await call(b, "recall", **slot))["evidence"][0]["value"] == "$500"
        ticket = (await call(a, "propose_correction", **corrected))["proposal_id"]
        assert store.decide(ticket, True) == "approved"
    # Both clients close and new OS processes reopen the persisted database.
    async with client(root, "agent-a") as a, client(root, "agent-b") as b:
        assert (await call(b, "search", query="budget"))["evidence"][0]["value"] == "$800"
        assert (await call(b, "recall", **slot, as_of="2025-01-15"))["evidence"][0]["value"] == "$500"
        assert [r["value"] for r in (await call(b, "history", **slot))["evidence"]] == ["$800", "$500"]
        assert (await call(a, "recall", **slot, as_of="2025-01-15"))["status"] == "abstain"
        ticket = (await call(a, "propose_correction", **dict(corrected, kind="uncertain")))["proposal_id"]
        assert store.decide(ticket, True) == "deferred"
        assert (await call(b, "recall", **slot))["evidence"][0]["value"] == "$800"
        stale = (await call(a, "propose_correction", **corrected))["proposal_id"]
        delete = (await call(a, "propose_forgetting", **slot, source="fiction:erase"))["proposal_id"]
        assert store.decide(delete, True) == "approved"
        for session in (a, b):
            for tool, args in (("history", slot), ("recall", slot), ("search", {"query": "800"})):
                assert (await call(session, tool, **args))["status"] == "abstain"
        assert (await call(a, "proposal_status", proposal_id=stale))["status"] == "unavailable"
        # Independent server processes submit competing candidates at the same revision.
        for agent in ("agent-a", "agent-b"):
            store.grant(agent, "project capacity", read=True, propose=True)
        requests = [call(session, "propose", **dict(initial, label="project capacity", value=value))
                    for session, value in ((a, "12"), (b, "15"))]
        first, second = await asyncio.gather(*requests)
        assert store.decide(first["proposal_id"], True) == "approved"
        assert (await call(b, "proposal_status", proposal_id=second["proposal_id"]))["status"] == "stale"
        assert (await call(b, "recall", label="project capacity"))["evidence"][0]["value"] == "12"
    print("PASS: discovery, schemas, grants, review, $500 to $800, restart, history, uncertainty and forgetting.")


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        asyncio.run(scenario(Path(tmp) / "practice"))
