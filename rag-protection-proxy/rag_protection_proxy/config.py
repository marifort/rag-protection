"""Policy and ACL configuration loading."""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

MAX_CUSTOM_PATTERN_LENGTH = 500
CUSTOM_PATTERN_VALIDATION_TIMEOUT_SEC = 0.25
_DANGEROUS_REGEX = re.compile(r"(\([^)]*[+*][^)]*\)[+*{])|(\)[+*{]\s*[+*{])")


class PolicyValidationError(ValueError):
    """Raised when policy.yaml contains invalid guardrail configuration."""


VALID_CUSTOM_PATTERN_KINDS = frozenset({"dlp", "secret"})


@dataclass
class CustomPattern:
    name: str
    regex: re.Pattern[str]
    replacement: str
    label: Optional[str] = None
    severity: float = 0.5
    enabled: bool = True
    kind: str = "dlp"


@dataclass
class InjectionPattern:
    name: str
    regex: re.Pattern[str]
    severity: float = 0.85
    detail: str = "Policy-defined injection pattern."
    enabled: bool = True


BUILTIN_INJECTION_CATEGORIES: List[str] = [
    "instruction_override",
    "role_hijack",
    "fake_system_prompt",
    "chat_template_injection",
    "exfiltration_directive",
    "destructive_action",
    "secret_extraction",
    "pii_exfiltration",
    "obfuscated_payload",
    "hidden_chars",
    "html_comment_injection",
    "markdown_js_link",
    "base64_payload",
]

BUILTIN_INJECTION_CATEGORY_META: Dict[str, Dict[str, str]] = {
    "instruction_override": {
        "label": "Instruction override",
        "detail": "Ignore or override prior instructions.",
    },
    "role_hijack": {
        "label": "Role hijack",
        "detail": "Act as admin, jailbroken, or unfiltered assistant.",
    },
    "fake_system_prompt": {
        "label": "Fake system prompt",
        "detail": "Embedded system:/developer: prefixes.",
    },
    "chat_template_injection": {
        "label": "Chat template injection",
        "detail": "im_start/im_end and similar control tokens.",
    },
    "exfiltration_directive": {
        "label": "Exfiltration directive",
        "detail": "Send data externally or embed outbound HTTP calls.",
    },
    "destructive_action": {
        "label": "Destructive action",
        "detail": "Delete, drop, wipe, or rm -rf directives.",
    },
    "secret_extraction": {
        "label": "Secret extraction",
        "detail": "Reveal API keys, passwords, tokens, or system prompts.",
    },
    "pii_exfiltration": {
        "label": "PII exfiltration",
        "detail": "Request to dump SSNs or other PII values (ask intent, not value redaction).",
    },
    "obfuscated_payload": {
        "label": "Obfuscated payload",
        "detail": "Decode-then-execute instructions.",
    },
    "hidden_chars": {
        "label": "Hidden characters",
        "detail": "Zero-width and bidi control characters.",
    },
    "html_comment_injection": {
        "label": "HTML comment injection",
        "detail": "Instructional content inside HTML comments.",
    },
    "markdown_js_link": {
        "label": "Markdown JS link",
        "detail": "javascript: links in markdown.",
    },
    "base64_payload": {
        "label": "Base64 payload",
        "detail": "Base64 blobs with instruction-like decode.",
    },
}


def default_injection_categories() -> Dict[str, bool]:
    return {category: True for category in BUILTIN_INJECTION_CATEGORIES}


def builtin_injection_category_catalog() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for category in BUILTIN_INJECTION_CATEGORIES:
        meta = BUILTIN_INJECTION_CATEGORY_META.get(category, {})
        rows.append(
            {
                "category": category,
                "label": meta.get("label", category),
                "detail": meta.get("detail", ""),
            }
        )
    return rows


@dataclass
class DLPPolicy:
    enable_ner: bool = True
    labels: List[str] = field(default_factory=lambda: ["PCI", "PHI"])
    custom_patterns: List[CustomPattern] = field(default_factory=list)


@dataclass
class InputPolicy:
    challenge_threshold: float = 0.4
    block_threshold: float = 0.8
    challenge_mode: str = "block"
    strip_hidden_chars: bool = True
    strip_html_comments: bool = True
    redact_pii: bool = True
    redact_secrets: bool = True
    ml_injection_enabled: bool = True
    ml_injection_threshold: float = 0.72
    injection_categories: Dict[str, bool] = field(default_factory=default_injection_categories)
    custom_injection_patterns: List[InjectionPattern] = field(default_factory=list)


@dataclass
class OutputPolicy:
    challenge_threshold: float = 0.5
    block_threshold: float = 0.85
    challenge_mode: str = "block"
    min_citation_coverage: float = 0.15
    block_system_prompt_leak: bool = True
    per_claim_citations: bool = True
    # When true, every substantive claim must map to a source chunk_id (hard gate).
    hard_citation_gate: bool = False
    substantive_min_tokens: int = 3
    entailment_check: bool = True
    entailment_threshold: float = 0.55


@dataclass
class NetworkPolicy:
    allowed_domains: List[str] = field(default_factory=list)
    denied_domains: List[str] = field(default_factory=list)
    block_private_ranges: bool = True


@dataclass
class LLMPolicy:
    base_url: str = "http://model-runner.docker.internal/engines/v1"
    model: str = "ai/gemma3-qat"
    api_key: str = "not-needed"
    timeout_seconds: float = 60.0
    max_tokens: int = 512
    temperature: float = 0.2


@dataclass
class LLMEndpointProfile:
    """Named LLM endpoint override for residency / multi-region routing (T0.6)."""

    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[float] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


@dataclass
class LLMRouteRule:
    """Map a classification label (exact or prefix) to an endpoint id."""

    match: str
    endpoint_id: str


@dataclass
class LLMRoutingPolicy:
    """Classification → LLM endpoint routing (T0.6 / #18). Off by default."""

    enabled: bool = False
    fail_closed: bool = True
    default_endpoint_id: str = "default"
    # Highest sensitivity first (e.g. highly-confidential before public).
    classification_rank: List[str] = field(default_factory=list)
    endpoints: Dict[str, LLMEndpointProfile] = field(default_factory=dict)
    routes: List[LLMRouteRule] = field(default_factory=list)


@dataclass
class AuditSampleRule:
    """Write-time sampling for high-volume hygiene audit kinds.

    When an event's decision is in ``when_decision`` and it is not "interesting"
    (see ``audit.should_record_event``), keep 1 of every ``keep_every`` events.
    ``keep_every: 0`` drops all routine matches (default for connector heartbeats).
    """

    when_decision: List[str] = field(default_factory=lambda: ["allow"])
    keep_every: int = 0


