"""Human-readable text reporter."""

from __future__ import annotations

from ..models import LintReport, Severity

_ICON = {
    Severity.CRITICAL: "[CRIT]",
    Severity.WARNING: "[WARN]",
    Severity.INFO: "[INFO]",
}


def render(report: LintReport) -> str:
    if report.load_error:
        return f"[ERROR] {report.load_error}"

    lines: list[str] = []
    ordered = sorted(report.findings, key=lambda f: (-f.severity.rank, f.rule_id, f.location))
    for f in ordered:
        lines.append(f"{_ICON[f.severity]} {f.rule_id}  {f.title}")
        lines.append(f"        {f.message}")
        if f.location:
            lines.append(f"        location: {f.location}")
        if f.remediation:
            lines.append(f"        fix: {f.remediation}")
        lines.append("")

    counts = report.counts()
    summary = (
        f"mcp-lint: {report.tools_scanned} tool(s); "
        f"{counts['critical']} critical, {counts['warning']} warning, {counts['info']} info"
    )
    if not report.findings:
        lines.append("mcp-lint: no issues found.")
    lines.append(summary)
    return "\n".join(lines)
