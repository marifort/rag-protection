"""Report formatters for MCP lint results."""

from __future__ import annotations

from ..models import LintReport
from . import junit, sarif, text

FORMATS = {
    "text": text.render,
    "junit": junit.render,
    "sarif": sarif.render,
}


def render(report: LintReport, fmt: str) -> str:
    try:
        return FORMATS[fmt](report)
    except KeyError as exc:
        raise ValueError(f"unknown report format: {fmt}") from exc
