from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any

from agents import (
    OpenAIChatCompletionsModel,
    Runner,
)
from openai import (
    AsyncOpenAI,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


DEFAULT_FALLBACK_MODEL = "qwen/qwen3.6-27b"

DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 300.0


class ModelFallbackExhaustedError(
    RuntimeError
):
    """
    Raised when model routing cannot currently continue
    because one or more configured models are unavailable
    due to provider rate limiting.

    This includes mixed routes where another model may have
    encountered a compatibility failure but rate-limited
    models still prevent the complete configured route from
    being evaluated fairly.
    """


class ModelCompatibilityFallbackExhaustedError(
    RuntimeError
):
    """
    Raised when all currently usable configured agent models
    fail because of a narrowly recognized tool-protocol
    compatibility issue and no rate-limited model remains
    that could change the outcome after its cooldown.
    """


# ---------------------------------------------------------
# RATE-LIMIT COOLDOWN STATE
# ---------------------------------------------------------

_model_cooldowns: dict[str, float] = {}


# ---------------------------------------------------------
# BASIC CONFIGURATION
# ---------------------------------------------------------


def get_primary_model_name() -> str:
    """
    Return the project's configured primary model.

    GROQ_MODEL remains the source of truth for the
    primary model.
    """

    model = str(
        settings.groq_model
    ).strip()

    if not model:
        raise RuntimeError(
            "GROQ_MODEL is not configured."
        )

    return model


def _fallback_enabled() -> bool:
    """
    Model fallback is enabled by default.

    It can optionally be disabled at process level with:

        GROQ_MODEL_FALLBACK_ENABLED=false
    """

    raw_value = os.getenv(
        "GROQ_MODEL_FALLBACK_ENABLED",
        "true",
    )

    return (
        raw_value.strip()
        .lower()
        not in {
            "0",
            "false",
            "no",
            "off",
        }
    )


def _configured_fallback_models() -> tuple[str, ...]:
    """
    Return fallback models.

    Optional process-level override:

        GROQ_FALLBACK_MODELS=model1,model2

    If no override exists, Qwen 3.6 27B is used as the
    default fallback.
    """

    raw_value = os.getenv(
        "GROQ_FALLBACK_MODELS",
        "",
    ).strip()

    if not raw_value:
        return (
            DEFAULT_FALLBACK_MODEL,
        )

    models: list[str] = []

    for item in raw_value.split(","):
        model = item.strip()

        if (
            model
            and model not in models
        ):
            models.append(
                model
            )

    return tuple(models)


def get_model_sequence(
    primary_model: str | None = None,
) -> tuple[str, ...]:
    """
    Return the ordered model routing sequence.

    Example:

        openai/gpt-oss-120b
        openai/gpt-oss-20b
        qwen/qwen3.6-27b

    Duplicate models are removed.
    """

    primary = (
        primary_model.strip()
        if primary_model
        else get_primary_model_name()
    )

    models: list[str] = [
        primary,
    ]

    if _fallback_enabled():
        for model in (
            _configured_fallback_models()
        ):
            if model not in models:
                models.append(
                    model
                )

    return tuple(models)


# ---------------------------------------------------------
# CLIENTS
# ---------------------------------------------------------


def _secret_value(
    value: object,
) -> str:
    if hasattr(
        value,
        "get_secret_value",
    ):
        return str(
            value.get_secret_value()
        )

    return str(
        value
    )


@lru_cache(maxsize=1)
def get_async_groq_client() -> AsyncOpenAI:
    """
    Shared asynchronous Groq-compatible client.
    """

    api_key = getattr(
        settings,
        "groq_api_key",
        None,
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    return AsyncOpenAI(
        api_key=_secret_value(
            api_key
        ),
        base_url=settings.groq_base_url,
        timeout=60.0,
        max_retries=2,
    )


@lru_cache(maxsize=1)
def get_sync_groq_client() -> OpenAI:
    """
    Shared synchronous Groq-compatible client.
    """

    api_key = getattr(
        settings,
        "groq_api_key",
        None,
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    return OpenAI(
        api_key=_secret_value(
            api_key
        ),
        base_url=settings.groq_base_url,
        timeout=60.0,
        max_retries=2,
    )


@lru_cache(maxsize=16)
def get_agents_model(
    model_name: str,
) -> OpenAIChatCompletionsModel:
    """
    Create/cache an Agents SDK model for a specific Groq
    model name.
    """

    normalized_model = (
        model_name.strip()
    )

    if not normalized_model:
        raise ValueError(
            "A model name is required."
        )

    return OpenAIChatCompletionsModel(
        model=normalized_model,
        openai_client=(
            get_async_groq_client()
        ),
    )


# ---------------------------------------------------------
# EXCEPTION CHAIN
# ---------------------------------------------------------


def _iter_exception_chain(
    exc: BaseException,
):
    """
    Walk through wrapped exceptions safely.

    The Agents SDK or application services may wrap the
    original OpenAI/Groq error in another exception.
    """

    current: BaseException | None = (
        exc
    )

    seen: set[int] = set()

    while (
        current is not None
        and id(current) not in seen
    ):
        seen.add(
            id(current)
        )

        yield current

        next_exception = (
            current.__cause__
            or current.__context__
        )

        current = next_exception


# ---------------------------------------------------------
# RATE-LIMIT DETECTION
# ---------------------------------------------------------


def is_rate_limit_error(
    exc: BaseException,
) -> bool:
    """
    Detect provider rate/quota exhaustion.

    Normal coding errors, invalid JSON, validation errors,
    model reasoning errors and application failures do not
    trigger rate-limit fallback.
    """

    markers = (
        "rate limit",
        "rate_limit_exceeded",
        "tokens per day",
        "tokens per minute",
        "requests per day",
        "requests per minute",
        "daily token limit",
        "daily request limit",
        "quota exceeded",
        "too many requests",
    )

    for current in (
        _iter_exception_chain(
            exc
        )
    ):
        if isinstance(
            current,
            RateLimitError,
        ):
            return True

        status_code = getattr(
            current,
            "status_code",
            None,
        )

        if status_code == 429:
            return True

        message = str(
            current
        ).lower()

        if any(
            marker in message
            for marker in markers
        ):
            return True

    return False


# ---------------------------------------------------------
# TOOL-PROTOCOL COMPATIBILITY DETECTION
# ---------------------------------------------------------


def _bad_request_body(
    exc: BaseException,
) -> Any:
    """
    Return an OpenAI BadRequestError response body when
    available.
    """

    return getattr(
        exc,
        "body",
        None,
    )


def _tool_error_code(
    exc: BaseException,
) -> str:
    """
    Read provider error code from BadRequestError.body.
    """

    body = _bad_request_body(
        exc
    )

    if not isinstance(
        body,
        dict,
    ):
        return ""

    code = body.get(
        "code"
    )

    if code is not None:
        return str(
            code
        ).lower()

    nested_error = body.get(
        "error"
    )

    if isinstance(
        nested_error,
        dict,
    ):
        nested_code = (
            nested_error.get(
                "code"
            )
        )

        if nested_code is not None:
            return str(
                nested_code
            ).lower()

    return ""


def is_tool_protocol_compatibility_error(
    exc: BaseException,
) -> bool:
    """
    Detect one narrow class of model/tool compatibility
    failure.

    Example:

        search_code<|channel|>commentary

    instead of:

        search_code

    Generic HTTP 400 errors do not trigger model fallback.
    """

    protocol_markers = (
        "<|channel|>",
        "<|recipient|>",
        "<|constrain|>",
        "<|analysis|>",
        "<|commentary|>",
        "<|final|>",
    )

    tool_failure_markers = (
        "tool call validation failed",
        "tool_use_failed",
        "attempted to call tool",
        "was not in request.tools",
    )

    for current in (
        _iter_exception_chain(
            exc
        )
    ):
        status_code = getattr(
            current,
            "status_code",
            None,
        )

        message = str(
            current
        ).lower()

        error_code = (
            _tool_error_code(
                current
            )
        )

        has_protocol_marker = any(
            marker in message
            for marker in protocol_markers
        )

        has_tool_failure_marker = (
            error_code
            == "tool_use_failed"
            or any(
                marker in message
                for marker in tool_failure_markers
            )
        )

        is_bad_request = (
            isinstance(
                current,
                BadRequestError,
            )
            or status_code == 400
        )

        if (
            is_bad_request
            and has_protocol_marker
            and has_tool_failure_marker
        ):
            return True

    return False


# ---------------------------------------------------------
# RETRY / COOLDOWN PARSING
# ---------------------------------------------------------


def _parse_retry_seconds_from_text(
    text: str,
) -> float | None:
    """
    Parse Groq messages such as:

        try again in 244.9s
        try again in 3m24.9s
    """

    normalized = (
        text.lower()
    )

    match = re.search(
        r"try again in\s+"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
        r"(?P<seconds>\d+(?:\.\d+)?)s",
        normalized,
    )

    if match is None:
        return None

    minutes_text = match.group(
        "minutes"
    )

    seconds_text = match.group(
        "seconds"
    )

    minutes = (
        float(minutes_text)
        if minutes_text
        else 0.0
    )

    seconds = float(
        seconds_text
    )

    return (
        minutes * 60.0
        + seconds
    )


def _retry_after_from_headers(
    exc: BaseException,
) -> float | None:
    response = getattr(
        exc,
        "response",
        None,
    )

    if response is None:
        return None

    headers = getattr(
        response,
        "headers",
        None,
    )

    if headers is None:
        return None

    try:
        raw_value = headers.get(
            "retry-after"
        )

    except Exception:
        return None

    if not raw_value:
        return None

    try:
        return float(
            raw_value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def get_retry_after_seconds(
    exc: BaseException,
) -> float | None:
    """
    Extract provider retry guidance from a wrapped error.
    """

    for current in (
        _iter_exception_chain(
            exc
        )
    ):
        header_value = (
            _retry_after_from_headers(
                current
            )
        )

        if (
            header_value is not None
            and header_value > 0
        ):
            return header_value

        text_value = (
            _parse_retry_seconds_from_text(
                str(
                    current
                )
            )
        )

        if (
            text_value is not None
            and text_value > 0
        ):
            return text_value

    return None


def _default_cooldown_seconds() -> float:
    raw_value = os.getenv(
        "GROQ_RATE_LIMIT_COOLDOWN_SECONDS",
        str(
            DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        ),
    )

    try:
        value = float(
            raw_value
        )

    except ValueError:
        return (
            DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        )

    return max(
        value,
        1.0,
    )


def _mark_model_rate_limited(
    model_name: str,
    exc: BaseException,
) -> float:
    """
    Temporarily mark a model unavailable.
    """

    retry_after = (
        get_retry_after_seconds(
            exc
        )
    )

    cooldown_seconds = (
        retry_after
        if retry_after is not None
        else _default_cooldown_seconds()
    )

    cooldown_seconds += 5.0

    _model_cooldowns[
        model_name
    ] = (
        time.monotonic()
        + cooldown_seconds
    )

    return cooldown_seconds


def _remaining_cooldown(
    model_name: str,
) -> float:
    deadline = (
        _model_cooldowns.get(
            model_name
        )
    )

    if deadline is None:
        return 0.0

    remaining = (
        deadline
        - time.monotonic()
    )

    if remaining <= 0:
        _model_cooldowns.pop(
            model_name,
            None,
        )

        return 0.0

    return remaining


def _configured_cooldown_waits(
    configured_sequence: tuple[str, ...],
) -> dict[str, float]:
    """
    Return currently active cooldowns for configured models.
    """

    waits: dict[str, float] = {}

    for model_name in (
        configured_sequence
    ):
        remaining = (
            _remaining_cooldown(
                model_name
            )
        )

        if remaining > 0:
            waits[
                model_name
            ] = remaining

    return waits


def _next_configured_retry(
    configured_sequence: tuple[str, ...],
) -> float:
    """
    Return the nearest configured model cooldown expiry.
    """

    waits = (
        _configured_cooldown_waits(
            configured_sequence
        )
    )

    if not waits:
        return 0.0

    return min(
        waits.values()
    )


def clear_model_cooldowns() -> None:
    """
    Primarily useful for tests and manual debugging.
    """

    _model_cooldowns.clear()


def get_available_model_sequence(
    primary_model: str | None = None,
) -> tuple[str, ...]:
    """
    Return models that are not currently cooling down.
    """

    sequence = (
        get_model_sequence(
            primary_model
        )
    )

    return tuple(
        model
        for model in sequence
        if _remaining_cooldown(
            model
        )
        <= 0
    )


# ---------------------------------------------------------
# LOGGING HELPERS
# ---------------------------------------------------------


def _log_model_attempt(
    *,
    operation_name: str,
    model_name: str,
    position: int,
) -> None:
    logger.info(
        "AI model attempt | operation=%s | model=%s | "
        "route_position=%s",
        operation_name,
        model_name,
        position,
    )


def _log_rate_limit_fallback(
    *,
    operation_name: str,
    model_name: str,
    next_model: str | None,
    cooldown_seconds: float,
) -> None:
    logger.warning(
        "AI model rate limited | operation=%s | model=%s | "
        "cooldown_seconds=%.1f | fallback=%s",
        operation_name,
        model_name,
        cooldown_seconds,
        next_model or "none",
    )


def _log_tool_protocol_fallback(
    *,
    operation_name: str,
    model_name: str,
    next_model: str | None,
) -> None:
    logger.warning(
        "AI model tool-protocol compatibility failure | "
        "operation=%s | model=%s | fallback=%s",
        operation_name,
        model_name,
        next_model or "none",
    )


# ---------------------------------------------------------
# GENERIC MODEL FALLBACK EXECUTION
# ---------------------------------------------------------


async def run_async_model_call_with_fallback(
    *,
    operation_name: str,
    request_factory: Callable[
        [AsyncOpenAI, str],
        Awaitable[Any],
    ],
    primary_model: str | None = None,
) -> Any:
    """
    Execute a direct asynchronous model request.

    Only provider rate-limit errors trigger another model.
    """

    configured_sequence = (
        get_model_sequence(
            primary_model
        )
    )

    available_sequence = (
        get_available_model_sequence(
            primary_model
        )
    )

    if not available_sequence:
        next_retry = (
            _next_configured_retry(
                configured_sequence
            )
        )

        raise ModelFallbackExhaustedError(
            "All configured AI models are currently "
            "rate limited. "
            "Next retry is approximately "
            f"{next_retry:.1f} seconds."
        )

    last_rate_limit_error: (
        BaseException | None
    ) = None

    client = (
        get_async_groq_client()
    )

    for index, model_name in enumerate(
        available_sequence,
        start=1,
    ):
        _log_model_attempt(
            operation_name=operation_name,
            model_name=model_name,
            position=index,
        )

        try:
            return await request_factory(
                client,
                model_name,
            )

        except Exception as exc:
            if not is_rate_limit_error(
                exc
            ):
                raise

            last_rate_limit_error = exc

            cooldown_seconds = (
                _mark_model_rate_limited(
                    model_name,
                    exc,
                )
            )

            next_model = (
                available_sequence[index]
                if index
                < len(
                    available_sequence
                )
                else None
            )

            _log_rate_limit_fallback(
                operation_name=(
                    operation_name
                ),
                model_name=model_name,
                next_model=next_model,
                cooldown_seconds=(
                    cooldown_seconds
                ),
            )

    error = ModelFallbackExhaustedError(
        "All configured AI models were rate limited "
        f"while running '{operation_name}'."
    )

    if last_rate_limit_error is not None:
        raise error from last_rate_limit_error

    raise error


def run_sync_model_call_with_fallback(
    *,
    operation_name: str,
    request_factory: Callable[
        [OpenAI, str],
        Any,
    ],
    primary_model: str | None = None,
) -> Any:
    """
    Synchronous equivalent used by services such as
    correction proposal generation.

    Only provider rate-limit errors trigger another model.
    """

    configured_sequence = (
        get_model_sequence(
            primary_model
        )
    )

    available_sequence = (
        get_available_model_sequence(
            primary_model
        )
    )

    if not available_sequence:
        next_retry = (
            _next_configured_retry(
                configured_sequence
            )
        )

        raise ModelFallbackExhaustedError(
            "All configured AI models are currently "
            "rate limited. "
            "Next retry is approximately "
            f"{next_retry:.1f} seconds."
        )

    last_rate_limit_error: (
        BaseException | None
    ) = None

    client = (
        get_sync_groq_client()
    )

    for index, model_name in enumerate(
        available_sequence,
        start=1,
    ):
        _log_model_attempt(
            operation_name=operation_name,
            model_name=model_name,
            position=index,
        )

        try:
            return request_factory(
                client,
                model_name,
            )

        except Exception as exc:
            if not is_rate_limit_error(
                exc
            ):
                raise

            last_rate_limit_error = exc

            cooldown_seconds = (
                _mark_model_rate_limited(
                    model_name,
                    exc,
                )
            )

            next_model = (
                available_sequence[index]
                if index
                < len(
                    available_sequence
                )
                else None
            )

            _log_rate_limit_fallback(
                operation_name=(
                    operation_name
                ),
                model_name=model_name,
                next_model=next_model,
                cooldown_seconds=(
                    cooldown_seconds
                ),
            )

    error = ModelFallbackExhaustedError(
        "All configured AI models were rate limited "
        f"while running '{operation_name}'."
    )

    if last_rate_limit_error is not None:
        raise error from last_rate_limit_error

    raise error


# ---------------------------------------------------------
# OPENAI AGENTS SDK FALLBACK
# ---------------------------------------------------------


async def run_agent_with_fallback(
    *,
    operation_name: str,
    agent_factory: Callable[
        [OpenAIChatCompletionsModel],
        Any,
    ],
    input_data: Any,
    max_turns: int,
    context: Any | None = None,
    reset_before_fallback: (
        Callable[[], None] | None
    ) = None,
    primary_model: str | None = None,
) -> Any:
    """
    Run an OpenAI Agents SDK agent with controlled fallback.

    The agent is rebuilt from scratch for each model.

    Another model is attempted only for:

    1. Genuine provider rate-limit/quota failures.
    2. Narrowly recognized malformed tool-protocol failures.

    Final error classification is conservative:

    - If ANY configured model is still cooling down because
      of a rate limit, the operation is considered temporarily
      blocked by provider capacity and raises
      ModelFallbackExhaustedError.

    - ModelCompatibilityFallbackExhaustedError is raised only
      when no configured model is rate-limited and the usable
      routing sequence genuinely ends in compatibility
      failures.

    This prevents mixed routes such as:

        120B -> rate limit
        20B  -> compatibility failure
        Qwen -> rate limit

    from being incorrectly recorded as a permanent model
    compatibility failure.
    """

    configured_sequence = (
        get_model_sequence(
            primary_model
        )
    )

    available_sequence = (
        get_available_model_sequence(
            primary_model
        )
    )

    if not available_sequence:
        next_retry = (
            _next_configured_retry(
                configured_sequence
            )
        )

        raise ModelFallbackExhaustedError(
            "All configured AI models are currently "
            "rate limited. "
            "Next retry is approximately "
            f"{next_retry:.1f} seconds."
        )

    last_rate_limit_error: (
        BaseException | None
    ) = None

    last_compatibility_error: (
        BaseException | None
    ) = None

    last_failure_kind: (
        str | None
    ) = None

    for index, model_name in enumerate(
        available_sequence,
        start=1,
    ):
        _log_model_attempt(
            operation_name=operation_name,
            model_name=model_name,
            position=index,
        )

        model = get_agents_model(
            model_name
        )

        agent = agent_factory(
            model
        )

        runner_kwargs: dict[
            str,
            Any,
        ] = {
            "max_turns": max_turns,
        }

        if context is not None:
            runner_kwargs[
                "context"
            ] = context

        try:
            return await Runner.run(
                agent,
                input_data,
                **runner_kwargs,
            )

        except Exception as exc:
            rate_limit_failure = (
                is_rate_limit_error(
                    exc
                )
            )

            protocol_failure = (
                is_tool_protocol_compatibility_error(
                    exc
                )
            )

            if (
                not rate_limit_failure
                and not protocol_failure
            ):
                raise

            next_model = (
                available_sequence[index]
                if index
                < len(
                    available_sequence
                )
                else None
            )

            if rate_limit_failure:
                last_failure_kind = (
                    "rate_limit"
                )

                last_rate_limit_error = (
                    exc
                )

                cooldown_seconds = (
                    _mark_model_rate_limited(
                        model_name,
                        exc,
                    )
                )

                _log_rate_limit_fallback(
                    operation_name=(
                        operation_name
                    ),
                    model_name=model_name,
                    next_model=next_model,
                    cooldown_seconds=(
                        cooldown_seconds
                    ),
                )

            else:
                last_failure_kind = (
                    "compatibility"
                )

                last_compatibility_error = (
                    exc
                )

                _log_tool_protocol_fallback(
                    operation_name=(
                        operation_name
                    ),
                    model_name=model_name,
                    next_model=next_model,
                )

            if next_model is None:
                break

            if (
                reset_before_fallback
                is not None
            ):
                reset_before_fallback()

    cooldown_waits = (
        _configured_cooldown_waits(
            configured_sequence
        )
    )

    if cooldown_waits:
        next_retry = min(
            cooldown_waits.values()
        )

        cooling_models = ", ".join(
            sorted(
                cooldown_waits
            )
        )

        error = (
            ModelFallbackExhaustedError(
                "Model routing could not complete "
                f"'{operation_name}' because one or more "
                "configured AI models are currently "
                "rate limited. "
                f"Cooling models: {cooling_models}. "
                "Next retry is approximately "
                f"{next_retry:.1f} seconds."
            )
        )

        if last_rate_limit_error is not None:
            raise error from (
                last_rate_limit_error
            )

        if last_compatibility_error is not None:
            raise error from (
                last_compatibility_error
            )

        raise error

    if (
        last_failure_kind
        == "compatibility"
        and last_compatibility_error
        is not None
    ):
        error = (
            ModelCompatibilityFallbackExhaustedError(
                "Configured agent models could not complete "
                f"'{operation_name}' because a recognized "
                "tool-protocol compatibility failure "
                "persisted after fallback."
            )
        )

        raise error from (
            last_compatibility_error
        )

    if (
        last_failure_kind
        == "rate_limit"
        and last_rate_limit_error
        is not None
    ):
        error = (
            ModelFallbackExhaustedError(
                "All configured AI models were rate limited "
                f"while running '{operation_name}'."
            )
        )

        raise error from (
            last_rate_limit_error
        )

    raise RuntimeError(
        "Model routing ended without a successful result "
        f"while running '{operation_name}'."
    )


__all__ = [
    "ModelCompatibilityFallbackExhaustedError",
    "ModelFallbackExhaustedError",
    "clear_model_cooldowns",
    "get_agents_model",
    "get_async_groq_client",
    "get_available_model_sequence",
    "get_model_sequence",
    "get_primary_model_name",
    "get_retry_after_seconds",
    "get_sync_groq_client",
    "is_rate_limit_error",
    "is_tool_protocol_compatibility_error",
    "run_agent_with_fallback",
    "run_async_model_call_with_fallback",
    "run_sync_model_call_with_fallback",
]