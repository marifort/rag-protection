"""Request/response schemas for Marifort Gate."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "allow"
    CHALLENGE = "challenge"
    BLOCK = "block"


class Finding(BaseModel):
    scanner: str
    category: str
    severity: float = Field(ge=0.0, le=1.0)
    snippet: Optional[str] = None
    detail: Optional[str] = None
    label: Optional[str] = None


class Verdict(BaseModel):
    decision: Decision
    risk_score: float = Field(ge=0.0, le=1.0)
    reason: str
    findings: List[Finding] = Field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.decision == Decision.BLOCK


class InputScanRequest(BaseModel):
    text: str
    source: str = "unknown"
    trusted: bool = False
    subject: Optional[str] = None
    tenant_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class InputScanResponse(BaseModel):
    verdict: Verdict
    sanitized_text: str
    redactions: int = 0


class OutputScanRequest(BaseModel):
    text: str
    subject: Optional[str] = None
    tenant_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class OutputScanResponse(BaseModel):
    verdict: Verdict
    sanitized_text: str
    redactions: int = 0


class CitationClaimAuditPreview(BaseModel):
    """Compact per-claim citation row for audit detail / debug forensics (E3.4 / E3.5)."""

    sentence: str
    chunk_id: Optional[str] = None
    supported: bool = False
    entailment_score: Optional[float] = None


class AuditDebugPreview(BaseModel):
    """Sanitized, truncated text previews for forensic audit (opt-in via audit.debug_mode)."""

    query_preview: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    redactions: Optional[int] = None
    chunk_ids: List[str] = Field(default_factory=list)
    citation_coverage_ratio: Optional[float] = None
    citation_claims: List[CitationClaimAuditPreview] = Field(default_factory=list)


class AuditEvent(BaseModel):
    timestamp: float
    kind: str
    decision: Decision
    risk_score: float
    source: Optional[str] = None
    subject: Optional[str] = None
    tenant_id: Optional[str] = None
    findings: List[Finding] = Field(default_factory=list)
    detail: Optional[str] = None
    debug: Optional[AuditDebugPreview] = None


class DocumentIngestRequest(BaseModel):
    document_id: str
    title: str
    content: str
    allowed_groups: List[str] = Field(default_factory=lambda: ["all-staff"])
    metadata: Dict[str, Any] = Field(default_factory=dict)
    audit_debug: bool = False


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=4, ge=1, le=20)
    include_audit: bool = False
    audit_debug: bool = False
    include_retrieval_trace: bool = False


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    text: str
    score: float
    scan_verdict: Optional[str] = None
    blocked: bool = False


class RetrievalDecision(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    score: float
    outcome: str  # selected | excluded_acl | excluded_quarantine | excluded_low_score | not_in_top_k
    detail: str = ""


class CitationClaim(BaseModel):
    sentence: str
    chunk_id: Optional[str] = None
    offset_start: int = 0
    offset_end: int = 0
    supported: bool = False
    entailment_score: Optional[float] = None


class CitationCheck(BaseModel):
    passed: bool
    coverage_ratio: float
    system_prompt_leak: bool = False
    detail: str = ""
    claims: List[CitationClaim] = Field(default_factory=list)
    hard_gate_failed: bool = False
    unsupported_count: int = 0


class QueryResponse(BaseModel):
    answer: str
    blocked: bool = False
    block_reason: Optional[str] = None
    block_detail: Optional[str] = None
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    citations: Optional[CitationCheck] = None
    retrieval_trace: List[RetrievalDecision] = Field(default_factory=list)
    llm_route: Optional[Dict[str, Any]] = None
    output_verdict: Optional[str] = None
    query_verdict: Optional[str] = None
    subject: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    audit: List[AuditEvent] = Field(default_factory=list)


class ToolInvokeRequest(BaseModel):
    tool: str = Field(min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    tool: str
    decision: Decision
    risk_score: float = Field(ge=0.0, le=1.0)
    reason: str
    findings: List[Finding] = Field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    blocked: bool = False
    subject: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    http_status_hint: Optional[int] = None
    challenge_id: Optional[str] = None


class ToolSummary(BaseModel):
    name: str
    description: str
    allowed: bool
    description_blocked: bool = False
