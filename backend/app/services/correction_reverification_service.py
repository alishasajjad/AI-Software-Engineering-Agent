from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.correction import (
    SelfCorrectionSession,
)
from app.schemas.correction_proposal import (
    CorrectionProposal,
)
from app.schemas.correction_reverification import (
    CorrectionReverificationResponse,
)
from app.schemas.verification import (
    VerificationRunResponse,
)
from app.services.correction_service import (
    CorrectionSessionNotFoundError,
    InvalidCorrectionSessionStateError,
)
from app.services.failure_analyzer import (
    FailureAnalysisError,
    analyze_verification_failure,
)
from app.services.verification_service import (
    verify_task as verify_task_service,
)


class CorrectionReverificationError(
    RuntimeError
):
    """Base error for correction re-verification."""


class CorrectionAttemptLimitError(
    CorrectionReverificationError
):
    """Maximum self-correction attempts were reached."""


def _status_value(
    value: object,
) -> str:
    if hasattr(
        value,
        "value",
    ):
        return str(
            value.value
        )

    return str(value)


def determine_reverification_transition(
    *,
    verification_status: str,
    attempt: int,
    max_attempts: int,
) -> str:
    """
    Decide the next self-correction lifecycle state.

    Returned values:

    completed
        Verification passed.

    retry
        Verification failed but attempts remain.

    exhausted
        Verification failed and attempt budget is exhausted.

    verification_error
        Verification infrastructure returned an error state.
    """

    if verification_status == "passed":
        return "completed"

    if verification_status == "failed":
        if attempt >= max_attempts:
            return "exhausted"

        return "retry"

    return "verification_error"


def _normalize_targets(
    values: Iterable[str],
) -> list[str]:
    targets: list[str] = []

    for value in values:
        normalized = value.strip()

        if (
            normalized
            and normalized not in targets
        ):
            targets.append(
                normalized
            )

    return targets


def _extract_pytest_targets_from_steps(
    steps: Iterable[object],
) -> list[str]:
    """
    Recover pytest targets from a previous verification command.

    This is a fallback when the correction proposal did not
    explicitly specify pytest_targets.
    """

    for step in steps:
        command_type = _status_value(
            getattr(
                step,
                "command_type",
                "",
            )
        )

        if command_type != "pytest":
            continue

        raw_command = getattr(
            step,
            "command",
            [],
        )

        if not isinstance(
            raw_command,
            (list, tuple),
        ):
            continue

        command = [
            str(item)
            for item in raw_command
        ]

        pytest_index: int | None = None

        for index, token in enumerate(
            command
        ):
            normalized_token = (
                token.lower()
                .replace("\\", "/")
            )

            if (
                normalized_token == "pytest"
                or normalized_token.endswith(
                    "/pytest"
                )
                or normalized_token.endswith(
                    "/pytest.exe"
                )
            ):
                pytest_index = index
                break

        if pytest_index is None:
            continue

        candidates = command[
            pytest_index + 1:
        ]

        targets: list[str] = []

        for candidate in candidates:
            normalized = (
                candidate.strip()
            )

            if not normalized:
                continue

            if normalized.startswith("-"):
                continue

            if (
                ".py" not in normalized
                and "::" not in normalized
            ):
                continue

            if normalized not in targets:
                targets.append(
                    normalized
                )

        if targets:
            return targets

    return []


def _resolve_pytest_targets(
    *,
    session: SelfCorrectionSession,
    source_verification: VerificationRunResponse,
) -> list[str]:
    """
    Prefer targets stored in the AI proposal.

    If none are available, recover targets from the original
    verification command. An empty list means the verification
    service can run its configured/default pytest scope.
    """

    if (
        session.proposal_json
        is not None
    ):
        try:
            proposal = (
                CorrectionProposal.model_validate(
                    session.proposal_json
                )
            )

        except Exception as exc:
            raise (
                CorrectionReverificationError(
                    "The stored correction "
                    "proposal is invalid."
                )
            ) from exc

        proposal_targets = (
            _normalize_targets(
                proposal.pytest_targets
            )
        )

        if proposal_targets:
            return proposal_targets

    return _extract_pytest_targets_from_steps(
        source_verification.steps
    )


