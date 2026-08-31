# CE deploy

Community Edition deploy artifacts. **Public MIT** at launch.

| Path | Role |
|------|------|
| [`../helm/rag-protection/`](../../docs/ce/README.md) | Baseline Helm chart |
| [`../siem/`](../siem/README.md) | #5 SIEM pack |

EE overlays that stay next to the chart as a **seam** (not EE source): `values-ee-local.yaml`. New EE-only deploy files go in [`../ee/`](../../ENTERPRISE.md).
