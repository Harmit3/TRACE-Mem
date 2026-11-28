# Claude Desktop, Claude Code and other stdio clients

Complete the [installation and grants](README.md). Use a separate binding and explicit label grants for each client. This example assigns the proposing identity A to Claude Desktop. Use the following PowerShell to **print** its configuration entry using the actual absolute paths.

```powershell
@{ mcpServers = @{ 'trace-practice' = @{ command = $python; args = @('-I', $server, '--binding', $agentA) } } } | ConvertTo-Json -Depth 5
```

In Claude Desktop open Settings → Developer → Edit Config. Back up the existing file, then merge the generated entry into its existing `mcpServers` object under an unused name. Save, fully quit, reopen and check the tools menu. To disconnect, remove only that entry and restart. Other stdio hosts can use the same executable and argument array in their own configuration format. [Example JSON with placeholder paths](client-example.json) · [Official local server configuration](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

For Claude Code, create a separate binding from the repository root. Choose the project where the registration should apply and check that the server name is unused.

```powershell
& $python -m trace_mem.mcp_admin --profile $practice bind agent-c
& $python -m trace_mem.mcp_admin --profile $practice grant agent-c 'project budget' --read
$agentC = (Resolve-Path (Join-Path $practice 'bindings\agent-c.json')).Path
claude mcp list
claude mcp add --transport stdio --scope local trace-practice -- "$python" -I "$server" --binding "$agentC"
claude mcp get trace-practice
```

Use `/mcp` in Claude Code to inspect the connection. Remove it with `claude mcp remove --scope local trace-practice`. The Claude configurations are documented examples. Neither Claude client was exercised on the reference host. [Official Claude Code MCP guide](https://code.claude.com/docs/en/mcp)
