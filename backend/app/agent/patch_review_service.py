import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.correction import (
    SelfCorrectionPatchRecord,
    SelfCorrectionSession,
)
from app.models.pending_patch import PendingPatchRecord
from app.models.task import Task
from app.schemas.patch import (
    PatchActionResponse,
    PendingPatchRead,
    PendingPatchStatus,
)
from app.tools.patch import (
    PatchError,
    SafePatchEngine,
    StalePatchError,
)
from app.tools.repository import SecureWorkspace


class PatchReviewError(RuntimeError):
    """Base error for patch review operations."""


class PatchNotFoundError(PatchReviewError):
    """Raised when a patch does not exist for a task."""


class PatchStateConflictError(PatchReviewError):
    """Raised when the requested status transition is invalid."""


class PatchStaleConflictError(PatchReviewError):
    """Raised when an approved patch has become stale."""


class PatchApplicationError(PatchReviewError):
    """Raised when an approved patch cannot be safely applied."""


def _get_task(
    db: Session,
    task_id: uuid.UUID,
) -> Task:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    return task


def _get_patch_for_update(
    db: Session,
    *,
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
) -> PendingPatchRecord:
    statement = (
        select(PendingPatchRecord)
        .where(
            PendingPatchRecord.id
            == patch_id,
            PendingPatchRecord.task_id
            == task_id,
        )
        .with_for_update()
    )

    patch = db.scalar(
        statement
    )

    if patch is None:
        raise PatchNotFoundError(
            "Patch not found for this task."
        )

    return patch


def _sync_correction_session_status(
    db: Session,
    *,
    patch_id: uuid.UUID,
) -> None:
    """
    Synchronize the self-correction session linked to a patch.

    Pending ORM changes are explicitly flushed before reading
    linked patch statuses so the state calculation always uses
    the latest transaction state.
    """

    # Critical:
    # Persist in-memory patch status changes inside the current
    # transaction before querying linked patch statuses.
    db.flush()

    session_id = db.scalar(
        select(
            SelfCorrectionPatchRecord.session_id
        )
        .where(
            SelfCorrectionPatchRecord.pending_patch_id
            == patch_id
        )
        .limit(1)
    )

    # Ordinary task patches may not belong to a correction
    # session. In that case there is nothing to synchronize.
    if session_id is None:
        return

    session = db.scalar(
        select(
            SelfCorrectionSession
        )
        .where(
            SelfCorrectionSession.id
            == session_id
        )
        .with_for_update()
    )

    if session is None:
        return

    status_statement = (
        select(
            PendingPatchRecord.status
        )
        .join(
            SelfCorrectionPatchRecord,
            (
                SelfCorrectionPatchRecord.pending_patch_id
                == PendingPatchRecord.id
            ),
        )
        .where(
            SelfCorrectionPatchRecord.session_id
            == session_id
        )
    )

    linked_statuses = list(
        db.scalars(
            status_statement
        ).all()
    )

    if not linked_statuses:
        return

    pending = (
        PendingPatchStatus.PENDING.value
    )

    approved = (
        PendingPatchStatus.APPROVED.value
    )

    rejected = (
        PendingPatchStatus.REJECTED.value
    )

    applied = (
        PendingPatchStatus.APPLIED.value
    )

    stale = (
        PendingPatchStatus.STALE.value
    )

    if rejected in linked_statuses:
        correction_status = (
            "patch_rejected"
        )

    elif stale in linked_statuses:
        correction_status = (
            "patch_stale"
        )

    elif all(
        patch_status == applied
        for patch_status in linked_statuses
    ):
        correction_status = (
            "patches_applied"
        )

    elif all(
        patch_status
        in {
            approved,
            applied,
        }
        for patch_status in linked_statuses
    ):
        correction_status = (
            "patches_approved"
        )

    elif any(
        patch_status == pending
        for patch_status in linked_statuses
    ):
        correction_status = (
            "patch_ready"
        )

    else:
        correction_status = (
            "patch_ready"
        )

    session.status = correction_status
    session.updated_at = datetime.now(UTC)

    # Make the synchronized workflow state explicit inside the
    # same transaction before the caller commits.
    db.flush()


def _to_response(
    *,
    message: str,
    patch: PendingPatchRecord,
) -> PatchActionResponse:
    return PatchActionResponse(
        message=message,
        patch=PendingPatchRead.model_validate(
            patch
        ),
    )


