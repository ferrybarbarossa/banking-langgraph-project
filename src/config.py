"""LLM provider configuration.

Selects between Anthropic and OpenAI at runtime via the `LLM_PROVIDER` env var.
Provider and model can also be overridden per-call (e.g. per-agent) by passing
arguments directly to `get_llm`.
"""

from __future__ import annotations

import os
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

Provider = Literal["anthropic", "openai"]

DEFAULT_PROVIDER: Provider = "anthropic"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_OPENAI_MODEL = "gpt-5"


def get_llm(
    provider: Provider | None = None,
    model: str | None = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    resolved_provider = (provider or os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER)).lower()

    if resolved_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
            temperature=temperature,
        )

    if resolved_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            temperature=temperature,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {resolved_provider!r}. Expected 'anthropic' or 'openai'.")