def _default_audit_sample_by_kind() -> Dict[str, AuditSampleRule]:
    # Routine green connector ticks flood the operator UI at 1‑minute intervals.
    # Always-keep paths (errors, acl_updated, drift, mapping failure) bypass this.
    return {
        "connector_sync": AuditSampleRule(when_decision=["allow"], keep_every=0),
        "acl_sync": AuditSampleRule(when_decision=["allow"], keep_every=0),
    }


def _default_audit_retention_by_kind() -> Dict[str, int]:
    return {
        "connector_sync": 3,
        "acl_sync": 7,
        "permission_drift": 90,
        "canary_triggered": 90,
        "extraction_suspected": 90,
    }


def _default_audit_retain_decisions() -> Dict[str, int]:
    return {
        "block": 90,
        "challenge": 30,
    }


@dataclass
class AuditPolicy:
    retention_days: int = 7
    backup_keep_days: int = 7
    scrub_export: bool = True
    max_export_rows: int = 5000
    debug_mode: bool = False
    debug_max_preview_chars: int = 500
    debug_retention_hours: int = 24
    debug_webhook: bool = False
    # Hash-chained JSONL integrity (T0.4). Each event links to the previous via SHA-256.
    integrity_chain: bool = False
    # Drop/sample routine hygiene kinds at write time (connector heartbeats).
    sample_by_kind: Dict[str, AuditSampleRule] = field(default_factory=_default_audit_sample_by_kind)
    # Per-kind TTL (days); retain_decisions extends keep for high-severity outcomes.
    retention_by_kind: Dict[str, int] = field(default_factory=_default_audit_retention_by_kind)
    retain_decisions: Dict[str, int] = field(default_factory=_default_audit_retain_decisions)


@dataclass
class RetrievalPolicy:
    """Retrieval-decision explainability (T0.7)."""

    explainability_enabled: bool = False
    max_trace_candidates: int = 100


@dataclass
class TenantQuotas:
    queries_per_minute: int = 0
    burst: int = 10


@dataclass
class ConnectorSyncJob:
    connector: str
    tenant_id: str = "default"
    source_id: str = ""
    fixture_path: Optional[str] = None
    group_map: Optional[Dict[str, str]] = None


@dataclass
class DriftPolicy:
    """Permission drift monitor (Lab 4). Off by default."""

    enabled: bool = False
    critical_if_public: bool = True
    critical_group_count: int = 5
    auto_quarantine_on_critical: bool = False


@dataclass
class AclSyncPolicy:
    """Real-time ACL sync v2 (T0.5) — faster permission refresh without full re-ingest."""

    enabled: bool = False
    min_interval_minutes: int = 1
    acl_only_when_unchanged: bool = True


@dataclass
class ConnectorsPolicy:
    enabled: bool = False
    schedule_interval_minutes: int = 60
    jobs: List[ConnectorSyncJob] = field(default_factory=list)
    # deny = empty allowed_groups (fail-closed); all_staff = legacy permissive fallback
    unmapped_permissions: str = "deny"
    drift: DriftPolicy = field(default_factory=DriftPolicy)
    acl_sync: AclSyncPolicy = field(default_factory=AclSyncPolicy)


@dataclass
class ExtractionPolicy:
    """Corpus-extraction (scraping) monitor (Lab 9).

    A cross-query behavioral signal on the retrieval stream: detects an authorized
    user quietly walking the whole corpus via many innocuous queries. Off by default.
    """

    enabled: bool = False
    window_seconds: int = 3600
    min_window_queries: int = 20  # ignore short sessions for breadth/novelty
    min_corpus_size: int = 50  # disable coverage signal below this (small-corpus noise)
    elevated_coverage: float = 0.25
    severe_coverage: float = 0.50
    breadth_ratio_threshold: float = 0.8
    novelty_ratio_threshold: float = 0.9
    action: str = "alert"  # alert | challenge | throttle


@dataclass
class CanaryPolicy:
    """Canary / honeypot document tripwire (Lab 10).

    A retrieved canary document for a non-auditor subject is an unambiguous signal
    that ACL enforcement has broken (or that a scraper surfaced the decoy).
    """

    enabled: bool = False
    # Subjects/groups permitted to retrieve canaries without tripping (verification bots).
    auditor_subjects: List[str] = field(default_factory=list)
    auditor_groups: List[str] = field(default_factory=list)
    # Also scan the final answer for registered canary tokens (defense in depth).
    output_backstop: bool = True
    # Default sensitivity label recorded when seeding a canary.
    default_sensitivity: str = "restricted"


@dataclass
class Policy:
    version: int = 1
    input: InputPolicy = field(default_factory=InputPolicy)
    output: OutputPolicy = field(default_factory=OutputPolicy)
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    llm: LLMPolicy = field(default_factory=LLMPolicy)
    llm_routing: LLMRoutingPolicy = field(default_factory=LLMRoutingPolicy)
    dlp: DLPPolicy = field(default_factory=DLPPolicy)
    audit: AuditPolicy = field(default_factory=AuditPolicy)
    tenant: TenantQuotas = field(default_factory=TenantQuotas)
    connectors: ConnectorsPolicy = field(default_factory=ConnectorsPolicy)
    canary: CanaryPolicy = field(default_factory=CanaryPolicy)
    extraction: ExtractionPolicy = field(default_factory=ExtractionPolicy)
    retrieval: RetrievalPolicy = field(default_factory=RetrievalPolicy)


@dataclass
class DemoUser:
    token: str
    subject: str
    groups: List[str]
    tenant_id: str = "default"


@dataclass
class AdminUser:
    token: str
    subject: str
    roles: List[str]
    tenant_id: Optional[str] = None


@dataclass
class SCIMConfig:
    enabled: bool = False
    base_url: str = ""
    bearer_token: str = ""
    poll_interval_seconds: int = 300
    fixture_file: str = ""


@dataclass
class TenantConfig:
    policy_file: str = ""


@dataclass
class OIDCConfig:
    enabled: bool = False
    issuer: str = ""
    audience: str = ""
    jwks_uri: str = ""
    algorithms: List[str] = field(default_factory=lambda: ["RS256"])
    groups_claim: str = "groups"
    roles_claim: str = "roles"
    tenant_claim: str = "tenant_id"
    # IdP group/role names → operator admin roles (policy_admin, audit_reader, …).
    admin_role_map: Dict[str, List[str]] = field(default_factory=dict)
    # Members of these IdP groups receive global (all-tenant) admin scope.
    admin_global_groups: List[str] = field(default_factory=list)
    # EE operator console "Sign in with IdP" (auth code + PKCE). Unused on CE-only.
    ui_client_id: str = ""
    ui_client_secret: str = ""
    ui_redirect_uri: str = ""
    ui_scopes: str = "openid profile email"
    ui_authorize_url: str = ""
    ui_token_url: str = ""


