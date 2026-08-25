from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.verification import (
    VerificationRunRecord,
    VerificationStepRecord,
)
from app.schemas.execution import CommandExecutionResult
from app.schemas.verification import VerificationRunResponse
from app.services.task_service import get_task
from app.tools.execution import RestrictedSandboxRunner
from app.tools.repository import SecureWorkspace


def _command_type_value(
    result: CommandExecutionResult,
) -> str:
    """
    Return the serializable command type value.

    CommandExecutionResult.command_type may be either
    a string or a string-backed enum.
    """

    command_type = result.command_type

    if hasattr(
        command_type,
        "value",
    ):
        return str(command_type.value)

    return str(command_type)


def _create_step_record(
    *,
    verification_run_id: uuid.UUID,
    position: int,
    result: CommandExecutionResult,
) -> VerificationStepRecord:
    """
    Convert a sandbox execution result into a persistent
    verification step record.
    """

    return VerificationStepRecord(
        verification_run_id=verification_run_id,
        position=position,
        command_type=_command_type_value(
            result
        ),
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
        duration_seconds=(
            result.duration_seconds
        ),
        succeeded=result.succeeded,
    )


def _get_step_records(
    *,
    db: Session,
    verification_run_id: uuid.UUID,
) -> list[VerificationStepRecord]:
    """
    Load verification steps in execution order.
    """

    statement = (
        select(
            VerificationStepRecord
        )
        .where(
            VerificationStepRecord.verification_run_id
            == verification_run_id
        )
        .order_by(
            VerificationStepRecord.position.asc()
        )
    )

    return list(
        db.scalars(statement).all()
    )


def _to_response(
    *,
    db: Session,
    run: VerificationRunRecord,
) -> VerificationRunResponse:
    """
    Convert persistent verification records into the API schema.
    """

    steps = _get_step_records(
        db=db,
        verification_run_id=run.id,
    )

    return VerificationRunResponse.model_validate(
        {
            "id": run.id,
            "task_id": run.task_id,
            "status": run.status,
            "error_message": (
                run.error_message
            ),
            "started_at": run.started_at,
            "completed_at": (
                run.completed_at
            ),
            "created_at": run.created_at,
            "steps": [
                {
                    "id": step.id,
                    "verification_run_id": (
                        step.verification_run_id
                    ),
                    "position": (
                        step.position
                    ),
                    "command_type": (
                        step.command_type
                    ),
                    "command": step.command,
                    "exit_code": (
                        step.exit_code
                    ),
                    "stdout": step.stdout,
                    "stderr": step.stderr,
                    "timed_out": (
                        step.timed_out
                    ),
                    "duration_seconds": (
                        step.duration_seconds
                    ),
                    "succeeded": (
                        step.succeeded
                    ),
                    "created_at": (
                        step.created_at
                    ),
                }
                for step in steps
            ],
        }
    )


def verify_task(
    *,
    db: Session,
    task_id: uuid.UUID,
    pytest_targets: list[str] | None = None,
) -> VerificationRunResponse:
    """
    Run automated verification for a task.

    The repository is copied into a restricted temporary
    sandbox before any verification commands execute.

    Verification sequence:

    1. Python compileall
    2. Ruff linting
    3. Pytest

    Every execution result is persisted in verification history.
    """

    task = get_task(
        db=db,
        task_id=task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    repository_path = Path(
        task.repository_path
    )

    workspace = SecureWorkspace(
        repository_path
    )

    runner = RestrictedSandboxRunner(
        workspace
    )

    verification_run = (
        VerificationRunRecord(
            task_id=task_id,
            status="running",
            started_at=datetime.now(
                UTC
            ),
        )
    )

    db.add(
        verification_run
    )
    db.commit()
    db.refresh(
        verification_run
    )

    try:
        with runner.open_session() as session:
            results: list[
                CommandExecutionResult
            ] = []

            compile_result = (
                session.run_compileall()
            )

            results.append(
                compile_result
            )

            ruff_result = (
                session.run_ruff()
            )

            results.append(
                ruff_result
            )

            pytest_result = (
                session.run_pytest(
                    pytest_targets
                )
            )

            results.append(
                pytest_result
            )

            for (
                position,
                result,
            ) in enumerate(
                results,
                start=1,
            ):
                step = (
                    _create_step_record(
                        verification_run_id=(
                            verification_run.id
                        ),
                        position=position,
                        result=result,
                    )
                )

                db.add(
                    step
                )

            all_succeeded = all(
                result.succeeded
                for result in results
            )

            verification_run.status = (
                "passed"
                if all_succeeded
                else "failed"
            )

            verification_run.completed_at = (
                datetime.now(
                    UTC
                )
            )

            db.commit()
            db.refresh(
                verification_run
            )

    except Exception as exc:
        db.rollback()

        verification_run = db.get(
            VerificationRunRecord,
            verification_run.id,
        )

        if verification_run is not None:
            verification_run.status = (
                "error"
            )

            verification_run.error_message = (
                str(exc)
            )

            verification_run.completed_at = (
                datetime.now(
                    UTC
                )
            )

            db.commit()
            db.refresh(
                verification_run
            )

        raise

    return _to_response(
        db=db,
        run=verification_run,
    )


def get_verification_history(
    *,
    db: Session,
    task_id: uuid.UUID,
) -> list[VerificationRunResponse]:
    """
    Return verification history for a task,
    newest verification first.
    """

    task = get_task(
        db=db,
        task_id=task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    statement = (
        select(
            VerificationRunRecord
        )
        .where(
            VerificationRunRecord.task_id
            == task_id
        )
        .order_by(
            VerificationRunRecord.created_at.desc()
        )
    )

    runs = list(
        db.scalars(statement).all()
    )

    return [
        _to_response(
            db=db,
            run=run,
        )
        for run in runs
    ]


def get_verification_run(
    *,
    db: Session,
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
) -> VerificationRunResponse | None:
    """
    Return a single verification run belonging to a task.
    """

    statement = (
        select(
            VerificationRunRecord
        )
        .where(
            VerificationRunRecord.id
            == verification_id,
            VerificationRunRecord.task_id
            == task_id,
        )
    )

    run = db.scalar(
        statement
    )

    if run is None:
        return None

    return _to_response(
        db=db,
        run=run,
    )