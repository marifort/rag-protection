"""Tool registry with description injection scanning at load time."""

from __future__ import annotations

from typing import Dict, List, Optional

from rag_protection_proxy.config import Policy
from rag_protection_proxy.models import Finding
from rag_protection_proxy.scanners.prompt_injection import PromptInjectionScanner
from rag_protection_proxy.tools_gateway.policy import ToolGatewayPolicy, ToolPolicyEntry


def build_registry(
    tool_policy: ToolGatewayPolicy,
    rag_policy: Optional[Policy] = None,
) -> Dict[str, ToolPolicyEntry]:
    """Return tool entries with description injection flags applied."""
    scanner = _description_scanner(rag_policy)
    registry: Dict[str, ToolPolicyEntry] = {}
    for name, entry in tool_policy.tools.items():
        findings = _scan_description(scanner, entry.description)
        registry[name] = ToolPolicyEntry(
            name=entry.name,
            description=entry.description,
            backend=entry.backend,
            allowed_groups=list(entry.allowed_groups),
            max_args_bytes=entry.max_args_bytes,
            blocked_patterns=list(entry.blocked_patterns),
            blocked_domains=list(entry.blocked_domains),
            scan_arguments=list(entry.scan_arguments),
            mcp_tool=entry.mcp_tool,
            description_blocked=bool(findings),
            description_findings_count=len(findings),
        )
    return registry


def _description_scanner(rag_policy: Optional[Policy]) -> PromptInjectionScanner:
    if rag_policy is None:
        return PromptInjectionScanner()
    return PromptInjectionScanner(
        strip_hidden_chars=rag_policy.input.strip_hidden_chars,
        strip_html_comments=rag_policy.input.strip_html_comments,
        enabled_categories=rag_policy.input.injection_categories,
        extra_patterns=rag_policy.input.custom_injection_patterns,
    )


def _scan_description(scanner: PromptInjectionScanner, description: str) -> List[Finding]:
    result = scanner.scan(description)
    return list(result.findings)


def get_tool(registry: Dict[str, ToolPolicyEntry], name: str) -> Optional[ToolPolicyEntry]:
    return registry.get(name)
