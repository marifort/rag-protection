"""LLM outage fallback must not echo prompt content.

Regression test: the old fallback embedded a preview of the user message,
which included the <retrieved_untrusted_context> scaffolding and tripped the
citation guardrail's system-prompt-leak pattern, masking the real error.
"""

from unittest.mock import patch

import httpx

from rag_protection_proxy.config import LLMPolicy, OutputPolicy
from rag_protection_proxy.context_builder import build_messages
from rag_protection_proxy.guardrails.citation import verify_citations
from rag_protection_proxy.llm import LLMClient, _fallback_answer


def test_fallback_answer_contains_no_prompt_scaffolding():
    answer = _fallback_answer(detail="Name or service not known")
    assert "retrieved_untrusted_context" not in answer
    assert "temporarily unavailable" in answer
    assert "Name or service not known" in answer


async def test_chat_fallback_on_connection_error_excludes_prompt():
    messages = build_messages(
        "What is the Q1 payroll total?",
        [("chunk-1", "Payroll Doc", "Q1 payroll total is $1M.")],
    )
    client = LLMClient(LLMPolicy(base_url="http://unreachable.invalid/v1"))
    with patch.object(
        httpx.AsyncClient, "post", side_effect=httpx.ConnectError("Name or service not known")
    ):
        answer = await client.chat(messages)
    assert "retrieved_untrusted_context" not in answer
    assert "temporarily unavailable" in answer


def test_fallback_answer_does_not_trip_system_prompt_leak_check():
    answer = _fallback_answer(detail="connection refused")
    check = verify_citations(
        answer,
        [("chunk-1", "Payroll Doc: Q1 payroll total is $1M.")],
        OutputPolicy(entailment_check=False),
    )
    assert check.system_prompt_leak is False
