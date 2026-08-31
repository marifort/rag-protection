FROM python:3.13-slim

LABEL org.opencontainers.image.title="Marifort Gate"
LABEL org.opencontainers.image.description="ACL gateway for RAG — Community Edition"
LABEL org.opencontainers.image.vendor="Marifort Systems Inc."
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/marifort/rag-protection"

WORKDIR /app

ARG INSTALL_EE_WHEEL=0

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Build context: repository root (see compose.yml)
# CE-only image — INSTALL_EE_WHEEL=0 (metadata; see COMPOSE_OVERLAYS.md). Does not copy rag-protection-enterprise/.
# EE image: Dockerfile.ee (INSTALL_EE_WHEEL=1) via compose.ee.yml → tag rag-protection-proxy:ee
# Contributor guide: docs/commercial/COMPOSE_OVERLAYS.md § CE-only Docker for contributors
COPY rag-protection-proxy/requirements.txt ./requirements.txt
# CPU torch first: the default CUDA wheel from sentence-transformers exceeds
# GitHub-hosted runner disk (pip Errno 28). The CE image is CPU-only.
# torch is unpinned on purpose so the CPU index supplies the current wheel;
# everything else is pinned via requirements.txt.
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r requirements.txt

COPY rag-protection-proxy/rag_protection_proxy ./rag_protection_proxy
COPY rag-protection-proxy/config ./config

ENV RAG_POLICY_FILE=/app/config/policy.yaml
ENV RAG_ACL_FILE=/app/config/acl_policy.yaml
ENV RAG_SAMPLE_DOCS=/app/config/sample_documents.json
ENV RAG_DATA_DIR=/data
ENV RAG_HOST=0.0.0.0
ENV RAG_PORT=8090

EXPOSE 8090

HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=20s \
  CMD curl -sf http://localhost:8090/health | grep -q healthy

CMD ["uvicorn", "rag_protection_proxy.app:app", "--host", "0.0.0.0", "--port", "8090"]
