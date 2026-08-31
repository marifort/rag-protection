# Demo: #1 — ACL + 4-guardrail pipeline

**~5 minutes.** Employee cannot retrieve payroll; HR can. See injection / DLP / citation in T01.

**Feature:** [../features/01-acl-pipeline.md](../features/01-acl-pipeline.md) · **Tutorial:** [T01](../tutorials/01-getting-started-and-guardrails.md)

```bash
bash tools/docker_start.sh --smoke

# Engineer — no payroll chunks
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?"}' \
  | jq '{chunks: [.chunks[].document_id], blocked}'

# HR — payroll retrieved
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?"}' \
  | jq '{chunks: [.chunks[].document_id]}'
```

Full walkthrough: [T01](../tutorials/01-getting-started-and-guardrails.md).
