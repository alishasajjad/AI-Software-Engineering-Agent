"""add verification history

Revision ID: 168813304978
Revises: dd734441ece5
Create Date: 2026-08-25 15:55:36.183884

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '168813304978'
down_revision: str | Sequence[str] | None = 'dd734441ece5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('running', 'passed', 'failed', 'error')"
            ),
            name="ck_verification_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
    )

    op.create_index(
        "ix_verification_runs_task_id",
        "verification_runs",
        ["task_id"],
        unique=False,
    )

    op.create_index(
        "ix_verification_runs_status",
        "verification_runs",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_verification_runs_started_at",
        "verification_runs",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "verification_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "verification_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "command_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "command",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "exit_code",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "stdout",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "stderr",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "timed_out",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "duration_seconds",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "succeeded",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "command_type IN "
                "('compileall', 'ruff', 'pytest')"
            ),
            name="ck_verification_steps_command_type",
        ),
        sa.ForeignKeyConstraint(
            ["verification_run_id"],
            ["verification_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
        ),
        sa.UniqueConstraint(
            "verification_run_id",
            "position",
            name=(
                "uq_verification_steps_run_position"
            ),
        ),
    )

    op.create_index(
        "ix_verification_steps_run_id",
        "verification_steps",
        ["verification_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verification_steps_run_id",
        table_name="verification_steps",
    )

    op.drop_table(
        "verification_steps"
    )

    op.drop_index(
        "ix_verification_runs_started_at",
        table_name="verification_runs",
    )

    op.drop_index(
        "ix_verification_runs_status",
        table_name="verification_runs",
    )

    op.drop_index(
        "ix_verification_runs_task_id",
        table_name="verification_runs",
    )

    op.drop_table(
        "verification_runs"
    )
