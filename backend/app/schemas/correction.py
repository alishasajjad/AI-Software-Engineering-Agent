from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class FailureType(StrEnum):
    COMPILE_ERROR = "compile_error"
    LINT_ERROR = "lint_error"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    EXECUTION_ERROR = "execution_error"
    UNKNOWN = "unknown"


class CorrectionStatus(StrEnum):
    ANALYSIS_READY = "analysis_ready"
    CORRECTION_PENDING = "correction_pending"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    STOPPED = "stopped"


class FailureAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    verification_run_id: uuid.UUID

    failure_type: FailureType

    failed_command: str

    failed_step_position: int

    exit_code: int | None

    stdout: str

    stderr: str

    timed_out: bool

    summary: str


class SelfCorrectionSessionRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID

    task_id: uuid.UUID

    source_verification_run_id: uuid.UUID

    status: CorrectionStatus

    current_attempt: int

    max_attempts: int

    failure_type: FailureType

    failure_summary: str

    created_at: datetime

    updated_at: datetime

    completed_at: datetime | None


class FailureAnalysisResponse(BaseModel):
    session: SelfCorrectionSessionRead

    analysis: FailureAnalysis