"""Base scanner interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from rag_protection_proxy.models import Finding


@dataclass
class ScannerResult:
    sanitized_text: str
    findings: List[Finding] = field(default_factory=list)
    redactions: int = 0


class Scanner(ABC):
    name: str = "scanner"

    @abstractmethod
    def scan(self, text: str) -> ScannerResult:
        """Scan text without raising on bad input."""
