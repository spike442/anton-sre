from dataclasses import dataclass
from datetime import datetime

from domain.enums import AgentStatus


@dataclass(frozen=True)
class Agent:
    name: str
    status: AgentStatus
    updated_at: datetime | None = None
