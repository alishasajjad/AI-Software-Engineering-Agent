from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from agents import Runner
from agents.exceptions import MaxTurnsExceeded
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.context import EngineeringAgentContext
from app.agent.edit_service import (
    PendingPatchConflictError,
    add_pending_patch_records,
    find_existing_pending_patches,
)
from app.agent.editor import build_code_editor_agent
from app.core.config import settings
from app.models.correction import (
    SelfCorrectionPatchRecord,
    SelfCorrectionSession,
)
from app.models.task import Task
from app.schemas.correction_patch import (
    CorrectionPatchPreparationResponse,
)
from app.schemas.correction_proposal import (
    CorrectionProposal,
)
from app.schemas.patch import (
    PendingPatch,
    PendingPatchRead,
    PendingPatchStatus,
)
from app.schemas.verification import (
    VerificationRunResponse,
)
from app.services.correction_service import (
    CorrectionSessionNotFoundError,
    InvalidCorrectionSessionStateError,
    InvalidVerificationStateError,
)
from app.services.failure_analyzer import (
    analyze_verification_failure,
)
from app.tools.repository import SecureWorkspace

MAX_FAILURE_OUTPUT_CHARACTERS = 12_000


class CorrectionPatchError(RuntimeError):
    """Base error for correction patch generation."""


class CorrectionPatchGenerationError(
    CorrectionPatchError
):
    """Correction patches could not be generated safely."""


class ExistingCorrectionPatchesError(
    CorrectionPatchError
):
    """Correction patches already exist for this session."""


class CorrectionPendingPatchConflictError(
    CorrectionPatchError
):
    """The task already contains unresolved pending patches."""


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


def _normalize_path(
    path: str,
) -> str:
    normalized = (
        path.strip()
        .replace("\\", "/")
    )

    while normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def _get_correction_session(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run_id: uuid.UUID,
) -> SelfCorrectionSession | None:
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

    return db.scalar(statement)


def _correction_patches_exist(
    *,
    db: Session,
    session_id: uuid.UUID,
) -> bool:
    existing = db.scalar(
        select(
            SelfCorrectionPatchRecord.id
        )
        .where(
            SelfCorrectionPatchRecord.session_id
            == session_id
        )
        .limit(1)
    )

    return existing is not None


def validate_generated_correction_patches(
    *,
    proposal: CorrectionProposal,
    patches: list[PendingPatch],
) -> None:
    """
    Ensure the editor generated only patches explicitly allowed
    by the approved correction proposal.
    """

    if not patches:
        raise CorrectionPatchGenerationError(
            "The correction editor did not prepare "
            "any pending patches."
        )

    allowed_paths = {
        _normalize_path(
            proposed_file.path
        )
        for proposed_file in proposal.files
    }

    generated_paths: set[str] = set()

    for patch in patches:
        normalized_path = (
            _normalize_path(
                patch.path
            )
        )

        if normalized_path not in allowed_paths:
            raise CorrectionPatchGenerationError(
                "The correction editor attempted to "
                "prepare a patch outside the approved "
                "correction proposal: "
                f"'{normalized_path}'."
            )

        if normalized_path in generated_paths:
            raise CorrectionPatchGenerationError(
                "The correction editor generated more "
                "than one patch for the same file: "
                f"'{normalized_path}'."
            )

        if (
            patch.status
            != PendingPatchStatus.PENDING
        ):
            raise CorrectionPatchGenerationError(
                "Correction patches must be created "
                "with pending status."
            )

        generated_paths.add(
            normalized_path
        )


def _editor_summary(
    final_output: object,
) -> str:
    if final_output is None:
        return (
            "Correction editor completed without "
            "a final summary."
        )

    summary = str(
        final_output
    ).strip()

    if not summary:
        return (
            "Correction editor completed without "
            "a final summary."
        )

    return summary


