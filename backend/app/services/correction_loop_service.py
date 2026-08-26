from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.correction import (
    SelfCorrectionPatchRecord,
    SelfCorrectionSession,
)
from app.models.pending_patch import (
    PendingPatchRecord,
)
from app.schemas.correction_loop import (
    CorrectionLoopNextAction,
    CorrectionLoopPatchRead,
    CorrectionLoopResponse,
    CorrectionLoopSessionRead,
)
from app.services.correction_patch_service import (
    create_correction_patches,
)
from app.services.correction_reverification_service import (
    reverify_correction,
)
from app.services.correction_service import (
    CorrectionSessionNotFoundError,
    create_correction_proposal,
)
from app.services.verification_service import (
    get_verification_run as get_verification_run_service,
)

MAX_AUTOMATIC_TRANSITIONS_PER_REQUEST = 6


class CorrectionLoopError(RuntimeError):
    """Base self-correction loop error."""


class CorrectionLoopStateError(
    CorrectionLoopError
):
    """
    Raised when persisted correction state cannot be advanced
    safely.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class CorrectionLoopClassification:
    terminal: bool

    safe_stopped: bool

    requires_human_action: bool

    next_action: CorrectionLoopNextAction

    stop_reason: str | None

    message: str


def classify_correction_status(
    status: str,
) -> CorrectionLoopClassification:
    """
    Convert a persisted correction session state into the
    next safe workflow action.

    No repository mutation happens here.
    """

    if status == "analysis_ready":
        return CorrectionLoopClassification(
            terminal=False,
            safe_stopped=False,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction
                .GENERATE_PROPOSAL
            ),
            stop_reason=None,
            message=(
                "Failure analysis is ready. "
                "The correction proposal can "
                "be generated automatically."
            ),
        )

    if status == "proposal_ready":
        return CorrectionLoopClassification(
            terminal=False,
            safe_stopped=False,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction
                .PREPARE_PATCHES
            ),
            stop_reason=None,
            message=(
                "The correction proposal is ready. "
                "Safe pending patches can be prepared."
            ),
        )

    if status == "patch_ready":
        return CorrectionLoopClassification(
            terminal=False,
            safe_stopped=False,
            requires_human_action=True,
            next_action=(
                CorrectionLoopNextAction
                .REVIEW_PATCHES
            ),
            stop_reason=None,
            message=(
                "Correction patches are pending. "
                "Human approval or rejection is required."
            ),
        )

    if status == "patches_approved":
        return CorrectionLoopClassification(
            terminal=False,
            safe_stopped=False,
            requires_human_action=True,
            next_action=(
                CorrectionLoopNextAction
                .APPLY_APPROVED_PATCHES
            ),
            stop_reason=None,
            message=(
                "Correction patches are approved. "
                "Explicit patch application is required "
                "before automated verification."
            ),
        )

    if status == "patches_applied":
        return CorrectionLoopClassification(
            terminal=False,
            safe_stopped=False,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction
                .REVERIFY
            ),
            stop_reason=None,
            message=(
                "Correction patches have been applied. "
                "Automated re-verification can run."
            ),
        )

    if status == "completed":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=False,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=None,
            message=(
                "The self-correction workflow "
                "completed successfully."
            ),
        )

    if status == "exhausted":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "maximum_attempts_reached"
            ),
            message=(
                "The maximum self-correction "
                "attempt count was reached. "
                "The workflow stopped safely."
            ),
        )

    if status == "verification_error":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "verification_execution_error"
            ),
            message=(
                "Automated verification ended "
                "in an error state. "
                "No further automatic correction "
                "was attempted."
            ),
        )

    if status == "analysis_error":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "failure_analysis_error"
            ),
            message=(
                "The new verification failure "
                "could not be analyzed safely. "
                "Automatic correction stopped."
            ),
        )

    if status == "patch_rejected":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "patch_rejected_by_human"
            ),
            message=(
                "A correction patch was rejected. "
                "The automatic correction cycle stopped."
            ),
        )

    if status == "patch_stale":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "patch_became_stale"
            ),
            message=(
                "A correction patch became stale "
                "before application. "
                "The workflow stopped safely."
            ),
        )

    if status == "retry_created":
        return CorrectionLoopClassification(
            terminal=True,
            safe_stopped=True,
            requires_human_action=False,
            next_action=(
                CorrectionLoopNextAction.NONE
            ),
            stop_reason=(
                "retry_session_missing"
            ),
            message=(
                "The previous correction attempt "
                "created a retry state but no active "
                "child session could be resolved."
            ),
        )

    return CorrectionLoopClassification(
        terminal=True,
        safe_stopped=True,
        requires_human_action=False,
        next_action=(
            CorrectionLoopNextAction.NONE
        ),
        stop_reason=(
            f"unsupported_state:{status}"
        ),
        message=(
            "The correction workflow entered "
            f"unsupported state '{status}'. "
            "Automatic execution stopped safely."
        ),
    )


def _get_session_by_source_verification(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> SelfCorrectionSession:
    statement = select(
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

    session = db.scalar(
        statement
    )

    if session is None:
        raise CorrectionSessionNotFoundError(
            "Self-correction session not found "
            "for this verification run."
        )

    return session


def _get_children(
    *,
    db: Session,
    session_id: uuid.UUID,
) -> list[SelfCorrectionSession]:
    statement = (
        select(
            SelfCorrectionSession
        )
        .where(
            SelfCorrectionSession.parent_session_id
            == session_id
        )
        .order_by(
            SelfCorrectionSession.created_at.asc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


def _get_leaf_session(
    *,
    db: Session,
    initial_session: SelfCorrectionSession,
) -> SelfCorrectionSession:
    """
    Follow retry lineage until the newest active session.

    More than one child would indicate ambiguous workflow
    history, so automatic execution stops rather than guessing.
    """

    current = initial_session

    visited: set[uuid.UUID] = set()

    while True:
        if current.id in visited:
            raise CorrectionLoopStateError(
                "A cycle was detected in self-correction "
                "session lineage."
            )

        visited.add(
            current.id
        )

        children = _get_children(
            db=db,
            session_id=current.id,
        )

        if not children:
            return current

        if len(children) > 1:
            raise CorrectionLoopStateError(
                "Multiple retry sessions exist for one "
                "correction attempt. Automatic execution "
                "cannot safely choose a branch."
            )

        current = children[0]


def _build_chain_from_leaf(
    *,
    db: Session,
    leaf_session: SelfCorrectionSession,
) -> list[SelfCorrectionSession]:
    chain: list[
        SelfCorrectionSession
    ] = []

    current = leaf_session

    visited: set[uuid.UUID] = set()

    while True:
        if current.id in visited:
            raise CorrectionLoopStateError(
                "A cycle was detected while building "
                "correction lineage."
            )

        visited.add(
            current.id
        )

        chain.append(
            current
        )

        if current.parent_session_id is None:
            break

        parent = db.get(
            SelfCorrectionSession,
            current.parent_session_id,
        )

        if parent is None:
            raise CorrectionLoopStateError(
                "Correction session lineage references "
                "a missing parent session."
            )

        current = parent

    chain.reverse()

    return chain


def _get_patch_summaries(
    *,
    db: Session,
    session_id: uuid.UUID,
) -> list[CorrectionLoopPatchRead]:
    statement = (
        select(
            PendingPatchRecord
        )
        .join(
            SelfCorrectionPatchRecord,
            (
                SelfCorrectionPatchRecord
                .pending_patch_id
                == PendingPatchRecord.id
            ),
        )
        .where(
            SelfCorrectionPatchRecord.session_id
            == session_id
        )
        .order_by(
            SelfCorrectionPatchRecord.position.asc()
        )
    )

    records = list(
        db.scalars(
            statement
        ).all()
    )

    return [
        CorrectionLoopPatchRead(
            id=record.id,
            path=record.path,
            status=record.status,
        )
        for record in records
    ]


def _build_loop_response(
    *,
    db: Session,
    initial_session: SelfCorrectionSession,
) -> CorrectionLoopResponse:
    leaf_session = _get_leaf_session(
        db=db,
        initial_session=initial_session,
    )

    chain = _build_chain_from_leaf(
        db=db,
        leaf_session=leaf_session,
    )

    classification = (
        classify_correction_status(
            leaf_session.status
        )
    )

    remaining_attempts = max(
        (
            leaf_session.max_attempts
            - leaf_session.current_attempt
        ),
        0,
    )

    return CorrectionLoopResponse(
        root_session_id=(
            chain[0].id
        ),
        active_session=(
            CorrectionLoopSessionRead.model_validate(
                leaf_session
            )
        ),
        chain=[
            CorrectionLoopSessionRead.model_validate(
                session
            )
            for session in chain
        ],
        terminal=(
            classification.terminal
        ),
        safe_stopped=(
            classification.safe_stopped
        ),
        requires_human_action=(
            classification.requires_human_action
        ),
        next_action=(
            classification.next_action
        ),
        remaining_attempts=(
            remaining_attempts
        ),
        stop_reason=(
            classification.stop_reason
        ),
        message=(
            classification.message
        ),
        patches=_get_patch_summaries(
            db=db,
            session_id=leaf_session.id,
        ),
    )


def get_correction_loop_status(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> CorrectionLoopResponse:
    """
    Return the latest state of a complete correction lineage.

    The caller can provide the original failed verification id
    even after retry child sessions have been created.
    """

    initial_session = (
        _get_session_by_source_verification(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_run_id
            ),
        )
    )

    return _build_loop_response(
        db=db,
        initial_session=initial_session,
    )


async def advance_correction_loop(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> CorrectionLoopResponse:
    """
    Advance automatic parts of the self-correction workflow.

    The function intentionally stops at every human approval
    or explicit application gate.

    It never approves or applies patches automatically.
    """

    initial_session = (
        _get_session_by_source_verification(
            db=db,
            task_id=task_id,
            verification_run_id=(
                verification_run_id
            ),
        )
    )

    initial_session_id = (
        initial_session.id
    )

    for _ in range(
        MAX_AUTOMATIC_TRANSITIONS_PER_REQUEST
    ):
        initial_session = db.get(
            SelfCorrectionSession,
            initial_session_id,
        )

        if initial_session is None:
            raise CorrectionLoopStateError(
                "The correction session disappeared "
                "while advancing the workflow."
            )

        active_session = (
            _get_leaf_session(
                db=db,
                initial_session=(
                    initial_session
                ),
            )
        )

        classification = (
            classify_correction_status(
                active_session.status
            )
        )

        # Terminal states and human gates must never be
        # crossed automatically.
        if (
            classification.terminal
            or
            classification.requires_human_action
        ):
            return _build_loop_response(
                db=db,
                initial_session=(
                    initial_session
                ),
            )

        source_verification = (
            get_verification_run_service(
                db=db,
                task_id=task_id,
                verification_id=(
                    active_session
                    .source_verification_run_id
                ),
            )
        )

        if source_verification is None:
            raise CorrectionLoopStateError(
                "The correction session references "
                "a missing verification run."
            )

        if (
            classification.next_action
            == CorrectionLoopNextAction
            .GENERATE_PROPOSAL
        ):
            create_correction_proposal(
                db=db,
                task_id=task_id,
                verification_run=(
                    source_verification
                ),
            )

            db.expire_all()

            continue

        if (
            classification.next_action
            == CorrectionLoopNextAction
            .PREPARE_PATCHES
        ):
            await create_correction_patches(
                db=db,
                task_id=task_id,
                verification_run=(
                    source_verification
                ),
            )

            db.expire_all()

            continue

        if (
            classification.next_action
            == CorrectionLoopNextAction
            .REVERIFY
        ):
            reverify_correction(
                db=db,
                task_id=task_id,
                source_verification=(
                    source_verification
                ),
            )

            db.expire_all()

            continue

        raise CorrectionLoopStateError(
            "The correction loop resolved an "
            "automatic state without a supported "
            "automatic action."
        )

    raise CorrectionLoopStateError(
        "The automatic correction transition "
        "budget was reached. Execution stopped "
        "to prevent an unbounded loop."
    )


__all__ = [
    "CorrectionLoopError",
    "CorrectionLoopStateError",
    "MAX_AUTOMATIC_TRANSITIONS_PER_REQUEST",
    "advance_correction_loop",
    "classify_correction_status",
    "get_correction_loop_status",
]