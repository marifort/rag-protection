"""RAG query orchestration pipeline."""

from __future__ import annotations

import json
import time
from typing import List, Optional, Tuple

from rag_protection_proxy.acl import AuthContext
from rag_protection_proxy.audit import audit_debug_active, build_audit_debug_preview, record
from rag_protection_proxy.config import Policy
from rag_protection_proxy.context_builder import build_messages
from rag_protection_proxy.guardrails.canary import (
    filter_canaries,
    find_canary_token_in_text,
    inspect_candidates,
    record_canary_event,
    CanaryHit,
)
from rag_protection_proxy.guardrails.citation import verify_citations
from rag_protection_proxy.guardrails.extraction import observe_query
from rag_protection_proxy.guardrails.input_pipeline import scan_input
from rag_protection_proxy.guardrails.output_pipeline import scan_output
from rag_protection_proxy.guardrails.risk_scoring import is_effective_block
from rag_protection_proxy.llm import LLMClient
from rag_protection_proxy.llm_routing import record_llm_routed, resolve_llm_route
from rag_protection_proxy.models import (
    AuditEvent,
    CitationCheck,
    CitationClaimAuditPreview,
    Decision,
    InputScanRequest,
    InputScanResponse,
    OutputScanRequest,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
    RetrievalDecision,
)
from rag_protection_proxy.otel import trace_span
from rag_protection_proxy.retrieval_trace import explain_search, record_retrieval_trace
from rag_protection_proxy.store import DocumentStoreBackend


SAFE_FALLBACK = (
    "I cannot provide that answer because the response failed security verification. "
    "Please rephrase your question or contact an administrator."
)


def _query_audit_debug(policy: Policy, req: QueryRequest) -> bool:
    return audit_debug_active(policy, request_flag=req.audit_debug)


def _input_scan_request(
    req: QueryRequest,
    policy: Policy,
    auth: AuthContext,
    *,
    text: str,
    source: str,
    trusted: bool = False,
) -> InputScanRequest:
    return InputScanRequest(
        text=text,
        source=source,
        trusted=trusted,
        subject=auth.subject,
        tenant_id=auth.tenant_id,
        context={"audit_debug": _query_audit_debug(policy, req)},
    )


def _debug_preview(
    policy: Policy,
    req: QueryRequest,
    *,
    query_text: Optional[str] = None,
    output_text: Optional[str] = None,
    chunk_ids: Optional[List[str]] = None,
    citation: Optional[CitationCheck] = None,
):
    claims = _citation_claim_previews(citation) if citation is not None else None
    return build_audit_debug_preview(
        enabled=_query_audit_debug(policy, req),
        max_preview_chars=policy.audit.debug_max_preview_chars,
        query_text=query_text,
        output_text=output_text,
        chunk_ids=chunk_ids,
        citation_coverage_ratio=citation.coverage_ratio if citation is not None else None,
        citation_claims=claims,
    )


def _attach_recent_audit(response: QueryResponse, req: QueryRequest) -> QueryResponse:
    if req.include_audit:
        from rag_protection_proxy.audit import recent

        response.audit = recent(20)
    return response


def _record_query_trace(
    policy: Policy,
    req: QueryRequest,
    auth: AuthContext,
    *,
    decision: Decision,
    risk_score: float,
    detail: str,
    query_scan: Optional[InputScanResponse] = None,
    output_text: Optional[str] = None,
    chunk_ids: Optional[List[str]] = None,
    citation: Optional[CitationCheck] = None,
) -> None:
    debug = _debug_preview(
        policy,
        req,
        query_text=query_scan.sanitized_text if query_scan else None,
        output_text=output_text,
        chunk_ids=chunk_ids,
        citation=citation,
    )
    if debug is None:
        return
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="query_trace",
            decision=decision,
            risk_score=risk_score,
            subject=auth.subject,
            tenant_id=auth.tenant_id,
            source="rag:query",
            detail=detail,
            debug=debug,
        )
    )


def _citation_claim_previews(
    citation: CitationCheck,
    *,
    limit: int = 20,
) -> List[CitationClaimAuditPreview]:
    rows: List[CitationClaimAuditPreview] = []
    for claim in citation.claims[:limit]:
        rows.append(
            CitationClaimAuditPreview(
                sentence=(claim.sentence or "")[:200],
                chunk_id=claim.chunk_id,
                supported=bool(claim.supported),
                entailment_score=claim.entailment_score,
            )
        )
    return rows


