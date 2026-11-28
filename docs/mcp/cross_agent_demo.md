# Rehearse shared memory with two clients

From the checkout or extracted source package, after installation:

```powershell
& .\results\step45\venv\Scripts\python.exe .\scripts\test_mcp_integration.py
```

The script creates a temporary fictional profile, starts two separate MCP server processes through official SDK clients, and scripts the trusted administration decisions. It checks actual structured tool responses. For a hands-on run, register the clients with separate grants as described in the [setup guide](README.md), and use the following sequence.

| Actor | Action | Expected observation |
| --- | --- | --- |
| A | Propose project budget $500, effective 2025-01-01, source fiction:budget | Pending ticket |
| B | Recall project budget before approval | Abstain |
| Administrator | Inspect pending queue and approve A's ticket | B can now recall $500 |
| A and administrator | Propose and approve correction to $800 effective 2025-02-01, source fiction:revision | Approved |
| B | Restart both clients, recall current budget and query as of 2025-01-15 | $800 current and $500 historical, each with provenance |
| A and administrator | Propose uncertain correction and attempt approval | Deferred; $800 remains current |
| A and administrator | Propose forgetting, review and approve | Both clients abstain on managed reads, including historical lookup |

The SDK rehearsal also checks invalid input, attempted impersonation, ticket isolation and simultaneous competing proposals. The actual Codex smoke check covered discovery and readiness only. The optional loopback verifier was exercised on a fictional correction. It returned an incorrect historical verdict (258 input tokens, 12 output tokens, about 6.4 seconds). Its advice left the ticket pending. This single example provides no estimate of verifier accuracy.
