"""MCP manifest lint rules (MCP001–MCP005)."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set

from rag_protection_proxy.config import BUILTIN_INJECTION_CATEGORY_META
from rag_protection_proxy.scanners.prompt_injection import PromptInjectionScanner

from .models import Finding, LintReport, McpTool, Severity

# Categories routed to MCP005 (structural hiding) vs MCP001 (injection).
_MCP005_CATEGORIES = frozenset({"hidden_chars", "html_comment_injection"})

_DESTRUCTIVE_KEYWORDS = re.compile(
    r"\b(delete|drop|truncate|wipe|destroy|exec(?:ute)?|shell|run_sql|rm\s+-rf)\b",
    re.I,
)
_WRITE_KEYWORDS = re.compile(r"\b(write|overwrite|modify|update|put|patch)\b", re.I)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def lint_tools(tools: Iterable[McpTool]) -> LintReport:
    """Run all MCP lint rules against normalized tool entries."""
    report = LintReport()
    tool_list = list(tools)
    report.tools_scanned = len(tool_list)

    scanner = PromptInjectionScanner()
    for tool in tool_list:
        location = f"tool:{tool.name}"
        mcp001_categories: Set[str] = set()
        mcp005_categories: Set[str] = set()

        for finding in scanner.scan(tool.description).findings:
            category = finding.category
            label = BUILTIN_INJECTION_CATEGORY_META.get(category, {}).get("label", category)
            detail = finding.detail or BUILTIN_INJECTION_CATEGORY_META.get(category, {}).get(
                "detail", "Suspicious content in tool description."
            )
            snippet = f" ({finding.snippet})" if finding.snippet else ""
            message = f"{detail}{snippet}"

            if category in _MCP005_CATEGORIES:
                mcp005_categories.add(category)
                report.add(
                    Finding(
                        rule_id="MCP005",
                        severity=Severity.WARNING,
                        title="Hidden or HTML-comment content in description",
                        message=message,
                        location=location,
                        remediation=(
                            "Remove zero-width characters and HTML comments from tool descriptions; "
                            "they can hide instructions from human reviewers."
                        ),
                    )
                )
            else:
                mcp001_categories.add(category)
                report.add(
                    Finding(
                        rule_id="MCP001",
                        severity=Severity.CRITICAL,
                        title=f"Tool-description injection ({label})",
                        message=message,
                        location=location,
                        remediation=(
                            "Rewrite the tool description to describe capability only — no "
                            "instructions to the model. Enforce at runtime with the Lab 1 tool gateway."
                        ),
                    )
                )

        _check_external_destinations(tool, location, report, skip_if_mcp001=bool(mcp001_categories))
        _check_destructive_scope(tool, location, report)
        _check_input_schema(tool, location, report)

    return report


def _check_external_destinations(
    tool: McpTool,
    location: str,
    report: LintReport,
    *,
    skip_if_mcp001: bool,
) -> None:
    if skip_if_mcp001:
        return

    text = tool.description
    emails = _EMAIL_RE.findall(text)
    urls = _URL_RE.findall(text)
    if not emails and not urls:
        return

    parts: List[str] = []
    if emails:
        parts.append(f"email(s): {', '.join(emails[:3])}")
    if urls:
        parts.append(f"URL(s): {', '.join(urls[:3])}")
    report.add(
        Finding(
            rule_id="MCP002",
            severity=Severity.WARNING,
            title="External destination in description",
            message=f"Description references {'; '.join(parts)}.",
            location=location,
            remediation=(
                "Avoid embedding URLs or email addresses in tool descriptions; "
                "they can steer agents to exfiltration sinks."
            ),
        )
    )


def _check_destructive_scope(tool: McpTool, location: str, report: LintReport) -> None:
    haystacks = _scope_haystacks(tool)
    if not _looks_destructive(haystacks):
        return
    if _schema_has_constraints(tool.input_schema):
        return

    report.add(
        Finding(
            rule_id="MCP003",
            severity=Severity.WARNING,
            title="Destructive scope without constraints",
            message=(
                f"Tool {tool.name!r} name or schema implies destructive/write capability "
                "but the input schema lacks required fields, enums, or patterns."
            ),
            location=location,
            remediation=(
                "Narrow the tool name/description, add required arguments with enums or "
                "patterns, and enforce allowed paths or operations in the MCP server."
            ),
        )
    )


def _check_input_schema(tool: McpTool, location: str, report: LintReport) -> None:
    schema = tool.input_schema
    if schema is None:
        report.add(
            Finding(
                rule_id="MCP004",
                severity=Severity.INFO,
                title="Missing input schema",
                message=f"Tool {tool.name!r} has no inputSchema — arguments are unconstrained at declaration time.",
                location=location,
                remediation="Declare an inputSchema with typed, required properties.",
            )
        )
        return

    if schema.get("type") != "object":
        return

    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        report.add(
            Finding(
                rule_id="MCP004",
                severity=Severity.INFO,
                title="Unconstrained input schema",
                message=f"Tool {tool.name!r} inputSchema has no properties defined.",
                location=location,
                remediation="Define typed properties and mark sensitive fields as required.",
            )
        )
        return

    if schema.get("additionalProperties") is True and not schema.get("required"):
        report.add(
            Finding(
                rule_id="MCP004",
                severity=Severity.INFO,
                title="Permissive input schema",
                message=(
                    f"Tool {tool.name!r} allows additionalProperties without required fields — "
                    "callers can pass arbitrary arguments."
                ),
                location=location,
                remediation="Set additionalProperties: false or require the critical arguments.",
            )
        )


def _scope_haystacks(tool: McpTool) -> List[str]:
    parts = [tool.name, tool.description]
    schema = tool.input_schema
    if isinstance(schema, dict):
        parts.append(str(schema.get("description", "")))
        props = schema.get("properties")
        if isinstance(props, dict):
            for key, spec in props.items():
                parts.append(str(key))
                if isinstance(spec, dict):
                    parts.append(str(spec.get("description", "")))
    return parts


def _looks_destructive(haystacks: Iterable[str]) -> bool:
    for text in haystacks:
        if not text:
            continue
        if _DESTRUCTIVE_KEYWORDS.search(text):
            return True
        if _WRITE_KEYWORDS.search(text) and re.search(r"\b(file|path|database|table|disk)\b", text, re.I):
            return True
    return False


def _schema_has_constraints(schema: dict | None) -> bool:
    if not isinstance(schema, dict):
        return False
    if schema.get("required"):
        return True

    props = schema.get("properties")
    if not isinstance(props, dict):
        return False

    for spec in props.values():
        if not isinstance(spec, dict):
            continue
        if spec.get("enum") or spec.get("pattern") or spec.get("const"):
            return True
        if spec.get("type") in {"integer", "number", "boolean"}:
            return True
        if spec.get("minimum") is not None or spec.get("maximum") is not None:
            return True
    return False