def _citation_audit_detail(citation: CitationCheck) -> str:
    """Structured audit detail for citation failures (includes hard-gate + entailment)."""
    claims = _citation_claim_previews(citation)
    payload: dict = {
        "summary": citation.detail,
        "hard_gate_failed": citation.hard_gate_failed,
        "unsupported_count": citation.unsupported_count,
        "coverage_ratio": citation.coverage_ratio,
    }
    if claims:
        payload["claims"] = [claim.model_dump() for claim in claims]
        payload["unsupported_claims"] = [
            {
                "sentence": claim.sentence,
                "chunk_id": claim.chunk_id,
                "entailment_score": claim.entailment_score,
            }
            for claim in claims
            if not claim.supported
        ]
    return json.dumps(payload, separators=(",", ":"))


def _compute_retrieval_trace(policy: Policy, req: QueryRequest) -> bool:
    """Run explain_search when the client requests a response trace or policy audits traces."""
    return bool(policy.retrieval.explainability_enabled or req.include_retrieval_trace)


def _trace_for_response(
    req: QueryRequest,
    decisions: List[RetrievalDecision],
) -> List[RetrievalDecision]:
    # FR-15.2: response field only when the request opts in. Policy explainability
    # (FR-15.3) persists to audit without forcing the response payload.
    if req.include_retrieval_trace:
        return decisions
    return []