@dataclass
class ACLPolicy:
    default_groups: List[str] = field(default_factory=lambda: ["all-staff"])
    group_hierarchy: Dict[str, List[str]] = field(default_factory=dict)
    demo_users: List[DemoUser] = field(default_factory=list)
    admin_users: List[AdminUser] = field(default_factory=list)
    jwt_groups_claim: str = "groups"
    jwt_tenant_claim: str = "tenant_id"
    jwt_secret: str = ""
    jwt_algorithms: List[str] = field(default_factory=lambda: ["HS256"])
    oidc: OIDCConfig = field(default_factory=OIDCConfig)
    scim: SCIMConfig = field(default_factory=SCIMConfig)
    tenants: Dict[str, TenantConfig] = field(default_factory=dict)


def _parse_audit_days_map(
    raw: Any,
    *,
    default: Dict[str, int],
) -> Dict[str, int]:
    if raw is None:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    out: Dict[str, int] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            days = int(value)
        except (TypeError, ValueError):
            continue
        out[name] = max(0, days)
    return out


def _parse_audit_sample_by_kind(raw: Any) -> Dict[str, AuditSampleRule]:
    """Parse sample_by_kind; missing/null → product defaults. Explicit ``{}`` disables sampling."""
    if raw is None:
        return _default_audit_sample_by_kind()
    if not isinstance(raw, dict):
        return _default_audit_sample_by_kind()
    out: Dict[str, AuditSampleRule] = {}
    for key, value in raw.items():
        kind = str(key).strip()
        if not kind:
            continue
        entry = value if isinstance(value, dict) else {}
        when_raw = entry.get("when_decision", ["allow"])
        if isinstance(when_raw, str):
            when_decision = [when_raw.strip().lower()] if when_raw.strip() else []
        elif isinstance(when_raw, list):
            when_decision = [str(item).strip().lower() for item in when_raw if str(item).strip()]
        else:
            when_decision = ["allow"]
        try:
            keep_every = int(entry.get("keep_every", 0))
        except (TypeError, ValueError):
            keep_every = 0
        out[kind] = AuditSampleRule(
            when_decision=when_decision or ["allow"],
            keep_every=max(0, keep_every),
        )
    return out


