# Production architecture

| Field | Value |
|-------|-------|
| **Audience** | Platform engineers, security reviewers, operators, GTM |
| **Classification** | Customer shareable |
| **Status** | Canonical for HTTPS / TLS placement and HA honesty |
| **Companion** | [PRODUCTION_SCENARIOS.md](PRODUCTION_SCENARIOS.md) |

This document describes how Marifort Gate is meant to sit on a customer network. It is the architecture for **transport security and availability**, not the query pipeline. The ordered guardrail pipeline (identity → ACL retrieval → DLP → injection shielding → citation) lives in [architecture.md](architecture.md). How to choose HTTP versus HTTPS, and when high availability is in or out of scope, lives in the [scenario companion](PRODUCTION_SCENARIOS.md).

The product is a **self-hosted policy enforcement gateway**. It is not a load balancer, not a TLS terminator, not a WAF, and not a multi-region cluster. Those jobs belong to the customer’s existing platform. The gateway’s job is to enforce document-level access control and content guardrails on retrieval, ingest, and tool calls.

---

## What the software listens on

The proxy process serves **plain HTTP on port 8090**. That is true in local development, Docker Compose, and the Helm chart. There is no in-process TLS listener, no certificate store inside the Python app, and no plan to add one as a sales gate.

Encryption in transit for production is applied **in front of** the process. A browser, RAG client, or IdP callback talks HTTPS to the customer’s ingress (an ALB, nginx, API gateway, or service mesh). That ingress terminates TLS and forwards HTTP to the ClusterIP or container on 8090.

```text
Client, browser, IdP, SIEM
        │
        │  HTTPS  (customer certificate)
        ▼
Ingress / ALB / nginx / service mesh
        │
        │  HTTP   (cluster or private network)
        ▼
Marifort Gate  :8090
        │
        ├── document store (SQLite, Qdrant, or customer Postgres/pgvector)
        ├── LLM (customer or local Model Runner)
        └── audit JSONL / webhook
```

Inside a segmented cluster, HTTP between the proxy, the vector store, and the LLM can be acceptable. That choice is the customer’s network policy, not a product default. Admin bearer tokens in a browser on a real hostname still require HTTPS at the edge, because the token would otherwise travel in the clear.

---

## Three different problems

Security questionnaires often collapse three independent layers into one “is it production-ready?” question. They are not the same feature.

**Transport** is HTTPS. The customer terminates TLS at ingress. The proxy does not.

**Identity** is who the caller is. Demo tokens are enough for sales and local tutorials. OIDC (Okta, Azure AD) is shipped configuration: issuer, audience, JWKS. Live IdP wiring belongs on POC days, not as a prerequisite to outbound sales. Identity does not encrypt the wire.

**Availability** is whether a second replica can serve the same traffic with the same policy and a single audit trail. A **named two-process demo** (Helm `values-ha-demo.yaml`, or Docker `compose.ha-demo.yml` with nginx) proves two processes + shared Qdrant + the same injection verdict. That is not high availability: audit, quotas, and CHALLENGE queues stay per-process. Full HA is still planned (E4.2 remainder). A successful Helm install, a healthy `/health` response, or a working pgvector connection does **not** mean the deployment is highly available. A silent `replicaCount: 2` on sqlite is refused by the chart. Full prose: [E4.2](../../ENTERPRISE.md).

Treat a buyer question as one of these three. “Do you support TLS?” means point them at ingress. “Do you support Okta?” means the OIDC runbook. “We need two pods and no policy drift” means E4.2, scoped in a signed SOW, not implied by the chart.

---

## Shared responsibility

The software is designed to run **in the customer’s environment**. The EULA states that the customer owns the deployment environment, network security, TLS termination at ingress, identity-provider configuration, and backup of customer data. The product owns guardrail enforcement, audit event generation, and the APIs those controls use.

| Concern | Who | What that means |
|---------|-----|-----------------|
| TLS certificates, HTTPS listeners, WAF | Customer platform | Ingress in front of :8090 |
| Network segmentation | Customer platform | Who can reach 8090; east-west policy |
| IdP / group accuracy | Customer identity | OIDC claims and `allowed_groups` mapping |
| Proxy process, policy, ACL, guardrails | Product | HTTP service on 8090 |
| Document and vector storage | Customer (or chart PVC) | SQLite on a volume, Qdrant, or their Postgres |
| Audit file protection, SIEM sink, backups | Customer operations | Filesystem, webhook HTTPS URL, retention at the sink |
| Multi-replica HA / failover | **Partial** | Two-pod demo slice shipped; full E4.2 (shared audit, rolling deploy) planned. Do not infer from default Helm. |

