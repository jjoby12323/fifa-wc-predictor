from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel
from app.db import Base


# ── ORM Models ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)

    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="user")
    scores: Mapped[list["Score"]] = relationship("Score", back_populates="user")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="messages")


class SentNotification(Base):
    """Idempotency ledger for Slack posts — one row per already-sent announcement."""
    __tablename__ = "sent_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    match_label: Mapped[str] = mapped_column(String, nullable=False)
    team_a: Mapped[str] = mapped_column(String, nullable=False)
    team_b: Mapped[str] = mapped_column(String, nullable=False)
    kickoff_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    polls_open_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # "group" | "r16" | "qf" | "sf" | "final"
    stage: Mapped[str] = mapped_column(String, nullable=False, default="group")
    matchday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fifa_rank_a: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    fifa_rank_b: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    # "team_a" | "team_b" | "draw" | None (not yet settled)
    result: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="match")
    scores: Mapped[list["Score"]] = relationship("Score", back_populates="match")


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("user_id", "match_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    prediction: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="votes")
    match: Mapped["Match"] = relationship("Match", back_populates="votes")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("user_id", "match_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    base_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    perfect_round_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    participation_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="scores")
    match: Mapped["Match"] = relationship("Match", back_populates="scores")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    match_id: int
    prediction: str  # "team_a", "team_b", or "draw" (draw is group-stage only)


class MatchStatus(BaseModel):
    id: int
    match_label: str
    team_a: str
    team_b: str
    kickoff_utc: datetime
    polls_open_utc: datetime
    stage: str
    matchday: int
    status: str  # "pending" | "open" | "closed" | "settled"
    result: Optional[str]
    my_vote: Optional[str]
    correct: Optional[bool]
    underdog: Optional[str]  # "team_a" | "team_b" | None (if ranks equal)


class MatchVoteEntry(BaseModel):
    display_name: str
    prediction: Optional[str]  # None if user hasn't voted


class MatchDetail(BaseModel):
    id: int
    match_label: str
    team_a: str
    team_b: str
    kickoff_utc: datetime
    polls_open_utc: datetime
    stage: str
    matchday: int
    status: str
    result: Optional[str]
    underdog: Optional[str]
    fifa_rank_a: int
    fifa_rank_b: int
    my_vote: Optional[str]
    votes: list[MatchVoteEntry]  # all participants' votes


class ChatMessage(BaseModel):
    id: int
    username: str
    display_name: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    content: str


class PredictionHistoryRow(BaseModel):
    match_id: int
    match_label: str
    kickoff_utc: datetime
    stage: str
    prediction: Optional[str]       # None if they didn't vote
    result: Optional[str]           # None if not settled yet
    correct: Optional[bool]
    points: int


class ScoreRow(BaseModel):
    match_id: int
    match_label: str
    base_points: int
    streak_bonus: int
    perfect_round_bonus: int
    participation_bonus: int
    total: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    display_name: str
    total: int
    base: int
    streak: int
    perfect: int
    participation: int


class SettleRequest(BaseModel):
    match_id: int
    result: str  # "team_a" or "team_b"


class AnnounceRequest(BaseModel):
    text: str
