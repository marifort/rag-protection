"""Human-readable text reporter."""

from __future__ import annotations

from ..models import ScanReport, Severity

_ICON = {
    Severity.CRITICAL: "[CRIT]",
    Severity.WARNING: "[WARN]",
    Severity.INFO: "[INFO]",
}


def render(report: ScanReport) -> str:
    if report.load_error:
        return f"[ERROR] configuration could not be loaded: {report.load_error}"

    lines: list[str] = []
    ordered = sorted(report.findings, key=lambda f: (-f.severity.rank, f.rule_id))
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
        f"rag-scan: {counts['critical']} critical, "
        f"{counts['warning']} warning, {counts['info']} info"
    )
    if report.suppressed:
        summary += f" ({report.suppressed} suppressed by baseline)"
    if not report.findings:
        lines.append("rag-scan: no issues found.")
    lines.append(summary)
    return "\n".join(lines)
