from domain import Agent, AgentConfig, AgentStatus
from health import AgentHealth
from sql import AgentStore


class AgentService:
    def __init__(self, agents: list[AgentConfig], store: AgentStore, health: AgentHealth):
        self.agents = {agent.name: agent for agent in agents}
        self.store = store
        self.health = health
        self.store.ensure_agents()

    def list_agents(self) -> list[Agent]:
        return [self.status(name) for name in self.agents]

    def status(self, name: str) -> Agent:
        config = self._config(name)
        healthy, version = self.health.check(config)
        if not healthy:
            status = AgentStatus.DOWN
        else:
            status = AgentStatus.ACTIVE if self.store.is_active(name) else AgentStatus.IDLE
        return Agent(name=name, status=status, healthy=healthy, version=version)

    def set_status(self, name: str, status: AgentStatus) -> Agent:
        self._config(name)
        self.store.set_status(name, status)
        return self.status(name)

    def _config(self, name: str) -> AgentConfig:
        try:
            return self.agents[name]
        except KeyError as exc:
            raise KeyError(name) from exc
