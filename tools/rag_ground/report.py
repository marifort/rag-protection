"""Render a grounding result (single or batch) as text / json / junit.

Three formats:
  * ``text``  — human-readable verdict + ungrounded sentences (default).
  * ``json``  — machine-readable, stable shape for eval dashboards.
  * ``junit`` — JUnit XML so CI test panels show grounding regressions per item.

All formats are produced locally; no answer or source text leaves the machine.
"""

from __future__ import annotations

import json
from typing import List, Union
from xml.sax.saxutils import escape, quoteattr

from .grounding import BatchResult, GroundingResult

PRODUCT_NAME = "Marifort Gate"
ASSESSMENT_URL = (
    "https://github.com/marifort/rag-protection/blob/main/docs/commercial/"
    "SOLOPRENEUR_PRODUCT_OPPORTUNITIES.md#1-genai--rag-security-assessment"
)
DISCLAIMER = (
    "Measures grounding in the supplied context, not factual correctness of that "
    "context. Indicative gate, not a hallucination guarantee. Runs entirely "
    "locally — no answer or source text is uploaded."
)

_VERDICT_LABEL = {
    "grounded": "GROUNDED",
    "ungrounded": "UNGROUNDED",
    "leak": "LEAK",
}

Result = Union[GroundingResult, BatchResult]


def render(result: Result, fmt: str) -> str:
    formatters = {"text": render_text, "json": render_json, "junit": render_junit}
    try:
        formatter = formatters[fmt]
    except KeyError as exc:
        raise ValueError(f"unknown report format: {fmt}") from exc
    return formatter(result)


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #


def render_text(result: Result) -> str:
    if isinstance(result, BatchResult):
        return _text_batch(result)
    return _text_single(result)


def _text_single(r: GroundingResult) -> str:
    lines: List[str] = []
    lines.append(f"{PRODUCT_NAME} — grounding check")
    lines.append("")
    verdict = _VERDICT_LABEL[r.verdict]
    lines.append(
        f"Verdict: {verdict}  "
        f"(coverage {r.coverage_ratio:.2f}, threshold {r.threshold:.2f})"
    )
    lines.append(f"  {r.detail}")
    lines.append("")
    if r.system_prompt_leak:
        lines.append("System-prompt-like phrasing detected in the answer.")
        lines.append("")
    ungrounded = r.ungrounded_claims
    if ungrounded:
        lines.append(f"Ungrounded sentences ({len(ungrounded)}):")
        for claim in ungrounded:
            lines.append(f"  - {_fmt_claim(claim)}")
        lines.append("")
    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def _text_batch(b: BatchResult) -> str:
    lines: List[str] = []
    lines.append(f"{PRODUCT_NAME} — grounding check (batch)")
    lines.append("")
    gate = "PASS" if b.gate_passed else "FAIL"
    lines.append(
        f"Pass rate: {b.passed_count}/{b.total} ({b.pass_rate:.2f})  "
        f"threshold {b.threshold:.2f}  "
        f"min-pass-rate {b.min_pass_rate:.2f} -> {gate}"
    )
    if b.leak_count:
        lines.append(f"System-prompt leaks: {b.leak_count}")
    lines.append("")
    lines.append("Items:")
    for r in b.results:
        ident = f"  id={r.id}" if r.id else ""
        lines.append(
            f"  [{r.index}] {r.verdict:<10} coverage {r.coverage_ratio:.2f}{ident}"
        )
    lines.append("")
    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def _fmt_claim(claim) -> str:
    sentence = claim.sentence.strip()
    if len(sentence) > 120:
        sentence = sentence[:117] + "..."
    return f'"{sentence}"'


# --------------------------------------------------------------------------- #
# json
# --------------------------------------------------------------------------- #


def render_json(result: Result) -> str:
    if isinstance(result, BatchResult):
        payload = _json_batch(result)
    else:
        payload = _json_single(result)
    payload["tool"] = "rag-ground"
    payload["product"] = PRODUCT_NAME
    payload["disclaimer"] = DISCLAIMER
    return json.dumps(payload, indent=2)


def _json_single(r: GroundingResult) -> dict:
    return {
        "mode": "single",
        "verdict": r.verdict,
        "passed": r.passed,
        "coverage_ratio": r.coverage_ratio,
        "threshold": r.threshold,
        "system_prompt_leak": r.system_prompt_leak,
        "detail": r.detail,
        "claims": [_json_claim(c) for c in r.claims],
        "ungrounded_sentences": [c.sentence for c in r.ungrounded_claims],
    }


def _json_batch(b: BatchResult) -> dict:
    return {
        "mode": "batch",
        "total": b.total,
        "passed_count": b.passed_count,
        "leak_count": b.leak_count,
        "pass_rate": round(b.pass_rate, 3),
        "threshold": b.threshold,
        "min_pass_rate": b.min_pass_rate,
        "gate_passed": b.gate_passed,
        "items": [
            {
                "index": r.index,
                "id": r.id,
                "verdict": r.verdict,
                "passed": r.passed,
                "coverage_ratio": r.coverage_ratio,
                "system_prompt_leak": r.system_prompt_leak,
                "ungrounded_sentences": [c.sentence for c in r.ungrounded_claims],
            }
            for r in b.results
        ],
    }


def _json_claim(claim) -> dict:
    return {
        "sentence": claim.sentence,
        "chunk_id": claim.chunk_id,
        "supported": claim.supported,
        "entailment_score": claim.entailment_score,
        "offset_start": claim.offset_start,
        "offset_end": claim.offset_end,
    }


# --------------------------------------------------------------------------- #
# junit
# --------------------------------------------------------------------------- #


def render_junit(result: Result) -> str:
    if isinstance(result, BatchResult):
        cases = [_junit_case(r) for r in result.results]
        failures = sum(1 for r in result.results if not r.passed)
        body = "\n".join(cases) + "\n"
        return _suite(body, tests=result.total, failures=failures)

    failures = 0 if result.passed else 1
    body = _junit_case(result) + "\n"
    return _suite(body, tests=1, failures=failures)


def _junit_case(r: GroundingResult) -> str:
    name = r.id or (f"item-{r.index}" if r.index is not None else "answer")
    case_attr = f'classname="rag-ground" name={quoteattr(name)}'
    if r.passed:
        return f"  <testcase {case_attr}/>"
    msg = quoteattr(f"{r.verdict}: coverage {r.coverage_ratio:.2f} < {r.threshold:.2f}")
    detail_lines = [r.detail]
    if r.system_prompt_leak:
        detail_lines.append("system-prompt leak detected")
    detail_lines += [f"ungrounded: {c.sentence}" for c in r.ungrounded_claims]
    text = "\n".join(detail_lines)
    return (
        f"  <testcase {case_attr}>\n"
        f"    <failure message={msg}>{escape(text)}</failure>\n"
        f"  </testcase>"
    )


def _suite(body: str, *, tests: int, failures: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="rag-ground" tests="{tests}" failures="{failures}" errors="0">\n'
        f"{body}"
        "</testsuite>\n"
    )
