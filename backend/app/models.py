from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint, DateTime, Float
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
    # The message this one replies to (WhatsApp-style quote); null for a normal message.
    reply_to_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("messages.id"), nullable=True)

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
    # Final score in goals (team_a = home, team_b = away); set when settled, null until then.
    score_a: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_b: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Shootout score, only for a match decided on penalties (else null).
    pens_a: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pens_b: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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
    base_points: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    streak_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    perfect_round_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    participation_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0)

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
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    pens_a: Optional[int] = None
    pens_b: Optional[int] = None
    my_vote: Optional[str]
    correct: Optional[bool]


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
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    pens_a: Optional[int] = None
    pens_b: Optional[int] = None
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
    reply_to_id: Optional[int] = None
    reply_to_name: Optional[str] = None      # author of the quoted message
    reply_to_content: Optional[str] = None   # text of the quoted message


class ChatRequest(BaseModel):
    content: str
    reply_to: Optional[int] = None


class PredictionHistoryRow(BaseModel):
    match_id: int
    match_label: str
    kickoff_utc: datetime
    stage: str
    matchday: int
    prediction: Optional[str]       # None if they didn't vote
    result: Optional[str]           # None if not settled yet
    correct: Optional[bool]
    # Per-match score components — bonuses are shown as their own lines in the UI
    base_points: float              # 1 for a correct pick, 0.5 for a draw, else 0
    streak_bonus: int
    perfect_round_bonus: int
    participation_bonus: int


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    display_name: str
    total: float
    base: float
    streak: int
    perfect: int
    participation: int


class SettleRequest(BaseModel):
    match_id: int
    result: str  # "team_a" or "team_b"


class AnnounceRequest(BaseModel):
    text: str


class GraceRequest(BaseModel):
    enabled: bool
    minutes: Optional[int] = None  # how long the late-voting window stays open (default in grace.py)