def load_policy(path: str | None = None) -> Policy:
    policy_path = Path(path or os.getenv("RAG_POLICY_FILE", "./config/policy.yaml"))
    if not policy_path.exists():
        return Policy(
            llm=LLMPolicy(
                base_url=os.getenv("RAG_LLM_BASE_URL", LLMPolicy.base_url),
                model=os.getenv("RAG_LLM_MODEL", LLMPolicy.model),
                api_key=os.getenv("RAG_LLM_API_KEY", "not-needed"),
            )
        )

    raw: Dict[str, Any] = yaml.safe_load(policy_path.read_text()) or {}
    inp = raw.get("input", {}) or {}
    out = raw.get("output", {}) or {}
    net = raw.get("network", {}) or {}
    llm = raw.get("llm", {}) or {}
    dlp = raw.get("dlp", {}) or {}
    audit = raw.get("audit", {}) or {}
    tenant = raw.get("tenant", {}) or {}
    quotas = tenant.get("quotas", {}) or {}
    connectors_raw = raw.get("connectors", {}) or {}
    drift_raw = connectors_raw.get("drift", {}) or {}
    acl_sync_raw = connectors_raw.get("acl_sync", {}) or {}

    connector_jobs: List[ConnectorSyncJob] = []
    for entry in connectors_raw.get("jobs") or []:
        if not isinstance(entry, dict):
            continue
        connector = str(entry.get("connector") or "").strip()
        source_id = str(entry.get("source_id") or "").strip()
        if not connector or not source_id:
            continue
        group_map = entry.get("group_map")
        connector_jobs.append(
            ConnectorSyncJob(
                connector=connector,
                tenant_id=str(entry.get("tenant_id") or "default"),
                source_id=source_id,
                fixture_path=str(entry.get("fixture_path") or "") or None,
                group_map=dict(group_map) if isinstance(group_map, dict) else None,
            )
        )

    connectors_enabled = bool(connectors_raw.get("enabled", False)) or _env_flag("RAG_CONNECTORS_ENABLED")
    if connector_jobs and not connectors_enabled:
        connectors_enabled = True

    canary_raw = raw.get("canary", {}) or {}
    extraction_raw = raw.get("extraction", {}) or {}
    retrieval_raw = raw.get("retrieval", {}) or {}
    llm_routing_raw = raw.get("llm_routing", {}) or {}

    routing_endpoints: Dict[str, LLMEndpointProfile] = {}
    endpoints_raw = llm_routing_raw.get("endpoints") or {}
    if isinstance(endpoints_raw, dict):
        for ep_id, ep_cfg in endpoints_raw.items():
            if not isinstance(ep_cfg, dict):
                continue
            routing_endpoints[str(ep_id)] = LLMEndpointProfile(
                base_url=str(ep_cfg["base_url"]) if ep_cfg.get("base_url") is not None else None,
                model=str(ep_cfg["model"]) if ep_cfg.get("model") is not None else None,
                api_key=str(ep_cfg["api_key"]) if ep_cfg.get("api_key") is not None else None,
                timeout_seconds=(
                    float(ep_cfg["timeout_seconds"])
                    if ep_cfg.get("timeout_seconds") is not None
                    else None
                ),
                max_tokens=(
                    int(ep_cfg["max_tokens"]) if ep_cfg.get("max_tokens") is not None else None
                ),
                temperature=(
                    float(ep_cfg["temperature"])
                    if ep_cfg.get("temperature") is not None
                    else None
                ),
            )

    routing_routes: List[LLMRouteRule] = []
    for entry in llm_routing_raw.get("routes") or []:
        if not isinstance(entry, dict):
            continue
        match = str(entry.get("match") or "").strip()
        endpoint_id = str(entry.get("endpoint_id") or "").strip()
        if match and endpoint_id:
            routing_routes.append(LLMRouteRule(match=match, endpoint_id=endpoint_id))

    return Policy(
        version=int(raw.get("version", 1)),
        input=InputPolicy(
            challenge_threshold=float(inp.get("challenge_threshold", 0.4)),
            block_threshold=float(inp.get("block_threshold", 0.8)),
            challenge_mode=str(inp.get("challenge_mode", "block")),
            strip_hidden_chars=bool(inp.get("strip_hidden_chars", True)),
            strip_html_comments=bool(inp.get("strip_html_comments", True)),
            redact_pii=bool(inp.get("redact_pii", True)),
            redact_secrets=bool(inp.get("redact_secrets", True)),
            ml_injection_enabled=bool(inp.get("ml_injection_enabled", True)),
            ml_injection_threshold=float(inp.get("ml_injection_threshold", 0.72)),
            injection_categories=load_injection_categories(inp.get("injection_categories")),
            custom_injection_patterns=load_custom_injection_patterns(
                inp.get("custom_injection_patterns")
            ),
        ),
        output=OutputPolicy(
            challenge_threshold=float(out.get("challenge_threshold", 0.5)),
            block_threshold=float(out.get("block_threshold", 0.85)),
            challenge_mode=str(out.get("challenge_mode", "block")),
            min_citation_coverage=float(out.get("min_citation_coverage", 0.15)),
            block_system_prompt_leak=bool(out.get("block_system_prompt_leak", True)),
            per_claim_citations=bool(out.get("per_claim_citations", True)),
            hard_citation_gate=bool(out.get("hard_citation_gate", False)),
            substantive_min_tokens=int(out.get("substantive_min_tokens", 3)),
            entailment_check=bool(out.get("entailment_check", True)),
            entailment_threshold=float(out.get("entailment_threshold", 0.55)),
        ),
        dlp=DLPPolicy(
            enable_ner=bool(dlp.get("enable_ner", True)),
            labels=[str(label) for label in (dlp.get("labels") or ["PCI", "PHI"])],
            custom_patterns=load_custom_patterns(dlp.get("custom_patterns")),
        ),
        network=NetworkPolicy(
            allowed_domains=_normalize_domain_list(
                net.get("allowed_domains"), "network.allowed_domains"
            ),
            denied_domains=_normalize_domain_list(
                net.get("denied_domains"), "network.denied_domains"
            ),
            block_private_ranges=bool(net.get("block_private_ranges", True)),
        ),
        llm=LLMPolicy(
            base_url=os.getenv("RAG_LLM_BASE_URL", llm.get("base_url", LLMPolicy.base_url)),
            model=os.getenv("RAG_LLM_MODEL", llm.get("model", LLMPolicy.model)),
            api_key=os.getenv("RAG_LLM_API_KEY", llm.get("api_key", "not-needed")),
            timeout_seconds=float(llm.get("timeout_seconds", 60.0)),
            max_tokens=int(llm.get("max_tokens", 512)),
            temperature=float(llm.get("temperature", 0.2)),
        ),
        llm_routing=LLMRoutingPolicy(
            enabled=bool(llm_routing_raw.get("enabled", False))
            or _env_flag("RAG_LLM_ROUTING_ENABLED"),
            fail_closed=bool(llm_routing_raw.get("fail_closed", True)),
            default_endpoint_id=str(
                llm_routing_raw.get("default_endpoint_id", "default") or "default"
            ),
            classification_rank=[
                str(item).strip()
                for item in (llm_routing_raw.get("classification_rank") or [])
                if str(item).strip()
            ],
            endpoints=routing_endpoints,
            routes=routing_routes,
        ),
        audit=AuditPolicy(
            retention_days=int(audit.get("retention_days", 7)),
            backup_keep_days=int(audit.get("backup_keep_days", 7)),
            scrub_export=bool(audit.get("scrub_export", True)),
            max_export_rows=int(audit.get("max_export_rows", 5000)),
            debug_mode=bool(audit.get("debug_mode", False)),
            debug_max_preview_chars=int(audit.get("debug_max_preview_chars", 500)),
            debug_retention_hours=int(audit.get("debug_retention_hours", 24)),
            debug_webhook=bool(audit.get("debug_webhook", False)),
            integrity_chain=bool(audit.get("integrity_chain", False)) or _env_flag("RAG_AUDIT_INTEGRITY_CHAIN"),
            sample_by_kind=_parse_audit_sample_by_kind(audit.get("sample_by_kind")),
            retention_by_kind=_parse_audit_days_map(
                audit.get("retention_by_kind"),
                default=_default_audit_retention_by_kind(),
            ),
            retain_decisions=_parse_audit_days_map(
                audit.get("retain_decisions"),
                default=_default_audit_retain_decisions(),
            ),
        ),
        tenant=TenantQuotas(
            queries_per_minute=int(quotas.get("queries_per_minute", 0)),
            burst=int(quotas.get("burst", 10)),
        ),
        connectors=ConnectorsPolicy(
            enabled=connectors_enabled,
            schedule_interval_minutes=int(connectors_raw.get("schedule_interval_minutes", 60)),
            jobs=connector_jobs,
            unmapped_permissions=str(connectors_raw.get("unmapped_permissions", "deny") or "deny"),
            drift=DriftPolicy(
                enabled=bool(drift_raw.get("enabled", False)) or _env_flag("RAG_DRIFT_ENABLED"),
                critical_if_public=bool(drift_raw.get("critical_if_public", True)),
                critical_group_count=int(drift_raw.get("critical_group_count", 5)),
                auto_quarantine_on_critical=bool(drift_raw.get("auto_quarantine_on_critical", False)),
            ),
            acl_sync=AclSyncPolicy(
                enabled=bool(acl_sync_raw.get("enabled", False)) or _env_flag("RAG_ACL_SYNC_REALTIME"),
                min_interval_minutes=max(1, int(acl_sync_raw.get("min_interval_minutes", 1))),
                acl_only_when_unchanged=bool(acl_sync_raw.get("acl_only_when_unchanged", True)),
            ),
        ),
        canary=CanaryPolicy(
            enabled=bool(canary_raw.get("enabled", False)) or _env_flag("RAG_CANARY_ENABLED"),
            auditor_subjects=_load_string_list(canary_raw.get("auditor_subjects")),
            auditor_groups=_load_string_list(canary_raw.get("auditor_groups")),
            output_backstop=bool(canary_raw.get("output_backstop", True)),
            default_sensitivity=str(canary_raw.get("default_sensitivity", "restricted") or "restricted"),
        ),
        extraction=ExtractionPolicy(
            enabled=bool(extraction_raw.get("enabled", False)) or _env_flag("RAG_EXTRACTION_ENABLED"),
            window_seconds=int(extraction_raw.get("window_seconds", 3600)),
            min_window_queries=int(extraction_raw.get("min_window_queries", 20)),
            min_corpus_size=int(extraction_raw.get("min_corpus_size", 50)),
            elevated_coverage=float(extraction_raw.get("elevated_coverage", 0.25)),
            severe_coverage=float(extraction_raw.get("severe_coverage", 0.50)),
            breadth_ratio_threshold=float(extraction_raw.get("breadth_ratio_threshold", 0.8)),
            novelty_ratio_threshold=float(extraction_raw.get("novelty_ratio_threshold", 0.9)),
            action=str(extraction_raw.get("action", "alert") or "alert"),
        ),
        retrieval=RetrievalPolicy(
            explainability_enabled=bool(retrieval_raw.get("explainability_enabled", False))
            or _env_flag("RAG_RETRIEVAL_EXPLAINABILITY"),
            max_trace_candidates=int(retrieval_raw.get("max_trace_candidates", 100)),
        ),
    )


