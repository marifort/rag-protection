"""Baseline suppression for brownfield repos (L2-104).

A *baseline* is a JSON snapshot of findings that are known and intentionally
accepted (for now). On subsequent runs, `--baseline` removes any finding whose
fingerprint is recorded in the file, so a CI gate can be adopted on a repo with
pre-existing issues without going red on day one — while still failing on any
*new* or *changed* finding.

Format (version 1)::

    {
      "version": 1,
      "fingerprints": [
        {"rule_id": "ACL003", "location": "config/acl_policy.yaml", "fingerprint": "<sha1>"}
      ]
    }

Only the ``fingerprint`` field is load-bearing; ``rule_id``/``location`` are kept
for human review of the committed file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Set

from .models import Finding, ScanReport

BASELINE_VERSION = 1


class BaselineError(Exception):
    """Raised when a baseline file cannot be parsed (CLI exit code 2)."""


def load_fingerprints(path: str) -> Set[str]:
    """Read the set of suppressed fingerprints from a baseline file."""
    p = Path(path)
    if not p.exists():
        raise BaselineError(f"baseline file not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(f"invalid baseline JSON ({path}): {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("fingerprints"), list):
        raise BaselineError("baseline must be an object with a 'fingerprints' array")
    fingerprints: Set[str] = set()
    for entry in data["fingerprints"]:
        if isinstance(entry, str):
            fingerprints.add(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("fingerprint"), str):
            fingerprints.add(entry["fingerprint"])
    return fingerprints


def apply(report: ScanReport, fingerprints: Set[str]) -> None:
    """Drop findings present in the baseline; record how many were suppressed."""
    kept: List[Finding] = []
    suppressed = 0
    for finding in report.findings:
        if finding.fingerprint in fingerprints:
            suppressed += 1
            continue
        kept.append(finding)
    report.findings = kept
    report.suppressed += suppressed


def serialize(findings: List[Finding]) -> str:
    """Render a baseline file capturing the given findings."""
    doc = {
        "version": BASELINE_VERSION,
        "fingerprints": [
            {
                "rule_id": f.rule_id,
                "location": f.location,
                "fingerprint": f.fingerprint,
            }
            for f in findings
        ],
    }
    return json.dumps(doc, indent=2)
