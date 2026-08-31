"""FastAPI application for Marifort Gate."""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Optional

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

from rag_protection_proxy import __version__
from rag_protection_proxy.acl import resolve_auth, user_can_access_document
from rag_protection_proxy.admin_auth import (
    AUDIT_DEBUG_READER,
    AUDIT_READER,
    INGEST_ADMIN,
    POLICY_ADMIN,
    AdminContext,
    admin_allowed_tenant_ids,
    admin_can_access_tenant,
    admin_can_view_audit_debug,
    admin_effective_tenant_filter,
    admin_has_role,
    admin_is_global,
    resolve_admin,
)
from rag_protection_proxy.audit import (
    configure_audit,
    configure_audit_policy,
    compute_audit_stats,
    compute_overview_stats,
    export_jsonl,
    query_audit_events,
    recent,
    record,
    redact_audit_events_response,
    status as audit_status,
    verify_audit_integrity,
    warm_buffer_from_file,
)
from rag_protection_proxy.config import (
    ACLPolicy,
    Policy,
    PolicyValidationError,
    active_policy_path,
    allowed_dlp_labels,
    ensure_writable_policy_file,
    load_acl_policy,
    load_policy,
    policy_for_tenant,
)
from rag_protection_proxy.guardrails.canary import (
    is_metadata_canary,
    list_canaries,
    seed_canary,
)
from rag_protection_proxy.guardrails.extraction import watch as extraction_watch
from rag_protection_proxy.guardrails.ingest import (
    evaluate_ingest_scan,
    quarantine_metadata,
    scan_ingest_content,
    split_sanitized_ingest_text,
)
from rag_protection_proxy.guardrails.input_pipeline import scan_input
from rag_protection_proxy.guardrails.risk_scoring import is_effective_block
from rag_protection_proxy.guardrails.scan import SCAN_MAX_TEXT_BYTES, scan_disposition
from rag_protection_proxy.models import (
    AuditEvent,
    Decision,
    DocumentIngestRequest,
    Finding,
    InputScanRequest,
    QueryRequest,
    ToolInvokeRequest,
)
from rag_protection_proxy.tools_gateway.challenge_queue import get_tool_challenge_queue
from rag_protection_proxy.tools_gateway.policy import (
    ToolPolicyValidationError,
    load_tool_policy,
    tool_policy_admin_summary,
)
from rag_protection_proxy.tools_gateway.registry import build_registry
from rag_protection_proxy.tools_gateway.router import (
    approve_tool_challenge,
    deny_tool_challenge,
    invoke_tool,
    list_tools_for_auth,
)
from rag_protection_proxy.otel import configure_otel
from rag_protection_proxy.pipeline import run_query
from rag_protection_proxy.store import DocumentStoreBackend
from rag_protection_proxy.tenant_store import TenantDocumentStore

