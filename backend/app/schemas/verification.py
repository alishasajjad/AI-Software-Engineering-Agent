from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.execution import VerificationCommand


class VerificationRequest(BaseModel):
    """
    Request payload for automated verification.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    pytest_targets: list[str] = Field(
        default_factory=list,
    )


class VerificationStepResponse(BaseModel):
    """
    One command executed during a verification run.
    """

    model_config = ConfigDict(
        from_attributes=True,
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


class VerificationRunResponse(BaseModel):
    """
    Complete persisted verification run.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    task_id: uuid.UUID

    status: str
    error_message: str | None

    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    steps: list[VerificationStepResponse] = Field(
        default_factory=list,
    )