async def run_query(
    req: QueryRequest,
    auth: AuthContext,
    store: DocumentStoreBackend,
    policy: Policy,
) -> QueryResponse:
    with trace_span("rag.query", {"tenant_id": auth.tenant_id, "subject": auth.subject}):
        with trace_span("scan_input", {"source": "rag:user_query"}):
            query_scan = scan_input(
                _input_scan_request(req, policy, auth, text=req.query, source="rag:user_query"),
                policy,
            )
        if is_effective_block(query_scan.verdict.decision, policy.input.challenge_mode):
            record(
                AuditEvent(
                    timestamp=time.time(),
                    kind="query_blocked",
                    decision=Decision.BLOCK,
                    risk_score=query_scan.verdict.risk_score,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    source="rag:user_query",
                    findings=query_scan.verdict.findings,
                    detail=query_scan.verdict.reason,
                    debug=_debug_preview(policy, req, query_text=query_scan.sanitized_text),
                )
            )
            _record_query_trace(
                policy,
                req,
                auth,
                decision=Decision.BLOCK,
                risk_score=query_scan.verdict.risk_score,
                detail="query blocked by input guardrails",
                query_scan=query_scan,
            )
            return _attach_recent_audit(
                QueryResponse(
                    answer="Your query was blocked by security guardrails.",
                    blocked=True,
                    block_reason="query_guardrail_blocked",
                    subject=auth.subject,
                    groups=auth.groups,
                    chunks=[],
                    query_verdict=query_scan.verdict.decision.value,
                ),
                req,
            )

        with trace_span("retrieve_chunks", {"top_k": req.top_k}):
            retrieval_decisions: List[RetrievalDecision] = []
            if _compute_retrieval_trace(policy, req):
                retrieved, retrieval_decisions = explain_search(
                    store,
                    req.query,
                    auth.groups,
                    top_k=req.top_k,
                    rules=policy.retrieval,
                )
                if policy.retrieval.explainability_enabled:
                    record_retrieval_trace(
                        subject=auth.subject,
                        tenant_id=auth.tenant_id,
                        query=req.query,
                        decisions=retrieval_decisions,
                    )
            else:
                retrieved = store.search(req.query, auth.groups, top_k=req.top_k)

        response_trace = _trace_for_response(req, retrieval_decisions)

        canary_hit: Optional[CanaryHit] = inspect_candidates(retrieved, auth, policy.canary)
        if canary_hit is not None:
            # Tripwire fired: contain (never return the decoy) and record a P1 event.
            record_canary_event(canary_hit)
            retrieved = filter_canaries(retrieved)

        if policy.extraction.enabled:
            extraction_score = observe_query(
                subject=auth.subject,
                tenant_id=auth.tenant_id,
                document_ids=[chunk.document_id for chunk in retrieved],
                query=req.query,
                corpus_size=store.count_documents(),
                rules=policy.extraction,
            )
            if extraction_score.severity == "severe" and policy.extraction.action in (
                "challenge",
                "throttle",
            ):
                _record_query_trace(
                    policy,
                    req,
                    auth,
                    decision=Decision.BLOCK,
                    risk_score=0.9,
                    detail="corpus extraction suspected",
                    query_scan=query_scan,
                )
                cause = extraction_score.trigger_summary or "corpus extraction suspected"
                return QueryResponse(
                    answer=(
                        "Your session was paused because it looks like an attempt to "
                        f"systematically extract the knowledge base ({cause}). "
                        "Please contact an administrator."
                    ),
                    blocked=True,
                    block_reason="extraction_suspected",
                    block_detail=cause,
                    subject=auth.subject,
                    groups=auth.groups,
                    chunks=[],
                    query_verdict=query_scan.verdict.decision.value,
                    retrieval_trace=response_trace,
                )

        if not retrieved:
            return QueryResponse(
                answer="No authorized documents matched your question in the knowledge base.",
                subject=auth.subject,
                groups=auth.groups,
                chunks=[],
                query_verdict=query_scan.verdict.decision.value,
                retrieval_trace=response_trace,
            )

        chunk_models: List[RetrievedChunk] = []
        context_blocks: List[Tuple[str, str, str]] = []

        for chunk in retrieved:
            scan = scan_input(
                _input_scan_request(
                    req,
                    policy,
                    auth,
                    text=chunk.text,
                    source=f"rag:chunk:{chunk.chunk_id}",
                ),
                policy,
            )
            blocked = is_effective_block(scan.verdict.decision, policy.input.challenge_mode)
            chunk_models.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    text=scan.sanitized_text if not blocked else "[blocked chunk]",
                    score=chunk.score,
                    scan_verdict=scan.verdict.decision.value,
                    blocked=blocked,
                )
            )
            if not blocked:
                context_blocks.append((chunk.chunk_id, chunk.title, scan.sanitized_text))

        if not context_blocks:
            chunk_ids = [chunk.chunk_id for chunk in chunk_models]
            record(
                AuditEvent(
                    timestamp=time.time(),
                    kind="query_blocked",
                    decision=Decision.BLOCK,
                    risk_score=1.0,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    detail="all retrieved chunks blocked by input guardrails",
                    debug=_debug_preview(
                        policy,
                        req,
                        query_text=query_scan.sanitized_text,
                        chunk_ids=chunk_ids,
                    ),
                )
            )
            _record_query_trace(
                policy,
                req,
                auth,
                decision=Decision.BLOCK,
                risk_score=1.0,
                detail="all retrieved chunks blocked by input guardrails",
                query_scan=query_scan,
                chunk_ids=chunk_ids,
            )
            return QueryResponse(
                answer="Retrieved content was blocked by security guardrails.",
                blocked=True,
                block_reason="all_chunks_blocked",
                subject=auth.subject,
                groups=auth.groups,
                chunks=chunk_models,
                query_verdict=query_scan.verdict.decision.value,
                retrieval_trace=response_trace,
            )

        blocked_ids = {m.chunk_id for m in chunk_models if m.blocked}
        route_meta = [
            chunk.metadata if isinstance(getattr(chunk, "metadata", None), dict) else {}
            for chunk in retrieved
            if chunk.chunk_id not in blocked_ids
        ]
        route = resolve_llm_route(policy, route_meta)
        if policy.llm_routing.enabled:
            record_llm_routed(
                decision=route,
                subject=auth.subject,
                tenant_id=auth.tenant_id,
            )
        if route.blocked:
            _record_query_trace(
                policy,
                req,
                auth,
                decision=Decision.BLOCK,
                risk_score=0.9,
                detail=route.reason,
                query_scan=query_scan,
                chunk_ids=[c.chunk_id for c in chunk_models],
            )
            return QueryResponse(
                answer=(
                    "This query was blocked because retrieved document classification "
                    "has no allowed LLM endpoint under the residency routing policy."
                ),
                blocked=True,
                block_reason=route.block_reason or "llm_routing_blocked",
                subject=auth.subject,
                groups=auth.groups,
                chunks=chunk_models,
                llm_route=route.audit_detail(),
                query_verdict=query_scan.verdict.decision.value,
                retrieval_trace=response_trace,
            )

        messages = build_messages(req.query, context_blocks)
        llm = LLMClient(route.llm)
        with trace_span("llm_generate", {"endpoint_id": route.endpoint_id}):
            raw_answer = await llm.chat(messages)

        chunk_ids = [chunk_id for chunk_id, _, _ in context_blocks]
        with trace_span("verify_citations"):
            citation: CitationCheck = verify_citations(
                raw_answer,
                [(chunk_id, text) for chunk_id, _, text in context_blocks],
                policy.output,
            )
        if not citation.passed:
            record(
                AuditEvent(
                    timestamp=time.time(),
                    kind="citation_failed",
                    decision=Decision.BLOCK,
                    risk_score=0.9,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    detail=_citation_audit_detail(citation),
                    debug=_debug_preview(
                        policy,
                        req,
                        query_text=query_scan.sanitized_text,
                        output_text=raw_answer,
                        chunk_ids=chunk_ids,
                        citation=citation,
                    ),
                )
            )
            _record_query_trace(
                policy,
                req,
                auth,
                decision=Decision.BLOCK,
                risk_score=0.9,
                detail="citation verification failed",
                query_scan=query_scan,
                output_text=raw_answer,
                chunk_ids=chunk_ids,
                citation=citation,
            )
            block_reason = (
                "citation_hard_gate_failed"
                if citation.hard_gate_failed
                else "citation_verification_failed"
            )
            return QueryResponse(
                answer=SAFE_FALLBACK,
                blocked=True,
                block_reason=block_reason,
                subject=auth.subject,
                groups=auth.groups,
                chunks=chunk_models,
                citations=citation,
                query_verdict=query_scan.verdict.decision.value,
                retrieval_trace=response_trace,
            )

        with trace_span("scan_output"):
            output = scan_output(
                OutputScanRequest(
                    text=raw_answer,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    context={"audit_debug": _query_audit_debug(policy, req)},
                ),
                policy,
            )
        if is_effective_block(output.verdict.decision, policy.output.challenge_mode):
            record(
                AuditEvent(
                    timestamp=time.time(),
                    kind="query_blocked",
                    decision=Decision.BLOCK,
                    risk_score=output.verdict.risk_score,
                    subject=auth.subject,
                    tenant_id=auth.tenant_id,
                    source="rag:output",
                    findings=output.verdict.findings,
                    detail=output.verdict.reason,
                    debug=_debug_preview(
                        policy,
                        req,
                        query_text=query_scan.sanitized_text,
                        output_text=output.sanitized_text,
                        chunk_ids=chunk_ids,
                    ),
                )
            )
            _record_query_trace(
                policy,
                req,
                auth,
                decision=Decision.BLOCK,
                risk_score=output.verdict.risk_score,
                detail="output blocked by guardrails",
                query_scan=query_scan,
                output_text=output.sanitized_text,
                chunk_ids=chunk_ids,
            )
            return QueryResponse(
                answer=SAFE_FALLBACK,
                blocked=True,
                block_reason="output_guardrail_blocked",
                subject=auth.subject,
                groups=auth.groups,
                chunks=chunk_models,
                citations=citation,
                output_verdict=output.verdict.decision.value,
                query_verdict=query_scan.verdict.decision.value,
                retrieval_trace=response_trace,
            )

        if policy.canary.enabled and policy.canary.output_backstop:
            leaked = find_canary_token_in_text(
                output.sanitized_text, [c.token for c in [canary_hit] if c and c.token]
            )
            if leaked is not None:
                record_canary_event(
                    CanaryHit(
                        document_id=canary_hit.document_id if canary_hit else "",
                        chunk_id=canary_hit.chunk_id if canary_hit else "",
                        subject=auth.subject,
                        tenant_id=auth.tenant_id,
                        token=leaked,
                        sensitivity=canary_hit.sensitivity if canary_hit else "restricted",
                        stage="output",
                    )
                )
                return QueryResponse(
                    answer=SAFE_FALLBACK,
                    blocked=True,
                    block_reason="canary_token_in_output",
                    subject=auth.subject,
                    groups=auth.groups,
                    chunks=chunk_models,
                    citations=citation,
                    output_verdict=output.verdict.decision.value,
                    query_verdict=query_scan.verdict.decision.value,
                    retrieval_trace=response_trace,
                )

        response = QueryResponse(
            answer=output.sanitized_text,
            subject=auth.subject,
            groups=auth.groups,
            chunks=chunk_models,
            citations=citation,
            llm_route=route.audit_detail() if policy.llm_routing.enabled else None,
            output_verdict=output.verdict.decision.value,
            query_verdict=query_scan.verdict.decision.value,
            retrieval_trace=response_trace,
        )
        _record_query_trace(
            policy,
            req,
            auth,
            decision=Decision.ALLOW,
            risk_score=output.verdict.risk_score,
            detail="query completed",
            query_scan=query_scan,
            output_text=output.sanitized_text,
            chunk_ids=chunk_ids,
            citation=citation,
        )
        return _attach_recent_audit(response, req)
