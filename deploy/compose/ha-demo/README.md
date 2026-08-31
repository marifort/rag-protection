# Docker two-proxy demo (no Kubernetes)

This is the Compose packaging of the named E4.2 **demo slice**, not production HA. Two proxy containers share Qdrant and return the same injection verdict. nginx listens on host port **8090**. Audit JSONL is off; rate limits, extraction monitor, and CHALLENGE queues stay per-container. This host, nginx, and Qdrant are still single points of failure.

Full prose (what to tell a client, Helm vs Docker, CE vs EE, failover traps, how host 8090 is reached): [E4.2](../../../ENTERPRISE.md) · [How port 8090 is reached](../../../ENTERPRISE.md#how-port-8090-is-reached). Prefer this overlay over Helm when the goal is a LAN URL that stays up if one container dies. Prefer Helm `--ha-demo` when the audience is Kubernetes: [Compose versus Helm](../../../ENTERPRISE.md#compose-versus-helm).

Community Edition is the default. `GET /health` should show `enterprise_installed: false`. Enterprise is `--ee` and needs `rag-protection-enterprise/` checked out.

Stop whatever already owns host 8090 (single-replica Compose, Helm port-forward, or the other edition of this demo) before you start.

```bash
# CE
bash tools/docker_stop.sh --qdrant
bash tools/docker_ha_demo_start.sh
bash tools/docker_ha_demo_smoke.sh
bash tools/docker_ha_demo_failover.sh
bash tools/docker_ha_demo_stop.sh

# EE
bash tools/docker_stop.sh --ee --qdrant
bash tools/docker_ha_demo_start.sh --ee
bash tools/docker_ha_demo_smoke.sh
bash tools/docker_ha_demo_failover.sh
bash tools/docker_ha_demo_stop.sh --ee
```

Smoke execs into **proxy-a** and **proxy-b**; it does not trust nginx. Failover stops **a**; nginx should still serve via **b**. LAN clients use `http://<this-host-ip>:8090` (open inbound TCP 8090). Pass `--no-build` to skip rebuilding `:latest` / `:ee`.