def load_acl_policy(path: str | None = None) -> ACLPolicy:
    acl_path = Path(path or os.getenv("RAG_ACL_FILE", "./config/acl_policy.yaml"))
    if not acl_path.exists():
        return ACLPolicy()

    raw: Dict[str, Any] = yaml.safe_load(acl_path.read_text()) or {}
    demo_users = [
        DemoUser(
            token=str(u.get("token", "")),
            subject=str(u.get("subject", "unknown")),
            groups=list(u.get("groups", []) or []),
            tenant_id=str(u.get("tenant_id", "default")),
        )
        for u in (raw.get("demo_users") or [])
        if isinstance(u, dict)
    ]
    admin_users = [
        AdminUser(
            token=str(u.get("token", "")),
            subject=str(u.get("subject", "admin")),
            roles=[str(r) for r in (u.get("roles") or [])],
            tenant_id=(
                str(u["tenant_id"]).strip()
                if u.get("tenant_id") not in (None, "")
                else None
            ),
        )
        for u in (raw.get("admin_users") or [])
        if isinstance(u, dict)
    ]
    scim_raw = raw.get("scim", {}) or {}
    tenants_raw = raw.get("tenants", {}) or {}
    tenants = {
        str(name): TenantConfig(policy_file=str(cfg.get("policy_file", "")))
        for name, cfg in tenants_raw.items()
        if isinstance(cfg, dict)
    }
    return ACLPolicy(
        default_groups=list(raw.get("default_groups", ["all-staff"]) or ["all-staff"]),
        group_hierarchy=dict(raw.get("group_hierarchy", {}) or {}),
        demo_users=demo_users,
        admin_users=admin_users,
        jwt_groups_claim=str(raw.get("jwt_groups_claim", "groups")),
        jwt_tenant_claim=str(raw.get("jwt_tenant_claim", "tenant_id")),
        jwt_secret=str(raw.get("jwt_secret", os.getenv("RAG_JWT_SECRET", ""))),
        jwt_algorithms=list(raw.get("jwt_algorithms", ["HS256"]) or ["HS256"]),
        oidc=_load_oidc_config(raw.get("oidc", {}) or {}),
        scim=_load_scim_config(scim_raw),
        tenants=tenants,
    )


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_scim_config(raw: Dict[str, Any]) -> SCIMConfig:
    enabled = bool(raw.get("enabled", False)) or _env_flag("RAG_SCIM_ENABLED")
    fixture_file = str(raw.get("fixture_file") or os.getenv("RAG_SCIM_FIXTURE_FILE", ""))
    base_url = str(raw.get("base_url") or os.getenv("RAG_SCIM_BASE_URL", ""))
    bearer_token = str(raw.get("bearer_token") or os.getenv("RAG_SCIM_BEARER_TOKEN", ""))
    if enabled and not base_url and not fixture_file:
        enabled = False
    return SCIMConfig(
        enabled=enabled,
        base_url=base_url,
        bearer_token=bearer_token,
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 300)),
        fixture_file=fixture_file,
    )


def policy_for_tenant(tenant_id: str, default: Policy, acl: ACLPolicy) -> Policy:
    tenant = acl.tenants.get(tenant_id or "default")
    if tenant and tenant.policy_file:
        path = Path(tenant.policy_file)
        if path.exists():
            return load_policy(str(path))
    return default


def _load_oidc_config(raw: Dict[str, Any]) -> OIDCConfig:
    enabled = bool(raw.get("enabled", False)) or _env_flag("RAG_OIDC_ENABLED")
    issuer = str(raw.get("issuer") or os.getenv("RAG_OIDC_ISSUER", ""))
    audience = str(raw.get("audience") or os.getenv("RAG_OIDC_AUDIENCE", ""))
    jwks_uri = str(raw.get("jwks_uri") or os.getenv("RAG_OIDC_JWKS_URI", ""))
    if enabled and not jwks_uri:
        enabled = False
    ui_scopes_raw = raw.get("ui_scopes", os.getenv("RAG_OIDC_UI_SCOPES", "openid profile email"))
    if isinstance(ui_scopes_raw, list):
        ui_scopes = " ".join(str(s).strip() for s in ui_scopes_raw if str(s).strip())
    else:
        ui_scopes = str(ui_scopes_raw or "openid profile email").strip() or "openid profile email"
    return OIDCConfig(
        enabled=enabled,
        issuer=issuer,
        audience=audience,
        jwks_uri=jwks_uri,
        algorithms=list(raw.get("algorithms", ["RS256"]) or ["RS256"]),
        groups_claim=str(raw.get("groups_claim", "groups")),
        roles_claim=str(raw.get("roles_claim", "roles")),
        tenant_claim=str(raw.get("tenant_claim", "tenant_id")),
        admin_role_map=_load_admin_role_map(raw.get("admin_role_map")),
        admin_global_groups=_load_string_list(raw.get("admin_global_groups")),
        ui_client_id=str(raw.get("ui_client_id") or os.getenv("RAG_OIDC_UI_CLIENT_ID", "")),
        ui_client_secret=str(
            raw.get("ui_client_secret") or os.getenv("RAG_OIDC_UI_CLIENT_SECRET", "")
        ),
        ui_redirect_uri=str(
            raw.get("ui_redirect_uri") or os.getenv("RAG_OIDC_UI_REDIRECT_URI", "")
        ),
        ui_scopes=ui_scopes,
        ui_authorize_url=str(
            raw.get("ui_authorize_url") or os.getenv("RAG_OIDC_UI_AUTHORIZE_URL", "")
        ),
        ui_token_url=str(raw.get("ui_token_url") or os.getenv("RAG_OIDC_UI_TOKEN_URL", "")),
    )


def _load_string_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _load_admin_role_map(raw: Any) -> Dict[str, List[str]]:
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, List[str]] = {}
    for role, groups in raw.items():
        role_name = str(role).strip()
        if not role_name:
            continue
        result[role_name] = _load_string_list(groups)
    return result


def load_sample_documents(path: str | None = None) -> List[Dict[str, Any]]:
    doc_path = Path(path or os.getenv("RAG_SAMPLE_DOCS", "./config/sample_documents.json"))
    if not doc_path.exists():
        return []
    return json.loads(doc_path.read_text())


