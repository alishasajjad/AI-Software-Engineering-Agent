import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class VerificationRunRecord(Base):
    __tablename__ = "verification_runs"

    __table_args__ = (
        CheckConstraint(
            (
                "status IN "
                "('running', 'passed', 'failed', 'error')"
            ),
            name="ck_verification_runs_status",
        ),
        Index(
            "ix_verification_runs_task_id",
            "task_id",
        ),
        Index(
            "ix_verification_runs_status",
            "status",
        ),
        Index(
            "ix_verification_runs_started_at",
            "started_at",
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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class VerificationStepRecord(Base):
    __tablename__ = "verification_steps"

    __table_args__ = (
        CheckConstraint(
            (
                "command_type IN "
                "('compileall', 'ruff', 'pytest')"
            ),
            name="ck_verification_steps_command_type",
        ),
        UniqueConstraint(
            "verification_run_id",
            "position",
            name=(
                "uq_verification_steps_run_position"
            ),
        ),
        Index(
            "ix_verification_steps_run_id",
            "verification_run_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    verification_run_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "verification_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    command_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    command: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    stdout: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    stderr: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    timed_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    duration_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    succeeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )