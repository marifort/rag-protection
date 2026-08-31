# Production scenarios

| Field | Value |
|-------|-------|
| **Audience** | Operators, platform engineers, security reviewers, GTM |
| **Classification** | Customer shareable |
| **Status** | Canonical for HTTP vs HTTPS vs HA decisions |
| **Architecture** | [PRODUCTION_ARCHITECTURE.md](PRODUCTION_ARCHITECTURE.md) |

This document walks through the situations people actually run. Each scenario states what the network looks like, whether HTTPS is required, whether high availability is in scope, and what to tell a reviewer. The architecture underneath all of them is the same: the proxy speaks **HTTP on port 8090**; production HTTPS is terminated at **customer ingress**; **full multi-replica HA is not shipped**. A named two-process demo slice exists ([E4.2](../../ENTERPRISE.md)); it is not an uptime SLA.

If you only need the topology diagram and the shared-responsibility split, start with the [architecture document](PRODUCTION_ARCHITECTURE.md). If you need to answer “do we turn on TLS for this environment?”, stay here.

---

## How to choose

Ask two questions, in order.

First: **does this traffic leave loopback, and is a real hostname involved?** If the client is on the same machine (`localhost`, CI on 127.0.0.1, `kubectl port-forward`), HTTP on 8090 is the documented path. If users, an IdP, or a browser will hit a DNS name, put HTTPS on the ingress (or the webhook URL) and leave the process on HTTP.

Second: **did a signed buyer name uptime, two pods, or failover as a pass/fail criterion?** If no, production HA is out of scope. Single replica plus their ingress is the production-like story. If they only need to *see* two pods with the same injection block, that is the named `--ha-demo` overlay, not an SLA. If they need unified audit and rolling deploys, that is remaining E4.2 under a time-boxed SOW.

OIDC is a third question. Live Okta or Azure AD is not required to sell or to run a local demo. It is wired on POC days using the [OIDC validation runbook](../../ENTERPRISE.md). Turning on OIDC does not replace ingress TLS, and ingress TLS does not replace OIDC.

---

## Local demo, tutorial, and developer loop

A laptop or workstation runs Compose or uvicorn. The operator console is `http://localhost:8090/ui`. Curls use `http://localhost:8090`. Demo bearer tokens (`employee-demo-token`, `hr-demo-token`, `rag-admin-demo-key`) are expected.

HTTPS is **not** required. The browser and the process share the machine. Adding certificates here creates friction without a security gain for the evaluation.

HA is **not** in scope. One process is the entire system.

This is the path in the CE and EE admin guides, tutorials, and learn catalogs. Do not “upgrade” a tutorial to HTTPS unless you are specifically rehearsing a customer ingress.

---

## Continuous integration

CI jobs start the proxy (or import the app in-process) and call HTTP on localhost. Tests assert guardrail verdicts, not certificates.

HTTPS is **not** required. HA is **not** required. Do not add TLS termination to the test matrix as a proxy for production readiness. Production readiness for transport is an ingress concern on the customer’s cluster.

---

## Kubernetes POC with port-forward

The Helm chart installs one proxy pod and a ClusterIP Service. The evaluator runs `kubectl port-forward svc/rag-protection 8090:8090` (or `bash tools/helm_port_forward.sh` on kind, which restarts if kubectl drops the stream) and uses `http://localhost:8090` exactly as in the local demo. [E1.5](../../ENTERPRISE.md) documents the chart; the from-scratch kind walkthrough (image load, Compose-parity EE, Qdrant Service selector, port-forward RST) is [KIND_HELM_LOCAL.md](../../ENTERPRISE.md).

HTTPS is **not** required. Port-forward is loopback from the operator’s machine into the cluster. The Service is not published to the internet.

HA is **not** in scope for the default chart. `replicaCount` remains 1. A pod restart that recovers the PVC is persistence, not failover of a second replica. The named `--ha-demo` overlay is a separate path (shared Qdrant, emptyDir, no JSONL).

