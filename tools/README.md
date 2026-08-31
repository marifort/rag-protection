# Tools

Scripts and CLIs at the repo root. **Edition placement** is mandatory — see [edition/README.md](../docs/ce/README.md).

| New file | Put it in |
|----------|-----------|
| CE-only script | [`ce/`](ce/README.md) |
| EE-only script | [`ee/`](../ENTERPRISE.md) |
| Used by both | [`shared/`](shared/README.md) |
| CE product CLI (Python package) | existing `rag_scan/`, `mcp_lint/`, … |
| EE product CLI | `ee/` or the private `rag-protection-enterprise/` repo |

The flat `tools/*.sh` files are a **frozen mixed tree**. Call them as today (`bash tools/docker_start.sh`). Do not add new siblings there; CI (`python3 edition/check_tree.py`) will fail.