async def create_correction_patches(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_run: VerificationRunResponse,
) -> CorrectionPatchPreparationResponse:
    """
    Convert an AI correction proposal into safe PendingPatch
    records without modifying repository files.
    """

    if (
        verification_run.task_id
        != task_id
    ):
        raise LookupError(
            "Verification run was not found "
            "for this task."
        )

    if (
        _verification_status(
            verification_run
        )
        != "failed"
    ):
        raise InvalidVerificationStateError(
            "Only a failed verification run can "
            "generate correction patches."
        )

    session = _get_correction_session(
        db=db,
        task_id=task_id,
        verification_run_id=(
            verification_run.id
        ),
    )

    if session is None:
        raise CorrectionSessionNotFoundError(
            "Failure analysis must exist before "
            "correction patches can be generated."
        )

    if _correction_patches_exist(
        db=db,
        session_id=session.id,
    ):
        raise ExistingCorrectionPatchesError(
            "Correction patches already exist "
            "for this self-correction session."
        )

    if session.status != "proposal_ready":
        raise InvalidCorrectionSessionStateError(
            "Correction session is not ready for "
            "patch generation. "
            f"Current status is '{session.status}'."
        )

    if session.proposal_json is None:
        raise InvalidCorrectionSessionStateError(
            "The correction session does not contain "
            "a correction proposal."
        )

    try:
        proposal = (
            CorrectionProposal.model_validate(
                session.proposal_json
            )
        )

    except Exception as exc:
        raise CorrectionPatchGenerationError(
            "The stored correction proposal is invalid."
        ) from exc

    existing_pending = (
        find_existing_pending_patches(
            db=db,
            task_id=task_id,
        )
    )

    if existing_pending:
        raise CorrectionPendingPatchConflictError(
            "This task already has unresolved pending "
            "patches. Approve or reject them before "
            "generating correction patches."
        )

    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    try:
        workspace = SecureWorkspace(
            task.repository_path
        )

    except Exception as exc:
        raise CorrectionPatchGenerationError(
            "Unable to initialize the secure "
            f"repository workspace: {exc}"
        ) from exc

    analysis = (
        analyze_verification_failure(
            verification_run_id=(
                verification_run.id
            ),
            steps=verification_run.steps,
        )
    )

    allowed_file_list = "\n".join(
        (
            f"- {proposed_file.path}: "
            f"{proposed_file.reason}"
        )
        for proposed_file in proposal.files
    )

    context = EngineeringAgentContext(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description,
        workspace=workspace,
    )

    editor = build_code_editor_agent()

    editor_input = f"""
This is a SELF-CORRECTION patch preparation run.

Software task title:
{task.title}

Task description:
{task.description}

Failed verification:
{verification_run.id}

Failure type:
{analysis.failure_type.value}

Failure summary:
{analysis.summary}

Failed command:
{analysis.failed_command}

Verification stdout:
--------------------------------
{analysis.stdout[-MAX_FAILURE_OUTPUT_CHARACTERS:]}
--------------------------------

Verification stderr:
--------------------------------
{analysis.stderr[-MAX_FAILURE_OUTPUT_CHARACTERS:]}
--------------------------------

AI correction proposal:
--------------------------------
{proposal.model_dump_json(indent=2)}
--------------------------------

FILES ALLOWED TO BE MODIFIED:
{allowed_file_list}

Prepare the exact pending patches required by the correction
proposal.

MANDATORY RULES:

- Do not modify repository files directly.
- Every edit must use prepare_file_edit.
- Only modify files listed under FILES ALLOWED TO BE MODIFIED.
- Read the current file before preparing its edit.
- old_text must exactly match the current repository content.
- Make the smallest correction required.
- Do not weaken or delete tests merely to force a pass.
- Do not edit unrelated files.
- Do not create broad refactors.
- Do not prepare more than one patch for the same file.
- Stop once all required correction patches are prepared.
- Return a short final summary after preparing the patches.
""".strip()

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
        raise CorrectionPatchGenerationError(
            "Correction editor timed out before "
            "patch preparation completed."
        ) from exc

    except MaxTurnsExceeded as exc:
        raise CorrectionPatchGenerationError(
            "Correction editor exceeded the dedicated "
            "editor turn limit."
        ) from exc

    except Exception as exc:
        raise CorrectionPatchGenerationError(
            f"Correction editor failed: {exc}"
        ) from exc

    validate_generated_correction_patches(
        proposal=proposal,
        patches=context.pending_patches,
    )

    editor_summary = _editor_summary(
        editor_result.final_output
    )

    try:
        stored_records = (
            add_pending_patch_records(
                db=db,
                patches=(
                    context.pending_patches
                ),
            )
        )

    except PendingPatchConflictError as exc:
        raise (
            CorrectionPendingPatchConflictError(
                "A pending patch conflict occurred "
                "while storing correction patches."
            )
        ) from exc

    try:
        for position, record in enumerate(
            stored_records,
            start=1,
        ):
            link = SelfCorrectionPatchRecord(
                session_id=session.id,
                pending_patch_id=record.id,
                position=position,
            )

            db.add(link)

        session.status = "patch_ready"
        session.updated_at = datetime.now(UTC)

        db.commit()

    except Exception as exc:
        db.rollback()

        raise CorrectionPatchGenerationError(
            "Correction patches were generated but "
            "could not be persisted atomically."
        ) from exc

    for record in stored_records:
        db.refresh(record)

    db.refresh(session)

    stored_patches = [
        PendingPatchRead.model_validate(
            record
        )
        for record in stored_records
    ]

    return CorrectionPatchPreparationResponse(
        session_id=session.id,
        source_verification_run_id=(
            session.source_verification_run_id
        ),
        status=session.status,
        editor_summary=editor_summary,
        patches=stored_patches,
    )