def approve_patch(
    db: Session,
    *,
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
) -> PatchActionResponse:
    _get_task(
        db,
        task_id,
    )

    patch = _get_patch_for_update(
        db,
        task_id=task_id,
        patch_id=patch_id,
    )

    if (
        patch.status
        != PendingPatchStatus.PENDING.value
    ):
        db.rollback()

        raise PatchStateConflictError(
            "Only a pending patch can be approved. "
            f"Current status is '{patch.status}'."
        )

    now = datetime.now(UTC)

    patch.status = (
        PendingPatchStatus.APPROVED.value
    )
    patch.reviewed_at = now
    patch.updated_at = now

    try:
        _sync_correction_session_status(
            db,
            patch_id=patch.id,
        )

        db.commit()
        db.refresh(
            patch
        )

    except Exception:
        db.rollback()
        raise

    return _to_response(
        message="Patch approved successfully.",
        patch=patch,
    )


def reject_patch(
    db: Session,
    *,
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
) -> PatchActionResponse:
    _get_task(
        db,
        task_id,
    )

    patch = _get_patch_for_update(
        db,
        task_id=task_id,
        patch_id=patch_id,
    )

    allowed_statuses = {
        PendingPatchStatus.PENDING.value,
        PendingPatchStatus.APPROVED.value,
    }

    if patch.status not in allowed_statuses:
        db.rollback()

        raise PatchStateConflictError(
            "Only a pending or approved patch can "
            "be rejected. "
            f"Current status is '{patch.status}'."
        )

    now = datetime.now(UTC)

    patch.status = (
        PendingPatchStatus.REJECTED.value
    )
    patch.reviewed_at = now
    patch.updated_at = now

    try:
        _sync_correction_session_status(
            db,
            patch_id=patch.id,
        )

        db.commit()
        db.refresh(
            patch
        )

    except Exception:
        db.rollback()
        raise

    return _to_response(
        message="Patch rejected successfully.",
        patch=patch,
    )


def apply_patch(
    db: Session,
    *,
    task_id: uuid.UUID,
    patch_id: uuid.UUID,
) -> PatchActionResponse:
    task = _get_task(
        db,
        task_id,
    )

    patch = _get_patch_for_update(
        db,
        task_id=task_id,
        patch_id=patch_id,
    )

    if (
        patch.status
        != PendingPatchStatus.APPROVED.value
    ):
        db.rollback()

        raise PatchStateConflictError(
            "Only an approved patch can be applied. "
            f"Current status is '{patch.status}'."
        )

    try:
        workspace = SecureWorkspace(
            task.repository_path
        )

    except Exception as exc:
        db.rollback()

        raise PatchApplicationError(
            "Unable to initialize the secure "
            f"repository workspace: {exc}"
        ) from exc

    patch_engine = SafePatchEngine(
        workspace
    )

    try:
        patch_engine.apply_prepared_patch(
            path=patch.path,
            proposed_content=(
                patch.proposed_content
            ),
            expected_original_sha256=(
                patch.original_sha256
            ),
        )

    except StalePatchError as exc:
        now = datetime.now(UTC)

        patch.status = (
            PendingPatchStatus.STALE.value
        )
        patch.updated_at = now

        try:
            _sync_correction_session_status(
                db,
                patch_id=patch.id,
            )

            db.commit()
            db.refresh(
                patch
            )

        except Exception:
            db.rollback()
            raise

        raise PatchStaleConflictError(
            str(exc)
        ) from exc

    except PatchError as exc:
        db.rollback()

        raise PatchApplicationError(
            f"Patch could not be applied: {exc}"
        ) from exc

    except Exception as exc:
        db.rollback()

        raise PatchApplicationError(
            "Unexpected error while applying "
            f"patch: {exc}"
        ) from exc

    now = datetime.now(UTC)

    patch.status = (
        PendingPatchStatus.APPLIED.value
    )
    patch.applied_at = now
    patch.updated_at = now

    try:
        _sync_correction_session_status(
            db,
            patch_id=patch.id,
        )

        db.commit()
        db.refresh(
            patch
        )

    except Exception:
        db.rollback()
        raise

    return _to_response(
        message="Patch applied successfully.",
        patch=patch,
    )