from enum import StrEnum

from pydantic import BaseModel


class AgentStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    DOWN = "down"


class AgentConfig(BaseModel):
    name: str
    base_url: str


class Agent(BaseModel):
    name: str
    status: AgentStatus
    healthy: bool
    version: str = ""
