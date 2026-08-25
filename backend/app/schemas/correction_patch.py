from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.patch import PendingPatchRead


class CorrectionPatchPreparationResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    session_id: uuid.UUID

    source_verification_run_id: uuid.UUID

    status: str

    editor_summary: str

    patches: list[PendingPatchRead]