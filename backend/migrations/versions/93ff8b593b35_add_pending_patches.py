"""add pending patches

Revision ID: 93ff8b593b35
Revises: 463738a66b44
Create Date: 2026-08-25 13:00:52.018168

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '93ff8b593b35'
down_revision: str | Sequence[str] | None = '463738a66b44'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_patches",
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
            "path",
            sa.String(length=1024),
            nullable=False,
        ),
        sa.Column(
            "original_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "proposed_content",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "diff",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "original_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('pending', 'approved', 'rejected', "
                "'applied', 'stale')"
            ),
            name="ck_pending_patches_status",
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
        "ix_pending_patches_task_id",
        "pending_patches",
        ["task_id"],
        unique=False,
    )

    op.create_index(
        "ix_pending_patches_status",
        "pending_patches",
        ["status"],
        unique=False,
    )

    op.create_index(
        "uq_pending_patches_task_path_pending",
        "pending_patches",
        [
            "task_id",
            "path",
        ],
        unique=True,
        postgresql_where=sa.text(
            "status = 'pending'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_pending_patches_task_path_pending",
        table_name="pending_patches",
    )

    op.drop_index(
        "ix_pending_patches_status",
        table_name="pending_patches",
    )

    op.drop_index(
        "ix_pending_patches_task_id",
        table_name="pending_patches",
    )

    op.drop_table(
        "pending_patches"
    )
