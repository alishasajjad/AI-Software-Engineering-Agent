"""add patch review timestamps

Revision ID: dd734441ece5
Revises: 93ff8b593b35
Create Date: 2026-08-25 14:06:13.635562

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dd734441ece5'
down_revision: str | Sequence[str] | None = '93ff8b593b35'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pending_patches",
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_patches",
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "pending_patches",
        "applied_at",
    )

    op.drop_column(
        "pending_patches",
        "reviewed_at",
    )
