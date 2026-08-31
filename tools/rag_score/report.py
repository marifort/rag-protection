"""Render a :class:`~rag_score.posture.Posture` as a branded, shareable report.

Three formats:
  * ``markdown`` — the default ``POSTURE.md`` artifact (gist/README friendly).
  * ``html``     — a self-contained ``posture.html`` card (inline CSS, no assets).
  * ``json``     — machine-readable, for badges / automation.

All formats are produced locally; no configuration leaves the machine.
"""

from __future__ import annotations

import html
import json

from .posture import Posture

PRODUCT_NAME = "Marifort Gate"
ASSESSMENT_URL = (
    "https://github.com/marifort/rag-protection/blob/main/docs/commercial/"
    "SOLOPRENEUR_PRODUCT_OPPORTUNITIES.md#1-genai--rag-security-assessment"
)
DISCLAIMER = (
    "Indicative posture grade, not a certification. Scores the *declared* "
    "configuration only and runs entirely locally — no configuration is uploaded."
)

# Grade -> accent colour for the HTML badge.
_GRADE_COLOR = {
    "A": "#1a7f37",
    "B": "#3fb950",
    "C": "#d4a72c",
    "D": "#e3742f",
    "F": "#cf222e",
}

# Coverage status -> emoji-free marker reused across formats.
_STATUS_MARK = {
    "critical": "CRITICAL",
    "warning": "WARN",
    "info": "INFO",
    "clean": "OK",
    "not-assessed": "n/a",
}


def render(posture: Posture, fmt: str) -> str:
    formatters = {"markdown": render_markdown, "html": render_html, "json": render_json}
    try:
        return formatters[fmt](posture)
    except KeyError as exc:
        raise ValueError(f"unknown report format: {fmt}") from exc


def render_markdown(p: Posture) -> str:
    lines: list[str] = []
    lines.append(f"# {PRODUCT_NAME} — RAG security posture scorecard")
    lines.append("")
    lines.append(f"## Grade: {p.grade}  ({p.score}/100)")
    lines.append("")
    lines.append(f"_{p.blurb}_")
    lines.append("")
    lines.append(
        f"Scanned at `--env {p.env}` · "
        f"{p.counts['critical']} critical · "
        f"{p.counts['warning']} warning · "
        f"{p.counts['info']} info"
    )
    lines.append("")

    lines.append("## OWASP LLM Top 10 coverage")
    lines.append("")
    lines.append("| Risk | Area | Status | Rules |")
    lines.append("|------|------|--------|-------|")
    for row in p.coverage:
        rules = ", ".join(row.rule_ids) if row.rule_ids else "—"
        status = f"{_STATUS_MARK[row.status]} · {row.status_label}"
        lines.append(f"| {row.risk_id} | {row.name} | {status} | {rules} |")
    lines.append("")
    for row in p.coverage:
        if row.note:
            lines.append(f"> {row.risk_id}: {row.note}")
    lines.append("")

    lines.append("## Top fixes")
    lines.append("")
    if not p.top_fixes:
        lines.append("No issues found — nothing to fix in the declared config.")
    else:
        for i, f in enumerate(p.top_fixes, start=1):
            lines.append(f"{i}. **[{f.rule_id}] {f.title}** ({f.severity.value})")
            lines.append(f"   - {f.message}")
            if f.remediation:
                lines.append(f"   - Fix: {f.remediation}")
            if f.location:
                lines.append(f"   - Location: `{f.location}`")
    lines.append("")

    lines.append("## Next step")
    lines.append("")
    lines.append(
        f"This is a free self-serve grade. For a hands-on review of your RAG "
        f"deployment, book the [GenAI/RAG security assessment]({ASSESSMENT_URL})."
    )
    lines.append("")
    lines.append(f"---")
    lines.append(f"_{DISCLAIMER}_")
    return "\n".join(lines)


def render_json(p: Posture) -> str:
    payload = {
        "product": PRODUCT_NAME,
        "env": p.env,
        "grade": p.grade,
        "score": p.score,
        "blurb": p.blurb,
        "counts": p.counts,
        "owasp_coverage": [
            {
                "risk_id": row.risk_id,
                "name": row.name,
                "status": row.status,
                "status_label": row.status_label,
                "rule_ids": row.rule_ids,
                "note": row.note,
            }
            for row in p.coverage
        ],
        "top_fixes": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "title": f.title,
                "message": f.message,
                "remediation": f.remediation,
                "location": f.location,
            }
            for f in p.top_fixes
        ],
        "disclaimer": DISCLAIMER,
    }
    return json.dumps(payload, indent=2)