This scenario answers “do you have Helm?” It does not answer “are you highly available?” and it does not answer “how do we put this on our corporate hostname?” Those are the staging and HA scenarios below. Prefer Compose unless someone asked for the chart: [KIND_HELM_LOCAL.md § Compose versus Helm](../../ENTERPRISE.md#compose-versus-helm). Leaving kind for AWS/EKS (chart + image, not a kind bundle): [kind-helm-aws.md](../../ENTERPRISE.md). The `--ha-demo` overlay still uses this ClusterIP Service (not nginx); laptop `:8090` is still port-forward — [E4.2 § How port 8090 is reached](../../ENTERPRISE.md#how-port-8090-is-reached).

---

## Staging or production hostname

The customer publishes a DNS name such as `rag-protection.customer.example`. Browsers, RAG applications, and (in EE) OAuth callbacks will use that name.

HTTPS **is** required at the edge. The customer enables their Ingress, Application Load Balancer, API gateway, or mesh, attaches their certificate, and forwards to the proxy Service on 8090. The Python process stays on HTTP.

```text
https://rag-protection.customer.example
        →  Ingress / ALB  (TLS terminates here)
        →  Service  rag-protection:8090  (HTTP)
        →  Pod
```

The Helm chart does **not** create that Ingress today. `ingress.enabled` defaults to false, `ingress.tls` is an empty placeholder, and there is no ingress template. Platform engineers add their standard ingress resource, or they wait for a chart contribution that still terminates TLS **outside** the app.

HA remains **out of scope** unless the buyer has named it. One pod behind HTTPS ingress is a valid production-like posture for a pilot. Do not silently set `replicaCount: 2`. The chart refuses that combination with sqlite/RWO. Use `values-ha-demo.yaml` or Docker `compose.ha-demo.yml` only when you intend the documented two-process demo slice.

Admin API keys and OIDC client secrets must not be the demo defaults. Use the production ACL file pattern (`acl_policy.prod.yaml`) and rotate credentials. That is configuration hygiene, not a TLS feature.

### From kind Helm to AWS/EKS

Kind does **not** emit a packaged AWS bundle (`helm package` tarball, OCI chart, or cluster snapshot). A green kind install answers “does the chart run?” The inputs you take to EKS are the **same Helm chart** (`deploy/helm/rag-protection/`) plus the **same container image**, pushed to ECR. `tools/helm_start.sh` and `values-ee-local.yaml` stay on the laptop.

**Reuse:** `Chart.yaml`, `values.yaml`, `templates/` (Deployment, ClusterIP `:8090`, PVC, probes, `component: proxy` Service selector), `Dockerfile` / `Dockerfile.ee`, Secret **key names** for admin/Drive/entitlements, `acl_policy.prod.yaml`, `replicaCount: 1`.

**Drop:** `kind load`, port-forward, Model Runner `hostAliases`, laptop `./data` seed, demo Auth0 in `acl_policy.yaml`, localhost OAuth redirects, `values-ha-demo.yaml` as a prod overlay.

**Add on AWS:** EKS, ECR push, ALB/Ingress + ACM, Secrets Manager → Kubernetes Secret, StorageClass (`gp3`), a real LLM URL, HTTPS IdP/Drive callbacks, network egress to JWKS/LLM/SIEM, a **customer** `values-eks-prod.yaml` (not shipped in the chart).

GKE and AKS use the same Helm contract; only the registry, ingress controller, and StorageClass names change. Artifact table (Preview-safe): [kind-helm-aws.md](../../ENTERPRISE.md). Keep/drop tables and example customer values: [KIND_HELM_LOCAL.md](../../ENTERPRISE.md) (Part 15).

---

## Operator console on a real URL

As soon as `/ui` is reachable on a hostname that is not loopback, the browser will send the admin bearer token (or an OIDC session) over that URL. That token authorizes policy reload, audit export, and (on EE) quarantine review.

HTTPS **is** required. Serving the console over HTTP on a corporate hostname is an unacceptable exposure of the admin credential.

The application does not need to learn HTTPS for this. The same UI is served from the proxy; the ingress provides the lock icon. Content-Security and cookie flags beyond that are customer edge policy.

Drive connectors and Pattern Lab do not change this rule. If the console is on a real URL, the URL is HTTPS.

---

## Audit webhook to a SIEM

The proxy can POST audit events to Splunk HEC, Datadog, or a generic HTTPS collector (`RAG_AUDIT_WEBHOOK_URL`). Retry and dead-letter behavior are shipped (E1.4). The SIEM pack onboards detections; it does not terminate TLS for inbound query traffic.

The webhook URL **must be `https://`** in any environment that is not a closed lab. The product is the HTTP *client* here. TLS is the SIEM vendor’s certificate, validated by the ordinary HTTPS stack in the proxy’s HTTP library.

This is independent of whether *inbound* query traffic is HTTPS. You can run a local demo on HTTP:8090 and still POST to an `https://` HEC endpoint. You can also run inbound HTTPS at ingress and a webhook to an internal HTTP collector; that last choice is the customer’s network policy.

HA is unrelated. A single replica with a reliable webhook is the shipped story. Multi-replica audit fan-in is an E4.2 concern (shared sink, no split files).

---

## Google Drive OAuth callback (production)

Live Drive ingest (EE) uses an OAuth redirect. Google (and every other honest IdP) will not accept `http://` callbacks on a public hostname. Localhost exceptions exist for development; production redirect URIs must be HTTPS.

Set `RAG_GOOGLE_*` client id, secret, and redirect URI to `https://<customer-host>/.../callback` (exact path as configured). The callback still lands on the proxy process via ingress → HTTP:8090. If OAuth fails in production, check redirect URI match, HTTPS, and client secret rotation before assuming a product bug. The EE admin troubleshooting table already lists this.

A Kubernetes POC that only uses Drive **fixtures** does not need a public HTTPS callback. Live OAuth does.

---

## Security questionnaire

Reviewers ask whether data is encrypted in transit, whether the vendor terminates TLS, and whether the system is highly available.

Answer encryption in transit as: **yes, in production, at customer ingress or service mesh**. The application listens on HTTP internally. This is the standard pattern for cluster workloads and is written into [SECURITY_POSTURE.md](../ce/README.md) and the EULA.

Answer native TLS in the application as: **not required and not implemented**. Shared responsibility. No in-app certificate rotation, because there is no in-app TLS.

Answer HA as: **single-replica is the supported deploy; multi-replica is planned (E4.2)**. Helm does not imply HA. Do not check “active-active multi-AZ” unless E4.2 has been contracted and delivered.

If the questionnaire is a SOC 2 Availability TSC demand, that is a product-gap conversation (P10 on the readiness checklist), not a weekend patch. Encryption-in-transit for Security TSC is the ingress model, which the customer implements.

---

## Paid pilot and design-partner POC

A two-week paid POC proves the **security control**: an unauthorized user cannot retrieve restricted documents; DLP redacts; injection is blocked; citations fail closed; audit export exists. The [POC SOW](../../ENTERPRISE.md) lists production HA as **out of scope**.

HTTPS: use whatever the customer already uses to publish an internal hostname, or stay on port-forward HTTP if the POC is confined to evaluators’ laptops. Do not block the POC on writing an ingress template.

HA: out of scope. One replica. If the champion asks “what about production?”, the honest sentence is that production HTTPS is their load balancer, and multi-replica HA is an Enterprise conversion / E4.2 item when they name an SLA.

Live Okta or Azure AD can be wired in the first days of the POC. Demo tokens remain valid for the wedge demo itself.

Do not implement native TLS or HA in order to start selling. Those are packaging items after a buyer names them as a blocker.

---

## Annual conversion when the buyer names an SLA

Some customers will not sign annual production without two pods, rolling deploys, or a stated availability target.

That is the trigger for [E4.2](../../ENTERPRISE.md): stateless replicas, shared policy, shared audit sink, shared vector backend. It is new engineering under a signed SOW with a time box. It is not a values-file change on the current chart.

TLS still terminates at their ingress. E4.2 does not move TLS into Python. The load balancer in front of several HTTP pods is still their load balancer.

Until that SOW is signed, keep saying full HA is planned. You may demo the named overlay as two processes + shared Qdrant + the same injection block: Helm `--ha-demo` on kind, or Docker `docker_ha_demo_start.sh` (CE default; `--ee` for Enterprise) on a LAN host without Kubernetes. Limitations and talk track: [E4.2](../../ENTERPRISE.md). Do not demo a forked `replicaCount: 2` on sqlite.

---

## SOC 2 Availability versus Security

If the company later claims SOC 2 **Availability**, an HA or failover guide is a gap (checklist P10). That claim is optional. Many self-hosted vendors certify Security (and Confidentiality) without Availability TSC.

**Security** encryption in transit is already described: TLS at customer ingress. That does not require E4.2.

Do not volunteer Availability TSC in order to look more mature. Volunteer the ingress TLS model and the single-replica honesty. Add HA documentation or software when you are actually going to claim Availability or when a customer pays for E4.2.

---

## Scenario map

| Situation | HTTPS? | HA? | Typical access |
|-----------|--------|-----|----------------|
| Local demo, tutorial, CI | No | No | `http://localhost:8090` |
| Helm POC via port-forward | No | No | `kubectl port-forward` → localhost:8090 |
| Staging / production hostname | Yes, at ingress | No, unless SOW | `https://hostname` → :8090 |
| Operator console on a real URL | Yes, at ingress | No, unless SOW | `https://hostname/ui` |
| Audit webhook to SIEM | Yes on the webhook URL | No | Proxy POSTs to `https://…` |
| Drive OAuth in production | Yes on the callback | No | IdP redirects to `https://…/callback` |
| Security questionnaire | Customer ingress | Planned E4.2 | Shared-responsibility language |
| Paid POC | Optional; often port-forward or their ingress | Out of scope | SOW already excludes production HA |
| Annual + named SLA | Ingress | Build E4.2 under SOW | Multi-pod only after that work |
| SOC 2 Availability TSC | Ingress (Security) | Needed only if you claim Availability | Do not volunteer the TSC |

---

## Language that stays honest

Use these sentences in demos, admin kickoffs, and questionnaires.

The gateway runs HTTP on an internal port. Production deployments terminate TLS at customer ingress. Identity uses standard OIDC/JWKS or demo tokens for evaluation.

The Helm chart packages a single replica for Kubernetes pilots by default. It is not a high-availability topology. A named two-process demo slice (`values-ha-demo.yaml` on kind, or `compose.ha-demo.yml` with nginx on Docker) shares Qdrant and proves verdict parity; unified audit and rolling deploys remain E4.2. Full prose: [E4.2](../../ENTERPRISE.md).

pgvector and Qdrant are storage backends. Connecting them successfully does not mean the proxy is highly available.

---

## Related documentation

| Need | Document |
|------|----------|
| Two-process demo vs remaining HA | [E4.2](../../ENTERPRISE.md) |
| Compact TLS table (internal) | [OSS licensing § When to apply TLS](../../ENTERPRISE.md#when-to-apply-tls) |
| Helm smoke path | [E1.5](../../ENTERPRISE.md) |
| Local kind + Helm (from scratch) | [KIND_HELM_LOCAL.md](../../ENTERPRISE.md) |
| OIDC on POC days | [OIDC_VALIDATION.md](../../ENTERPRISE.md) |
| Honest GTM FAQ | [GTM_HONEST_POSITIONING.md](../../ENTERPRISE.md#is-the-product-mature-enough-without-native-tls--ha) |
| EE stakeholder non-claims | [EE ADMIN_GUIDE § 23](../../ENTERPRISE.md#23-limitations-and-planned--stakeholder-table) |