VALID_DLP_LABELS = frozenset({"PCI", "PHI", "INTERNAL"})
_CUSTOM_DLP_LABEL = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")


def pattern_labels_from_dicts(custom_patterns: Optional[List[Dict[str, Any]]]) -> List[str]:
    labels: List[str] = []
    for row in custom_patterns or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip().upper()
        if label:
            labels.append(label)
    return labels


def allowed_dlp_labels(custom_patterns: Optional[List[Dict[str, Any]]] = None) -> set[str]:
    """Built-in labels plus any label declared on custom patterns in the same save."""
    allowed = set(VALID_DLP_LABELS)
    for label in pattern_labels_from_dicts(custom_patterns):
        if _CUSTOM_DLP_LABEL.match(label):
            allowed.add(label)
    return allowed


def _normalize_domain_list(raw: Any, path: str) -> List[str]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise PolicyValidationError(f"{path} must be a list")
    domains: List[str] = []
    for idx, entry in enumerate(raw):
        domain = str(entry).strip().lower()
        if not domain:
            raise PolicyValidationError(f"{path}[{idx}] must be a non-empty domain")
        domains.append(domain)
    return domains


def filter_custom_patterns_by_kind(
    patterns: List[CustomPattern], kind: str = "dlp"
) -> List[CustomPattern]:
    return [pattern for pattern in patterns if pattern.kind == kind]


def load_custom_patterns(raw: Any) -> List[CustomPattern]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise PolicyValidationError("dlp.custom_patterns must be a list")
    patterns: List[CustomPattern] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PolicyValidationError(f"dlp.custom_patterns[{idx}] must be an object")
        patterns.append(_compile_custom_pattern(entry, idx))
    return patterns


def _compile_policy_regex(pattern: str, idx: int, path_prefix: str) -> re.Pattern[str]:
    if not pattern:
        raise PolicyValidationError(f"{path_prefix}[{idx}].regex is required")
    if len(pattern) > MAX_CUSTOM_PATTERN_LENGTH:
        raise PolicyValidationError(
            f"{path_prefix}[{idx}].regex exceeds max length ({MAX_CUSTOM_PATTERN_LENGTH})"
        )
    if _DANGEROUS_REGEX.search(pattern):
        raise PolicyValidationError(
            f"{path_prefix}[{idx}].regex may cause catastrophic backtracking"
        )
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise PolicyValidationError(f"{path_prefix}[{idx}].regex is invalid: {exc}") from exc
    _validate_custom_pattern_runtime(compiled, idx, path_prefix=path_prefix)
    return compiled


def _compile_custom_pattern(entry: Dict[str, Any], idx: int) -> CustomPattern:
    name = str(entry.get("name") or "").strip()
    if not name:
        raise PolicyValidationError(f"dlp.custom_patterns[{idx}].name is required")
    pattern = str(entry.get("regex") or "").strip()
    compiled = _compile_policy_regex(pattern, idx, "dlp.custom_patterns")
    replacement = str(entry.get("replacement") or "[REDACTED]")
    label_raw = entry.get("label")
    label = str(label_raw).strip().upper() if label_raw else None
    kind = str(entry.get("kind") or "dlp").strip().lower()
    if kind not in VALID_CUSTOM_PATTERN_KINDS:
        raise PolicyValidationError(
            f"dlp.custom_patterns[{idx}].kind must be one of: dlp, secret"
        )
    default_severity = 0.95 if kind == "secret" else 0.5
    severity = float(entry.get("severity", default_severity))
    if not 0.0 <= severity <= 1.0:
        raise PolicyValidationError(f"dlp.custom_patterns[{idx}].severity must be between 0 and 1")
    return CustomPattern(
        name=name,
        regex=compiled,
        replacement=replacement,
        label=label,
        severity=severity,
        enabled=bool(entry.get("enabled", True)),
        kind=kind,
    )


def _validate_custom_pattern_runtime(
    compiled: re.Pattern[str],
    idx: int,
    *,
    path_prefix: str = "dlp.custom_patterns",
) -> None:
    probes = ("EMP-442198", "a" * 30 + "X", "sample text for pattern validation")
    for probe in probes:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda text=probe: list(compiled.finditer(text)))
            try:
                future.result(timeout=CUSTOM_PATTERN_VALIDATION_TIMEOUT_SEC)
            except FuturesTimeout as exc:
                raise PolicyValidationError(
                    f"{path_prefix}[{idx}].regex exceeded safety timeout (ReDoS guard)"
                ) from exc


def normalize_custom_pattern_dicts(raw: Any) -> List[Dict[str, Any]]:
    """Validate and normalize custom pattern dicts for YAML persistence."""
    if not raw:
        return []
    if not isinstance(raw, list):
        raise PolicyValidationError("dlp.custom_patterns must be a list")
    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PolicyValidationError(f"dlp.custom_patterns[{idx}] must be an object")
        label_raw = entry.get("label")
        kind = str(entry.get("kind") or "dlp").strip().lower()
        default_severity = 0.95 if kind == "secret" else 0.5
        normalized.append(
            {
                "name": str(entry.get("name") or "").strip(),
                "regex": str(entry.get("regex") or "").strip(),
                "replacement": str(entry.get("replacement") or "[REDACTED]"),
                "label": str(label_raw).strip().upper() if label_raw else None,
                "severity": float(entry.get("severity", default_severity)),
                "enabled": bool(entry.get("enabled", True)),
                "kind": kind,
            }
        )
    load_custom_patterns(normalized)
    rows: List[Dict[str, Any]] = []
    for row in normalized:
        stored = {
            "name": row["name"],
            "regex": row["regex"],
            "replacement": row["replacement"],
            "severity": row["severity"],
            "enabled": row["enabled"],
            "kind": row["kind"],
        }
        if row.get("label"):
            stored["label"] = row["label"]
        rows.append(stored)
    return rows


def parse_dlp_pattern_pack(raw: Any) -> List[Dict[str, Any]]:
    """Parse a JSON pattern pack ({ patterns: [] } or bare array) into validated dicts."""
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict) and isinstance(raw.get("patterns"), list):
        rows = raw["patterns"]
    else:
        raise PolicyValidationError("Pattern pack must be { patterns: [] } or a bare array")
    return normalize_custom_pattern_dicts(rows)


