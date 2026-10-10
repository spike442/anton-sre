from datetime import UTC, datetime

from sensei.application.policy import decide_merge
from sensei.domain.models import PullRequest, PullRequestReview, ReviewContext
from sensei.infrastructure.config import RepositoryConfig
from sensei.integrations.review import ReviewEngine


class ReviewService:
    def __init__(self, settings, workspace, engine: ReviewEngine, prompt_store):
        self.settings = settings
        self.workspace = workspace
        self.engine = engine
        self.prompt_store = prompt_store

    def review(self, pull_request: PullRequest, repository: RepositoryConfig, mergeable: bool) -> PullRequestReview:
        review_actions: list[dict] = []

        def record_action(action: str, details: dict) -> None:
            review_actions.append(
                {
                    "action": action,
                    "details": details,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        with self.workspace.checkout(pull_request, repository, record_action) as checkout:
            checks = self.workspace.run_checks(checkout, pull_request, record_action)
            diff = self.workspace.diff(checkout, pull_request, record_action, self.settings.max_diff_bytes)
            review_context = ReviewContext(
                project=repository.name,
                context=self.prompt_store.context(repository.name),
                version=self.prompt_store.version(repository.name),
            )
            review = self.engine.review(
                pull_request,
                diff,
                review_context,
                self.prompt_store.action(repository.name),
                repository.tools,
                record_action,
            )
        decision = decide_merge(
            review,
            checks_passed=all(check.passed for check in checks),
            mergeable=mergeable,
            merge_enabled=self.settings.merge_enabled,
            allowed_risk_levels=self.settings.allowed_risk_levels,
            allowed_confidence_levels=self.settings.allowed_confidence_levels,
        )
        pull_request_review = PullRequestReview(
            pull_request=pull_request,
            checks=checks,
            review=review,
            mergeable=mergeable,
            decision=decision,
            review_actions=review_actions,
        )
        return pull_request_review
