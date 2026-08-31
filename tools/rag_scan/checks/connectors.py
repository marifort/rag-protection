"""Connector configuration checks (CON001, DRIFT001)."""

from __future__ import annotations

from typing import List

from ..context import ScanContext
from ..models import Finding, Severity


def check_drift_monitor_disabled(ctx: ScanContext) -> List[Finding]:
    """DRIFT001 — connectors enabled in prod without permission drift monitor."""
    if ctx.policy is None:
        return []
    connectors = ctx.policy.connectors
    if not connectors.enabled:
        return []
    if connectors.drift.enabled:
        return []
    return [
        Finding(
            rule_id="DRIFT001",
            severity=Severity.WARNING,
            title="Permission drift monitor disabled",
            message=(
                "connectors.enabled is true but connectors.drift.enabled is false. "
                "Source ACL changes after ingest will not emit permission_drift alerts."
            ),
            location=str(ctx.policy_path or "policy.yaml"),
            remediation="Set connectors.drift.enabled: true (or RAG_DRIFT_ENABLED=1).",
        )
    ]


def check_missing_acl_mapping(ctx: ScanContext) -> List[Finding]:
    """CON001 — a connector sync job has no group mapping (ACL mapping)."""
    if ctx.policy is None:
        return []
    connectors = ctx.policy.connectors
    if not connectors.enabled or not connectors.jobs:
        return []
    findings: List[Finding] = []
    for job in connectors.jobs:
        if job.group_map:
            continue
        findings.append(
            Finding(
                rule_id="CON001",
                severity=Severity.WARNING,
                title="Connector job missing ACL mapping",
                message=(
                    f"Connector job {job.connector!r} (source {job.source_id!r}) has no "
                    "`group_map`; source permissions cannot be translated to allowed_groups."
                ),
                location=str(ctx.policy_path or "policy.yaml"),
                remediation="Add a `group_map` to the connector job, or set unmapped_permissions: deny.",
            )
        )
    return findings
