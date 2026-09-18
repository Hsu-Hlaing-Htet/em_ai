"""Factory for the chat model used across the service.

Uses ``langchain-openai``'s ``ChatOpenAI``, the official LangChain integration
for the OpenAI API. The default model is ``gpt-4o``.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


@lru_cache
def get_chat_model() -> ChatOpenAI | None:
    api_key = (settings.openai_api_key or "").strip()
    if not api_key or api_key == "sk-...":
        return None

    return ChatOpenAI(
        model=settings.openai_model,
        max_tokens=settings.openai_max_tokens,
        api_key=api_key,
        timeout=60,
        temperature=0,  # grounded, deterministic answers over backend data
    )