Customer-shareable posture: [SECURITY_POSTURE.md](../ce/README.md). Questionnaire answers that mention encryption in transit should say **TLS at customer ingress or service mesh**, not “the application terminates TLS.”

---

## What is shipped today

Three install paths exist. They are the same binary and the same port. They are not three grades of production HA.

**Local process.** Developers run uvicorn (or the repo start scripts) on `http://localhost:8090`. Tutorials, CI, and the operator console on loopback use HTTP. That is correct: the traffic never leaves the machine.

**Docker Compose.** `bash tools/docker_start.sh` (add `--ee` for Enterprise) publishes the proxy on host port 8090. Persistence is a Docker volume. This is the demo and workshop path. It is not a production topology.

**Helm / Kubernetes (E1.5).** The chart at `deploy/helm/rag-protection/` deploys a single proxy pod, a ClusterIP Service on 8090, and a PVC for `/data` (SQLite plus audit JSONL). Optional in-cluster Qdrant is a values flag. Health probes hit `GET /health`. The documented smoke path is `kubectl port-forward` (on kind, `tools/helm_port_forward.sh`) to localhost:8090, then curl and the UI. That is a **Kubernetes POC pack**, not a production HTTPS topology. Local cluster create, image load, Compose-parity EE, and failure modes: [KIND_HELM_LOCAL.md](../../ENTERPRISE.md). On kind, Drive/entitlement secrets come from repo-root `.env` into a Secret; `RAG_STORE_BACKEND` and other non-secret knobs come from Helm values, not from `.env` — [KIND_HELM_LOCAL.md](../../ENTERPRISE.md) (Part 6: Where env lives).

