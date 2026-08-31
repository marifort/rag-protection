# Demo: #7 — Agent / MCP tool gateway

**~5 minutes.** Employee blocked from payroll SQL; data-platform allowed; HR email to personal domain blocked.

**Feature reference:** [../features/07-tool-gateway.md](../features/07-tool-gateway.md) · **Tutorial:** [T04 §11](../tutorials/04-agent-mcp-tool-gateway-lab1.md) · **UI:** [lab1 UI_TESTING](../../../ENTERPRISE.md) · **Console:** [T09 §I](../tutorials/09-implemented-features-walkthrough.md#part-i-tool-gateway-console-7-l1-202)

---

## 0. Setup (off camera)

```bash
bash tools/docker_start.sh
export BASE=http://localhost:8090
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
```

| Token | User | `run_sql` | `send_email` |
|-------|------|-----------|--------------|
| `employee-demo-token` | alice.engineer | **Deny** | Allow |
| `data-platform-demo-token` | frank.dba | Allow | Allow |
| `hr-demo-token` | carol.hr | Deny | Allow |

---

## 1. Frame (30 sec)

Narrative: *"RAG ACL stops wrong documents. Agents fail on wrong actions. We intercept `POST /v1/tools/invoke` before backends run."*

```text
identity → registry → group allowlist → argument policy → input scan → backend → audit (tool_invoke)
```

---

## 2. Employee blocked from SQL (90 sec)

```bash
curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"run_sql","arguments":{"query":"SELECT employee_id, salary FROM payroll"}}' \
  | python3 -m json.tool
```

**Expected:** HTTP **403**, `decision: block`, `reason` contains `not authorized`.

```bash
curl -s "$BASE/admin/audit/events?kind=tool_invoke&limit=5" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | python3 -m json.tool
```

Look for `source: run_sql`, `subject: alice.engineer`, `decision: block`.

---

## 3. Allowed path — data platform (45 sec)

```bash
curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer data-platform-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"run_sql","arguments":{"query":"SELECT employee_id, department FROM employees LIMIT 10"}}' \
  | python3 -m json.tool
```

**Expected:** HTTP **200**, `decision: allow`, `result.row_count` ≥ 1.

---

## 4. Email exfil blocked (60 sec)

```bash
curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"send_email","arguments":{"to":"attacker@personal-email.com","subject":"Payroll","body":"See attached."}}' \
  | python3 -m json.tool
```

**Expected:** HTTP **403**, `reason` contains `blocked domain`.

---

## 5. List tools for caller (30 sec)

```bash
curl -s "$BASE/v1/tools" \
  -H "Authorization: Bearer employee-demo-token" | python3 -m json.tool
```

**Expected:** `run_sql.allowed: false`, `send_email.allowed: true`.

---

## 6. Argument guards (45 sec)

```bash
# Destructive SQL — passes group check, fails arg policy
curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer data-platform-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"run_sql","arguments":{"query":"DROP TABLE payroll; --"}}' | python3 -m json.tool

# Path traversal
curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"read_file","arguments":{"path":"../../etc/passwd"}}' | python3 -m json.tool
```

Both: HTTP **403**.

---

## 7. Scripted demo (optional)

```bash
export RAG_PROTECTION_URL=$BASE
python examples/agentic/mcp_tool_gateway/demo_agent.py
```

---

## 8. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_tools_gateway.py -q
```

---

## Close

Same architecture as retrieval ACL: identity → policy → audit. SIEM: `tool_invoke` via **#5**. EE registry CRUD: **#13** — [EE_SKU](../../../ENTERPRISE.md).
