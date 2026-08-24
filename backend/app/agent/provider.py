from functools import lru_cache

from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI

from app.core.config import settings

# We are using Groq, not OpenAI-hosted tracing.
set_tracing_disabled(True)


@lru_cache(maxsize=1)
def get_groq_model() -> OpenAIChatCompletionsModel:
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        timeout=60.0,
        max_retries=2,
    )

    return OpenAIChatCompletionsModel(
        model=settings.groq_model,
        openai_client=client,
    )