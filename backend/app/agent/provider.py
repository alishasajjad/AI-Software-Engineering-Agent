from __future__ import annotations

from agents import (
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)
from openai import (
    AsyncOpenAI,
    OpenAI,
)

from app.agent.model_router import (
    get_agents_model,
    get_async_groq_client,
    get_primary_model_name,
    get_sync_groq_client,
)

# Groq is used through an OpenAI-compatible endpoint.
# OpenAI-hosted tracing is not required.
set_tracing_disabled(True)


def get_groq_client() -> AsyncOpenAI:
    """
    Return the shared asynchronous Groq-compatible client.

    Kept for backward compatibility with existing services
    that currently import get_groq_client().
    """

    return get_async_groq_client()


def get_groq_sync_client() -> OpenAI:
    """
    Return the shared synchronous Groq-compatible client.

    This is useful for synchronous services such as
    correction proposal generation.
    """

    return get_sync_groq_client()


def get_groq_model(
    model_name: str | None = None,
) -> OpenAIChatCompletionsModel:
    """
    Return an Agents SDK model instance.

    If model_name is omitted, the configured primary model
    from GROQ_MODEL is used.

    A specific model name can also be supplied by the
    central model router when a fallback model is needed.
    """

    selected_model = (
        model_name.strip()
        if model_name
        else get_primary_model_name()
    )

    if not selected_model:
        raise RuntimeError(
            "A Groq model name is required."
        )

    return get_agents_model(
        selected_model
    )


__all__ = [
    "get_groq_client",
    "get_groq_model",
    "get_groq_sync_client",
]