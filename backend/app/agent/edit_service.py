import asyncio
import uuid

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.context import EngineeringAgentContext
from app.agent.editor import build_code_editor_agent
from app.agent.service import (
    PlanGenerationError,
    create_implementation_plan,
)
from app.core.config import settings
from app.models.pending_patch import PendingPatchRecord
from app.models.task import Task
from app.schemas.patch import (
    PatchPreparationResponse,
    PendingPatch,
    PendingPatchRead,
    PendingPatchStatus,
)
from app.tools.repository import SecureWorkspace


class PatchPreparationError(RuntimeError):
    """Raised when AI patch preparation cannot be completed."""


class PendingPatchConflictError(RuntimeError):
    """
    Raised when a task already contains pending patches.
    """


def find_existing_pending_patches(
    db: Session,
    task_id: uuid.UUID,
) -> list[PendingPatchRecord]:
    statement = (
        select(PendingPatchRecord)
        .where(
            PendingPatchRecord.task_id
            == task_id,
            PendingPatchRecord.status
            == PendingPatchStatus.PENDING.value,
        )
        .order_by(
            PendingPatchRecord.created_at.asc()
        )
    )

    return list(
        db.scalars(statement).all()
    )


def add_pending_patch_records(
    db: Session,
    patches: list[PendingPatch],
) -> list[PendingPatchRecord]:
    """
    Add pending patch records to the current transaction.

    This function flushes but does not commit. That allows larger
    workflows, such as self-correction, to persist patch records
    and workflow state atomically.
    """

    records: list[PendingPatchRecord] = []

    for patch in patches:
        record = PendingPatchRecord(
            id=patch.id,
            task_id=patch.task_id,
            path=patch.path,
            original_content=(
                patch.original_content
            ),
            proposed_content=(
                patch.proposed_content
            ),
            diff=patch.diff,
            original_sha256=(
                patch.original_sha256
            ),
            status=patch.status.value,
            created_at=patch.created_at,
            updated_at=patch.created_at,
        )

        db.add(record)
        records.append(record)

    try:
        db.flush()

    except IntegrityError as exc:
        db.rollback()

        raise PendingPatchConflictError(
            "A pending patch already exists for one "
            "of the files modified by this task."
        ) from exc

    except Exception:
        db.rollback()
        raise

    return records


def persist_pending_patches(
    db: Session,
    patches: list[PendingPatch],
) -> list[PendingPatchRecord]:
    """
    Persist a standalone set of pending patches.
    """

    try:
        records = add_pending_patch_records(
            db=db,
            patches=patches,
        )

        db.commit()

    except PendingPatchConflictError:
        raise

    except IntegrityError as exc:
        db.rollback()

        raise PendingPatchConflictError(
            "A pending patch already exists for one "
            "of the files modified by this task."
        ) from exc

    except Exception:
        db.rollback()
        raise

    for record in records:
        db.refresh(record)

    return records


def list_task_patches(
    db: Session,
    task_id: uuid.UUID,
) -> list[PendingPatchRead]:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    statement = (
        select(PendingPatchRecord)
        .where(
            PendingPatchRecord.task_id
            == task_id
        )
        .order_by(
            PendingPatchRecord.created_at.desc()
        )
    )

    records = list(
        db.scalars(statement).all()
    )

    return [
        PendingPatchRead.model_validate(
            record
        )
        for record in records
    ]


async def prepare_task_patches(
    db: Session,
    task_id: uuid.UUID,
) -> PatchPreparationResponse:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    existing_pending = (
        find_existing_pending_patches(
            db=db,
            task_id=task_id,
        )
    )

    if existing_pending:
        raise PendingPatchConflictError(
            "This task already has pending patches. "
            "Review, approve, or reject them before "
            "preparing another editing run."
        )

    try:
        workspace = SecureWorkspace(
            task.repository_path
        )

    except Exception as exc:
        raise PatchPreparationError(
            "Unable to initialize the secure "
            f"repository workspace: {exc}"
        ) from exc

    try:
        implementation_plan = (
            await create_implementation_plan(
                db=db,
                task_id=task_id,
            )
        )

    except PlanGenerationError as exc:
        raise PatchPreparationError(
            "Unable to generate the implementation "
            f"plan required for editing: {exc}"
        ) from exc

    context = EngineeringAgentContext(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        workspace=workspace,
    )

    editor = build_code_editor_agent()

    editor_input = (
        "Software task title:\n"
        f"{task.title}\n\n"
        "Task description:\n"
        f"{task.description}\n\n"
        "Implementation plan:\n"
        "--------------------------------\n"
        f"{implementation_plan.model_dump_json(indent=2)}\n"
        "--------------------------------\n\n"
        "Prepare the required pending code patches.\n\n"
        "Important execution rules:\n"
        "- The implementation plan already identifies relevant files.\n"
        "- Read those exact files directly whenever possible.\n"
        "- Do not repeat repository searches unnecessarily.\n"
        "- Do not re-read files after a successful patch proposal.\n"
        "- Every modification must use prepare_file_edit.\n"
        "- Do not modify files directly.\n"
        "- Make the smallest changes required by the task.\n"
        "- Stop calling tools once all necessary patches are prepared.\n"
        "- Return a final summary after patch preparation."
    )

    try:
        editor_result = await asyncio.wait_for(
            Runner.run(
                editor,
                editor_input,
                context=context,
                max_turns=(
                    settings.agent_editor_max_turns
                ),
            ),
            timeout=(
                settings.agent_editor_timeout_seconds
            ),
        )

    except TimeoutError as exc:
        raise PatchPreparationError(
            "Code editor timed out before completing "
            "patch preparation."
        ) from exc

    except MaxTurnsExceeded as exc:
        raise PatchPreparationError(
            "Code editor exceeded the dedicated editor "
            "turn limit. The editing workflow did not "
            "finish safely."
        ) from exc

    except Exception as exc:
        raise PatchPreparationError(
            f"Code editor failed: {exc}"
        ) from exc

    editor_output = (
        editor_result.final_output
    )

    if editor_output is None:
        editor_summary = (
            "Code editor completed without a "
            "final summary."
        )

    else:
        editor_summary = str(
            editor_output
        ).strip()

        if not editor_summary:
            editor_summary = (
                "Code editor completed without a "
                "final summary."
            )

    if not context.pending_patches:
        return PatchPreparationResponse(
            task_id=task.id,
            editor_summary=editor_summary,
            patches=[],
        )

    try:
        stored_records = (
            persist_pending_patches(
                db=db,
                patches=context.pending_patches,
            )
        )

    except PendingPatchConflictError:
        raise

    except Exception as exc:
        raise PatchPreparationError(
            "The generated patches could not be "
            f"persisted: {exc}"
        ) from exc

    stored_patches = [
        PendingPatchRead.model_validate(
            record
        )
        for record in stored_records
    ]

    return PatchPreparationResponse(
        task_id=task.id,
        editor_summary=editor_summary,
        patches=stored_patches,
    )