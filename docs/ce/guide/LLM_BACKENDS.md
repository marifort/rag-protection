# LLM backends (Community Edition)

**Audience:** Evaluators and contributors running CE locally.  
**Goal:** Get `POST /v1/query` generation working. Guardrails, ACL, and `/health` still run without a reachable model — answers then fall back to “temporarily unavailable.”

The gateway does **not** bundle an LLM. It posts OpenAI-compatible chat completions. Default local path: [Docker Model Runner](https://docs.docker.com/ai/model-runner/). Any other OpenAI-compatible URL uses the same three variables.

Clone / Desktop install: root [README.md](../../../README.md). Python venv: [LOCAL_SETUP.md](LOCAL_SETUP.md). Why Model Runner is the baseline: [TECH_STACK.md](../../product/TECH_STACK.md#llm-integration).

---

## Contract

`LLMClient` in `rag_protection_proxy/llm.py` posts to `/chat/completions`. If `RAG_LLM_BASE_URL` already ends with `/v1`, that suffix is kept; otherwise `/v1` is inserted:

```text
POST {RAG_LLM_BASE_URL}/chat/completions      # when the URL already ends with /v1
POST {RAG_LLM_BASE_URL}/v1/chat/completions   # otherwise
```

| Variable | Role |
|----------|------|
| `RAG_LLM_BASE_URL` | OpenAI-compatible base URL |
| `RAG_LLM_MODEL` | Model name the **server** expects (not a Marifort catalog) |
| `RAG_LLM_API_KEY` | Bearer token; use `not-needed` for local servers that ignore it |

These three variables are enough for any OpenAI-compatible backend; CE does not require a Marifort-hosted model.

Compose reads these from `.env` (copy [`.env.example`](../README.md)). Host `uvicorn` does not load `.env` unless you source it — `export` the same names.

---

## Which path

| Path | When | Compose file | What you set |
|------|------|----------------|--------------|
| **Docker Model Runner** (default) | Docker Desktop **4.40+**, Model Runner enabled | [`compose.yml`](../../../compose.yml) via `bash tools/docker_start.sh` | Nothing — Compose injects the URL |
| **Host OpenAI-compatible server** (Ollama, vLLM, LM Studio, …) | No Model plugin (Linux Engine, Colima, CI) **or** you already run a local server | [`compose.ci.yml`](../../../compose.ci.yml) | `RAG_LLM_BASE_URL`, `RAG_LLM_MODEL` |
| **Hosted API** | You have a vendor key | `compose.ci.yml` or host process | Same two vars plus `RAG_LLM_API_KEY` |

Ollama is **not** a second CE default and is **not** a tested install matrix in this repo. It is one common host server. Do not install it in order to run CE if Model Runner already works.

---

## Default: Docker Model Runner

1. Install or update [Docker Desktop](https://docs.docker.com/desktop/) **4.40+**.
2. Configure Desktop as in [Docker Desktop (standard CE setup)](#docker-desktop-standard-ce-setup).
3. From the repo root: `cp -n .env.example .env`, then `bash tools/docker_start.sh` (add `--smoke` on first run).

`compose.yml` uses the Compose `models:` key. That is the **Model Runner plugin**, not a second service you `docker run` and not a container you will see as `ollama` in `docker ps`. GitHub Actions and Docker Engine without the plugin cannot start this file.

<a id="docker-desktop-standard-ce-setup"></a>

### Docker Desktop (standard CE setup)

Docker owns the UI labels; they can move. Canonical Docker page: [Get started with DMR](https://docs.docker.com/ai/model-runner/get-started/). This table is what **this repo** expects.

Open Docker Desktop → **Settings → AI** (gear → AI). Apply & restart if Desktop asks.

| Desktop setting | CE Compose (`docker_start.sh` / `compose.yml`) | Host Python (`uvicorn` / `python -m rag_protection_proxy`) |
|-----------------|-----------------------------------------------|--------------------------------------------------------------|
| **Enable Docker Model Runner** | **Required** | **Required** |
| **Enable GPU-backed inference** | Optional (Windows + supported NVIDIA GPU only) | Same |
| **Enable host-side TCP support** (port **12434**) | **Not required** — Compose injects `RAG_LLM_BASE_URL` via `models:` | **Required** — host process talks to `localhost:12434` |
| **CORS Allowed Origins** | Unused (the proxy calls DMR server-side) | Unused |

CLI equivalent (optional): `docker desktop enable model-runner`. For host TCP: `docker desktop enable model-runner --tcp 12434`. Check: `docker model status` (or `docker model version`).

Do **not** set `RAG_LLM_BASE_URL` in `.env` for the default Compose path — the `models:` binding overwrites it. Leave [`.env.example`](../README.md) as:

```bash
MODEL_RUNNER_MODEL=ai/gemma3-qat
RAG_LLM_MODEL=ai/gemma3-qat
RAG_LLM_API_KEY=not-needed
```

What Compose wires ([`compose.yml`](../../../compose.yml)):

```yaml
models:
  llm:
    model: ${MODEL_RUNNER_MODEL:-ai/gemma3-qat}
    context_size: 4096
services:
  rag-protection-proxy:
    models:
      llm:
        endpoint_var: RAG_LLM_BASE_URL
        model_var: RAG_LLM_MODEL
```

| Item | Value |
|------|--------|
| Model | `ai/gemma3-qat` |
| URL inside the proxy container | `http://model-runner.docker.internal/engines/v1` (injected; also the fallback in `config/policy.yaml`) |
| URL from a host process | `http://localhost:12434/engines/v1` (TCP enabled) |
| API key | `not-needed` |
| First pull | Happens on the first `/v1/query` (or `--smoke`), not on `/health`. Desktop **Models** tab / `docker model list` shows it after pull. |

`GET /health` → `"status": "healthy"` means the **proxy** is up. It does **not** mean the model is pulled or warm.

**Resources:** give Desktop enough RAM under **Settings → Resources**. About **16 GB** on the machine is the realistic demo floor (Desktop + first model load). 8 GB is often too tight. OS/GPU support is whatever [Docker documents](https://docs.docker.com/ai/model-runner/get-started/) — do not assume Intel Macs or every Linux GPU path.

If compose fails with `'models' support requires Docker Model plugin`, Model Runner is off or you are not on Docker Desktop. Use `compose.ci.yml` below.

---

## No Model Runner: `compose.ci.yml`

[`compose.ci.yml`](../../../compose.ci.yml) is a **standalone** file (not an overlay). It starts the proxy only. CI leaves `RAG_LLM_*` unset so the client fail-fasts to `http://127.0.0.1:9` (ACL and `/health` still work).

From inside that container, `localhost` is the **proxy**. Use `host.docker.internal` for an LLM on the host (`compose.ci.yml` already sets `extra_hosts`). Use a public HTTPS URL for a hosted API.

```bash
# .env — example only (Ollama-shaped URL; any OpenAI-compatible server works)
# RAG_LLM_BASE_URL=http://host.docker.internal:11434/v1
# RAG_LLM_MODEL=llama3
# RAG_LLM_API_KEY=not-needed
docker compose -f compose.ci.yml up -d --build --wait
```

Stop with `docker compose -f compose.ci.yml down`. `tools/docker_stop.sh` targets `compose.yml`, not this file.

---

## Host Ollama (typical URLs)

Use this only if Ollama is **already** running. This page does not document installing or pulling Ollama models.

Typical OpenAI-compatible listen address is port **11434**. The model name must be whatever `ollama list` shows — **not** `ai/gemma3-qat`.

| Who calls the LLM | Typical `RAG_LLM_BASE_URL` |
|-------------------|----------------------------|
| Proxy in `compose.ci.yml` | `http://host.docker.internal:11434/v1` |
| Host uvicorn / `python -m rag_protection_proxy` | `http://localhost:11434/v1` |

Set `RAG_LLM_MODEL` to that listed name. Keep `/v1` on the base URL so the client posts to `/v1/chat/completions`.

Other local OpenAI-compatible servers (vLLM, LM Studio, llama.cpp HTTP) use the same three variables. This repo does not maintain a vendor matrix for them.

---

## Hosted APIs

Same three variables. Example shape (not a recommended vendor):

```bash
RAG_LLM_BASE_URL=https://api.example.com/v1
RAG_LLM_MODEL=your-model-id
RAG_LLM_API_KEY=sk-...
```

The customer chooses the LLM trust boundary. CE does not require a paid API to demo guardrails.

---

## Host Python (no Compose)

From `rag-protection-proxy/` after [LOCAL_SETUP.md](LOCAL_SETUP.md):

```bash
export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1   # Model Runner TCP
export RAG_LLM_MODEL=ai/gemma3-qat
python -m rag_protection_proxy
```

Do not use `model-runner.docker.internal` from a process on the host. For a host Ollama server, use `http://localhost:11434/v1` and the Ollama model name instead.

---

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| `'models' support requires Docker Model plugin` | **Settings → AI → Enable Docker Model Runner**, or switch to `compose.ci.yml` + `RAG_LLM_BASE_URL`. |
| `/health` is healthy but the first query hangs or times out | First model pull / cold start. Wait; later queries are faster. Desktop **Models → Logs** or `docker model logs`. |
| Host uvicorn cannot reach `localhost:12434` | Enable **host-side TCP support** (port 12434). Compose does not need this. |
| Answers say the assistant is temporarily unavailable | Nothing listening at `RAG_LLM_BASE_URL`, wrong `/v1` suffix, or model name the server does not know. |
| Connection refused to `localhost:11434` **from Docker** | The LLM is on the host — use `host.docker.internal`, not `localhost`. |
| Model Runner URL from host uvicorn | `http://localhost:12434/engines/v1`, not `model-runner.docker.internal`. |

---

## Related

| Document | Contents |
|----------|----------|
| Root [README.md](../../../README.md) | Clone, Desktop, `docker_start.sh` |
| [LOCAL_SETUP.md](LOCAL_SETUP.md) | Python venv, host uvicorn |
| [TECH_STACK.md](../../product/TECH_STACK.md#llm-integration) | Why Model Runner; when `/v1/query` calls the LLM |
| [`.env.example`](../README.md) | Env comments for Compose |
