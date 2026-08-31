"""DLP label mapping for audit export (E3.2)."""

from __future__ import annotations

from typing import Dict, List, Optional

from rag_protection_proxy.models import Finding

CATEGORY_LABELS: Dict[str, str] = {
    "person_name": "PHI",
    "address": "PHI",
    "ssn": "PHI",
    "sin": "PHI",
    "email": "PHI",
    "phone": "PHI",
    "credit_card": "PCI",
    "credit_card_candidate": "PCI",
    "openai_api_key": "PCI",
    "anthropic_api_key": "PCI",
    "aws_access_key": "PCI",
    "github_pat": "PCI",
    "slack_token": "PCI",
    "private_key": "PCI",
    "jwt_token": "PCI",
    "credential_assignment": "PCI",
}


CATEGORY_DISPLAY: Dict[str, str] = {
    "ssn": "SSN",
    "sin": "SIN",
    "sample_us_ssn": "SSN",
    "sample_ca_sin": "SIN",
    "person_name": "Name",
    "credit_card": "Card",
    "credit_card_candidate": "Card",
    "email": "Email",
    "phone": "Phone",
    "address": "Address",
}


def label_for_category(category: str) -> Optional[str]:
    return CATEGORY_LABELS.get(category)


def category_display_name(category: str) -> str:
    if not category:
        return ""
    return CATEGORY_DISPLAY.get(category, category.replace("_", " "))


def format_finding_categories(findings: List[Finding]) -> str:
    cats = sorted({category_display_name(f.category) for f in findings if f.category})
    return ", ".join(cats)


def apply_dlp_labels(findings: List[Finding], enabled_labels: List[str]) -> List[Finding]:
    if not enabled_labels:
        return findings
    allowed = {label.upper() for label in enabled_labels}
    labeled: List[Finding] = []
    for finding in findings:
        if finding.label and finding.label.upper() in allowed:
            labeled.append(finding)
            continue
        label = label_for_category(finding.category)
        if label and label in allowed:
            labeled.append(finding.model_copy(update={"label": label}))
        else:
            labeled.append(finding)
    return labeled
