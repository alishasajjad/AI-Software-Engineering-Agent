import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.verification import (
    VerificationRunRecord,
    VerificationStepRecord,
)
from app.schemas.execution import (
    CommandExecutionResult,
    VerificationRequest,
    VerificationRunRead,
    VerificationRunStatus,
    VerificationStepRead,
)
from app.tools.execution import (
    RestrictedSandboxRunner,
    SandboxExecutionError,
    SandboxPolicyError,
)
from app.tools.repository import SecureWorkspace


class VerificationError(RuntimeError):
    """Base error for verification operations."""


class VerificationNotFoundError(
    VerificationError
):
    """Raised when a verification run is not found."""


class VerificationPolicyError(
    VerificationError
):
    """Raised when requested verification violates policy."""


def _create_run(
    db: Session,
    *,
    task_id: uuid.UUID,
) -> VerificationRunRecord:
    now = datetime.now(UTC)

    run = VerificationRunRecord(
        task_id=task_id,
        status=VerificationRunStatus.RUNNING.value,
        started_at=now,
        created_at=now,
    )

    db.add(run)

    try:
        db.commit()
        db.refresh(run)

    except Exception:
        db.rollback()
        raise

    return run


def _store_step(
    db: Session,
    *,
    run_id: uuid.UUID,
    position: int,
    result: CommandExecutionResult,
) -> VerificationStepRecord:
    step = VerificationStepRecord(
        verification_run_id=run_id,
        position=position,
        command_type=result.command_type.value,
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
        duration_seconds=result.duration_seconds,
        succeeded=result.succeeded,
    )

    db.add(step)

    try:
        db.commit()
        db.refresh(step)

    except Exception:
        db.rollback()
        raise

    return step


def _finish_run(
    db: Session,
    *,
    run: VerificationRunRecord,
    status: VerificationRunStatus,
    error_message: str | None = None,
) -> None:
    run.status = status.value
    run.error_message = error_message
    run.completed_at = datetime.now(UTC)

    try:
        db.commit()
        db.refresh(run)

    except Exception:
        db.rollback()
        raise


def _build_run_response(
    db: Session,
    *,
    run: VerificationRunRecord,
) -> VerificationRunRead:
    statement = (
        select(VerificationStepRecord)
        .where(
            VerificationStepRecord.verification_run_id
            == run.id
        )
        .order_by(
            VerificationStepRecord.position.asc()
        )
    )

    records = list(
        db.scalars(statement).all()
    )

    steps = [
        VerificationStepRead.model_validate(
            record
        )
        for record in records
    ]

    return VerificationRunRead(
        id=run.id,
        task_id=run.task_id,
        status=run.status,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        steps=steps,
    )


def run_task_verification(
    db: Session,
    *,
    task_id: uuid.UUID,
    request: VerificationRequest,
) -> VerificationRunRead:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    run = _create_run(
        db,
        task_id=task_id,
    )

    try:
        workspace = SecureWorkspace(
            task.repository_path
        )

        runner = RestrictedSandboxRunner(
            workspace,
            timeout_seconds=120.0,
            max_output_characters=30_000,
        )

        results: list[
            CommandExecutionResult
        ] = []

        with runner.open_session() as session:
            results.append(
                session.run_compileall()
            )

            results.append(
                session.run_ruff()
            )

            results.append(
                session.run_pytest(
                    request.pytest_targets
                )
            )

        for position, result in enumerate(
            results,
            start=1,
        ):
            _store_step(
                db,
                run_id=run.id,
                position=position,
                result=result,
            )

        if all(
            result.succeeded
            for result in results
        ):
            final_status = (
                VerificationRunStatus.PASSED
            )

        else:
            final_status = (
                VerificationRunStatus.FAILED
            )

        _finish_run(
            db,
            run=run,
            status=final_status,
        )

    except SandboxPolicyError as exc:
        _finish_run(
            db,
            run=run,
            status=VerificationRunStatus.ERROR,
            error_message=str(exc),
        )

        raise VerificationPolicyError(
            str(exc)
        ) from exc

    except SandboxExecutionError as exc:
        _finish_run(
            db,
            run=run,
            status=VerificationRunStatus.ERROR,
            error_message=str(exc),
        )

    except Exception as exc:
        _finish_run(
            db,
            run=run,
            status=VerificationRunStatus.ERROR,
            error_message=(
                "Unexpected verification error: "
                f"{exc}"
            ),
        )

    return _build_run_response(
        db,
        run=run,
    )


def list_task_verifications(
    db: Session,
    *,
    task_id: uuid.UUID,
) -> list[VerificationRunRead]:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    statement = (
        select(VerificationRunRecord)
        .where(
            VerificationRunRecord.task_id
            == task_id
        )
        .order_by(
            VerificationRunRecord.started_at.desc()
        )
    )

    runs = list(
        db.scalars(statement).all()
    )

    return [
        _build_run_response(
            db,
            run=run,
        )
        for run in runs
    ]


def get_task_verification(
    db: Session,
    *,
    task_id: uuid.UUID,
    verification_id: uuid.UUID,
) -> VerificationRunRead:
    task = db.get(
        Task,
        task_id,
    )

    if task is None:
        raise LookupError(
            "Task not found."
        )

    statement = (
        select(VerificationRunRecord)
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
        raise VerificationNotFoundError(
            "Verification run not found for this task."
        )

    return _build_run_response(
        db,
        run=run,
    )