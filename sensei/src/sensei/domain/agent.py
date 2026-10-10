from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AgentStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"


@dataclass(frozen=True)
class Agent:
    name: str
    status: AgentStatus
    updated_at: datetime | None = None