def custom_patterns_as_dicts(patterns: List[CustomPattern]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for pattern in patterns:
        row: Dict[str, Any] = {
            "name": pattern.name,
            "regex": pattern.regex.pattern,
            "replacement": pattern.replacement,
            "severity": pattern.severity,
            "enabled": pattern.enabled,
            "kind": pattern.kind,
        }
        if pattern.label:
            row["label"] = pattern.label
        rows.append(row)
    return rows


def load_injection_categories(raw: Any) -> Dict[str, bool]:
    categories = default_injection_categories()
    if not raw:
        return categories
    if not isinstance(raw, dict):
        raise PolicyValidationError("input.injection_categories must be an object")
    for key, value in raw.items():
        category = str(key).strip()
        if category not in BUILTIN_INJECTION_CATEGORIES:
            raise PolicyValidationError(
                f"input.injection_categories contains unknown category: {category}"
            )
        categories[category] = bool(value)
    return categories


def normalize_injection_categories_dict(raw: Any) -> Dict[str, bool]:
    loaded = load_injection_categories(raw)
    return {category: loaded[category] for category in BUILTIN_INJECTION_CATEGORIES}


def load_custom_injection_patterns(raw: Any) -> List[InjectionPattern]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise PolicyValidationError("input.custom_injection_patterns must be a list")
    patterns: List[InjectionPattern] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PolicyValidationError(f"input.custom_injection_patterns[{idx}] must be an object")
        patterns.append(_compile_custom_injection_pattern(entry, idx))
    return patterns


def _compile_custom_injection_pattern(entry: Dict[str, Any], idx: int) -> InjectionPattern:
    name = str(entry.get("name") or "").strip()
    if not name:
        raise PolicyValidationError(f"input.custom_injection_patterns[{idx}].name is required")
    pattern = str(entry.get("regex") or "").strip()
    compiled = _compile_policy_regex(pattern, idx, "input.custom_injection_patterns")
    severity = float(entry.get("severity", 0.85))
    if not 0.0 <= severity <= 1.0:
        raise PolicyValidationError(
            f"input.custom_injection_patterns[{idx}].severity must be between 0 and 1"
        )
    detail = str(entry.get("detail") or "Policy-defined injection pattern.").strip()
    return InjectionPattern(
        name=name,
        regex=compiled,
        severity=severity,
        detail=detail or "Policy-defined injection pattern.",
        enabled=bool(entry.get("enabled", True)),
    )


def normalize_custom_injection_pattern_dicts(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise PolicyValidationError("input.custom_injection_patterns must be a list")
    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PolicyValidationError(f"input.custom_injection_patterns[{idx}] must be an object")
        normalized.append(
            {
                "name": str(entry.get("name") or "").strip(),
                "regex": str(entry.get("regex") or "").strip(),
                "severity": float(entry.get("severity", 0.85)),
                "detail": str(entry.get("detail") or "Policy-defined injection pattern.").strip(),
                "enabled": bool(entry.get("enabled", True)),
            }
        )
    load_custom_injection_patterns(normalized)
    return [
        {
            "name": row["name"],
            "regex": row["regex"],
            "severity": row["severity"],
            "detail": row["detail"] or "Policy-defined injection pattern.",
            "enabled": row["enabled"],
        }
        for row in normalized
    ]


def custom_injection_patterns_as_dicts(patterns: List[InjectionPattern]) -> List[Dict[str, Any]]:
    return [
        {
            "name": pattern.name,
            "regex": pattern.regex.pattern,
            "severity": pattern.severity,
            "detail": pattern.detail,
            "enabled": pattern.enabled,
        }
        for pattern in patterns
    ]

_POLICY_KNOB_MAP = {
    "input_challenge_threshold": ("input", "challenge_threshold"),
    "input_block_threshold": ("input", "block_threshold"),
    "input_challenge_mode": ("input", "challenge_mode"),
    "input_ml_injection_enabled": ("input", "ml_injection_enabled"),
    "input_ml_injection_threshold": ("input", "ml_injection_threshold"),
    "output_challenge_threshold": ("output", "challenge_threshold"),
    "output_block_threshold": ("output", "block_threshold"),
    "output_challenge_mode": ("output", "challenge_mode"),
    "output_min_citation_coverage": ("output", "min_citation_coverage"),
    "output_entailment_check": ("output", "entailment_check"),
    "output_entailment_threshold": ("output", "entailment_threshold"),
    "output_per_claim_citations": ("output", "per_claim_citations"),
    "output_hard_citation_gate": ("output", "hard_citation_gate"),
    "output_substantive_min_tokens": ("output", "substantive_min_tokens"),
    "dlp_enable_ner": ("dlp", "enable_ner"),
    "dlp_labels": ("dlp", "labels"),
    "dlp_custom_patterns": ("dlp", "custom_patterns"),
    "network_denied_domains": ("network", "denied_domains"),
    "network_allowed_domains": ("network", "allowed_domains"),
    "network_block_private_ranges": ("network", "block_private_ranges"),
    "llm_routing_enabled": ("llm_routing", "enabled"),
    "llm_routing_fail_closed": ("llm_routing", "fail_closed"),
    "input_injection_categories": ("input", "injection_categories"),
    "input_custom_injection_patterns": ("input", "custom_injection_patterns"),
    "extraction_enabled": ("extraction", "enabled"),
    "extraction_window_seconds": ("extraction", "window_seconds"),
    "extraction_min_window_queries": ("extraction", "min_window_queries"),
    "extraction_min_corpus_size": ("extraction", "min_corpus_size"),
    "extraction_elevated_coverage": ("extraction", "elevated_coverage"),
    "extraction_severe_coverage": ("extraction", "severe_coverage"),
    "extraction_breadth_ratio_threshold": ("extraction", "breadth_ratio_threshold"),
    "extraction_novelty_ratio_threshold": ("extraction", "novelty_ratio_threshold"),
    "extraction_action": ("extraction", "action"),
    "canary_enabled": ("canary", "enabled"),
    "canary_auditor_subjects": ("canary", "auditor_subjects"),
    "canary_auditor_groups": ("canary", "auditor_groups"),
    "canary_output_backstop": ("canary", "output_backstop"),
    "canary_default_sensitivity": ("canary", "default_sensitivity"),
    "retrieval_explainability_enabled": ("retrieval", "explainability_enabled"),
    "retrieval_max_trace_candidates": ("retrieval", "max_trace_candidates"),
    "audit_integrity_chain": ("audit", "integrity_chain"),
    # Nested connector knobs: (section, nested_block, field)
    "connectors_drift_enabled": ("connectors", "drift", "enabled"),
    "connectors_drift_critical_if_public": ("connectors", "drift", "critical_if_public"),
    "connectors_drift_critical_group_count": ("connectors", "drift", "critical_group_count"),
    "connectors_drift_auto_quarantine_on_critical": ("connectors", "drift", "auto_quarantine_on_critical"),
    "connectors_acl_sync_enabled": ("connectors", "acl_sync", "enabled"),
    "connectors_acl_sync_min_interval_minutes": ("connectors", "acl_sync", "min_interval_minutes"),
    "connectors_acl_sync_acl_only_when_unchanged": ("connectors", "acl_sync", "acl_only_when_unchanged"),
}


@dataclass
class PolicyKnobUpdateResult:
    policy: Policy
    backup_path: Optional[Path]
    updated_keys: List[str]


@dataclass
class PolicyRestoreResult:
    policy: Policy
    backup_path: Optional[Path]
    restored_from: Path


class PolicyWriteError(OSError):
    """Raised when policy.yaml cannot be written (e.g. read-only mount)."""


def policy_source_path() -> Path:
    return Path(os.getenv("RAG_POLICY_FILE", "./config/policy.yaml"))


def policy_writable_path() -> Path:
    override = os.getenv("RAG_POLICY_WRITABLE_FILE", "").strip()
    if override:
        return Path(override)
    source = policy_source_path()
    if _path_is_writable(source):
        return source
    return Path(os.getenv("RAG_DATA_DIR", "./data")) / "policy.yaml"


def _path_is_writable(path: Path) -> bool:
    target = path if path.exists() else path.parent
    if not target.exists():
        return False
    return os.access(target, os.W_OK)


def ensure_writable_policy_file() -> Path:
    """Return the policy file used for load/save; seed from source when needed."""
    source = policy_source_path()
    writable = policy_writable_path()
    writable.parent.mkdir(parents=True, exist_ok=True)
    if not writable.exists():
        if not source.exists():
            raise FileNotFoundError(f"Policy file not found: {source}")
        writable.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return writable


def active_policy_path() -> Path:
    return ensure_writable_policy_file()


def _policy_backup_dir(policy_path: Path) -> Path:
    override = os.getenv("RAG_POLICY_BACKUP_DIR", "").strip()
    if override:
        return Path(override)
    return policy_path.parent / "backups"


def _prune_policy_backups(backup_dir: Path, stem: str, suffix: str) -> None:
    keep = max(1, int(os.getenv("RAG_POLICY_BACKUP_KEEP", "20")))
    pattern = f"{stem}-*{suffix}" if suffix else f"{stem}-*"
    backups = sorted(backup_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)


def backup_policy_file(policy_path: Path) -> Path:
    """Copy the current policy file to a timestamped backup before edits."""
    backup_dir = _policy_backup_dir(policy_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    suffix = policy_path.suffix
    backup_path = backup_dir / f"{policy_path.stem}-{stamp}{suffix}"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"{policy_path.stem}-{stamp}-{counter}{suffix}"
        counter += 1
    backup_path.write_text(policy_path.read_text(encoding="utf-8"), encoding="utf-8")
    _prune_policy_backups(backup_dir, policy_path.stem, suffix)
    return backup_path


def update_policy_knobs(path: str, updates: Dict[str, Any]) -> PolicyKnobUpdateResult:
    """Back up policy YAML, persist editable knobs, and return the reloaded policy."""
    policy_path = Path(path)
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    backup_path = backup_policy_file(policy_path)
    raw: Dict[str, Any] = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    applied: List[str] = []
    for key, value in updates.items():
        if value is None:
            continue
        if key == "dlp_custom_patterns":
            raw.setdefault("dlp", {})
            if not isinstance(raw["dlp"], dict):
                raw["dlp"] = {}
            raw["dlp"]["custom_patterns"] = normalize_custom_pattern_dicts(value)
            applied.append(key)
            continue
        if key == "input_custom_injection_patterns":
            raw.setdefault("input", {})
            if not isinstance(raw["input"], dict):
                raw["input"] = {}
            raw["input"]["custom_injection_patterns"] = normalize_custom_injection_pattern_dicts(
                value
            )
            applied.append(key)
            continue
        if key == "input_injection_categories":
            raw.setdefault("input", {})
            if not isinstance(raw["input"], dict):
                raw["input"] = {}
            raw["input"]["injection_categories"] = normalize_injection_categories_dict(value)
            applied.append(key)
            continue
        mapping = _POLICY_KNOB_MAP.get(key)
        if mapping is None:
            continue
        if len(mapping) == 3:
            section, nested, field_name = mapping
            raw.setdefault(section, {})
            if not isinstance(raw[section], dict):
                raw[section] = {}
            raw[section].setdefault(nested, {})
            if not isinstance(raw[section][nested], dict):
                raw[section][nested] = {}
            raw[section][nested][field_name] = value
            applied.append(key)
            continue
        section, field_name = mapping
        raw.setdefault(section, {})
        if not isinstance(raw[section], dict):
            raw[section] = {}
        raw[section][field_name] = value
        applied.append(key)

    try:
        policy_path.write_text(
            yaml.safe_dump(raw, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise PolicyWriteError(
            f"Unable to write policy file {policy_path}: {exc.strerror or exc}"
        ) from exc
    try:
        reloaded = load_policy(str(policy_path))
    except PolicyValidationError:
        if backup_path.exists():
            policy_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
        raise
    return PolicyKnobUpdateResult(
        policy=reloaded,
        backup_path=backup_path,
        updated_keys=applied,
    )


def list_policy_backups(policy_path: str) -> List[Dict[str, Any]]:
    """Return timestamped policy backups newest-first."""
    path = Path(policy_path)
    backup_dir = _policy_backup_dir(path)
    if not backup_dir.exists():
        return []
    suffix = path.suffix
    pattern = f"{path.stem}-*{suffix}" if suffix else f"{path.stem}-*"
    backups = sorted(backup_dir.glob(pattern), key=lambda entry: entry.stat().st_mtime, reverse=True)
    return [
        {
            "filename": entry.name,
            "path": str(entry),
            "modified_at": entry.stat().st_mtime,
            "size_bytes": entry.stat().st_size,
        }
        for entry in backups
    ]


def restore_policy_from_backup(policy_path: str, backup_filename: str) -> PolicyRestoreResult:
    """Replace active policy YAML with a prior backup (current file backed up first)."""
    path = Path(policy_path)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    backup_dir = _policy_backup_dir(path)
    safe_name = Path(backup_filename).name
    if not safe_name or safe_name != backup_filename.strip():
        raise PolicyValidationError("backup must be a filename without path separators")
    source = backup_dir / safe_name
    if not source.exists():
        raise FileNotFoundError(f"Backup not found: {safe_name}")
    if source.resolve().parent != backup_dir.resolve():
        raise PolicyValidationError("backup must reside in the policy backup directory")

    current_backup = backup_policy_file(path)
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        reloaded = load_policy(str(path))
    except PolicyValidationError:
        if current_backup.exists():
            path.write_text(current_backup.read_text(encoding="utf-8"), encoding="utf-8")
        raise
    return PolicyRestoreResult(
        policy=reloaded,
        backup_path=current_backup,
        restored_from=source,
    )
