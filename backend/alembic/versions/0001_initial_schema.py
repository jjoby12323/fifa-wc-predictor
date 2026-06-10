"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-05

Single consolidated schema (users, matches, votes, scores, messages,
sent_notifications). There is intentionally only one migration — the app has no
released data, so earlier migrations were squashed into this one.

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String, unique=True, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.Integer, unique=True, nullable=True),
        sa.Column("match_label", sa.String, nullable=False),
        sa.Column("team_a", sa.String, nullable=False),
        sa.Column("team_b", sa.String, nullable=False),
        sa.Column("kickoff_utc", sa.DateTime, nullable=False),
        sa.Column("polls_open_utc", sa.DateTime, nullable=False),
        sa.Column("stage", sa.String, nullable=False, server_default="group"),
        sa.Column("matchday", sa.Integer, nullable=False, server_default="1"),
        sa.Column("fifa_rank_a", sa.Integer, nullable=False, server_default="50"),
        sa.Column("fifa_rank_b", sa.Integer, nullable=False, server_default="50"),
        sa.Column("result", sa.String, nullable=True),
    )
    op.create_table(
        "votes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("prediction", sa.String, nullable=False),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "match_id"),
    )
    op.create_table(
        "scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("base_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("streak_bonus", sa.Integer, nullable=False, server_default="0"),
        sa.Column("perfect_round_bonus", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "match_id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "sent_notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("key", name="uq_sent_notifications_key"),
    )


def downgrade() -> None:
    op.drop_table("sent_notifications")
    op.drop_table("messages")
    op.drop_table("scores")
    op.drop_table("votes")
    op.drop_table("matches")
    op.drop_table("users")
