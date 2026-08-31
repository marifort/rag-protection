# How clients use RAG Protection (Plain English)

**Audience:** Buyers, evaluators, platform engineers, security operators, and anyone who needs to explain *how* customers consume the product — via API, Python, and UI — for both RAG and MCP security.  
**Style:** Full prose. Plain English. Links point to depth docs; this page is the narrative spine.  
**Related:** [PRODUCT_OBJECTIVE.md](../ce/README.md) (why) · [HOW_RAG_WORKS.md](HOW_RAG_WORKS.md) (what RAG / augmentation / embeddings / extraction ratios are) · [COMMERCIAL_SUMMARY.md](../../ENTERPRISE.md) (shareable overview) · [ce/guide/USER_GUIDE.md](../ce/guide/USER_GUIDE.md) (day-to-day CE ops) · [INTEGRATIONS.md](INTEGRATIONS.md) (LangChain / scan patterns) · [ce/learn/00-study-path.md](../ce/learn/00-study-path.md) (curriculum)

---

**Clients use RAG Protection as a security gateway in front of chat-over-documents and agent tool calls.** They do not replace their chatbot, vector database, language model, or MCP servers with it. They route questions and tool invokes through the proxy so identity, policy, scanning, and audit apply in one place. In plain English, the product’s job is to stop company AI from seeing, saying, or leaking things people are not allowed to see—and to prove what happened with an audit trail. That objective is written out in [PRODUCT_OBJECTIVE.md](../ce/README.md); a shareable overview for security and procurement is [COMMERCIAL_SUMMARY.md](../../ENTERPRISE.md). If you want a guided curriculum instead of the whole docs tree, start with [ce/learn/00-study-path.md](../ce/learn/00-study-path.md).

---

## What the product is doing

Think of it as a guarded records desk for AI. When someone asks a question over company documents, the gateway figures out who they are, searches only documents that person is allowed to see, cleans or blocks risky text, asks the model for an answer, checks that the answer is grounded in those sources, and writes an audit record. When an agent wants to run a tool—read a file, send email, run SQL—the same identity and policy model decides whether that action is allowed before anything happens on the backend. That second path is the MCP / agent tool gateway.

The important design choice is that the language model never talks to the document store directly. The gateway owns retrieval and safety for RAG, and owns allow, deny, or challenge for tools. That choice is spelled out in [PRODUCT_OBJECTIVE.md](../ce/README.md) and [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md).

