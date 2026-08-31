# Where Helm env comes from (kind)

This file sits next to `values-ee-local.yaml` so Cmd+click from that overlay can open a real markdown page. Cursor does not resolve a repo-root path such as `docs/ee/runbooks/…` from this folder.

**Canonical runbook (Cmd+click in the source editor):** [KIND_HELM_LOCAL.md](../../../ENTERPRISE.md)

Same-folder docs hop for E1.5 Preview: [kind-helm-env.md](../../../ENTERPRISE.md) · AWS artifacts: [KIND_HELM_AWS.md](KIND_HELM_AWS.md)

In the runbook, use the Summary table → **Part 6: Where env lives**, or search for `extraEnvFrom`. Direct section id: `#part-6-env`.

---

`proxy.extraEnvFrom` / `secretRef.name: rag-protection-compose-env` in `values-ee-local.yaml` does **not** store variables. It only names a Kubernetes Secret.

`tools/helm_start.sh` loads repo-root `.env` and copies **these keys only** into that Secret: `RAG_ADMIN_API_KEY`, `RAG_EE_ENTITLEMENTS`, `RAG_GOOGLE_CLIENT_ID`, `RAG_GOOGLE_CLIENT_SECRET`, `RAG_GOOGLE_REDIRECT_URI`, `RAG_JWT_SECRET`.

Non-secret knobs such as `RAG_STORE_BACKEND` come from Helm `proxy.storeBackend` in this overlay (`hybrid`), not from `.env`. `--ha-demo` then sets `vector`. Compose still reads `.env` `RAG_STORE_BACKEND`; Helm does not.
