import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FileEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        min_length=1,
        description="Repository-relative path of the file to edit.",
    )

    old_text: str = Field(
        min_length=1,
        description="Exact existing text that should be replaced.",
    )

    new_text: str = Field(
        description="Replacement text.",
    )


class PatchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    original_content: str
    proposed_content: str
    diff: str
    changed: bool


class PendingPatchStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    STALE = "stale"


class PendingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
    )

    task_id: uuid.UUID
    path: str

    original_content: str
    proposed_content: str
    diff: str

    original_sha256: str

    status: PendingPatchStatus = (
        PendingPatchStatus.PENDING
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class PreparedEditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_id: uuid.UUID
    path: str
    diff: str
    status: PendingPatchStatus


class PendingPatchRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: uuid.UUID
    task_id: uuid.UUID

    path: str

    original_content: str
    proposed_content: str
    diff: str

    original_sha256: str
    status: PendingPatchStatus

    created_at: datetime
    updated_at: datetime

    reviewed_at: datetime | None = None
    applied_at: datetime | None = None


class PatchPreparationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    editor_summary: str

    patches: list[PendingPatchRead]


class PatchActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    patch: PendingPatchRead