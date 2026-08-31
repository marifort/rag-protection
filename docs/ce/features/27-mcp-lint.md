# #27 — MCP manifest linter

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/27-mcp-lint.md) · [Learn](../learn/03-tools-and-assessment.md#27-mcp-manifest-linter) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/06-labs-a2-a3-a6-a7.md)

| Field | Value |
|-------|-------|
| **Edition** | CE (CLI) |
| **Status** | Shipped |
| **Code** | `tools/mcp_lint/` · pairs with [#7](07-tool-gateway.md) |

**Demo:** [../demos/27-mcp-lint.md](../demos/27-mcp-lint.md) · **Tutorial:** [T06](../tutorials/06-labs-a2-a3-a6-a7.md)

---

## What & why

Shift-left CI gate on MCP `tools/list` metadata — catch poisoned descriptions and over-broad scopes before connect. Runtime invoke enforcement remains #7.

```bash
tools/mcp-lint check --manifest tools.json
tools/mcp-lint check --url http://localhost:…   # live
```

## Engineering

[lab7 SPEC](../../../ENTERPRISE.md)
