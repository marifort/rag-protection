"""Tool invoke routing, policy enforcement, and audit."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from rag_protection_proxy.acl import AuthContext
from rag_protection_proxy.audit import record
from rag_protection_proxy.config import Policy
from rag_protection_proxy.guardrails.input_pipeline import scan_input
from rag_protection_proxy.guardrails.risk_scoring import aggregate_risk, apply_challenge_mode, decide
from rag_protection_proxy.models import (
    AuditEvent,
    Decision,
    Finding,
    InputScanRequest,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolSummary,
)
from rag_protection_proxy.tools_gateway.backends import BACKEND_ARG_MODELS, BACKEND_HANDLERS
from rag_protection_proxy.tools_gateway.backends.mcp_shim import McpShimError
from rag_protection_proxy.tools_gateway.challenge_queue import (
    PendingToolChallenge,
    get_tool_challenge_queue,
)
from rag_protection_proxy.tools_gateway.policy import (
    ToolGatewayPolicy,
    args_byte_size,
    caller_allowed_for_tool,
    find_blocked_domains,
    find_blocked_patterns,
)
from rag_protection_proxy.tools_gateway.registry import build_registry, get_tool


def list_tools_for_auth(
    auth: AuthContext,
    tool_policy: ToolGatewayPolicy,
    rag_policy: Optional[Policy] = None,
) -> List[ToolSummary]:
    registry = build_registry(tool_policy, rag_policy)
    visible: List[ToolSummary] = []
    for name, entry in sorted(registry.items()):
        allowed = caller_allowed_for_tool(auth.groups, entry)
        visible.append(
            ToolSummary(
                name=name,
                description=entry.description,
                allowed=allowed,
                description_blocked=entry.description_blocked,
            )
        )
    return visible


def invoke_tool(
    req: ToolInvokeRequest,
    auth: AuthContext,
    tool_policy: ToolGatewayPolicy,
    rag_policy: Policy,
) -> ToolInvokeResponse:
    registry = build_registry(tool_policy, rag_policy)
    entry = get_tool(registry, req.tool)
    findings: List[Finding] = []
    risk_score = 0.0
    reason = ""

    if entry is None:
        reason = f"Unknown tool: {req.tool}"
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    if entry.description_blocked:
        reason = "Tool blocked — description failed injection scan at registry load"
        findings.append(
            Finding(
                scanner="prompt_injection",
                category="tool_description_injection",
                severity=0.95,
                detail=f"Tool {req.tool} description flagged ({entry.description_findings_count} findings)",
            )
        )
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    if not caller_allowed_for_tool(auth.groups, entry):
        reason = f"Caller not authorized for tool {req.tool}"
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    arg_model = BACKEND_ARG_MODELS.get(entry.backend)
    if arg_model is None:
        reason = f"No argument schema for backend {entry.backend}"
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    try:
        arg_model.model_validate(req.arguments)
    except ValidationError as exc:
        reason = f"Invalid arguments for tool {req.tool}"
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=0.5,
            reason=f"{reason}: {exc.errors()[0]['msg']}",
            findings=findings,
            auth=auth,
            result=None,
            http_status_hint=422,
        )

    size = args_byte_size(req.arguments)
    if size > entry.max_args_bytes:
        reason = f"Arguments exceed max size ({size} > {entry.max_args_bytes} bytes)"
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=0.8,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    pattern_hits = find_blocked_patterns(req.arguments, entry.blocked_patterns)
    if pattern_hits:
        reason = pattern_hits[0]
        findings.append(
            Finding(
                scanner="tool_policy",
                category="blocked_pattern",
                severity=0.95,
                detail=reason,
            )
        )
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    domain_hits = find_blocked_domains(req.arguments, entry.blocked_domains)
    if domain_hits:
        reason = domain_hits[0]
        findings.append(
            Finding(
                scanner="tool_policy",
                category="blocked_domain",
                severity=0.9,
                detail=reason,
            )
        )
        return _finalize(
            req.tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    scan_fields = entry.scan_arguments or list(req.arguments.keys())
    for field in scan_fields:
        raw = req.arguments.get(field)
        if not isinstance(raw, str) or not raw.strip():
            continue
        scan = scan_input(
            InputScanRequest(
                text=raw,
                source=f"tool:{req.tool}:{field}",
                subject=auth.subject,
                tenant_id=auth.tenant_id,
            ),
            rag_policy,
        )
        findings.extend(scan.verdict.findings)

    risk_score = aggregate_risk(findings)
    decision = decide(
        risk_score,
        tool_policy.challenge_threshold,
        tool_policy.block_threshold,
    )
    decision = apply_challenge_mode(decision, tool_policy.challenge_mode)

    if decision == Decision.CHALLENGE and tool_policy.challenge_mode == "allow":
        reason = "Tool arguments held for operator CHALLENGE approval"
        if findings:
            reason = f"{reason}: {findings[0].category}"
        pending = get_tool_challenge_queue().enqueue(
            tool=req.tool,
            arguments=req.arguments,
            subject=auth.subject,
            groups=list(auth.groups),
            tenant_id=auth.tenant_id,
            risk_score=risk_score,
            reason=reason,
            findings=[f.model_dump() for f in findings],
        )
        return _finalize(
            req.tool,
            Decision.CHALLENGE,
            risk_score=risk_score,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
            challenge_id=pending.id,
            http_status_hint=202,
        )

    if decision != Decision.ALLOW:
        reason = "Tool arguments blocked by guardrail scan"
        if findings:
            reason = f"{reason}: {findings[0].category}"
        return _finalize(
            req.tool,
            decision,
            risk_score=risk_score,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    return _execute_backend(
        req.tool,
        req.arguments,
        entry,
        auth=auth,
        findings=findings,
        risk_score=risk_score,
    )


def approve_tool_challenge(
    challenge_id: str,
    *,
    operator_subject: str,
    tool_policy: ToolGatewayPolicy,
    rag_policy: Policy,
    tenant_id: str = "default",
) -> Tuple[ToolInvokeResponse, PendingToolChallenge]:
    """Approve a held invoke: re-validate policy, run backend once, remove from queue."""
    queue = get_tool_challenge_queue()
    pending = queue.get(challenge_id, tenant_id=tenant_id)
    if pending is None:
        raise KeyError(challenge_id)

    caller = AuthContext(
        subject=pending.subject,
        groups=list(pending.groups),
        auth_method="tool_challenge",
        tenant_id=pending.tenant_id,
    )
    registry = build_registry(tool_policy, rag_policy)
    entry = get_tool(registry, pending.tool)
    findings = [Finding(**f) if isinstance(f, dict) else f for f in pending.findings]

    if entry is None:
        queue.remove(challenge_id, tenant_id=tenant_id)
        raise ValueError(f"Unknown tool: {pending.tool}")
    if entry.description_blocked:
        queue.remove(challenge_id, tenant_id=tenant_id)
        raise ValueError("Tool blocked — description failed injection scan at registry load")
    if not caller_allowed_for_tool(caller.groups, entry):
        queue.remove(challenge_id, tenant_id=tenant_id)
        raise ValueError(f"Caller not authorized for tool {pending.tool}")

    record(
        AuditEvent(
            timestamp=time.time(),
            kind="tool_challenge_approved",
            decision=Decision.ALLOW,
            risk_score=pending.risk_score,
            source=pending.tool,
            subject=operator_subject,
            tenant_id=pending.tenant_id,
            findings=findings,
            detail=f"Approved pending tool invoke {challenge_id} (caller={pending.subject})",
        )
    )

    response = _execute_backend(
        pending.tool,
        pending.arguments,
        entry,
        auth=caller,
        findings=findings,
        risk_score=pending.risk_score,
        reason_override="Tool invocation allowed after operator CHALLENGE approval",
    )
    queue.remove(challenge_id, tenant_id=tenant_id)
    return response, pending


def deny_tool_challenge(
    challenge_id: str,
    *,
    operator_subject: str,
    tenant_id: str = "default",
    reason: str = "",
) -> PendingToolChallenge:
    """Deny a held invoke: audit, remove from queue, never run backend."""
    queue = get_tool_challenge_queue()
    pending = queue.remove(challenge_id, tenant_id=tenant_id)
    if pending is None:
        raise KeyError(challenge_id)

    findings = [Finding(**f) if isinstance(f, dict) else f for f in pending.findings]
    detail = reason.strip() or f"Denied pending tool invoke {challenge_id} (caller={pending.subject})"
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="tool_challenge_denied",
            decision=Decision.BLOCK,
            risk_score=pending.risk_score,
            source=pending.tool,
            subject=operator_subject,
            tenant_id=pending.tenant_id,
            findings=findings,
            detail=detail,
        )
    )
    return pending


def _execute_backend(
    tool: str,
    arguments: Dict[str, Any],
    entry: Any,
    *,
    auth: AuthContext,
    findings: List[Finding],
    risk_score: float,
    reason_override: Optional[str] = None,
) -> ToolInvokeResponse:
    handler = BACKEND_HANDLERS.get(entry.backend)
    if handler is None:
        reason = f"Unknown backend: {entry.backend}"
        return _finalize(
            tool,
            Decision.BLOCK,
            risk_score=1.0,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    try:
        result = handler(arguments, entry)
    except ValidationError as exc:
        reason = f"Backend rejected arguments: {exc.errors()[0]['msg']}"
        return _finalize(
            tool,
            Decision.BLOCK,
            risk_score=0.5,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
            http_status_hint=422,
        )
    except McpShimError as exc:
        reason = f"MCP backend error: {exc}"
        return _finalize(
            tool,
            Decision.BLOCK,
            risk_score=0.8,
            reason=reason,
            findings=findings,
            auth=auth,
            result=None,
        )

    reason = reason_override or "Tool invocation allowed"
    return _finalize(
        tool,
        Decision.ALLOW,
        risk_score=risk_score,
        reason=reason,
        findings=findings,
        auth=auth,
        result=result,
    )


def _finalize(
    tool: str,
    decision: Decision,
    *,
    risk_score: float,
    reason: str,
    findings: List[Finding],
    auth: AuthContext,
    result: Optional[Dict[str, Any]],
    http_status_hint: Optional[int] = None,
    challenge_id: Optional[str] = None,
) -> ToolInvokeResponse:
    response = ToolInvokeResponse(
        tool=tool,
        decision=decision,
        risk_score=risk_score,
        reason=reason,
        findings=findings,
        result=result,
        blocked=decision != Decision.ALLOW,
        subject=auth.subject,
        groups=list(auth.groups),
        http_status_hint=http_status_hint,
        challenge_id=challenge_id,
    )
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="tool_invoke",
            decision=decision,
            risk_score=risk_score,
            source=tool,
            subject=auth.subject,
            tenant_id=auth.tenant_id,
            findings=findings,
            detail=reason if not challenge_id else f"{reason} [challenge_id={challenge_id}]",
        )
    )
    return response
