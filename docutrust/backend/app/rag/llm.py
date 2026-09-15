"""Shared async OpenAI-compatible client."""
from __future__ import annotations
from openai import AsyncOpenAI

from ..config import settings

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY not set. Add it to backend/.env")
        _client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client
