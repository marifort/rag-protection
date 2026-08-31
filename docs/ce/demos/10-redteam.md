# Demo: #10 — Red-team harness

**~5 minutes.** Run all scenarios → open executive report.

**Feature:** [../features/10-redteam.md](../features/10-redteam.md) · **Tutorial:** [T05](../tutorials/05-labs-2-through-5.md) · [T08 §16](../../../ENTERPRISE.md#part-16--lab-5-packaged-red-team-harness-rank-1)

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

tools/rag-redteam run --all \
  --base-url http://localhost:8090 \
  --out /tmp/rt-demo \
  --engagement "acme-staging-demo"

less /tmp/rt-demo/report.md
```

Full: [lab5 DEMO](../../../ENTERPRISE.md).
