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
    # "team_a" | "team_b" | None (not yet settled)
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
    upset_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    perfect_round_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="scores")
    match: Mapped["Match"] = relationship("Match", back_populates="scores")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    match_id: int
    prediction: str  # "team_a" or "team_b"


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


class ScoreRow(BaseModel):
    match_id: int
    match_label: str
    base_points: int
    streak_bonus: int
    upset_bonus: int
    perfect_round_bonus: int
    total: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    display_name: str
    total: int
    base: int
    streak: int
    upset: int
    perfect: int


class SettleRequest(BaseModel):
    match_id: int
    result: str  # "team_a" or "team_b"
