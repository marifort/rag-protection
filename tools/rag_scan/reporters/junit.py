"""JUnit XML reporter for CI test panels (GitHub checks, GitLab, etc.)."""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from ..models import ScanReport, Severity

# Each rule becomes a test case; critical/warning findings render as failures.
_RULES = [
    "ACL001", "ACL002", "ACL003",
    "POL001", "POL002", "POL003",
    "CON001", "SEC001", "SEC002", "VEC001",
]


def render(report: ScanReport) -> str:
    if report.load_error:
        body = (
            f'  <testcase classname="rag-scan" name="config-load">\n'
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
        case_attr = f'classname="rag-scan" name={quoteattr(rule_id)}'
        if not blocking:
            cases.append(f"  <testcase {case_attr}/>")
            continue
        failures += 1
        text = "\n".join(f"{f.severity.value.upper()}: {f.message}" for f in blocking)
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
        f'<testsuite name="rag-scan" tests="{tests}" failures="{failures}" errors="{errors}">\n'
        f"{body}"
        "</testsuite>\n"
    )
