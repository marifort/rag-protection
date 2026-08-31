#!/usr/bin/env python3
"""Generate static SVG diagrams for docs (Cursor preview safe)."""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "diagrams"

STYLE = """
<style>
  .box { fill: #e8f4fc; stroke: #2563eb; stroke-width: 1.5; rx: 6; }
  .store { fill: #fef3c7; stroke: #d97706; stroke-width: 1.5; }
  .llm { fill: #ede9fe; stroke: #7c3aed; stroke-width: 1.5; }
  .user { fill: #dcfce7; stroke: #16a34a; stroke-width: 1.5; }
  .label { font: 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #111; }
  .title { font: bold 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #111; }
  .small { font: 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #444; }
  .arrow { stroke: #64748b; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
  .group { fill: #f8fafc; stroke: #94a3b8; stroke-width: 1; stroke-dasharray: 4 3; rx: 8; }
</style>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#64748b"/></marker></defs>
"""


def wrap(title: str, body: str, w: int, h: int) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f"{STYLE}\n"
        f'<text x="{w//2}" y="22" text-anchor="middle" class="title">{title}</text>\n'
        f"{body}\n</svg>\n"
    )


def rect(x, y, w, h, cls="box", text="", sub=""):
    lines = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{cls}"/>'
    if text:
        lines += f'<text x="{x + w//2}" y="{y + h//2 - (6 if sub else 0)}" text-anchor="middle" class="label">{text}</text>'
    if sub:
        lines += f'<text x="{x + w//2}" y="{y + h//2 + 14}" text-anchor="middle" class="small">{sub}</text>'
    return lines