logger = logging.getLogger("rag_protection_proxy")
logging.basicConfig(
    level=os.getenv("RAG_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

RAG_QUERIES_TOTAL = Counter("rag_queries_total", "RAG queries processed", ["decision"])
RAG_INGEST_TOTAL = Counter("rag_ingest_total", "Documents ingested")
RAG_RATE_LIMITED_TOTAL = Counter("rag_rate_limited_total", "Queries rate limited", ["tenant_id"])


def _data_dir() -> Path:
    return Path(os.getenv("RAG_DATA_DIR", "./data"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_audit()
    configure_otel()
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    app.state.policy_path = ensure_writable_policy_file()
    app.state.policy = load_policy(str(app.state.policy_path))
    app.state.acl = load_acl_policy(os.getenv("RAG_ACL_FILE"))
    app.state.tool_policy = load_tool_policy()
    _sync_audit_policy(app.state.policy)
    warm_buffer_from_file()
    app.state.store = TenantDocumentStore(data_dir)
    ee_startup = getattr(app.state, "ee_startup", None)
    if ee_startup is not None:
        ee_startup()
    backend = os.getenv("RAG_STORE_BACKEND", "sqlite").strip().lower()
    connector_scheduler = (
        app.state.policy.connectors.enabled if getattr(app.state, "enterprise_registered", False) else False
    )
    logger.info(
        "Marifort Gate ready (%d documents, store=%s, scim=%s, connector_scheduler=%s, enterprise=%s)",
        app.state.store.count_documents(),
        backend,
        app.state.acl.scim.enabled,
        connector_scheduler,
        getattr(app.state, "enterprise_registered", False),
    )
    yield


app = FastAPI(
    title="Marifort Gate",
    version=__version__,
    description="ACL gateway for RAG with DLP, injection shielding, and citation auditing.",
    lifespan=lifespan,
)

static_dir = Path(__file__).resolve().parent / "ui" / "static"
# EE static must mount before the parent /ui/static tree (Starlette matches first prefix).
try:
    from rag_protection_enterprise.ui import mount_ee_ui

    mount_ee_ui(app)
except ImportError:
    pass
if static_dir.exists():
    app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")


def _sync_audit_policy(policy: Policy) -> None:
    configure_audit_policy(
        retention_days=policy.audit.retention_days,
        backup_keep_days=policy.audit.backup_keep_days,
        scrub_export=policy.audit.scrub_export,
        max_export_rows=policy.audit.max_export_rows,
        debug_webhook=policy.audit.debug_webhook,
        debug_retention_hours=policy.audit.debug_retention_hours,
        integrity_chain=policy.audit.integrity_chain,
        sample_by_kind=policy.audit.sample_by_kind,
        retention_by_kind=policy.audit.retention_by_kind,
        retain_decisions=policy.audit.retain_decisions,
    )


def _policy_file() -> Path:
    cached = getattr(app.state, "policy_path", None)
    if cached is not None:
        return cached
    return active_policy_path()


def _acl_file() -> Path:
    return Path(os.getenv("RAG_ACL_FILE", "./config/acl_policy.yaml"))


def _load_raw_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _sanitize_policy_yaml(raw: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(raw)
    llm = dict(out.get("llm") or {})
    if llm.get("api_key"):
        llm["api_key"] = "***redacted***"
    out["llm"] = llm
    return out


def _sanitize_acl_yaml(raw: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(raw)
    if out.get("jwt_secret"):
        out["jwt_secret"] = "***configured***"
    scim = dict(out.get("scim") or {})
    if scim.get("bearer_token"):
        scim["bearer_token"] = "***configured***"
    out["scim"] = scim
    return out


def _tenant_store() -> TenantDocumentStore:
    return app.state.store


def _store_for_auth(auth: Any) -> DocumentStoreBackend:
    return _tenant_store().for_tenant(auth.tenant_id)


def _policy_for_auth(auth: Any) -> Policy:
    return policy_for_tenant(auth.tenant_id, app.state.policy, app.state.acl)


def _canary_policy():
    return app.state.policy.canary


def _require_auth(authorization: Optional[str] = Header(default=None)) -> Any:
    auth = resolve_auth(authorization, app.state.acl)
    if auth is None:
        raise HTTPException(status_code=401, detail="Unauthorized — provide Bearer demo token or JWT")
    return auth


def _require_admin_role(required_role: str) -> Callable:
    def dependency(authorization: Optional[str] = Header(default=None)) -> AdminContext:
        admin_key = os.getenv("RAG_ADMIN_API_KEY", "")
        if not admin_key and not app.state.acl.admin_users:
            return AdminContext(subject="admin.open", roles=frozenset({required_role}), auth_method="open")
        admin = resolve_admin(authorization, app.state.acl)
        if admin is None:
            raise HTTPException(status_code=401, detail="Admin bearer token required")
        if not admin_has_role(admin, required_role):
            raise HTTPException(
                status_code=403,
                detail=f"Missing required admin role: {required_role}",
            )
        return admin

    return dependency


def _require_admin_any() -> Callable:
    def dependency(authorization: Optional[str] = Header(default=None)) -> AdminContext:
        admin_key = os.getenv("RAG_ADMIN_API_KEY", "")
        if not admin_key and not app.state.acl.admin_users and not app.state.acl.oidc.admin_role_map:
            return AdminContext(
                subject="admin.open",
                roles=frozenset({POLICY_ADMIN, AUDIT_READER, INGEST_ADMIN}),
                auth_method="open",
            )
        admin = resolve_admin(authorization, app.state.acl)
        if admin is None:
            raise HTTPException(status_code=401, detail="Admin bearer token required")
        if not admin.roles:
            raise HTTPException(status_code=403, detail="No admin roles assigned")
        return admin

    return dependency


def _guard_admin_tenant(admin: AdminContext, tenant_id: str) -> str:
    tid = tenant_id or "default"
    if not admin_can_access_tenant(admin, tid):
        raise HTTPException(
            status_code=403,
            detail=f"Admin access denied for tenant: {tid}",
        )
    return tid


def _record_query_completed(
    auth,
    *,
    blocked: bool,
    detail: Optional[str] = None,
    risk_score: float = 0.0,
) -> None:
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="query_completed",
            decision=Decision.BLOCK if blocked else Decision.ALLOW,
            risk_score=risk_score if blocked else 0.0,
            subject=auth.subject,
            tenant_id=auth.tenant_id,
            detail=detail or ("blocked" if blocked else "allowed"),
        )
    )


def _ingest_document(
    store: DocumentStoreBackend,
    policy: Policy,
    req: DocumentIngestRequest,
    *,
    tenant_id: str = "default",
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    scan = scan_ingest_content(
        req.document_id,
        req.title,
        req.content,
        policy,
        tenant_id=tenant_id,
        subject=actor,
        audit_debug=bool(req.audit_debug),
    )
    status, reason = evaluate_ingest_scan(scan, policy)
    if status == "rejected":
        raise HTTPException(
            status_code=422,
            detail={
                "status": "rejected",
                "reason": reason,
                "risk_score": scan.verdict.risk_score,
                "findings": [f.model_dump() for f in scan.verdict.findings],
            },
        )

    metadata = dict(req.metadata)
    ingest_status = "ok"
    if status == "quarantined":
        metadata.update(quarantine_metadata(scan))
        ingest_status = "quarantined"

    sanitized_title, sanitized_content = split_sanitized_ingest_text(
        req.title, req.content, scan.sanitized_text
    )
    count = store.ingest(
        document_id=req.document_id,
        title=sanitized_title,
        content=sanitized_content,
        allowed_groups=req.allowed_groups,
        metadata=metadata,
    )
    RAG_INGEST_TOTAL.inc()
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="ingest_completed",
            decision=Decision.CHALLENGE if ingest_status == "quarantined" else Decision.ALLOW,
            risk_score=scan.verdict.risk_score,
            subject=actor or "ingest.api",
            tenant_id=tenant_id,
            detail=f"{req.document_id}:{ingest_status}",
        )
    )
    return {
        "document_id": req.document_id,
        "chunks": count,
        "status": ingest_status,
        "reason": reason if ingest_status == "quarantined" else None,
    }


@app.get("/")
async def root() -> HTMLResponse:
    return HTMLResponse(
        f"<h1>Marifort Gate {__version__}</h1>"
        f"<p>See <a href='/ui'>/ui</a>, <a href='/metrics'>/metrics</a>, <a href='/docs'>/docs</a>.</p>"
    )


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


def _ui_build_headers() -> Dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "X-RAG-Protection-UI-Build": _ui_build_label(),
    }


def _ui_build_label() -> str:
    html_path = _resolve_ui_html_path()
    if not html_path.exists():
        return "missing"
    for line in html_path.read_text(encoding="utf-8").splitlines():
        marker = "<!-- rag-protection-ui-build:"
        if marker in line:
            return line.split(marker, 1)[1].split("-->", 1)[0].strip()
    return "unknown"


def _resolve_ui_html_path() -> Path:
    """React CE shell at /ui."""
    return static_dir / "ce" / "index.html"


@app.get("/ui", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    html_path = _resolve_ui_html_path()
    if html_path.exists():
        return HTMLResponse(
            html_path.read_text(encoding="utf-8"),
            headers=_ui_build_headers(),
        )
    return HTMLResponse("<h1>Marifort Gate</h1><p>UI not bundled.</p>")


@app.head("/ui")
async def ui_head() -> Response:
    """Same headers as GET /ui (supports curl -I for build verification)."""
    return Response(status_code=200, headers=_ui_build_headers())


@app.get("/health")
async def health() -> Dict[str, Any]:
    acl: ACLPolicy = app.state.acl
    payload: Dict[str, Any] = {
        "status": "healthy",
        "version": __version__,
        "documents": app.state.store.count_documents(),
        "tenants": app.state.store.tenant_ids(),
        "store_backend": os.getenv("RAG_STORE_BACKEND", "sqlite").strip().lower(),
        "llm_model": app.state.policy.llm.model,
        "llm_base_url": app.state.policy.llm.base_url,
        "oidc_enabled": acl.oidc.enabled,
        "scim_enabled": acl.scim.enabled,
        "enterprise_installed": getattr(app.state, "enterprise_registered", False),
        "supported_dlp_labels": sorted(allowed_dlp_labels()),
        "audit": audit_status(),
        "policy_version": app.state.policy.version,
    }
    ee_health_extra = getattr(app.state, "ee_health_extra", None)
    if ee_health_extra is not None:
        payload.update(ee_health_extra(app))
    return payload


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/audit/recent")
async def audit_recent(limit: int = 50, _auth=Depends(_require_auth)) -> Dict[str, Any]:
    events = recent(min(max(limit, 1), 200))
    return {"events": [e.model_dump() for e in events]}


@app.get("/admin/audit/stats")
async def admin_audit_stats(
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
    bucket: str = "1h",
    limit: int = 10000,
    tenant_id: Optional[str] = None,
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    bucket_map = {"5m": 300, "1h": 3600, "1d": 86400}
    bucket_seconds = bucket_map.get(bucket.strip().lower(), 3600)
    capped = min(max(limit, 1), 10000)
    effective_tenant = admin_effective_tenant_filter(admin, tenant_id)
    return compute_audit_stats(
        since=from_ts,
        until=to_ts,
        bucket_seconds=bucket_seconds,
        limit=capped,
        tenant_id=effective_tenant,
    )


@app.get("/admin/audit/events")
async def admin_audit_events(
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
    tenant_id: Optional[str] = None,
    kind: Optional[str] = None,
    decision: Optional[str] = None,
    search: Optional[str] = None,
    where: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    result = query_audit_events(
        since=from_ts,
        until=to_ts,
        tenant_id=admin_effective_tenant_filter(admin, tenant_id),
        kind=kind,
        decision=decision,
        search=search,
        where=where,
        offset=offset,
        limit=limit,
    )
    return redact_audit_events_response(
        result,
        include_debug=admin_can_view_audit_debug(admin),
    )


@app.get("/admin/overview/stats")
async def admin_overview_stats(
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
    limit: int = 10000,
    tenant_id: Optional[str] = None,
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    capped = min(max(limit, 1), 10000)
    effective_tenant = admin_effective_tenant_filter(admin, tenant_id)
    tid = effective_tenant or "default"
    doc_count = app.state.store.count_documents(tid)
    challenges_pending = app.state.store.count_challenge_documents(tid)
    return compute_overview_stats(
        since=from_ts,
        until=to_ts,
        limit=capped,
        tenant_id=effective_tenant,
        documents_current=doc_count,
        challenges_pending=challenges_pending,
    )


@app.get("/admin/audit/export")
async def admin_audit_export(
    limit: int = 1000,
    scrub: Optional[bool] = None,
    tenant_id: Optional[str] = None,
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> PlainTextResponse:
    capped = min(max(limit, 1), 10000)
    body = export_jsonl(
        capped,
        scrub=scrub,
        tenant_id=admin_effective_tenant_filter(admin, tenant_id),
        include_debug=admin_can_view_audit_debug(admin),
    )
    return PlainTextResponse(
        body,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="audit-export.jsonl"'},
    )


@app.get("/admin/audit/integrity/verify")
async def admin_audit_integrity_verify(
    limit: Optional[int] = None,
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    """Verify SHA-256 hash chain on the configured audit JSONL file (T0.4)."""
    _ = admin
    capped = min(max(limit, 1), 100000) if limit is not None else None
    return verify_audit_integrity(limit=capped)


@app.post("/v1/query")
async def query(req: QueryRequest, auth=Depends(_require_auth)) -> JSONResponse:
    policy = _policy_for_auth(auth)
    rate_limit_check = getattr(app.state, "ee_rate_limit_check", None)
    if rate_limit_check is not None:
        allowed, retry_after = rate_limit_check(
            auth.tenant_id,
            policy.tenant.queries_per_minute,
            policy.tenant.burst,
        )
        if not allowed:
            counter = getattr(app.state, "ee_rate_limited_counter", None)
            if counter is not None:
                counter.labels(tenant_id=auth.tenant_id).inc()
            record(
                AuditEvent(
                    timestamp=time.time(),
                    kind="rate_limited",
                    decision=Decision.BLOCK,
                    risk_score=1.0,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    detail="query rate limit exceeded",
                )
            )
            _record_query_completed(
                auth,
                blocked=True,
                detail="query rate limit exceeded",
                risk_score=1.0,
            )
            headers = {"Retry-After": str(retry_after or 1)}
            raise HTTPException(status_code=429, detail="Query rate limit exceeded", headers=headers)

    store = _store_for_auth(auth)
    result = await run_query(req, auth, store, policy)
    decision = "blocked" if result.blocked else "allowed"
    RAG_QUERIES_TOTAL.labels(decision=decision).inc()
    _record_query_completed(
        auth,
        blocked=result.blocked,
        detail=result.block_reason,
        risk_score=1.0 if result.blocked else 0.0,
    )
    return JSONResponse(result.model_dump())


@app.post("/v1/ingest")
async def ingest(
    req: DocumentIngestRequest,
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(INGEST_ADMIN)),
) -> Dict[str, Any]:
    tid = _guard_admin_tenant(admin, tenant_id)
    store = _tenant_store().for_tenant(tid)
    policy = policy_for_tenant(tid, app.state.policy, app.state.acl)
    result = _ingest_document(store, policy, req, tenant_id=tid, actor=admin.subject)
    result["tenant_id"] = tid
    return result


@app.post("/admin/canary/seed")
async def canary_seed(
    payload: Dict[str, Any],
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(POLICY_ADMIN)),
) -> Dict[str, Any]:
    """Seed a canary/honeypot document (Lab 10). policy_admin only."""
    tid = _guard_admin_tenant(admin, tenant_id)
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")
    canary_policy = _canary_policy()
    store = _tenant_store().for_tenant(tid)
    allowed_groups = payload.get("allowed_groups")
    record_out = seed_canary(
        store,
        title=title,
        body=payload.get("body"),
        sensitivity=str(payload.get("sensitivity") or canary_policy.default_sensitivity),
        allowed_groups=list(allowed_groups) if isinstance(allowed_groups, list) else None,
    )
    record_out["tenant_id"] = tid
    return record_out


@app.get("/admin/canary/list")
async def canary_list(
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    tid = _guard_admin_tenant(admin, tenant_id)
    store = _tenant_store().for_tenant(tid)
    canaries = list_canaries(store)
    return {"tenant_id": tid, "count": len(canaries), "canaries": canaries}


@app.post("/admin/canary/retire")
async def canary_retire(
    payload: Dict[str, Any],
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(POLICY_ADMIN)),
) -> Dict[str, Any]:
    tid = _guard_admin_tenant(admin, tenant_id)
    document_id = str(payload.get("document_id") or "").strip()
    if not document_id:
        raise HTTPException(status_code=422, detail="document_id is required")
    store = _tenant_store().for_tenant(tid)
    detail = store.get_document_detail(document_id)
    if detail is None or not is_metadata_canary(detail.get("metadata")):
        raise HTTPException(status_code=404, detail=f"canary not found: {document_id}")
    store.delete_document(document_id)
    return {"tenant_id": tid, "document_id": document_id, "retired": True}


@app.get("/admin/extraction/watch")
async def extraction_watch_view(
    admin: AdminContext = Depends(_require_admin_role(AUDIT_READER)),
) -> Dict[str, Any]:
    """Subjects currently at elevated/severe corpus-extraction severity (Lab 9)."""
    rules = app.state.policy.extraction
    corpus_sizes = {tid: app.state.store.count_documents(tid) for tid in app.state.store.tenant_ids()}
    offenders = extraction_watch(rules=rules, corpus_sizes=corpus_sizes)
    if not admin_is_global(admin):
        allowed = set(admin_allowed_tenant_ids(admin, app.state.store.tenant_ids()))
        offenders = [o for o in offenders if o.get("tenant_id") in allowed]
    return {"enabled": rules.enabled, "action": rules.action, "count": len(offenders), "subjects": offenders}


@app.post("/v1/scan")
async def scan_text(
    req: InputScanRequest,
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(INGEST_ADMIN)),
) -> Dict[str, Any]:
    """Stateless input guardrail for BYO-RAG integrations (E7.1)."""
    tid = _guard_admin_tenant(admin, tenant_id)
    policy = policy_for_tenant(tid, app.state.policy, app.state.acl)

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="text must be non-empty")
    if len(req.text.encode("utf-8")) > SCAN_MAX_TEXT_BYTES:
        raise HTTPException(status_code=422, detail="text exceeds maximum size")

    source = "rag:scan:api" if req.source in ("unknown", "") else req.source
    scan_req = req.model_copy(
        update={
            "tenant_id": tid,
            "subject": req.subject or admin.subject,
            "source": source,
        }
    )
    scan = scan_input(scan_req, policy)
    return {
        "verdict": scan.verdict.model_dump(),
        "sanitized_text": scan.sanitized_text,
        "redactions": scan.redactions,
        "effective_block": is_effective_block(
            scan.verdict.decision, policy.input.challenge_mode
        ),
        "disposition": scan_disposition(scan, policy),
        "tenant_id": tid,
    }


@app.get("/v1/tools")
async def list_tools(auth=Depends(_require_auth)) -> Dict[str, Any]:
    """List registered tools and whether the caller may invoke each."""
    tools = list_tools_for_auth(auth, app.state.tool_policy, app.state.policy)
    return {
        "tools": [tool.model_dump() for tool in tools],
        "subject": auth.subject,
        "groups": auth.groups,
        "tenant_id": auth.tenant_id,
    }


@app.post("/v1/tools/invoke")
async def tools_invoke(req: ToolInvokeRequest, auth=Depends(_require_auth)) -> JSONResponse:
    """Identity-bound tool gateway — enforce allowlist and guardrails before backend invoke."""
    policy = _policy_for_auth(auth)
    result = invoke_tool(req, auth, app.state.tool_policy, policy)
    if result.http_status_hint:
        status_code = result.http_status_hint
    elif result.blocked:
        status_code = 403
    else:
        status_code = 200
    return JSONResponse(result.model_dump(), status_code=status_code)


@app.get("/admin/tools/policy")
async def admin_tools_policy(
    _admin=Depends(_require_admin_role(POLICY_ADMIN)),
) -> Dict[str, Any]:
    """Read-only tool gateway policy for the operator console (L1-202)."""
    registry = build_registry(app.state.tool_policy, app.state.policy)
    return tool_policy_admin_summary(app.state.tool_policy, registry)


class ToolChallengeDenyBody(BaseModel):
    reason: str = Field(default="", description="Optional operator deny reason")


@app.get("/admin/tools/challenges")
async def admin_tools_challenges(
    admin: AdminContext = Depends(_require_admin_role(POLICY_ADMIN)),
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """List pending tool-invoke CHALLENGE rows (L1-201)."""
    tid = _guard_admin_tenant(admin, tenant_id or "default")
    rows = get_tool_challenge_queue().list_pending(tid)
    return {
        "count": len(rows),
        "challenges": [row.to_dict() for row in rows],
        "tenant_id": tid,
        "tool_challenge_mode": app.state.tool_policy.challenge_mode,
    }


@app.post("/admin/tools/challenges/{challenge_id}/approve")
async def admin_tools_challenge_approve(
    challenge_id: str,
    admin: AdminContext = Depends(_require_admin_role(POLICY_ADMIN)),
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve a held tool invoke — run backend once (L1-201)."""
    tid = _guard_admin_tenant(admin, tenant_id or "default")
    try:
        response, pending = approve_tool_challenge(
            challenge_id,
            operator_subject=admin.subject,
            tool_policy=app.state.tool_policy,
            rag_policy=app.state.policy,
            tenant_id=tid,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown tool challenge: {challenge_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "status": "approved",
        "challenge_id": challenge_id,
        "pending": pending.to_dict(),
        "invoke": response.model_dump(),
    }


@app.post("/admin/tools/challenges/{challenge_id}/deny")
async def admin_tools_challenge_deny(
    challenge_id: str,
    admin: AdminContext = Depends(_require_admin_role(POLICY_ADMIN)),
    tenant_id: Optional[str] = None,
    body: Optional[ToolChallengeDenyBody] = None,
) -> Dict[str, Any]:
    """Deny a held tool invoke — never run backend (L1-201)."""
    tid = _guard_admin_tenant(admin, tenant_id or "default")
    reason = (body.reason if body else "") or ""
    try:
        pending = deny_tool_challenge(
            challenge_id,
            operator_subject=admin.subject,
            tenant_id=tid,
            reason=reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown tool challenge: {challenge_id}") from exc
    return {
        "status": "denied",
        "challenge_id": challenge_id,
        "pending": pending.to_dict(),
    }


@app.post("/admin/reload-policy")
async def reload_policy(_admin=Depends(_require_admin_role(POLICY_ADMIN))) -> Dict[str, Any]:
    policy_path = ensure_writable_policy_file()
    try:
        new_policy = load_policy(str(policy_path))
    except PolicyValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    app.state.policy_path = policy_path
    app.state.policy = new_policy
    app.state.acl = load_acl_policy(os.getenv("RAG_ACL_FILE"))
    try:
        app.state.tool_policy = load_tool_policy()
    except ToolPolicyValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _sync_audit_policy(app.state.policy)
    if app.state.acl.scim.enabled and getattr(app.state, "enterprise_registered", False):
        from rag_protection_enterprise.connectors.scim import sync_scim_once

        sync_scim_once(app.state.acl.scim)
    return {
        "status": "ok",
        "policy_version": app.state.policy.version,
        "tool_policy": app.state.tool_policy.source_path,
    }


@app.get("/v1/documents/count")
async def document_count(auth=Depends(_require_auth)) -> Dict[str, int]:
    return {"documents": _store_for_auth(auth).count_documents(), "tenant_id": auth.tenant_id}


@app.get("/v1/documents")
async def list_documents(auth=Depends(_require_auth)) -> Dict[str, Any]:
    docs = _store_for_auth(auth).list_documents()
    visible = [
        doc
        for doc in docs
        if user_can_access_document(auth.groups, doc["allowed_groups"])
    ]
    return {"count": len(visible), "documents": visible, "tenant_id": auth.tenant_id}


@app.get("/v1/documents/quarantined")
async def list_quarantined_document_summaries(
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(INGEST_ADMIN)),
) -> Dict[str, Any]:
    """Metadata-only visibility into quarantined documents (CE trust surface).

    Shows what ingest held back and why. Content preview, inspect, and
    approve/reject review workflows are Enterprise (Tier 2).
    """
    tid = _guard_admin_tenant(admin, tenant_id)
    store = _tenant_store().for_tenant(tid)
    docs = [
        {
            "document_id": doc.get("document_id"),
            "title": doc.get("title"),
            "quarantine_decision": doc.get("quarantine_decision"),
            "quarantine_reason": doc.get("quarantine_reason"),
            "quarantine_risk_score": doc.get("quarantine_risk_score"),
            "quarantine_scanners": list(doc.get("quarantine_scanners") or []),
            "quarantine_categories": list(doc.get("quarantine_categories") or []),
            "created_at": doc.get("created_at"),
            "chunk_count": doc.get("chunk_count"),
        }
        for doc in store.list_quarantined_documents()
    ]
    return {"tenant_id": tid, "count": len(docs), "documents": docs}


@app.delete("/v1/documents/{document_id}")
async def delete_document(
    document_id: str,
    tenant_id: str = "default",
    admin: AdminContext = Depends(_require_admin_role(INGEST_ADMIN)),
) -> Dict[str, Any]:
    """Delete a document — the CE lifecycle exit for stuck/quarantined docs.

    CE operators delete and re-ingest remediated content; approve-in-place
    review remains Enterprise (Tier 2).
    """
    tid = _guard_admin_tenant(admin, tenant_id)
    store = _tenant_store().for_tenant(tid)
    detail = store.get_document_detail(document_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    if is_metadata_canary(detail.get("metadata")):
        raise HTTPException(
            status_code=409,
            detail="Document is a canary — retire it via POST /admin/canary/retire (policy_admin)",
        )
    prior_status = str(detail.get("status") or "active")
    store.delete_document(document_id)
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="document_deleted",
            decision=Decision.ALLOW,
            risk_score=0.0,
            subject=admin.subject,
            tenant_id=tid,
            detail=f"{document_id}:deleted (was {prior_status})",
        )
    )
    return {
        "tenant_id": tid,
        "document_id": document_id,
        "deleted": True,
        "previous_status": prior_status,
    }


@app.get("/v1/auth/me")
async def user_auth_me(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    auth = resolve_auth(authorization, app.state.acl)
    if auth is None:
        raise HTTPException(status_code=401, detail="Unauthorized — provide Bearer demo token or JWT")
    return {
        "subject": auth.subject,
        "tenant_id": auth.tenant_id,
        "groups": sorted(auth.groups),
        "auth_method": auth.auth_method,
        "email": auth.email,
    }


@app.get("/admin/auth/me")
async def admin_auth_me(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    admin_key = os.getenv("RAG_ADMIN_API_KEY", "")
    acl: ACLPolicy = app.state.acl
    if not admin_key and not acl.admin_users and not acl.oidc.admin_role_map:
        return {
            "roles": sorted({POLICY_ADMIN, AUDIT_READER, AUDIT_DEBUG_READER, INGEST_ADMIN}),
            "auth_method": "open",
            "admin_key_required": False,
            "global_admin": True,
            "tenant_scope": None,
            "allowed_tenants": app.state.store.tenant_ids(),
        }
    admin = resolve_admin(authorization, acl)
    if admin is None:
        token = (authorization or "").split(" ", 1)[-1].strip() if authorization else ""
        if token:
            raise HTTPException(status_code=403, detail="Invalid admin bearer token")
        raise HTTPException(status_code=401, detail="Admin bearer token required")
    return {
        "subject": admin.subject,
        "roles": sorted(admin.roles),
        "auth_method": admin.auth_method,
        "admin_key_required": True,
        "global_admin": admin_is_global(admin),
        "tenant_scope": admin.tenant_scope,
        "allowed_tenants": admin_allowed_tenant_ids(admin, app.state.store.tenant_ids()),
    }


try:
    from rag_protection_enterprise import register_enterprise
    from rag_protection_enterprise.deps import EnterpriseDeps
    from rag_protection_enterprise.entitlements import Entitlements

    register_enterprise(
        app,
        deps=EnterpriseDeps(
            data_dir=_data_dir,
            tenant_store=_tenant_store,
            guard_admin_tenant=_guard_admin_tenant,
            ingest_document=_ingest_document,
            require_admin_role=_require_admin_role,
            require_admin_any=_require_admin_any,
            record_audit=record,
            sync_audit_policy=_sync_audit_policy,
            policy_file=_policy_file,
            acl_file=_acl_file,
            load_raw_yaml=_load_raw_yaml,
            sanitize_policy_yaml=_sanitize_policy_yaml,
            sanitize_acl_yaml=_sanitize_acl_yaml,
            rate_limited_counter=RAG_RATE_LIMITED_TOTAL,
            entitlements=Entitlements.from_env(),
        ),
    )
except ImportError:
    pass  # CE-only install — enterprise wheel not installed
