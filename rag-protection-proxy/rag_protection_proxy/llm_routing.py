"""LLM egress routing by document classification (T0.6 / #18 / D6).

Selects an LLM endpoint from a policy table using the highest-sensitivity
classification among retrieved chunks. Orthogonal to A8 URL/SSRF packs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from rag_protection_proxy.audit import record
from rag_protection_proxy.config import LLMPolicy, LLMRoutingPolicy, Policy
from rag_protection_proxy.models import AuditEvent, Decision


@dataclass(frozen=True)
class LLMRouteDecision:
    """Resolved LLM profile for one query."""

    endpoint_id: str
    llm: LLMPolicy
    classification: str
    matched_route: str
    reason: str
    blocked: bool = False
    block_reason: Optional[str] = None

    def audit_detail(self) -> Dict[str, Any]:
        host = ""
        try:
            host = urlparse(self.llm.base_url).netloc or self.llm.base_url
        except Exception:
            host = self.llm.base_url
        return {
            "endpoint_id": self.endpoint_id,
            "model": self.llm.model,
            "base_url_host": host,
            "classification": self.classification,
            "matched_route": self.matched_route,
            "reason": self.reason,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


def _norm(value: str) -> str:
    return str(value or "").strip().lower()


def _label_matches(needle: str, haystack: str) -> bool:
    """Exact or hyphen/underscore-prefix match (confidential → confidential-hr)."""
    n, h = _norm(needle), _norm(haystack)
    if not n or not h:
        return False
    if h == n:
        return True
    return h.startswith(n + "-") or h.startswith(n + "_")


def classification_rank_index(classification: str, rank_list: Sequence[str]) -> int:
    """Lower index = higher sensitivity. Unranked → len(rank_list)."""
    if not classification:
        return len(rank_list) + 1
    for idx, label in enumerate(rank_list):
        if _label_matches(label, classification):
            return idx
    return len(rank_list)


def highest_classification(
    classifications: Sequence[str],
    rank_list: Sequence[str],
) -> str:
    """Pick the highest-sensitivity label; ties keep first-seen order."""
    cleaned = [str(c).strip() for c in classifications if str(c or "").strip()]
    if not cleaned:
        return ""
    best = cleaned[0]
    best_rank = classification_rank_index(best, rank_list)
    for label in cleaned[1:]:
        rank = classification_rank_index(label, rank_list)
        if rank < best_rank:
            best = label
            best_rank = rank
    return best


def collect_classifications(metadata_list: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for meta in metadata_list:
        if not isinstance(meta, dict):
            continue
        raw = meta.get("classification")
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            out.append(text)
    return out


def _merge_endpoint(
    base: LLMPolicy,
    endpoint_id: str,
    routing: LLMRoutingPolicy,
) -> LLMPolicy:
    profile = routing.endpoints.get(endpoint_id)
    if profile is None:
        return LLMPolicy(
            base_url=base.base_url,
            model=base.model,
            api_key=base.api_key,
            timeout_seconds=base.timeout_seconds,
            max_tokens=base.max_tokens,
            temperature=base.temperature,
        )
    return LLMPolicy(
        base_url=profile.base_url if profile.base_url is not None else base.base_url,
        model=profile.model if profile.model is not None else base.model,
        api_key=profile.api_key if profile.api_key is not None else base.api_key,
        timeout_seconds=(
            profile.timeout_seconds
            if profile.timeout_seconds is not None
            else base.timeout_seconds
        ),
        max_tokens=profile.max_tokens if profile.max_tokens is not None else base.max_tokens,
        temperature=(
            profile.temperature if profile.temperature is not None else base.temperature
        ),
    )


def resolve_llm_route(
    policy: Policy,
    metadata_list: Sequence[Dict[str, Any]],
) -> LLMRouteDecision:
    """Resolve which LLM endpoint should process this query."""
    routing = policy.llm_routing
    default_llm = policy.llm

    if not routing.enabled:
        return LLMRouteDecision(
            endpoint_id="default",
            llm=default_llm,
            classification="",
            matched_route="",
            reason="llm_routing_disabled",
        )

    classifications = collect_classifications(metadata_list)
    winning = highest_classification(classifications, routing.classification_rank)

    matched_route = ""
    endpoint_id = routing.default_endpoint_id or "default"
    reason = "default_endpoint"

    if winning:
        for rule in routing.routes:
            if _label_matches(rule.match, winning):
                matched_route = rule.match
                endpoint_id = rule.endpoint_id
                reason = "classification_route"
                break
        else:
            if routing.fail_closed:
                return LLMRouteDecision(
                    endpoint_id=endpoint_id,
                    llm=default_llm,
                    classification=winning,
                    matched_route="",
                    reason="unmapped_classification",
                    blocked=True,
                    block_reason="llm_routing_unmapped_classification",
                )
            reason = "unmapped_fallback_default"

    if endpoint_id not in routing.endpoints and endpoint_id not in ("default", ""):
        if routing.fail_closed:
            return LLMRouteDecision(
                endpoint_id=endpoint_id,
                llm=default_llm,
                classification=winning,
                matched_route=matched_route,
                reason="unknown_endpoint",
                blocked=True,
                block_reason="llm_routing_unknown_endpoint",
            )
        endpoint_id = routing.default_endpoint_id or "default"
        reason = "unknown_endpoint_fallback_default"

    # "default" without an explicit profile uses policy.llm
    if endpoint_id == "default" and "default" not in routing.endpoints:
        llm = default_llm
    else:
        if endpoint_id not in routing.endpoints and routing.fail_closed:
            return LLMRouteDecision(
                endpoint_id=endpoint_id,
                llm=default_llm,
                classification=winning,
                matched_route=matched_route,
                reason="unknown_endpoint",
                blocked=True,
                block_reason="llm_routing_unknown_endpoint",
            )
        llm = _merge_endpoint(default_llm, endpoint_id, routing)

    return LLMRouteDecision(
        endpoint_id=endpoint_id,
        llm=llm,
        classification=winning,
        matched_route=matched_route,
        reason=reason,
    )


def record_llm_routed(
    *,
    decision: LLMRouteDecision,
    subject: str,
    tenant_id: str,
) -> None:
    """Emit filterable audit event with endpoint id + classification."""
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="llm_routed",
            decision=Decision.BLOCK if decision.blocked else Decision.ALLOW,
            risk_score=0.9 if decision.blocked else 0.0,
            subject=subject,
            tenant_id=tenant_id,
            source="rag:llm_routing",
            detail=json.dumps(decision.audit_detail(), sort_keys=True),
        )
    )