On the RAG path, the ordered pipeline is documented under [ce/security/README.md](../ce/security/README.md): identify the user, scan the question, retrieve only allowed documents, scan those chunks, isolate untrusted context from system instructions, call the LLM, verify citations, scan the answer, and audit. Depth for each layer lives in [GUARDRAIL_1_ACL.md](../ce/security/GUARDRAIL_1_ACL.md), [GUARDRAIL_2_DLP.md](../ce/security/GUARDRAIL_2_DLP.md), [GUARDRAIL_3_INJECTION.md](../ce/security/GUARDRAIL_3_INJECTION.md), and [GUARDRAIL_4_CITATION.md](../ce/security/GUARDRAIL_4_CITATION.md), with P1/P2 extensions such as [P1_USER_QUERY_GUARDRAILS.md](../ce/security/P1_USER_QUERY_GUARDRAILS.md), [P1_INGEST_SECURITY.md](../ce/security/P1_INGEST_SECURITY.md), [P1_CHALLENGE_MODE.md](../ce/security/P1_CHALLENGE_MODE.md), and [P2_PERSISTENT_AUDIT.md](../ce/security/P2_PERSISTENT_AUDIT.md). The feature card for this core wedge is [#1 ACL + pipeline](../ce/features/01-acl-pipeline.md); the teach-in-plain-English entry is [learn #1](../ce/learn/01-core-moats.md#1-document-level-acl--4-guardrail-pipeline).

On the agent path, the failure mode shifts from wrong *documents* in context to wrong *actions* executed—over-scoped service accounts, email exfiltration, or poisoned tool descriptions. Feature [#7](../ce/features/07-tool-gateway.md) applies the same badge-desk pattern to `POST /v1/tools/invoke`. Engineering depth is in [commercial/labs/lab1-mcp/ARCHITECTURE.md](../../ENTERPRISE.md); the teach entry is [learn #7](../ce/learn/01-core-moats.md#7-agent--mcp-tool-gateway-acl).

---

## Getting a stack running

Most client journeys assume a local or staging proxy. The root [README.md](../../README.md) and [TUTORIAL.md](TUTORIAL.md) point to starting with Docker (`bash tools/docker_start.sh`, optionally `--smoke`), checking health at `http://localhost:8090/health`, and opening the console at `http://localhost:8090/ui`. Demo user tokens such as `employee-demo-token` and `hr-demo-token`, and the admin key `rag-admin-demo-key`, are listed in the tutorial index. Day-to-day Community Edition use is [ce/guide/USER_GUIDE.md](../ce/guide/USER_GUIDE.md); admin settings and the pytest matrix sit in [ce/guide/ADMIN_SETTINGS_AND_TESTS.md](../ce/guide/ADMIN_SETTINGS_AND_TESTS.md). Hands-on RAG first steps are [tutorial/01](../ce/tutorials/01-getting-started-and-guardrails.md); console, ingest, and audit are [tutorial/02](../ce/tutorials/02-operator-console-ingest-and-audit.md). Compose overlays for CE, EE, and MCP are in [commercial/COMPOSE_OVERLAYS.md](../../ENTERPRISE.md).

---

## RAG security — how a client uses it

### Through the API

The everyday production path is **`POST /v1/query`**. The client app sends a bearer token for the end user and a natural-language question. The proxy runs the full secured pipeline and returns an answer, or a safe block or fallback, plus optional audit detail. That “gateway owns retrieval and the model call” shape is **Pattern A** in [INTEGRATIONS.md](INTEGRATIONS.md) and the E7 hub [ee/phases/E7_FRAMEWORK_INTEGRATIONS.md](../../ENTERPRISE.md). Optional flags such as `include_audit` and retrieval-trace knobs are listed in the [TUTORIAL.md](TUTORIAL.md) endpoint table and walked through in the user guide.

Operators load documents with **`POST /v1/ingest`** using an admin token, tagging each document with which groups may see it. Before text becomes searchable, ingest runs the same scanners used on queries; poisoned or high-risk content is rejected or quarantined—held out of search until an operator disposes or remediates it. That path is [P1_INGEST_SECURITY.md](../ce/security/P1_INGEST_SECURITY.md) and feature [#15](../ce/features/15-ingest-quarantine.md). Listing what a given user may see uses **`GET /v1/documents`**.

Teams that already own Pinecone or another vector database often use **Pattern C**: call **`POST /v1/scan`** at ingest for DLP and injection checks, then embed and store themselves, and enforce `allowed_groups` in their own search path. The scan contract is [ee/phases/e7/E7_1_SCAN_API.md](../../ENTERPRISE.md); LangChain and Pinecone wiring is [E7_2_LANGCHAIN_PINECONE.md](../../ENTERPRISE.md). **Pattern B** in INTEGRATIONS.md is ingest into the proxy’s own corpus and then query—useful for demos without an external vector product. In practice, most POCs start with Pattern A; Pattern C is for buyers who insist on keeping their existing store.

Concrete curl journeys—ACL deny for an engineer and allow for HR on the same payroll question, injection block, citation fallback—are in [USER_GUIDE.md](../ce/guide/USER_GUIDE.md). Architecture and pipeline diagrams live in [ARCHITECTURE.md](../ce/README.md) and [shared/architecture.md](../shared/architecture.md). A five-minute ACL demo script is [ce/demos/01-acl-pipeline.md](../ce/demos/01-acl-pipeline.md).

### Through the Python interface

There is not yet a separate published PyPI security SDK. The shipped client surface is the thin HTTP wrapper [examples/python/rag_protection_client.py](../../examples/python/rag_protection_client.py). A platform team points it at the proxy URL, sets a user token for questions and an admin key for ingest or scan, then calls `query`, `ingest`, `scan`, and `health` from their app or scripts instead of hand-writing curl. That is the E7.3 client surface described in INTEGRATIONS.md: same endpoints, friendlier for code.

For LangChain shops, [examples/langchain/README.md](../../examples/langchain/README.md) goes further. One script, [full_gateway_query.py](../../examples/langchain/full_gateway_query.py), sends the whole question through the gateway (Pattern A). Another, [byo_pinecone_ingest.py](../../examples/langchain/byo_pinecone_ingest.py), together with [transformers.py](../../examples/langchain/transformers.py) (`RAGProtectionScanTransformer`), calls `scan` per document before documents go into Pinecone (Pattern C). Tutorial coverage is in [ce/tutorials/03-extensions-troubleshooting-and-integrations.md](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md). Docker sidecar layout—proxy beside the app on a shared Compose network—is in the E7.2 guide. Adjacent Python CLIs such as posture scoring and config scanning are for platform and DevSecOps rather than the chat path; see [ce/learn/03-tools-and-assessment.md](../ce/learn/03-tools-and-assessment.md) and [tutorial/06](../ce/tutorials/06-labs-a2-a3-a6-a7.md).

So “Python library” here means a thin client and LangChain adapters over the HTTP API, not a second security engine running inside the customer process.

### Through the UI

Operators open **http://localhost:8090/ui**, set an admin bearer and a user bearer in the toolbar, and work in the Community Edition workspaces described in [USER_GUIDE.md](../ce/guide/USER_GUIDE.md) and [console/README.md](../../console/README.md). Console CE versus EE architecture is [CONSOLE_CE_EE_UI_ARCHITECTURE.md](../ce/README.md).

**Query Lab** is the human face of `/v1/query`. Pick a demo user—for example an engineer versus HR—ask the same payroll question, and see ACL deny versus allow, DLP redaction, injection blocks, and citation failures without writing code. Enable include-audit or retrieval explainability when you need forensics. The chunks panel shows retrieved document text and scan status; it does **not** display the XML-isolated prompt `context_builder.py` packs for the LLM ([HOW_RAG_WORKS.md](HOW_RAG_WORKS.md#what-the-operator-ui-shows-and-does-not-show)). That maps to features [#1](../ce/features/01-acl-pipeline.md), citation [#8](../ce/features/08-citation-hard-gate.md), and retrieval trace [#11](../ce/features/11-retrieval-trace.md).

**Documents & Ingest** is how they load and manage the corpus and see quarantine metadata. On CE they can dispose or re-ingest; full content preview and approve-in-place is an Enterprise workflow ([ee/features/15-quarantine-review.md](../../ENTERPRISE.md)), as called out in USER_GUIDE §9.

**Audit Log** is where they review allow, block, and challenge events, open findings, export NDJSON, and—when enabled—verify the integrity chain. That is feature [#9](../ce/features/09-audit-integrity.md), with depth in [P2_PERSISTENT_AUDIT.md](../ce/security/P2_PERSISTENT_AUDIT.md) and [P2_AUDIT_DEBUG_FORENSICS.md](../ce/security/P2_AUDIT_DEBUG_FORENSICS.md). A multi-feature UI walkthrough is [ce/tutorials/09-implemented-features-walkthrough.md](../ce/tutorials/09-implemented-features-walkthrough.md).

Day to day, security and platform people prove behavior in the UI; application teams wire the same behavior into production via the API or Python client.

---

## MCP / agent security — how a client uses it

### Through the API

Agents should not call MCP backends with a god-mode service account. They call the tool gateway: **`GET /v1/tools`** to see which tools this caller may use, and **`POST /v1/tools/invoke`** with the tool name and arguments under the end user’s bearer. The gateway resolves identity, checks the tool registry and policy—who may use which tool, argument size, patterns, and domains—scans tool descriptions and inputs for injection and secrets, applies risk thresholds (allow, challenge, or block), and only then talks to a mock backend or a real MCP server. Every decision becomes a `tool_invoke` audit event.

That pipeline is the core of [07-tool-gateway.md](../ce/features/07-tool-gateway.md) and [lab1-mcp/ARCHITECTURE.md](../../ENTERPRISE.md). Policy lives in YAML (`tool_policy.yaml`); admins reload with `POST /admin/reload-policy`. Mid-risk invokes use **CHALLENGE** mode ([P1_CHALLENGE_MODE.md](../ce/security/P1_CHALLENGE_MODE.md), lab [CHALLENGE_QUEUE.md](../../ENTERPRISE.md)): fail-closed by default, or hold for human approve or deny when `challenge_mode: allow`.

**Layer 1** uses mock backends for demos. **Layer 2** adds a real MCP filesystem backend when you start with `bash tools/docker_start.sh --mcp-tools`. The layer split and smoke tests are [MCP_INTEGRATION_LAYERS.md](../../ENTERPRISE.md) and [LAYER2_MCP_RUNBOOK.md](../../ENTERPRISE.md). Hands-on curls and steps are [ce/tutorials/04-agent-mcp-tool-gateway-lab1.md](../ce/tutorials/04-agent-mcp-tool-gateway-lab1.md) and [learn #7](../ce/learn/01-core-moats.md#7-agent--mcp-tool-gateway-acl). The test plan is [qa/test-plans/LAB1_TEST_PLAN.md](../../ENTERPRISE.md). Example agent code is under [examples/agentic/mcp_tool_gateway/](../../examples/agentic/mcp_tool_gateway/README.md). Enterprise extends this with a tool registry ([#13](../../ENTERPRISE.md)).

### Through the Python interface

The same [rag_protection_client.py](../../examples/python/rag_protection_client.py) exposes `list_tools` and `invoke_tool`, so a demo agent or production orchestrator can list and invoke under the user’s token and treat a policy block as a structured decision rather than a mysterious HTTP failure. The Lab 1 demo agent shows the pattern end to end: agent → gateway → backend.

Separately, teams can run **mcp-lint** ([tools/mcp_lint/README.md](../../tools/mcp_lint/README.md)) against an MCP server’s tool manifest before go-live. It statically flags dangerous or over-broad tool descriptions—shift-left review that complements runtime enforcement on invoke. The lab pack is under [commercial/labs/lab7-mcp-lint/](../../ENTERPRISE.md); tutorial coverage is in [06-labs-a2-a3-a6-a7.md](../ce/tutorials/06-labs-a2-a3-a6-a7.md). The intended pairing is simple: lint the manifest first, then enforce at invoke through the gateway.

### Through the UI

The **Tool Gateway** workspace is mainly for operators. As [USER_GUIDE.md §5](../ce/guide/USER_GUIDE.md) and [learn #7](../ce/learn/01-core-moats.md#7-agent--mcp-tool-gateway-acl) make clear, it shows a read-only policy summary for the selected caller and, when configured, the challenge queue for mid-risk held invokes. It is not a general-purpose form for clicking arbitrary MCP tools. Day-to-day list and invoke stay API-first—agents and scripts call `/v1/tools/invoke`—while the console is where security reviews who can do what and clears held actions. Those tool events also show up in **Audit Log**, so RAG queries and MCP invokes share one investigation surface. A short show script is [ce/demos/07-tool-gateway.md](../ce/demos/07-tool-gateway.md); the console walkthrough for #7 is in [tutorial/09](../ce/tutorials/09-implemented-features-walkthrough.md).

---

## How a typical client stitches it together

They deploy the proxy next to their app—often Docker, with EE and MCP overlays as needed. Identity starts as demo tokens in evaluation, then JWT or OIDC in a real deployment ([tutorial/03](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md), [ee/runbooks/OIDC_VALIDATION.md](../../ENTERPRISE.md)). Chat UIs and backends send user questions to `/v1/query`, or through the Python and LangChain wrappers. Agent runtimes send tool calls to `/v1/tools/invoke` with the **same user identity**, so document ACL and tool ACL stay aligned: an engineer’s agent session cannot read HR payroll through chat *or* through a “search policies” or `read_file` tool. Security and compliance live in the console—Query Lab and Tool Gateway for demos and ops, Audit Log for incidents and evidence, optionally shipping detections to SIEM via [#5](../ce/features/05-siem-pack.md). Developers stay on API and Python; operators and SOC stay on the UI; both paths enforce the same policies and write the same audit trail ([#9](../ce/features/09-audit-integrity.md)).

In short: **RAG security** is “ask only over documents you’re allowed to see, with DLP, injection shielding, citations, and audit.” **MCP security** is “run only tools you’re allowed to run, with the same identity, scanners, challenge, and audit.” Clients reach both through HTTP APIs, the Python client and LangChain examples, and the operator console—each suited to apps, agents, and humans respectively.

A sensible reading order if you are implementing this is [TUTORIAL.md](TUTORIAL.md) parts 01 → 02 → 03 for RAG, UI, and integrations, then part 04 for the MCP gateway, then feature cards [#1](../ce/features/01-acl-pipeline.md) and [#7](../ce/features/07-tool-gateway.md), opening [ce/security/](../ce/security/README.md) only when you need to debug a guardrail. The shipped capability index is [INDEX.md](../INDEX.md) / [ce/FEATURE_CATALOG.md](../ce/FEATURE_CATALOG.md).

---

## Document control

| Field | Value |
|-------|-------|
| Purpose | Plain-English narrative of how clients use RAG and MCP security via API, Python, and UI |
| Status | Active |
| Complements | [PRODUCT_OBJECTIVE.md](../ce/README.md) (why) · [USER_GUIDE.md](../ce/guide/USER_GUIDE.md) (ops steps) · [INTEGRATIONS.md](INTEGRATIONS.md) (patterns A–C) · [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md) (rerank/HyDE vs guardrails/citations) |