def _get_correction_session(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> SelfCorrectionSession | None:
    statement = (
        select(
            SelfCorrectionSession
        )
        .where(
            SelfCorrectionSession.task_id
            == task_id,
            (
                SelfCorrectionSession
                .source_verification_run_id
                == verification_run_id
            ),
        )
        .with_for_update()
    )

    return db.scalar(
        statement
    )


def _create_retry_session(
    *,
    db: Session,
    parent_session: SelfCorrectionSession,
    verification_run: VerificationRunResponse,
    attempt: int,
) -> SelfCorrectionSession:
    """
    Create a fresh correction session for a newly failed
    verification.

    Previous proposals and patches remain immutable history.
    """

    analysis = (
        analyze_verification_failure(
            verification_run_id=(
                verification_run.id
            ),
            steps=verification_run.steps,
        )
    )

    retry_session = SelfCorrectionSession(
        task_id=(
            parent_session.task_id
        ),
        source_verification_run_id=(
            verification_run.id
        ),
        parent_session_id=(
            parent_session.id
        ),
        last_verification_run_id=None,
        status="analysis_ready",
        current_attempt=attempt,
        max_attempts=(
            parent_session.max_attempts
        ),
        failure_type=(
            analysis.failure_type.value
        ),
        failure_summary=(
            analysis.summary
        ),
        proposal_json=None,
        proposal_generated_at=None,
        completed_at=None,
    )

    db.add(
        retry_session
    )

    db.flush()

    return retry_session


def reverify_correction(
    *,
    db: Session,
    task_id: uuid.UUID,
    source_verification: VerificationRunResponse,
) -> CorrectionReverificationResponse:
    """
    Run automated verification after correction patches have
    been applied.

    Passed:
        Complete the correction session.

    Failed with attempts remaining:
        Create a child correction session already containing
        failure analysis.

    Failed at max attempts:
        Mark the workflow exhausted and stop safely.

    Error:
        Stop safely without starting another correction cycle.
    """

    if (
        source_verification.task_id
        != task_id
    ):
        raise LookupError(
            "Verification run was not "
            "found for this task."
        )

    session = _get_correction_session(
        db=db,
        task_id=task_id,
        verification_run_id=(
            source_verification.id
        ),
    )

    if session is None:
        raise CorrectionSessionNotFoundError(
            "Self-correction session "
            "not found."
        )

    if (
        session.status
        != "patches_applied"
    ):
        raise InvalidCorrectionSessionStateError(
            "Correction patches must be "
            "applied before re-verification. "
            f"Current session status is "
            f"'{session.status}'."
        )

    if (
        session.current_attempt
        >= session.max_attempts
    ):
        raise CorrectionAttemptLimitError(
            "The maximum self-correction "
            "attempt count has already "
            "been reached."
        )

    pytest_targets = (
        _resolve_pytest_targets(
            session=session,
            source_verification=(
                source_verification
            ),
        )
    )

    try:
        verification = (
            verify_task_service(
                db=db,
                task_id=task_id,
                pytest_targets=(
                    pytest_targets
                ),
            )
        )

    except (LookupError, ValueError):
        raise

    except Exception as exc:
        raise (
            CorrectionReverificationError(
                "Automated correction "
                "re-verification could "
                "not be completed."
            )
        ) from exc

    next_attempt = (
        session.current_attempt + 1
    )

    verification_status = (
        _status_value(
            verification.status
        )
    )

    transition = (
        determine_reverification_transition(
            verification_status=(
                verification_status
            ),
            attempt=next_attempt,
            max_attempts=(
                session.max_attempts
            ),
        )
    )

    now = datetime.now(UTC)

    session.current_attempt = (
        next_attempt
    )

    session.last_verification_run_id = (
        verification.id
    )

    session.updated_at = now

    retry_session: (
        SelfCorrectionSession | None
    ) = None

    if transition == "completed":
        session.status = "completed"
        session.completed_at = now

        message = (
            "Correction verification "
            "passed successfully. "
            "The self-correction workflow "
            "is complete."
        )

    elif transition == "exhausted":
        try:
            analysis = (
                analyze_verification_failure(
                    verification_run_id=(
                        verification.id
                    ),
                    steps=(
                        verification.steps
                    ),
                )
            )

            session.failure_type = (
                analysis.failure_type.value
            )

            session.failure_summary = (
                analysis.summary
            )

        except FailureAnalysisError:
            pass

        session.status = "exhausted"
        session.completed_at = now

        message = (
            "Correction verification "
            "failed and the maximum "
            "attempt count has been "
            "reached. The workflow "
            "stopped safely."
        )

    elif transition == "retry":
        try:
            retry_session = (
                _create_retry_session(
                    db=db,
                    parent_session=session,
                    verification_run=(
                        verification
                    ),
                    attempt=next_attempt,
                )
            )

        except FailureAnalysisError as exc:
            session.status = (
                "analysis_error"
            )

            session.completed_at = now

            try:
                db.commit()
                db.refresh(
                    session
                )

            except Exception:
                db.rollback()
                raise

            raise (
                CorrectionReverificationError(
                    "Re-verification failed, "
                    "but the new failure "
                    "could not be analyzed "
                    "for another correction "
                    "attempt."
                )
            ) from exc

        session.status = "retry_created"
        session.completed_at = now

        message = (
            "Correction verification "
            "failed. A new analyzed "
            "self-correction session "
            "was created for the next "
            "attempt."
        )

    else:
        session.status = (
            "verification_error"
        )

        session.completed_at = now

        message = (
            "Automated verification "
            "ended in an error state. "
            "No automatic retry session "
            "was created."
        )

    try:
        db.commit()

        db.refresh(
            session
        )

        if retry_session is not None:
            db.refresh(
                retry_session
            )

    except Exception:
        db.rollback()
        raise

    remaining_attempts = max(
        (
            session.max_attempts
            - next_attempt
        ),
        0,
    )

    return CorrectionReverificationResponse(
        session_id=session.id,
        retry_session_id=(
            retry_session.id
            if retry_session is not None
            else None
        ),
        status=session.status,
        current_attempt=(
            session.current_attempt
        ),
        max_attempts=(
            session.max_attempts
        ),
        remaining_attempts=(
            remaining_attempts
        ),
        verification=verification,
        message=message,
    )


__all__ = [
    "CorrectionAttemptLimitError",
    "CorrectionReverificationError",
    "determine_reverification_transition",
    "reverify_correction",
]