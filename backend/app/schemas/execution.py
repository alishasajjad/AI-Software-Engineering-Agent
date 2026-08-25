import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VerificationCommand(StrEnum):
    PYTEST = "pytest"
    RUFF = "ruff"
    COMPILEALL = "compileall"


class VerificationRunStatus(StrEnum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class CommandExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_type: VerificationCommand
    command: list[str]

    exit_code: int | None

    stdout: str
    stderr: str

    timed_out: bool
    duration_seconds: float

    succeeded: bool


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pytest_targets: list[str] = Field(
        default_factory=list,
        max_length=25,
        description=(
            "Optional repository-relative pytest targets. "
            "An empty list runs the repository's full pytest suite."
        ),
    )


class VerificationStepRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: uuid.UUID
    verification_run_id: uuid.UUID

    position: int
    command_type: VerificationCommand
    command: list[str]

    exit_code: int | None

    stdout: str
    stderr: str

    timed_out: bool
    duration_seconds: float
    succeeded: bool

    created_at: datetime


class VerificationRunRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: uuid.UUID
    task_id: uuid.UUID

    status: VerificationRunStatus

    error_message: str | None

    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    steps: list[VerificationStepRead]