"""Render executive summary from scenario results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .models import ScenarioResult


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "report_template.md"


def render_report(
    results: List[ScenarioResult],
    *,
    engagement: str = "engagement",
    base_url: str = "",
) -> str:
    template = _template_path().read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    rows = []
    ranked = sorted(results, key=lambda r: r.risk_score, reverse=True)
    for result in ranked:
        status = "PASS" if result.passed else "FAIL"
        detail = "; ".join(result.messages) if result.messages else "—"
        rows.append(
            f"| {result.scenario_id} | {result.title} | {status} | {result.risk_score:.2f} | {detail} |"
        )
    scorecard = "\n".join(rows) if rows else "_No scenarios run._"
    findings = []
    for result in ranked:
        if result.passed:
            continue
        findings.append(
            f"- **{result.title}** (`{result.scenario_id}`) — risk {result.risk_score:.2f}: "
            + "; ".join(result.messages)
        )
    findings_block = "\n".join(findings) if findings else "_All scenarios passed — controls held._"
    report = template
    report = report.replace("{{ENGAGEMENT}}", engagement)
    report = report.replace("{{GENERATED_AT}}", now)
    report = report.replace("{{BASE_URL}}", base_url or "(not recorded)")
    report = report.replace("{{PASSED}}", str(passed))
    report = report.replace("{{FAILED}}", str(failed))
    report = report.replace("{{TOTAL}}", str(len(results)))
    report = report.replace("{{SCORECARD}}", scorecard)
    report = report.replace("{{FINDINGS}}", findings_block)
    return report


def write_report(out_dir: Path, markdown: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.md"
    path.write_text(markdown, encoding="utf-8")
    return path
