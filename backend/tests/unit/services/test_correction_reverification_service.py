from types import SimpleNamespace

from app.services.correction_reverification_service import (
    _extract_pytest_targets_from_steps,
    determine_reverification_transition,
)


def test_passed_verification_completes_workflow() -> None:
    result = determine_reverification_transition(
        verification_status="passed",
        attempt=1,
        max_attempts=3,
    )

    assert result == "completed"


def test_failed_verification_creates_retry_when_attempts_remain() -> None:
    result = determine_reverification_transition(
        verification_status="failed",
        attempt=1,
        max_attempts=3,
    )

    assert result == "retry"


def test_failed_verification_exhausts_final_attempt() -> None:
    result = determine_reverification_transition(
        verification_status="failed",
        attempt=3,
        max_attempts=3,
    )

    assert result == "exhausted"


def test_verification_error_stops_safely() -> None:
    result = determine_reverification_transition(
        verification_status="error",
        attempt=1,
        max_attempts=3,
    )

    assert result == "verification_error"


def test_extracts_pytest_target_from_verification_command() -> None:
    step = SimpleNamespace(
        command_type="pytest",
        command=[
            "python",
            "-m",
            "pytest",
            "test_sample.py",
        ],
    )

    result = (
        _extract_pytest_targets_from_steps(
            [step]
        )
    )

    assert result == [
        "test_sample.py"
    ]