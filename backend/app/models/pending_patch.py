import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingPatchRecord(Base):
    __tablename__ = "pending_patches"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN "
                "('pending', 'approved', 'rejected', "
                "'applied', 'stale')"
            ),
            name="ck_pending_patches_status",
        ),
        Index(
            "ix_pending_patches_task_id",
            "task_id",
        ),
        Index(
            "ix_pending_patches_status",
            "status",
        ),
        Index(
            "uq_pending_patches_task_path_pending",
            "task_id",
            "path",
            unique=True,
            postgresql_where=text(
                "status = 'pending'"
            ),
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
    )

    path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    original_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    proposed_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    diff: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    original_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )