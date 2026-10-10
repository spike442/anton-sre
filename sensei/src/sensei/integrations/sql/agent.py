from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sensei.domain.agent import Agent, AgentStatus


class Base(DeclarativeBase):
    pass


class AgentRecord(Base):
    __tablename__ = "agent"

    agent_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentStore:
    """Reads agent lifecycle state independently from review persistence."""

    def __init__(self, database_dsn: str, agent_name: str):
        self.agent_name = agent_name
        self.engine = create_engine(
            database_dsn,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True,
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def current(self) -> Agent:
        with self._sessions() as session:
            record = session.get(AgentRecord, self.agent_name)
        return Agent(
            name=self.agent_name,
            status=AgentStatus.ACTIVE if record and record.active else AgentStatus.IDLE,
            updated_at=record.updated_at if record else None,
        )

    def is_active(self) -> bool:
        return self.current().status is AgentStatus.ACTIVE

    def close(self) -> None:
        self.engine.dispose()
