# CE tools

Community Edition scripts and CLIs. **Public MIT** at CE launch.

Put **new** CE-only shell scripts here (`tools/ce/<name>.sh`). Do not add new files next to the legacy flat scripts in `tools/*.sh` — that tree is frozen (see [edition/README.md](../../docs/ce/README.md)).

Existing CE CLIs already live in their own packages (keep using those paths):

| Path | Product |
|------|---------|
| `tools/rag_scan/` · `tools/rag-scan` | #6 config scanner |
| `tools/mcp_lint/` · `tools/mcp-lint` | #27 MCP linter |
| `tools/rag_ground/` · `tools/rag-ground` | #19 grounding |
| `tools/rag_score/` · `tools/rag-score` | #20 posture scorecard |
| `tools/inj_bench/` · `tools/rag-injbench` | #23 injbench |
| `tools/redteam/` · `tools/rag-redteam` | #10 red-team harness |
| `tools/acl_backfill/` · `tools/acl-backfill` | #29 ACL backfill |
| `tools/build_ce.sh` | Console + optional CE install (legacy flat path) |
| `tools/smoke_rag_proxy.sh` | CE smoke |

EE-only CLIs: [../ee/README.md](../../ENTERPRISE.md). Shared docker/git helpers: [../shared/README.md](../shared/README.md).
