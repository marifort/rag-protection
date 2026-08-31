"""SARIF 2.1.0 reporter for GitHub code scanning."""

from __future__ import annotations

import json

from .. import __version__
from ..models import ScanReport, Severity

_SARIF_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}


def render(report: ScanReport) -> str:
    results = []
    rules: dict[str, dict] = {}
    for f in report.findings:
        rules.setdefault(
            f.rule_id,
            {
                "id": f.rule_id,
                "name": f.title,
                "shortDescription": {"text": f.title},
                "helpUri": "https://github.com/marifort/rag-protection#rag-scan",
            },
        )
        results.append(
            {
                "ruleId": f.rule_id,
                "level": _SARIF_LEVEL[f.severity],
                "message": {"text": f"{f.message} Fix: {f.remediation}".strip()},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.location or "config"}
                        }
                    }
                ],
            }
        )

    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "rag-scan",
                        "version": __version__,
                        "informationUri": "https://github.com/marifort/rag-protection",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(doc, indent=2)
