"""SQLAlchemy ORM tables.

Each row stores the full Pydantic model as JSON in ``payload`` for lossless
replay, plus a handful of indexed columns the run/suite explorers query on.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ContextPackageRow(Base):
    __tablename__ = "context_packages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class EvalRunRow(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    suite_id: Mapped[str] = mapped_column(String, index=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    agent: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    score: Mapped[float] = mapped_column(Float, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    payload: Mapped[dict] = mapped_column(JSON)
