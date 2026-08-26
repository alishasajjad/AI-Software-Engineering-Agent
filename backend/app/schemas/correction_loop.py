from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.schemas.patch import (
    PendingPatchStatus,
)


class CorrectionLoopNextAction(StrEnum):
    GENERATE_PROPOSAL = "generate_proposal"
    PREPARE_PATCHES = "prepare_patches"
    REVIEW_PATCHES = "review_patches"
    APPLY_APPROVED_PATCHES = (
        "apply_approved_patches"
    )
    REVERIFY = "reverify"
    NONE = "none"


class CorrectionLoopPatchRead(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    id: uuid.UUID
    path: str
    status: PendingPatchStatus


class CorrectionLoopSessionRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: uuid.UUID

    task_id: uuid.UUID

    source_verification_run_id: uuid.UUID

    parent_session_id: uuid.UUID | None

    last_verification_run_id: uuid.UUID | None

    status: str

    current_attempt: int

    max_attempts: int

    created_at: datetime

    updated_at: datetime

    completed_at: datetime | None


class CorrectionLoopResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    root_session_id: uuid.UUID

    active_session: CorrectionLoopSessionRead

    chain: list[CorrectionLoopSessionRead]

    terminal: bool

    safe_stopped: bool

    requires_human_action: bool

    next_action: CorrectionLoopNextAction

    remaining_attempts: int

    stop_reason: str | None

    message: str

    patches: list[CorrectionLoopPatchRead]