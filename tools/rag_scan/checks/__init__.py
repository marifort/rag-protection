"""Rule registry. Each check is a callable: ScanContext -> List[Finding]."""

from __future__ import annotations

from typing import Callable, List

from ..context import ScanContext
from ..models import Finding
from . import acl, connectors, policy, secrets, vector

Check = Callable[[ScanContext], List[Finding]]

# Order is cosmetic; reporters sort by severity.
ALL_CHECKS: List[Check] = [
    acl.check_demo_tokens_in_prod,      # ACL001
    acl.check_confidential_world_readable,  # ACL002
    acl.check_overbroad_default_groups,     # ACL003
    policy.check_block_threshold_floor,     # POL001
    policy.check_connector_fail_open,       # POL002
    policy.check_disabled_injection_categories,  # POL003
    connectors.check_drift_monitor_disabled,  # DRIFT001
    connectors.check_missing_acl_mapping,   # CON001
    secrets.check_default_admin_key,        # SEC001
    secrets.check_no_auth_configured,       # SEC002
    vector.check_vector_payload_acl,        # VEC001
]


def run_all(ctx: ScanContext) -> List[Finding]:
    findings: List[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(ctx))
    return findings
