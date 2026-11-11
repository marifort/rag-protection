"""Identity-bound tool invoke lab.

The tool gateway allowlists which groups may call a tool. This package adds the
next check: the downstream API must see the user, not a bot service account.

How to run: docs/ce/labs/obo-identity.md
"""

from rag_protection_proxy.tools_gateway.obo.exchange import (
    AppOnlyDenied,
    DownscopeEmpty,
    OboDenied,
    exchange_on_behalf_of,
)
from rag_protection_proxy.tools_gateway.obo.matrix import AccessFinding, scan_access_matrix
from rag_protection_proxy.tools_gateway.obo.pipeline import IdentityBoundResult, invoke_identity_bound
from rag_protection_proxy.tools_gateway.obo.tokens import LabClaims, decode_lab_token, mint_lab_token

__all__ = [
    "AccessFinding",
    "AppOnlyDenied",
    "DownscopeEmpty",
    "IdentityBoundResult",
    "LabClaims",
    "OboDenied",
    "decode_lab_token",
    "exchange_on_behalf_of",
    "invoke_identity_bound",
    "mint_lab_token",
    "scan_access_matrix",
]
