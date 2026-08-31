# Artifacts kind / Helm produce for AWS

This file sits next to the chart so Cmd+click from `values.yaml` can open a real markdown page. Cursor does not resolve a repo-root path such as `docs/ee/runbooks/…` from this folder.

**Canonical runbook (Cmd+click in the source editor):** [KIND_HELM_LOCAL.md](../../../ENTERPRISE.md)

Same-folder docs hop for E1.5 Preview: [kind-helm-aws.md](../../../ENTERPRISE.md)

In the runbook, use the Summary table → **Part 15 — Cloud (AWS / EKS) vs kind**. Direct section ids: `#part-15-aws` · `#artifacts-for-aws`.

---

Kind does **not** emit a packaged AWS bundle. Take the **chart in this directory** (`Chart.yaml`, `values.yaml`, `templates/`) and the **same container image** (`Dockerfile` / `Dockerfile.ee`), pushed to ECR. Do **not** take `tools/helm_start.sh`, `values-ee-local.yaml`, `kind load`, or port-forward as the production overlay.

Full artifact table: [kind-helm-aws.md](../../../ENTERPRISE.md).
