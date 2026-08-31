"""JUnit XML reporter for CI test panels."""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from ..models import LintReport, Severity

_RULES = ["MCP001", "MCP002", "MCP003", "MCP004", "MCP005"]


def render(report: LintReport) -> str:
    if report.load_error:
        body = (
            f'  <testcase classname="mcp-lint" name="manifest-load">\n'
            f"    <error message={quoteattr(report.load_error)}/>\n"
            f"  </testcase>\n"
        )
        return _suite(body, tests=1, failures=0, errors=1)

    by_rule: dict[str, list] = {}
    for f in report.findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    cases: list[str] = []
    failures = 0
    rule_ids = list(dict.fromkeys(_RULES + list(by_rule.keys())))
    for rule_id in rule_ids:
        findings = by_rule.get(rule_id, [])
        blocking = [f for f in findings if f.severity is not Severity.INFO]
        case_attr = f'classname="mcp-lint" name={quoteattr(rule_id)}'
        if not blocking:
            cases.append(f"  <testcase {case_attr}/>")
            continue
        failures += 1
        text = "\n".join(
            f"{f.location}: {f.severity.value.upper()} — {f.message}" for f in blocking
        )
        msg = quoteattr(blocking[0].title)
        cases.append(
            f"  <testcase {case_attr}>\n"
            f"    <failure message={msg}>{escape(text)}</failure>\n"
            f"  </testcase>"
        )

    body = "\n".join(cases) + "\n"
    return _suite(body, tests=len(rule_ids), failures=failures, errors=0)


def _suite(body: str, *, tests: int, failures: int, errors: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="mcp-lint" tests="{tests}" failures="{failures}" errors="{errors}">\n'
        f"{body}"
        "</testsuite>\n"
    )