def render_html(p: Posture) -> str:
    color = _GRADE_COLOR.get(p.grade, "#57606a")

    coverage_rows = "\n".join(
        f"      <tr><td class='risk'>{html.escape(row.risk_id)}</td>"
        f"<td>{html.escape(row.name)}</td>"
        f"<td class='st st-{row.status}'>{html.escape(row.status_label)}</td>"
        f"<td class='rules'>{html.escape(', '.join(row.rule_ids) or '—')}</td></tr>"
        for row in p.coverage
    )

    notes = "".join(
        f"      <p class='note'><b>{html.escape(row.risk_id)}:</b> "
        f"{html.escape(row.note)}</p>\n"
        for row in p.coverage
        if row.note
    )

    if p.top_fixes:
        fixes_items = "\n".join(
            "      <li>"
            f"<span class='fix-rule'>[{html.escape(f.rule_id)}] "
            f"{html.escape(f.title)}</span> "
            f"<span class='sev sev-{f.severity.value}'>{html.escape(f.severity.value)}</span>"
            f"<div class='fix-msg'>{html.escape(f.message)}</div>"
            + (
                f"<div class='fix-do'>Fix: {html.escape(f.remediation)}</div>"
                if f.remediation
                else ""
            )
            + "</li>"
            for f in p.top_fixes
        )
        fixes_html = f"    <ol class='fixes'>\n{fixes_items}\n    </ol>"
    else:
        fixes_html = (
            "    <p class='clean'>No issues found — nothing to fix in the "
            "declared config.</p>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(PRODUCT_NAME)} — RAG posture scorecard</title>
<style>
  :root {{ --accent: {color}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         margin: 0; background: #f6f8fa; color: #1f2328; line-height: 1.5; }}
  .wrap {{ max-width: 820px; margin: 0 auto; padding: 32px 20px 64px; }}
  .card {{ background: #fff; border: 1px solid #d0d7de; border-radius: 12px;
          padding: 28px 32px; box-shadow: 0 1px 3px rgba(31,35,40,.08); }}
  h1 {{ font-size: 18px; color: #57606a; font-weight: 600; margin: 0 0 20px; }}
  .grade {{ display: flex; align-items: center; gap: 20px; margin-bottom: 8px; }}
  .badge {{ width: 96px; height: 96px; border-radius: 16px; background: var(--accent);
           color: #fff; font-size: 56px; font-weight: 800; display: flex;
           align-items: center; justify-content: center; flex: none; }}
  .score {{ font-size: 28px; font-weight: 700; }}
  .score small {{ color: #57606a; font-weight: 400; font-size: 16px; }}
  .blurb {{ color: #57606a; margin: 2px 0 0; }}
  .meta {{ margin: 16px 0 28px; font-size: 14px; color: #57606a; }}
  .meta code {{ background: #eff2f5; padding: 1px 6px; border-radius: 6px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .04em;
       color: #57606a; border-bottom: 1px solid #d0d7de; padding-bottom: 6px;
       margin: 28px 0 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eaecef; }}
  th {{ color: #57606a; font-weight: 600; }}
  td.risk {{ font-weight: 700; }}
  td.rules {{ color: #57606a; font-variant-numeric: tabular-nums; }}
  .st {{ font-weight: 600; }}
  .st-critical {{ color: #cf222e; }}
  .st-warning {{ color: #bc4c00; }}
  .st-info {{ color: #57606a; }}
  .st-clean {{ color: #1a7f37; }}
  .st-not-assessed {{ color: #8c959f; }}
  .note {{ font-size: 13px; color: #57606a; margin: 8px 0 0; }}
  ol.fixes {{ padding-left: 20px; }}
  ol.fixes li {{ margin-bottom: 16px; }}
  .fix-rule {{ font-weight: 700; }}
  .sev {{ font-size: 11px; text-transform: uppercase; padding: 1px 7px;
         border-radius: 999px; margin-left: 6px; vertical-align: middle; }}
  .sev-critical {{ background: #ffebe9; color: #cf222e; }}
  .sev-warning {{ background: #fff1e5; color: #bc4c00; }}
  .sev-info {{ background: #eff2f5; color: #57606a; }}
  .fix-msg {{ margin: 4px 0; }}
  .fix-do {{ color: #1a7f37; font-size: 14px; }}
  .clean {{ color: #1a7f37; font-weight: 600; }}
  .cta {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 10px;
         padding: 16px 18px; margin-top: 8px; }}
  .cta a {{ color: var(--accent); font-weight: 600; }}
  .foot {{ color: #8c959f; font-size: 12px; margin-top: 24px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>{html.escape(PRODUCT_NAME)} · RAG security posture scorecard</h1>
      <div class="grade">
        <div class="badge">{html.escape(p.grade)}</div>
        <div>
          <div class="score">{p.score}<small> / 100</small></div>
          <p class="blurb">{html.escape(p.blurb)}</p>
        </div>
      </div>
      <p class="meta">Scanned at <code>--env {html.escape(p.env)}</code> ·
        {p.counts['critical']} critical · {p.counts['warning']} warning ·
        {p.counts['info']} info</p>

      <h2>OWASP LLM Top 10 coverage</h2>
      <table>
        <tr><th>Risk</th><th>Area</th><th>Status</th><th>Rules</th></tr>
{coverage_rows}
      </table>
{notes}
      <h2>Top fixes</h2>
{fixes_html}

      <h2>Next step</h2>
      <div class="cta">
        This is a free self-serve grade. For a hands-on review of your RAG
        deployment, book the
        <a href="{ASSESSMENT_URL}">GenAI/RAG security assessment</a>.
      </div>

      <p class="foot">{html.escape(DISCLAIMER)}</p>
    </div>
  </div>
</body>
</html>"""
