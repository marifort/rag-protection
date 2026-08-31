"""Guardrail policy checks (POL001–POL003)."""

from __future__ import annotations

from typing import List

from ..context import ScanContext
from ..models import Finding, Severity

# Below this input block threshold the gateway blocks almost everything, which in
# practice gets disabled in a hurry — a smell that guardrails are mis-tuned.
BLOCK_THRESHOLD_FLOOR = 0.5


def check_block_threshold_floor(ctx: ScanContext) -> List[Finding]:
    """POL001 — input.block_threshold below a sane floor."""
    if ctx.policy is None:
        return []
    value = ctx.policy.input.block_threshold
    if value >= BLOCK_THRESHOLD_FLOOR:
        return []
    return [
        Finding(
            rule_id="POL001",
            severity=Severity.WARNING,
            title="Input block threshold below floor",
            message=(
                f"input.block_threshold={value} is below {BLOCK_THRESHOLD_FLOOR}; "
                "expect excessive false-positive blocks (and pressure to disable guardrails)."
            ),
            location=str(ctx.policy_path or "policy.yaml"),
            remediation=f"Set input.block_threshold >= {BLOCK_THRESHOLD_FLOOR} and tune challenge_threshold.",
        )
    ]


def check_connector_fail_open(ctx: ScanContext) -> List[Finding]:
    """POL002 — connectors enabled while unmapped permissions fail open."""
    if ctx.policy is None:
        return []
    connectors = ctx.policy.connectors
    if not connectors.enabled:
        return []
    if connectors.unmapped_permissions == "deny":
        return []
    return [
        Finding(
            rule_id="POL002",
            severity=Severity.CRITICAL,
            title="Connectors fail open on unmapped permissions",
            message=(
                "connectors.enabled is true but unmapped_permissions="
                f"{connectors.unmapped_permissions!r} (fail-open). Synced documents whose "
                "source ACL cannot be mapped become broadly readable."
            ),
            location=str(ctx.policy_path or "policy.yaml"),
            remediation="Set connectors.unmapped_permissions: deny (fail-closed).",
        )
    ]


def check_disabled_injection_categories(ctx: ScanContext) -> List[Finding]:
    """POL003 — input injection detection coverage has been weakened.

    The runtime input pipeline runs a set of built-in injection-category
    detectors (``input.injection_categories``) plus an optional ML classifier
    (``input.ml_injection_enabled``). Toggling any of these off silently lets the
    matching prompt-injection class through with no audit trail — a posture
    regression that is invisible at runtime but plain in config.
    """
    if ctx.policy is None:
        return []
    inp = ctx.policy.input
    disabled = sorted(name for name, enabled in inp.injection_categories.items() if not enabled)
    ml_off = not inp.ml_injection_enabled
    if not disabled and not ml_off:
        return []

    parts: List[str] = []
    if ml_off:
        parts.append("ml_injection_enabled is false (ML injection classifier off)")
    if disabled:
        noun = "category" if len(disabled) == 1 else "categories"
        parts.append(f"{len(disabled)} built-in injection {noun} disabled: {disabled}")
    return [
        Finding(
            rule_id="POL003",
            severity=Severity.WARNING,
            title="Injection detection coverage reduced",
            message=(
                "Input guardrail weakened — "
                + "; ".join(parts)
                + ". Disabled detectors let matching prompt-injection payloads through "
                "with no block and no audit event."
            ),
            location=str(ctx.policy_path or "policy.yaml"),
            remediation=(
                "Re-enable the disabled injection_categories (and ml_injection_enabled) "
                "unless a documented compensating control covers that class."
            ),
        )
    ]
