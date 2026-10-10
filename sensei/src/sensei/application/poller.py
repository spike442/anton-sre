import asyncio
import logging
import threading
from datetime import UTC, datetime

from sensei.application.review import ReviewService
from sensei.domain.models import ReviewStatus
from sensei.integrations.sql.agent import AgentStore
from sensei.integrations.sql.manager import ReviewStore

logger = logging.getLogger(__name__)


class PollingService:
    def __init__(self, settings, github, review_service: ReviewService, reviews: ReviewStore, sensei: AgentStore):
        self.settings = settings
        self.github = github
        self.review_service = review_service
        self.reviews = reviews
        self.sensei = sensei
        self._run_lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._run_lock.locked()

    def run_once(self) -> bool:
        if not self._run_lock.acquire(blocking=False):
            logger.info("Sensei check skipped because another check is already running")
            return False
        try:
            self._run_once()
            return True
        finally:
            self._run_lock.release()

    def _run_once(self) -> None:
        for repository in self.settings.repositories:
            for pull_request in self.github.list_open_pull_requests(repository):
                if self.reviews.has_processed(pull_request):
                    continue
                received = self.reviews.acknowledge(pull_request)
                if received:
                    logger.info(
                        "PR acknowledged repository=%s number=%s",
                        repository.name,
                        pull_request.number,
                    )
                    continue
                if not self.sensei.is_active():
                    logger.info(
                        "Acknowledged PR retained while Sensei is idle repository=%s number=%s",
                        repository.name,
                        pull_request.number,
                    )
                    continue
                try:
                    mergeable = self.github.is_mergeable(pull_request)
                except Exception as exc:
                    self.reviews.mark_pending(
                        pull_request,
                        f"GitHub mergeability is unavailable: {type(exc).__name__}.",
                    )
                    logger.warning(
                        "PR pending GitHub mergeability repository=%s number=%s error=%s",
                        repository.name,
                        pull_request.number,
                        type(exc).__name__,
                    )
                    continue
                if not mergeable:
                    self.reviews.mark_pending(
                        pull_request,
                        "Waiting for GitHub mergeable=true and mergeable_state=clean.",
                    )
                    logger.info(
                        "PR pending GitHub mergeability repository=%s number=%s",
                        repository.name,
                        pull_request.number,
                    )
                    continue
                self.reviews.mark_processing(pull_request)
                try:
                    review = self.review_service.review(pull_request, repository, mergeable)
                    if review.decision.merge:
                        review.merge_commit_sha = self.github.merge_pull_request(
                            pull_request,
                            self.settings.merge_method,
                        )
                        review.merged_at = datetime.now(UTC)
                        review.status = ReviewStatus.MERGED
                    else:
                        review.status = ReviewStatus.FAILED
                    self.reviews.save(review)
                except Exception as exc:
                    self.reviews.mark_failed(pull_request, f"review processing failed: {type(exc).__name__}")
                    logger.exception(
                        "PR processing failed repository=%s number=%s",
                        repository.name,
                        pull_request.number,
                    )
                    continue
                logger.info(
                    "PR review completed repository=%s number=%s risk=%s confidence=%s merge=%s merge_sha=%s",
                    repository.name,
                    pull_request.number,
                    review.review.risk,
                    review.review.confidence,
                    review.decision.merge,
                    review.merge_commit_sha,
                )

    async def run_forever(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.settings.poll_interval_seconds)
                await asyncio.to_thread(self.run_once)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Sensei polling cycle failed")
