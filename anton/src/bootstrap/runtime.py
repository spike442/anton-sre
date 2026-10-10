import logging
from dataclasses import dataclass

from application.agent import AgentSession, boot
from domain.enums import AgentStatus
from infrastructure.config import Settings
from integrations.prompts import PromptStore
from integrations.sql import SqlManager

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    settings: Settings
    prompts: PromptStore
    agent: AgentSession
    state: SqlManager

    @classmethod
    def load(cls, settings: Settings | None = None) -> "Runtime":
        settings = settings or Settings.load()
        state = SqlManager(settings.database_dsn, settings.agent_name)
        prompts = PromptStore(settings)
        system_prompt = f"{prompts.system()}\n\nOperating context:\n{prompts.context()}"
        agent = boot(settings, system_prompt)
        logger.info("runtime configuration, prompts, context, tools, and agent session loaded")
        return cls(settings=settings, prompts=prompts, agent=agent, state=state)

    @property
    def agent_status(self) -> AgentStatus:
        return self.state.agent().status

    def close(self) -> None:
        self.agent.close()
        self.prompts.close()
        self.state.close()
