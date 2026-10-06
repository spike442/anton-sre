from datetime import datetime
from typing import Any

from domain.enums import AgentStatus, IncidentStatus
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Enum as SqlEnum


class Base(DeclarativeBase):
    pass


def incident_status_type() -> SqlEnum:
    return SqlEnum(
        IncidentStatus,
        name="incident_status",
        native_enum=False,
        values_callable=lambda enum: [item.value for item in enum],
        length=32,
    )


class IncidentRecord(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[IncidentStatus] = mapped_column(incident_status_type(), nullable=False)
    alert: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    diagnosis: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pr_url: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replay_prompts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    manual_actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    diagnosis_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)


class AgentStateRecord(Base):
    __tablename__ = "agent_states"

    agent_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