def arrow(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="arrow"/>'


def high_level() -> str:
    body = """
<rect x="20" y="40" width="560" height="70" class="group"/>
<text x="30" y="58" class="small">Users and Operators</text>
""" + rect(40, 68, 200, 32, "user", "Employee / HR / Executive") + rect(280, 68, 220, 32, "user", "Operator Console /ui") + """
<rect x="20" y="130" width="560" height="280" class="group"/>
<text x="30" y="148" class="small">Marifort Gate (port 8090)</text>
""" + rect(220, 160, 160, 28, "box", "ACL Resolution") + arrow(300, 188, 300, 208) + rect(200, 208, 200, 28, "box", "Pre-Retrieval ACL Filter") + arrow(300, 236, 300, 256) + rect(190, 256, 220, 32, "store", "SQLite Document Store") + arrow(300, 288, 300, 308) + rect(200, 308, 200, 28, "box", "Input Guardrails") + arrow(300, 336, 300, 356) + rect(180, 356, 240, 28, "box", "Context Isolation Builder") + """
<rect x="20" y="430" width="560" height="70" class="group"/>
<text x="30" y="448" class="small">LLM Backend</text>
""" + rect(140, 460, 160, 28, "llm", "Docker Model Runner") + arrow(300, 384, 220, 460) + rect(340, 460, 160, 28, "box", "Citation Verifier") + arrow(420, 488, 420, 520) + rect(340, 520, 160, 28, "box", "Output Guardrails") + arrow(420, 548, 300, 580) + rect(200, 580, 200, 28, "user", "Secured Response to User") + rect(430, 308, 130, 28, "box", "Audit Buffer") + arrow(400, 322, 430, 322)
    return wrap("High-Level Architecture", body, 600, 630)


def query_pipeline() -> str:
    steps = [
        ("User", "POST /v1/query + Bearer token"),
        ("ACL", "resolve_auth → groups"),
        ("Store", "search with ACL filter"),
        ("Input", "scan_input per chunk"),
        ("Context", "XML-isolated prompt"),
        ("LLM", "chat completion"),
        ("Citation", "verify grounding"),
        ("Output", "scan_output DLP"),
        ("User", "answer or safe fallback"),
    ]
    body = ""
    y = 50
    for i, (name, detail) in enumerate(steps):
        cls = "user" if name == "User" else "box"
        body += rect(150, y, 300, 40, cls, name, detail)
        if i < len(steps) - 1:
            body += arrow(300, y + 40, 300, y + 55)
        y += 55
    return wrap("Query Pipeline", body, 600, y + 20)


def guardrails() -> str:
    nodes = [
        ("User Query", 30),
        ("1. ACL Filter", 150),
        ("2. Input DLP", 270),
        ("3. Context Isolation", 390),
        ("LLM", 510),
        ("4. Citation + Output", 630),
        ("Response", 750),
    ]
    body = ""
    for i, (label, x) in enumerate(nodes):
        cls = "llm" if label == "LLM" else "box"
        body += rect(x, 80, 100, 50, cls, label[:14], label[14:] if len(label) > 14 else "")
        if i < len(nodes) - 1:
            body += arrow(x + 100, 105, nodes[i + 1][1], 105)
    return wrap("Four Security Guardrails", body, 880, 180)


def components() -> str:
    body = """
<rect x="20" y="40" width="170" height="120" class="group"/><text x="30" y="58" class="small">HTTP (app.py)</text>
""" + rect(35, 70, 140, 24, "box", "/v1/query") + rect(35, 100, 140, 24, "box", "/v1/ingest") + rect(35, 130, 140, 24, "box", "/ui /health") + """
<rect x="210" y="40" width="170" height="160" class="group"/><text x="220" y="58" class="small">Core</text>
""" + rect(225, 70, 140, 22, "box", "pipeline.py") + rect(225, 98, 140, 22, "box", "acl.py / store.py") + rect(225, 126, 140, 22, "box", "llm.py") + rect(225, 154, 140, 22, "box", "config.py") + """
<rect x="400" y="40" width="170" height="160" class="group"/><text x="410" y="58" class="small">Guardrails</text>
""" + rect(415, 70, 140, 22, "box", "input_pipeline") + rect(415, 98, 140, 22, "box", "output_pipeline") + rect(415, 126, 140, 22, "box", "citation.py") + """
<rect x="590" y="40" width="170" height="160" class="group"/><text x="600" y="58" class="small">Scanners</text>
""" + rect(605, 70, 140, 22, "box", "prompt_injection") + rect(605, 98, 140, 22, "box", "pii / secrets") + rect(605, 126, 140, 22, "box", "url_threat") + """
<rect x="210" y="220" width="350" height="80" class="group"/><text x="220" y="238" class="small">Config files</text>
""" + rect(225, 250, 100, 28, "box", "policy.yaml") + rect(340, 250, 100, 28, "box", "acl_policy") + rect(455, 250, 90, 28, "box", "sample_docs") + arrow(105, 160, 310, 220) + arrow(295, 200, 415, 200) + arrow(485, 200, 605, 200)
    return wrap("Component Architecture", body, 780, 320)


def deployment() -> str:
    body = rect(240, 70, 200, 40, "box", "rag-protection-proxy", "port 8090") + rect(80, 160, 160, 40, "user", "Developer / UI") + rect(440, 160, 180, 40, "store", "rag-data volume") + rect(240, 250, 200, 40, "llm", "Docker Model Runner") + arrow(160, 180, 240, 110) + arrow(340, 110, 530, 160) + arrow(340, 110, 340, 250)
    return wrap("Deployment Architecture", body, 700, 320)


def threat_model() -> str:
    body = rect(300, 50, 120, 36, "box", "RAG Threats") + arrow(360, 86, 120, 130) + arrow(360, 86, 360, 130) + arrow(360, 86, 600, 130) + rect(40, 130, 160, 30, "box", "Data Leakage") + rect(280, 130, 160, 30, "box", "Injection") + rect(520, 130, 160, 30, "box", "Integrity") + """
<text x="50" y="185" class="small">• Unauthorized retrieval</text>
<text x="50" y="205" class="small">• PII in context/response</text>
<text x="50" y="225" class="small">• Secret exfiltration</text>
<text x="290" y="185" class="small">• HTML comment payloads</text>
<text x="290" y="205" class="small">• Instruction overrides</text>
<text x="290" y="225" class="small">• Role hijacking</text>
<text x="530" y="185" class="small">• Hallucinated facts</text>
<text x="530" y="205" class="small">• System prompt leaks</text>
<text x="530" y="225" class="small">• Malicious URLs</text>
"""
    return wrap("Threat Model", body, 720, 260)


def _flow_row(y: int, steps: list[tuple[str, str]], x0: int = 40, box_w: int = 130, gap: int = 40) -> str:
    """Horizontal left-to-right flow inside a subgraph row."""
    body = ""
    x = x0
    for i, (label, sub) in enumerate(steps):
        body += rect(x, y, box_w, 36, "box", label, sub)
        if i < len(steps) - 1:
            body += arrow(x + box_w, y + 18, x + box_w + gap, y + 18)
        x += box_w + gap
    return body


def p1_challenge_mode() -> str:
    body = """
<rect x="20" y="40" width="760" height="70" class="group"/><text x="30" y="58" class="small">Query path</text>
""" + _flow_row(62, [
        ("scan_input", "query"),
        ("effective block?", ""),
        ("query_guardrail_blocked", "or retrieval"),
    ], x0=40, box_w=150, gap=50) + """
<rect x="20" y="130" width="760" height="70" class="group"/><text x="30" y="148" class="small">Chunk path</text>
""" + _flow_row(152, [
        ("scan_input", "chunk"),
        ("effective block?", ""),
        ("exclude from LLM", "or sanitized"),
    ], x0=40, box_w=150, gap=50) + """
<rect x="20" y="220" width="760" height="70" class="group"/><text x="30" y="238" class="small">Ingest path</text>
""" + _flow_row(242, [
        ("scan_ingest", ""),
        ("effective block?", ""),
        ("HTTP 422", "or quarantine / active"),
    ], x0=40, box_w=130, gap=45)
    return wrap("P1 CHALLENGE Mode — Flow by Path", body, 800, 320)


def p1_user_query() -> str:
    body = rect(200, 50, 200, 32, "user", "User / UI", "POST /v1/query") + arrow(300, 82, 300, 100) + rect(
        170, 100, 260, 32, "box", "pipeline.run_query", ""
    ) + arrow(300, 132, 300, 150) + rect(190, 150, 220, 32, "box", "scan_input", "user query") + arrow(
        300, 182, 300, 210
    ) + rect(215, 210, 170, 36, "box", "effective BLOCK?", "") + """
<text x="60" y="280" class="small">yes → blocked (query_guardrail_blocked)</text>
<text x="60" y="300" class="small">no → store.search → chunks → LLM → QueryResponse</text>
""" + arrow(215, 228, 120, 260) + arrow(385, 228, 480, 260) + rect(40, 310, 160, 32, "box", "blocked", "no LLM") + rect(
        420, 310, 200, 32, "user", "QueryResponse", "after chunk scan + LLM"
    )
    return wrap("P1 User-Query Guardrails", body, 640, 370)


def p1_ingest_security() -> str:
    steps = [
        ("POST /v1/ingest", "admin"),
        ("scan_ingest_content", ""),
        ("evaluate_ingest_scan", "rejected / quarantined / ok"),
        ("store document", "active or quarantined"),
        ("admin approve", "if quarantined"),
        ("searchable", "ACL filter"),
    ]
    body = ""
    y = 50
    for i, (label, sub) in enumerate(steps):
        body += rect(170, y, 260, 40, "store" if i == 0 else "box", label, sub)
        if i < len(steps) - 1:
            body += arrow(300, y + 40, 300, y + 55)
        y += 55
    body += """
<text x="450" y="165" class="small">rejected → HTTP 422</text>
<text x="450" y="220" class="small">quarantined → approve → active</text>
"""
    return wrap("P1 Ingest-Time Security", body, 640, y + 30)


def e1_operator_architecture() -> str:
    body = """
<rect x="20" y="40" width="760" height="72" class="group"/><text x="30" y="58" class="small">Operator Console /ui (E1.1–E1.3)</text>
""" + _flow_row(62, [
        ("Query Lab", "Injection demo"),
        ("Documents", "Quarantine queue"),
        ("Audit Log", "NDJSON export"),
        ("Policy Viewer/Admin", "reload"),
    ], x0=30, box_w=155, gap=28) + """
<rect x="20" y="130" width="760" height="72" class="group"/><text x="30" y="148" class="small">Admin API</text>
""" + _flow_row(152, [
        ("GET quarantined", "E1.1"),
        ("POST approve", "E1.1"),
        ("GET audit/export", "E1.2"),
        ("POST reload-policy", ""),
    ], x0=30, box_w=155, gap=28) + """
<rect x="20" y="220" width="360" height="100" class="group"/><text x="30" y="238" class="small">Guardrail pipeline (existing)</text>
""" + rect(40, 252, 140, 36, "box", "P1 query scan", "") + rect(200, 252, 140, 36, "box", "P1 ingest scan", "") + """
<rect x="400" y="220" width="380" height="100" class="group"/><text x="410" y="238" class="small">E1.4 audit sinks</text>
""" + rect(420, 252, 90, 36, "box", "Buffer", "") + rect(520, 252, 90, 36, "store", "JSONL", "") + rect(620, 252, 90, 36, "box", "Webhook", "3x retry") + rect(720, 252, 50, 36, "box", "DLQ", "") + """
<text x="40" y="340" class="small">Query Lab → P1 scan → query_guardrail_blocked → verdict banner</text>
<text x="40" y="358" class="small">Documents → ingest → quarantine → Approve → active corpus</text>
"""
    return wrap("E1 — Operator Architecture", body, 800, 380)


def e1_quarantine_approve() -> str:
    body = _flow_row(55, [
        ("POST /v1/ingest", ""),
        ("scan_input", "title+content"),
        ("verdict", "ALLOW/CHALLENGE/BLOCK"),
    ], x0=30, box_w=120, gap=35) + """
<text x="30" y="115" class="small">BLOCK or CHALLENGE+block → HTTP 422</text>
<text x="30" y="133" class="small">CHALLENGE+allow → status quarantined</text>
""" + arrow(185, 91, 185, 150) + rect(95, 150, 180, 40, "store", "Quarantine Queue", "UI table E1.1") + arrow(185, 190, 185, 210) + rect(
        95, 210, 180, 40, "user", "Operator Approve", "POST /admin/.../approve"
    ) + arrow(185, 250, 185, 270) + rect(95, 270, 180, 40, "box", "Active document", "searchable + corpus") + """
<text x="320" y="175" class="small">hidden from GET /v1/documents</text>
<text x="320" y="290" class="small">visible after approve</text>
"""
    return wrap("E1.1 — Quarantine Approve Flow", body, 520, 330)


def e1_audit_export() -> str:
    body = _flow_row(70, [
        ("record()", "guardrails"),
        ("Ring buffer", ""),
        ("JSONL file", "RAG_AUDIT_FILE"),
        ("admin export", "GET /admin/audit/export"),
        ("UI Download", "E1.2"),
    ], x0=25, box_w=115, gap=28) + """
<text x="25" y="130" class="small">GET /audit/recent reads ring buffer (warmed from JSONL on startup; file fallback if empty)</text>
"""
    return wrap("E1.2 — Audit Export Flow", body, 700, 160)


def e1_query_verdict() -> str:
    body = rect(200, 50, 200, 32, "user", "Operator", "Injection demo") + arrow(300, 82, 300, 100) + rect(
        200, 100, 200, 32, "user", "Query Lab UI", ""
    ) + arrow(300, 132, 300, 150) + rect(170, 150, 260, 32, "box", "POST /v1/query", "") + arrow(
        300, 182, 300, 200
    ) + rect(190, 200, 220, 36, "box", "scan_input P1", "user query") + arrow(300, 236, 300, 254) + rect(
        215, 254, 170, 36, "box", "BLOCK?", "instruction_override"
    ) + """
<text x="40" y="310" class="small">yes → query_guardrail_blocked (no store.search, no LLM)</text>
<text x="40" y="328" class="small">UI verdict banner: query_verdict block + block_reason</text>
""" + arrow(215, 272, 100, 295) + rect(30, 295, 150, 32, "box", "Red banner", "E1.3") + arrow(385, 272, 470, 295) + rect(
        430, 295, 170, 32, "box", "QueryResponse", "chunks: []"
    )
    return wrap("E1.3 — Query Verdict Banner", body, 640, 360)


def e1_webhook_retry() -> str:
    steps = [
        ("record event", ""),
        ("async thread", ""),
        ("POST attempt 1", ""),
        ("backoff sleep", ""),
        ("POST attempt 2", ""),
        ("POST attempt 3", ""),
        ("dead-letter file", "if all fail"),
    ]
    body = ""
    y = 50
    for i, (label, sub) in enumerate(steps):
        body += rect(200, y, 240, 36, "box", label, sub)
        if i < len(steps) - 1:
            body += arrow(320, y + 36, 320, y + 48)
        y += 48
    body += """
<text x="460" y="95" class="small">fail → retry (default 3x)</text>
<text x="460" y="185" class="small">JSONL sink written regardless</text>
<text x="460" y="290" class="small">RAG_AUDIT_DEAD_LETTER_FILE optional</text>
"""
    return wrap("E1.4 — Webhook Retry + Dead Letter", body, 640, y + 20)


def e1_oidc_acl() -> str:
    body = _flow_row(70, [
        ("Azure AD / Okta", "RS256 JWT"),
        ("resolve_auth", "OIDC JWKS"),
        ("AuthContext", "groups"),
        ("store.search", "ACL filter"),
        ("pipeline", "scan + LLM"),
    ], x0=25, box_w=115, gap=28) + """
<text x="25" y="130" class="small">E1.6 runbook validates live IdP — see docs/qa/runbooks/OIDC_VALIDATION.md</text>
"""
    return wrap("E1.6 — OIDC to ACL Flow", body, 700, 160)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    diagrams = {
        "01-high-level.svg": high_level(),
        "02-query-pipeline.svg": query_pipeline(),
        "03-guardrails.svg": guardrails(),
        "04-components.svg": components(),
        "05-deployment.svg": deployment(),
        "06-threat-model.svg": threat_model(),
        "07-p1-challenge-mode.svg": p1_challenge_mode(),
        "08-p1-user-query.svg": p1_user_query(),
        "09-p1-ingest-security.svg": p1_ingest_security(),
        "10-e1-operator-architecture.svg": e1_operator_architecture(),
        "11-e1-quarantine-approve.svg": e1_quarantine_approve(),
        "12-e1-audit-export.svg": e1_audit_export(),
        "13-e1-query-verdict.svg": e1_query_verdict(),
        "14-e1-webhook-retry.svg": e1_webhook_retry(),
        "15-e1-oidc-acl.svg": e1_oidc_acl(),
    }
    for name, svg in diagrams.items():
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
