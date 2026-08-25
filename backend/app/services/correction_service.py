from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.models.correction import (
    SelfCorrectionSession,
)
from app.schemas.correction import (
    FailureAnalysisResponse,
)
from app.schemas.correction_proposal import (
    CorrectionProposal,
    CorrectionProposalResponse,
)
from app.schemas.verification import (
    VerificationRunResponse,
)
from app.services.correction_proposal_generator import (
    CorrectionProposalGenerationError,
    collect_correction_context,
    generate_correction_proposal,
)
from app.services.failure_analyzer import (
    analyze_verification_failure,
)
from app.tools.repository import (
    SecureWorkspace,
)

MAX_CORRECTION_ATTEMPTS = 3


class CorrectionSessionError(
    RuntimeError
):
    """Base self-correction workflow error."""


class InvalidVerificationStateError(
    CorrectionSessionError
):
    """Verification is not eligible for correction."""


class ExistingCorrectionSessionError(
    CorrectionSessionError
):
    """Correction session already exists."""


class CorrectionSessionNotFoundError(
    CorrectionSessionError
):
    """Correction analysis must be created first."""


class InvalidCorrectionSessionStateError(
    CorrectionSessionError
):
    """Correction session is not ready for this operation."""


def _verification_status(
    verification_run: VerificationRunResponse,
) -> str:
    status_value = verification_run.status

    if hasattr(
        status_value,
        "value",
    ):
        return str(
            status_value.value
        )

    return str(
        status_value
    )


def _get_correction_session(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> SelfCorrectionSession | None:
    return db.scalar(
        select(
            SelfCorrectionSession
        ).where(
            SelfCorrectionSession.task_id
            == task_id,
            (
                SelfCorrectionSession
                .source_verification_run_id
                == verification_run_id
            ),
        )
    )


def create_failure_analysis(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run: VerificationRunResponse,
) -> FailureAnalysisResponse:
    if (
        verification_run.task_id
        != task_id
    ):
        raise LookupError(
            "Verification run was not "
            "found for this task."
        )

    status_value = (
        _verification_status(
            verification_run
        )
    )

    if status_value != "failed":
        raise InvalidVerificationStateError(
            "Only a failed verification run "
            "can start a self-correction session."
        )

    existing_session = (
        _get_correction_session(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_run.id
            ),
        )
    )

    if (
        existing_session
        is not None
    ):
        raise ExistingCorrectionSessionError(
            "A self-correction session "
            "already exists for this "
            "verification run."
        )

    analysis = (
        analyze_verification_failure(
            verification_run_id=(
                verification_run.id
            ),
            steps=verification_run.steps,
        )
    )

    session = SelfCorrectionSession(
        task_id=task_id,
        source_verification_run_id=(
            verification_run.id
        ),
        status="analysis_ready",
        current_attempt=0,
        max_attempts=(
            MAX_CORRECTION_ATTEMPTS
        ),
        failure_type=(
            analysis.failure_type.value
        ),
        failure_summary=(
            analysis.summary
        ),
    )

    db.add(
        session
    )

    db.commit()

    db.refresh(
        session
    )

    return FailureAnalysisResponse(
        session=session,
        analysis=analysis,
    )


def create_correction_proposal(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run: VerificationRunResponse,
) -> CorrectionProposalResponse:
    """
    Generate and persist an AI correction proposal.

    Repository files are inspected but never modified.
    """

    if (
        verification_run.task_id
        != task_id
    ):
        raise LookupError(
            "Verification run was not "
            "found for this task."
        )

    if (
        _verification_status(
            verification_run
        )
        != "failed"
    ):
        raise InvalidVerificationStateError(
            "Only a failed verification "
            "run can generate a "
            "correction proposal."
        )

    session = (
        _get_correction_session(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_run.id
            ),
        )
    )

    if session is None:
        raise CorrectionSessionNotFoundError(
            "Failure analysis must be "
            "created before generating "
            "a correction proposal."
        )

    if (
        session.proposal_json
        is not None
    ):
        proposal = (
            CorrectionProposal.model_validate(
                session.proposal_json
            )
        )

        return CorrectionProposalResponse(
            session_id=session.id,
            source_verification_run_id=(
                session
                .source_verification_run_id
            ),
            status=session.status,
            proposal=proposal,
        )

    if (
        session.status
        != "analysis_ready"
    ):
        raise InvalidCorrectionSessionStateError(
            "Correction session is not "
            "ready for proposal generation. "
            f"Current status is "
            f"'{session.status}'."
        )

    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    analysis = (
        analyze_verification_failure(
            verification_run_id=(
                verification_run.id
            ),
            steps=verification_run.steps,
        )
    )

    workspace = SecureWorkspace(
        Path(
            task.repository_path
        )
    )

    repository_context = (
        collect_correction_context(
            workspace=workspace,
            stdout=analysis.stdout,
            stderr=analysis.stderr,
        )
    )

    proposal = (
        generate_correction_proposal(
            task_title=task.title,
            task_description=(
                task.description
            ),
            failure_type=(
                analysis
                .failure_type
                .value
            ),
            failure_summary=(
                analysis.summary
            ),
            failed_command=(
                analysis.failed_command
            ),
            stdout=analysis.stdout,
            stderr=analysis.stderr,
            repository_context=(
                repository_context
            ),
        )
    )

    session.proposal_json = (
        proposal.model_dump(
            mode="json"
        )
    )

    session.proposal_generated_at = (
        datetime.now(
            UTC
        )
    )

    session.status = (
        "proposal_ready"
    )

    db.add(
        session
    )

    db.commit()

    db.refresh(
        session
    )

    return CorrectionProposalResponse(
        session_id=session.id,
        source_verification_run_id=(
            session
            .source_verification_run_id
        ),
        status=session.status,
        proposal=proposal,
    )


__all__ = [
    "CorrectionProposalGenerationError",
    "CorrectionSessionNotFoundError",
    "ExistingCorrectionSessionError",
    "InvalidCorrectionSessionStateError",
    "InvalidVerificationStateError",
    "create_correction_proposal",
    "create_failure_analysis",
]