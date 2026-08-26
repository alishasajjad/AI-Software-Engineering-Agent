from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


class EvaluationApiError(RuntimeError):
    """Unexpected API response during evaluation."""

    def __init__(
        self,
        *,
        status_code: int,
        method: str,
        path: str,
        body: str,
    ) -> None:
        self.status_code = status_code
        self.method = method
        self.path = path
        self.body = body

        super().__init__(
            f"{method} {path} returned "
            f"HTTP {status_code}: {body}"
        )


class EvaluationRateLimitError(
    EvaluationApiError
):
    """
    Upstream model-provider rate limit.

    The FastAPI layer may expose a provider 429 as an outer
    HTTP 502.

    The backend model router may also exhaust all configured
    fallback models and return a wrapped rate-limit message.

    Detection therefore inspects both the HTTP status code
    and the response body.
    """

    def __init__(
        self,
        *,
        status_code: int,
        method: str,
        path: str,
        body: str,
        retry_after_seconds: float | None,
    ) -> None:
        self.retry_after_seconds = (
            retry_after_seconds
        )

        super().__init__(
            status_code=status_code,
            method=method,
            path=path,
            body=body,
        )


def _parse_retry_after_seconds(
    body: str,
) -> float | None:
    """
    Parse provider messages such as:

    try again in 13m30s
    try again in 7m32.304s
    try again in 3m35.136s
    try again in 45s

    If the model router reports a rate limit but the provider
    does not expose an exact retry duration, None is returned.
    The evaluation runner can then use its configured/default
    wait behavior.
    """

    match = re.search(
        r"try again in\s+"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
        r"(?P<seconds>\d+(?:\.\d+)?)?s?",
        body,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    minutes_text = match.group(
        "minutes"
    )

    seconds_text = match.group(
        "seconds"
    )

    if (
        minutes_text is None
        and seconds_text is None
    ):
        return None

    minutes = (
        float(minutes_text)
        if minutes_text
        else 0.0
    )

    seconds = (
        float(seconds_text)
        if seconds_text
        else 0.0
    )

    total_seconds = (
        minutes * 60.0
        + seconds
    )

    if total_seconds <= 0:
        return None

    return total_seconds


def _is_rate_limit_response(
    *,
    status_code: int,
    body: str,
) -> bool:
    """
    Determine whether an API failure represents model-provider
    quota/rate exhaustion.

    This covers:

    1. Direct HTTP 429 responses.
    2. Groq rate-limit errors wrapped by FastAPI as HTTP 502.
    3. The central model router exhausting all configured
       fallback models.

    Normal application failures, JSON errors, validation
    failures and agent-quality failures must not be classified
    as rate limits.
    """

    if status_code == 429:
        return True

    normalized = (
        body.lower()
    )

    indicators = (
        # Groq/provider messages.
        "rate limit reached",
        "rate_limit_exceeded",
        "tokens per day",
        "tokens per minute",
        "requests per day",
        "requests per minute",
        "daily token limit",
        "daily request limit",
        "quota exceeded",
        "too many requests",

        # Central model-router messages.
        "all configured ai models are currently rate limited",
        "all configured ai models were rate limited",
        "all configured ai models are rate limited",
    )

    return any(
        indicator in normalized
        for indicator in indicators
    )


class EvaluationApiClient:
    """HTTP client for the Phase 10 black-box evaluation."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 240.0,
    ) -> None:
        self.base_url = (
            base_url.rstrip("/")
        )

        self.timeout_seconds = (
            timeout_seconds
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: (
            dict[str, Any]
            | list[Any]
            | None
        ) = None,
    ) -> Any:
        url = (
            f"{self.base_url}/"
            f"{path.lstrip('/')}"
        )

        data: bytes | None = None

        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "AI-Software-Agent-"
                "Evaluation/1.0"
            ),
        }

        if method.upper() in {
            "POST",
            "PUT",
            "PATCH",
        }:
            if payload is None:
                payload = {}

            data = json.dumps(
                payload
            ).encode(
                "utf-8"
            )

            headers[
                "Content-Type"
            ] = "application/json"

        request = urllib.request.Request(
            url=url,
            data=data,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=(
                    self.timeout_seconds
                ),
            ) as response:
                body_bytes = (
                    response.read()
                )

                if not body_bytes:
                    return None

                body = body_bytes.decode(
                    "utf-8"
                )

                return json.loads(
                    body
                )

        except urllib.error.HTTPError as exc:
            body = (
                exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            )

            if _is_rate_limit_response(
                status_code=exc.code,
                body=body,
            ):
                raise EvaluationRateLimitError(
                    status_code=exc.code,
                    method=method.upper(),
                    path=path,
                    body=body,
                    retry_after_seconds=(
                        _parse_retry_after_seconds(
                            body
                        )
                    ),
                ) from exc

            raise EvaluationApiError(
                status_code=exc.code,
                method=method.upper(),
                path=path,
                body=body,
            ) from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Unable to connect to "
                f"the evaluation API at {url}: "
                f"{exc}"
            ) from exc

    def create_task(
        self,
        *,
        title: str,
        description: str,
        repository_path: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/tasks",
            payload={
                "title": title,
                "description": description,
                "repository_path": (
                    repository_path
                ),
            },
        )

    def generate_plan(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=f"/tasks/{task_id}/plan",
        )

    def prepare_patches(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                "/patches/prepare"
            ),
        )

    def list_patches(
        self,
        task_id: str,
    ) -> list[dict[str, Any]]:
        return self._request(
            method="GET",
            path=(
                f"/tasks/{task_id}"
                "/patches"
            ),
        )

    def approve_patch(
        self,
        *,
        task_id: str,
        patch_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/patches/{patch_id}"
                "/approve"
            ),
        )

    def reject_patch(
        self,
        *,
        task_id: str,
        patch_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/patches/{patch_id}"
                "/reject"
            ),
        )

    def apply_patch(
        self,
        *,
        task_id: str,
        patch_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/patches/{patch_id}"
                "/apply"
            ),
        )

    def verify_task(
        self,
        task_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                "/verifications"
            ),
            payload={},
        )

    def analyze_failure(
        self,
        *,
        task_id: str,
        verification_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/verifications/"
                f"{verification_id}"
                "/corrections/analyze"
            ),
        )

    def propose_correction(
        self,
        *,
        task_id: str,
        verification_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/verifications/"
                f"{verification_id}"
                "/corrections/propose"
            ),
        )

    def prepare_correction_patches(
        self,
        *,
        task_id: str,
        verification_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/verifications/"
                f"{verification_id}"
                "/corrections/patches/prepare"
            ),
        )

    def advance_correction(
        self,
        *,
        task_id: str,
        verification_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="POST",
            path=(
                f"/tasks/{task_id}"
                f"/verifications/"
                f"{verification_id}"
                "/corrections/advance"
            ),
        )

    def correction_status(
        self,
        *,
        task_id: str,
        verification_id: str,
    ) -> dict[str, Any]:
        return self._request(
            method="GET",
            path=(
                f"/tasks/{task_id}"
                f"/verifications/"
                f"{verification_id}"
                "/corrections/status"
            ),
        )


__all__ = [
    "EvaluationApiClient",
    "EvaluationApiError",
    "EvaluationRateLimitError",
]