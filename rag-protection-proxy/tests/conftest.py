"""Shared pytest markers for CE/EE boundary tests.

See ``docs/qa/test-plans/CE_EE_SEAM_TEST_PLAN.md`` (TC-CEEE-000–008).
"""

from __future__ import annotations

import pytest

from rag_protection_proxy.app import app

_ENTERPRISE_INSTALLED = getattr(app.state, "enterprise_registered", False)

ee_required = pytest.mark.skipif(
    not _ENTERPRISE_INSTALLED,
    reason="requires rag-protection-enterprise (Tier 2 routes)",
)


def assert_tier2_unauthenticated(resp) -> None:
    """Tier 2 routes return 404 without EE; 401 without bearer when EE is installed."""
    if _ENTERPRISE_INSTALLED:
        assert resp.status_code == 401
    else:
        assert resp.status_code == 404
