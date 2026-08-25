from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class SelfCorrectionSession(Base):
    __tablename__ = "self_correction_sessions"

    __table_args__ = (
        Index(
            "ix_self_correction_sessions_parent_session_id",
            "parent_session_id",
        ),
        Index(
            "ix_self_correction_sessions_last_verification_run_id",
            "last_verification_run_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_verification_run_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "verification_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    parent_session_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "self_correction_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        default=None,
    )

    last_verification_run_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "verification_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        default=None,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="analysis_ready",
    )

    current_attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    failure_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    failure_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    proposal_json: Mapped[
        dict[str, object] | None
    ] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    proposal_generated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class SelfCorrectionPatchRecord(Base):
    __tablename__ = "self_correction_patches"

    __table_args__ = (
        CheckConstraint(
            "position >= 1",
            name=(
                "ck_self_correction_patches_"
                "position_positive"
            ),
        ),
        UniqueConstraint(
            "pending_patch_id",
            name=(
                "uq_self_correction_patches_"
                "pending_patch_id"
            ),
        ),
        UniqueConstraint(
            "session_id",
            "position",
            name=(
                "uq_self_correction_patches_"
                "session_position"
            ),
        ),
        Index(
            "ix_self_correction_patches_session_id",
            "session_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "self_correction_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    pending_patch_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "pending_patches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )