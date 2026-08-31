# Shared tools

Scripts used by **both** CE and EE checkouts. Stay in the public CE repo (`launch: keep-ce`) so OSS contributors can run Docker and tests. EE-only work belongs in [../ee/README.md](../../ENTERPRISE.md).

Put **new** dual-use scripts here (`tools/shared/<name>.sh`). Do not add new files to the frozen flat `tools/*.sh` tree.

Legacy flat paths (frozen) that belong in this bucket:

| Path | Role |
|------|------|
| `tools/docker_common.sh` | Compose helpers |
| `tools/docker_start.sh` / `docker_stop.sh` / `docker_build.sh` | Stack lifecycle (`--ee` is a flag, not EE source) |
| `tools/setup_venv.sh` / `tools/run_tests.sh` | Dev env (Python 3.11+; see [LOCAL_SETUP.md](../../docs/ce/guide/LOCAL_SETUP.md)) |

Validate/commit and release-labelling helpers are maintainer-only tooling (`launch: omit`) and are not part of the public CE repo.