**Which path to prefer.** Neither Compose nor Helm is a better product. Prefer Compose for daily work, workshops, and the operator UI on a laptop. Prefer Helm when a platform team asked for the chart, or when the destination is a customer cluster behind their ingress. For the named two-process demo, Compose nginx holds host 8090 if one container dies; Helm uses a ClusterIP Service and a port-forward that may drop. Decision table: [KIND_HELM_LOCAL.md § Compose versus Helm](../../ENTERPRISE.md#compose-versus-helm). How 8090 is actually reached on each HA overlay: [E4.2 § How port 8090 is reached](../../ENTERPRISE.md#how-port-8090-is-reached).

Helm defaults that matter:

- `replicaCount: 1`
- `ingress.enabled: false`
- `ingress.tls: []`
- There is **no** `ingress.yaml` template in the chart. The TLS values are a placeholder. The OSS deployment guide records this as “ingress template TBD.”

A platform team that wants a real hostname puts **their** Ingress or ALB in front of the Service, attaches **their** certificate, and leaves the pod on HTTP. The chart does not do that for them.

Enterprise Edition is additive on the same process and port. Installing the EE wheel does not change TLS placement or replica count. pgvector is a store backend that requires customer Postgres; connecting to Postgres is not high availability.

---

## State inside one process

High availability is not a `replicaCount` bump because several important pieces of state are process-local today.

Policy is loaded into memory from files (`policy.yaml`, ACL files). Reloading policy updates that process. A second pod would not automatically share the same in-memory policy unless both read the same mounted files and you accept reload timing as a consistency window — which is exactly the gap E4.2 is meant to close with a shared policy cache or ConfigMap watch.

The audit ring buffer is per-process. Durable audit is the JSONL file (`RAG_AUDIT_FILE`) and optional HTTPS webhook. Two pods appending to a local disk without a shared volume will split history. Two pods with uncoordinated writes to the same file need locking or a webhook-only design; that is planned, not shipped.

The default document store is SQLite on the PVC. SQLite on `ReadWriteOnce` storage is a single-writer design. Production-like retrieval already supports Qdrant or EE pgvector as shared backends; those backends are necessary for multi-replica but not sufficient by themselves.

Per-tenant rate limits (E4.5) are enforced in the process that handled the request. They do not make the service HA. Shared limiting across replicas is part of the planned HA architecture.

This is why admin and developer guides say: do not infer HA readiness from a successful database connection, a green Helm install, or a passing health check.

---

## Intended production topology (single replica)

A production-like annual deployment, **without** claiming HA, looks like this.

The customer places the proxy (CE, or CE plus EE) in their cluster or VM network. A single replica is the honest default. Ingress terminates HTTPS and forwards to 8090. OIDC is pointed at the customer’s IdP; the redirect and issuer URLs are HTTPS. Drive OAuth, if used, has an HTTPS callback on the public hostname. Audit webhooks, if used, are `https://` URLs to Splunk, Datadog, or a similar sink. The operator console is served at `https://<hostname>/ui`. Postgres or Qdrant, if used, is the customer’s managed service or in-cluster store. Backup and DR of volumes, databases, and audit files are customer operations.

That topology is **documented intent plus customer ingress**. It is not a second product SKU. It does not require native TLS in Python. It does not require E4.2.

Paid pilots and POC statements of work already list **production HA as out of scope**. The POC proves the security control (ACL, DLP, injection, citation, audit). TLS sits at the load balancer. HA is an Enterprise conversion item when the buyer names an uptime SLA or “two pods with no drift.”

---

## Planned: full multi-replica HA (E4.2 remainder)

[E4.2](../../ENTERPRISE.md) is the design for stateless proxy replicas behind a load balancer, sharing policy, a durable audit sink, and a vector backend so two pods return the same guardrail verdict.

The **two-process demo slice is shipped** on Helm (`values-ha-demo.yaml`) and on Docker without Kubernetes (`compose.ha-demo.yml`, nginx on host 8090). Chart `fail()` if you only bump `replicaCount`. `GET /health` exposes `policy_version`. Smoke hits each process, not the load balancer. It is **not** current production HA. Do not describe it in demos as “we have HA.” Do not treat `replicaCount: 2` on sqlite as product HA. Community Edition is the Docker default; `--ee` is opt-in.

Until the remainder ships, the correct sentence is: two processes can share Qdrant and return the same injection block; production HTTPS is terminated at customer ingress; unified audit, policy broadcast, and rolling zero-downtime are still E4.2. Full prose: [E4.2](../../ENTERPRISE.md).

SOC 2 **Availability** trust criteria would also need an HA or failover story. Encryption in transit for the **Security** criteria is the ingress TLS model above. Those are different checkboxes. See [SOC2_READINESS_CHECKLIST.md](../ce/README.md).

---

## What not to claim

Do not say the product “has HTTPS” if that means the Python process speaks TLS. Say production deployments terminate TLS at customer ingress.

Do not say Helm or Kubernetes means high availability. Say the default chart packages a single replica for cluster POCs. The named `--ha-demo` overlay (Helm or Docker) is two processes plus shared Qdrant with listed limits, not E4.2.

Do not say pgvector, Qdrant, or a PVC implies failover. Shared storage is a prerequisite for a future HA design, not HA itself.

Do not promise multi-region, active-active, or zero-downtime rolling deploys as current capability.

Do not treat a security questionnaire line about “encryption in transit” as a feature request to implement TLS in-app. Point to this document and the customer’s ingress.

---

## Related documentation

| Need | Document |
|------|----------|
| When to use HTTP vs HTTPS, and when HA is in scope | [PRODUCTION_SCENARIOS.md](PRODUCTION_SCENARIOS.md) |
| Guardrail pipeline and threat model | [architecture.md](architecture.md) |
| Helm chart behavior | [E1.5 Helm / K8s](../../ENTERPRISE.md) |
| Compose vs Helm (which to prefer) | [KIND_HELM_LOCAL.md § Compose versus Helm](../../ENTERPRISE.md#compose-versus-helm) |
| How two replicas share :8090 | [E4.2 § How port 8090 is reached](../../ENTERPRISE.md#how-port-8090-is-reached) |
| Local kind + Helm (from scratch) | [KIND_HELM_LOCAL.md](../../ENTERPRISE.md) |
| Kind chart → AWS/EKS (chart + image, not a kind bundle) | [kind-helm-aws.md](../../ENTERPRISE.md) |
| Planned replicas | [E4.2](../../ENTERPRISE.md) |
| TLS decision table (internal/GTM) | [OSS licensing § When to apply TLS](../../ENTERPRISE.md#when-to-apply-tls) |
| Customer posture / shared model | [SECURITY_POSTURE.md](../ce/README.md) |
| EE operator non-claims | [EE ADMIN_GUIDE § Limitations](../../ENTERPRISE.md#23-limitations-and-planned--stakeholder-table) |
| Pilot vs conversion | [FOUNDER_DASHBOARD § Pilot readiness](../../ENTERPRISE.md#pilot-readiness-what-you-do--dont-need-to-sell) |
