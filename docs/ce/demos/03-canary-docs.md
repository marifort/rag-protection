# Demo: #3 — Canary / honeypot documents

**~5 minutes.** Seed a canary, trip retrieval, show scrub + P1 `canary_triggered` event.

**Feature reference:** [../features/03-canary-docs.md](../features/03-canary-docs.md) · **Tutorial:** [T09 §B](../tutorials/09-implemented-features-walkthrough.md#part-b-canary-honeypot-documents-lab-10-3) · **UI:** [lab10 UI_TESTING](../../../ENTERPRISE.md)

---

## 0. Setup (off camera)

Arm the trap **before** the demo query. `export RAG_CANARY_ENABLED=1` in a client shell does **not** change a server already running.

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

# Set canary.enabled: true in data/policy.yaml, then:
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq .
```

Alternative: `RAG_CANARY_ENABLED=1` in `.env` **before** `docker_start.sh`.

---

## 1. Seed a canary (45 sec)

```bash
# Pure tripwire: __canary__ group — only surfaces on ACL failure
curl -s -X POST http://localhost:8090/admin/canary/seed \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "2099 Executive Compensation — RESTRICTED"}' | jq '.'

curl -s http://localhost:8090/admin/canary/list \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.'
```

---

## 2. Trip the tripwire (60 sec)

Seed a **reachable honeypot** (demo user has `engineering` group):

```bash
curl -s -X POST http://localhost:8090/admin/canary/seed \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "Zephyr Phantom Ledger",
       "body": "zephyrphantom ledger quokka canary marker xyzzyq",
       "allowed_groups": ["engineering"]}' | jq -r '.document_id'

curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query": "zephyrphantom quokka xyzzyq ledger", "top_k": 4}' \
  | jq '{answer, chunks: [.chunks[].document_id]}'
```

**Expected:** canary `document_id` **absent** from `chunks` — scrubbed before context.

---

## 3. Show P1 event (45 sec)

```bash
curl -s "http://localhost:8090/admin/audit/events?kind=canary_triggered" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.events[0]'
```

**Expected:** `decision: "block"`, `risk_score: 1.0`, `source: "retrieval.canary"`.

---

## 4. Retire (30 sec)

```bash
curl -s -X POST http://localhost:8090/admin/canary/retire \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "<doc_id_from_step_2>"}' | jq '.'
```

Auditor bypass: subjects in `canary.auditor_subjects` / `auditor_groups` retrieve without tripping.

---

## 5. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_canary.py -q
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Canary in `chunks`, no audit event | Trap not armed — `canary.enabled: true` + reload or restart |
| `export RAG_CANARY_ENABLED=1` did nothing | Env applies only to **new** server processes |
| Hits without bait query; Documents has no matching id | [Operator notes](../features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows) |

---

## Close

Pair with **#2 extraction**: canary hit + high extraction score = high-confidence exfil alarm, shown in `/ui` as **Suspected data theft**. Combined curl + UI sample: [exfil-correlation DEMO_SCRIPT](../../../ENTERPRISE.md). Both export to **#5 SIEM**.
