"""OpenAI-compatible LLM client for Docker Model Runner."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from rag_protection_proxy.config import LLMPolicy

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, policy: LLMPolicy) -> None:
        self.policy = policy
        base = policy.base_url.rstrip("/")
        if base.endswith("/v1"):
            self.chat_url = f"{base}/chat/completions"
        else:
            self.chat_url = f"{base}/v1/chat/completions"

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        payload: Dict[str, Any] = {
            "model": self.policy.model,
            "messages": messages,
            "temperature": self.policy.temperature,
            "max_tokens": self.policy.max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.policy.api_key:
            headers["Authorization"] = f"Bearer {self.policy.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.policy.timeout_seconds) as client:
                resp = await client.post(self.chat_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("LLM request failed: %s", exc)
            return _fallback_answer(detail=str(exc))

        return _extract_content(data)


def _extract_content(data: Dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return "I could not generate a response from the configured LLM."
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return "I could not generate a response from the configured LLM."


def _fallback_answer(detail: str = "") -> str:
    # Never echo prompt content here: the prompt contains the
    # <retrieved_untrusted_context> scaffolding, which would trip the citation
    # guardrail's system-prompt-leak check and mask the real (LLM outage) error.
    reason = f" ({detail})" if detail else ""
    return f"The knowledge assistant is temporarily unavailable{reason}. Please try again later."
