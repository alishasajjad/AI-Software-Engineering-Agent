from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.verification import (
    VerificationRunResponse,
)


class CorrectionReverificationResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    session_id: uuid.UUID

    retry_session_id: uuid.UUID | None = None

    status: str

    current_attempt: int

    max_attempts: int

    remaining_attempts: int

    verification: VerificationRunResponse

    message: str