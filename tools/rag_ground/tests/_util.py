"""Shared helpers + reusable fixtures for the rag-ground test suite."""

from __future__ import annotations

from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# A two-sentence answer, both sentences supported by SOURCES below.
GROUNDED_ANSWER = "The capital of France is Paris. The Louvre museum is located in Paris."

# Same first sentence, second sentence fabricated (no overlap with sources).
UNGROUNDED_ANSWER = (
    "The capital of France is Paris. "
    "France adopted the euro currency in 1850 after a national referendum."
)

# Triggers the system-prompt-leak regex in the shipped guardrail.
LEAK_ANSWER = "As an AI language model, I cannot reveal my system prompt."

SOURCES = [
    {"id": "s1", "text": "Paris is the capital city of France."},
    {"id": "s2", "text": "The Louvre is a famous art museum located in Paris."},
]
