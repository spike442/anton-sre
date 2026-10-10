import logging
from dataclasses import dataclass

from hive_common.version import package_version

from sensei.application.poller import PollingService
from sensei.application.review import ReviewService
from sensei.infrastructure.config import Settings
from sensei.integrations.github import GitHubClient
from sensei.integrations.prompts import PromptStore
from sensei.integrations.review import OpenAIReviewEngine
from sensei.integrations.sql.agent import AgentStore
from sensei.integrations.sql.manager import ReviewStore
from sensei.integrations.tools import ToolRunner
from sensei.integrations.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    settings: Settings
    poller: PollingService

    @classmethod
    def load(cls, settings: Settings | None = None) -> "Runtime":
        settings = settings or Settings.load()
        github = GitHubClient(
            settings.github_api_url,
            settings.github_app_id,
            settings.github_installation_id,
            settings.github_private_key,
        )
        prompt_store = PromptStore(settings)
        reviews = ReviewStore(settings.database_dsn)
        workspace = WorkspaceManager(settings.workspace_root, settings.command_timeout_seconds)
        sensei = AgentStore(settings.database_dsn, settings.agent_name)
        tool_runner = ToolRunner(settings)
        review_service = ReviewService(
            settings,
            workspace,
            OpenAIReviewEngine(settings, tool_runner),
            prompt_store,
        )
        poller = PollingService(settings, github, review_service, reviews, sensei)
        logger.info(
            "Sensei runtime loaded version=%s repositories=%s", package_version("sensei"), len(settings.repositories)
        )
        return cls(settings=settings, poller=poller)

    def close(self) -> None:
        self.poller.github.close()
        self.poller.review_service.engine.close()
        self.poller.review_service.prompt_store.close()
        self.poller.reviews.close()
        self.poller.sensei.close()
