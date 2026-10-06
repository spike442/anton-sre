import logging
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from application.agent import AgentSession, boot
from domain.enums import AgentStatus
from infrastructure.config import Settings
from integrations.prompts import PromptStore
from integrations.sql import SqlManager

logger = logging.getLogger(__name__)


def package_version() -> str:
    try:
        return version("anton-sre-agent")
    except PackageNotFoundError:
        return "unknown"


@dataclass
class Runtime:
    settings: Settings
    prompts: PromptStore
    agent: AgentSession
    state: SqlManager
    agent_status: AgentStatus

    @classmethod
    def load(cls) -> "Runtime":
        settings = Settings.load()
        state = SqlManager(settings.database_dsn, settings.agent_name)
        persisted_status = state.agent_status()
        agent_status = AgentStatus(persisted_status["status"])
        prompts = PromptStore(settings)
        system_prompt = f"{prompts.system()}\n\nOperating context:\n{prompts.context()}"
        agent = boot(settings, system_prompt)
        logger.info("runtime configuration, prompts, context, tools, and agent session loaded")
        return cls(settings=settings, prompts=prompts, agent=agent, state=state, agent_status=agent_status)

    def set_agent_status(self, status: AgentStatus) -> dict[str, str]:
        result = self.state.set_agent_status(status)
        self.agent_status = status
        return result

    def close(self) -> None:
        self.agent.close()
        self.prompts.close()
        self.state.close()
