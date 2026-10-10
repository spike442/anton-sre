from datetime import UTC, datetime

from domain import AgentStatus
from sqlalchemy import Boolean, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class AgentRecord(Base):
    __tablename__ = "agent"

    agent_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentStore:
    def __init__(self, database_dsn: str, agent_names: list[str]):
        self.agent_names = agent_names
        self.engine = create_engine(
            database_dsn,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True,
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def ensure_agents(self) -> None:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            for agent_name in self.agent_names:
                if session.get(AgentRecord, agent_name) is None:
                    session.add(AgentRecord(agent_name=agent_name, active=False, updated_at=now))

    def is_active(self, agent_name: str) -> bool:
        with self._sessions() as session:
            record = session.get(AgentRecord, agent_name)
            return bool(record and record.active)

    def set_status(self, agent_name: str, status: AgentStatus) -> None:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            record = session.get(AgentRecord, agent_name)
            if record is None:
                record = AgentRecord(agent_name=agent_name, active=False, updated_at=now)
                session.add(record)
            record.active = status == AgentStatus.ACTIVE
            record.updated_at = now

    def close(self) -> None:
        self.engine.dispose()
