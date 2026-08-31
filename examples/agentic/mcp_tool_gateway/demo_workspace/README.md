# Demo workspace for MCP filesystem backend (Layer 2 compose)

Read-only mount for `@modelcontextprotocol/server-filesystem` when using Layer 2:

```bash
bash tools/docker_start.sh --mcp-tools
# or:
docker compose -f compose.yml -f compose.mcp-tools.yml --profile mcp-tools up -d --build
```

`docs/runbook.md` is the file exercised by MCP smoke tests and [TC-L1-L2-001](../../../../ENTERPRISE.md).

**Read the demo runbook via the tool gateway (MCP backend):**

```bash
curl -s -X POST http://localhost:8090/v1/tools/invoke \
  -H "Authorization: Bearer employee-demo-token" \
  -H 'Content-Type: application/json' \
  -d '{"tool":"read_file","arguments":{"path":"docs/runbook.md"}}' | jq .
```

Expect `"decision": "allow"`, `"result.source": "mcp"`, and runbook content in `result.content`.

Same command (and Layer 2 detail): [examples/agentic/mcp_tool_gateway/README.md](../README.md) · [LAYER2_MCP_RUNBOOK.md](../../../../ENTERPRISE.md) · [MCP_GATEWAY_DEPLOYMENT.md](../../../../ENTERPRISE.md).
