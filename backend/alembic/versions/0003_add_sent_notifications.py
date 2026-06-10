"""add sent_notifications table

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unique constraint defined inline — SQLite can't ALTER TABLE ADD CONSTRAINT.
    op.create_table(
        "sent_notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("key", name="uq_sent_notifications_key"),
    )


def downgrade() -> None:
    op.drop_table("sent_notifications")
