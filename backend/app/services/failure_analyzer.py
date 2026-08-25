from __future__ import annotations

from collections.abc import Iterable

from app.schemas.correction import (
    FailureAnalysis,
    FailureType,
)


class FailureAnalysisError(RuntimeError):
    """Raised when a verification run cannot be analyzed."""


def _detect_failure_type(
    *,
    command_type: str,
    timed_out: bool,
) -> FailureType:
    if timed_out:
        return FailureType.TIMEOUT

    normalized = command_type.lower()

    if normalized == "compileall":
        return FailureType.COMPILE_ERROR

    if normalized == "ruff":
        return FailureType.LINT_ERROR

    if normalized == "pytest":
        return FailureType.TEST_FAILURE

    return FailureType.EXECUTION_ERROR


def _build_summary(
    *,
    command_type: str,
    failure_type: FailureType,
    exit_code: int | None,
    timed_out: bool,
) -> str:
    if timed_out:
        return (
            f"{command_type} exceeded the sandbox "
            "execution timeout."
        )

    if failure_type == FailureType.COMPILE_ERROR:
        return (
            "Python compilation verification failed."
        )

    if failure_type == FailureType.LINT_ERROR:
        return "Ruff lint verification failed."

    if failure_type == FailureType.TEST_FAILURE:
        return "Pytest verification failed."

    return (
        f"{command_type} verification failed "
        f"with exit code {exit_code}."
    )


def analyze_verification_failure(
    *,
    verification_run_id,
    steps: Iterable,
) -> FailureAnalysis:
    """
    Convert verification execution history into a structured
    failure description suitable for the correction workflow.

    The first failed verification step is treated as the
    correction trigger.
    """

    failed_step = next(
        (
            step
            for step in steps
            if not step.succeeded
        ),
        None,
    )

    if failed_step is None:
        raise FailureAnalysisError(
            "Verification contains no failed step."
        )

    command_type = str(
        failed_step.command_type.value
        if hasattr(
            failed_step.command_type,
            "value",
        )
        else failed_step.command_type
    )

    failure_type = _detect_failure_type(
        command_type=command_type,
        timed_out=failed_step.timed_out,
    )

    summary = _build_summary(
        command_type=command_type,
        failure_type=failure_type,
        exit_code=failed_step.exit_code,
        timed_out=failed_step.timed_out,
    )

    return FailureAnalysis(
        verification_run_id=verification_run_id,
        failure_type=failure_type,
        failed_command=command_type,
        failed_step_position=(
            failed_step.position
        ),
        exit_code=failed_step.exit_code,
        stdout=failed_step.stdout or "",
        stderr=failed_step.stderr or "",
        timed_out=failed_step.timed_out,
        summary=summary,
    )