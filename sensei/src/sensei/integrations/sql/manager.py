from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from sensei.domain.models import PullRequest, PullRequestReview, ReviewStatus
from sensei.integrations.sql.models import PullRequestReview as PullRequestReviewRecord


class ReviewStore:
    """Persists reviewed PR heads and their decisions."""

    def __init__(self, database_dsn: str):
        self.engine = create_engine(
            database_dsn,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True,
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def has_processed(self, pull_request: PullRequest) -> bool:
        with self._sessions() as session:
            statement = select(PullRequestReviewRecord.status).where(
                PullRequestReviewRecord.owner == pull_request.owner,
                PullRequestReviewRecord.repository == pull_request.repository,
                PullRequestReviewRecord.pull_request_number == pull_request.number,
                PullRequestReviewRecord.head_sha == pull_request.head_sha,
            )
            return session.scalar(statement) in {ReviewStatus.MERGED.value, ReviewStatus.FAILED.value}

    def acknowledge(self, pull_request: PullRequest) -> bool:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            record = self._find(session, pull_request)
            if record is None:
                session.add(
                    PullRequestReviewRecord(
                        owner=pull_request.owner,
                        repository=pull_request.repository,
                        pull_request_number=pull_request.number,
                        base_sha=pull_request.base_sha,
                        head_sha=pull_request.head_sha,
                        pull_request_url=pull_request.html_url,
                        status=ReviewStatus.ACKNOWLEDGED.value,
                        updated_at=now,
                    )
                )
                return True
        return False

    def mark_processing(self, pull_request: PullRequest) -> None:
        self._set_status(pull_request, ReviewStatus.PROCESSING)

    def mark_pending(self, pull_request: PullRequest, reason: str) -> None:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            record = self._find(session, pull_request)
            if record is not None:
                record.status = ReviewStatus.PENDING.value
                record.summary = reason
                record.decision_reason = reason
                record.updated_at = now

    def mark_failed(self, pull_request: PullRequest, reason: str) -> None:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            record = self._find(session, pull_request)
            if record is None:
                record = PullRequestReviewRecord(
                    owner=pull_request.owner,
                    repository=pull_request.repository,
                    pull_request_number=pull_request.number,
                    base_sha=pull_request.base_sha,
                    head_sha=pull_request.head_sha,
                    pull_request_url=pull_request.html_url,
                    updated_at=now,
                )
                session.add(record)
            record.status = ReviewStatus.FAILED.value
            record.summary = reason
            record.decision_reason = reason
            record.updated_at = now

    def list_reviews(self, limit: int = 50, status: ReviewStatus | None = None) -> list[dict]:
        with self._sessions() as session:
            statement = select(PullRequestReviewRecord)
            if status:
                statement = statement.where(PullRequestReviewRecord.status == status.value)
            statement = statement.order_by(PullRequestReviewRecord.updated_at.desc()).limit(limit)
            return [self._as_dict(record) for record in session.scalars(statement)]

    def delete(self, review_id: int) -> None:
        with self._sessions.begin() as session:
            record = session.get(PullRequestReviewRecord, review_id)
            if record is None:
                raise RuntimeError("review not found")
            session.delete(record)

    def save(self, pull_request_review: PullRequestReview) -> None:
        pull_request = pull_request_review.pull_request
        review = pull_request_review.review
        decision = pull_request_review.decision
        with self._sessions.begin() as session:
            record = self._find(session, pull_request)
            if record is None:
                record = PullRequestReviewRecord(
                    owner=pull_request.owner,
                    repository=pull_request.repository,
                    pull_request_number=pull_request.number,
                    base_sha=pull_request.base_sha,
                    head_sha=pull_request.head_sha,
                    pull_request_url=pull_request.html_url,
                    updated_at=datetime.now(UTC),
                )
                session.add(record)
            record.status = pull_request_review.status.value
            record.checks = [check.model_dump(mode="json") for check in pull_request_review.checks]
            record.risk = review.risk.value
            record.confidence = review.confidence.value
            record.summary = review.summary
            record.findings = review.findings
            record.mergeable = pull_request_review.mergeable
            record.merge = decision.merge
            record.decision_reason = decision.reason
            record.reviewed_at = datetime.now(UTC)
            record.updated_at = record.reviewed_at
            record.merged_at = pull_request_review.merged_at
            record.merge_commit_sha = pull_request_review.merge_commit_sha
            record.review_actions = pull_request_review.review_actions

    def _set_status(self, pull_request: PullRequest, status: ReviewStatus) -> None:
        with self._sessions.begin() as session:
            record = self._find(session, pull_request)
            if record is not None:
                record.status = status.value
                record.updated_at = datetime.now(UTC)

    @staticmethod
    def _find(session, pull_request: PullRequest) -> PullRequestReviewRecord | None:
        statement = select(PullRequestReviewRecord).where(
            PullRequestReviewRecord.owner == pull_request.owner,
            PullRequestReviewRecord.repository == pull_request.repository,
            PullRequestReviewRecord.pull_request_number == pull_request.number,
            PullRequestReviewRecord.head_sha == pull_request.head_sha,
        )
        return session.scalar(statement)

    @staticmethod
    def _as_dict(record: PullRequestReviewRecord) -> dict:
        return {
            "id": record.id,
            "owner": record.owner,
            "repository": record.repository,
            "pull_request_number": record.pull_request_number,
            "base_sha": record.base_sha,
            "head_sha": record.head_sha,
            "pull_request_url": record.pull_request_url,
            "status": record.status,
            "checks": record.checks or [],
            "risk": record.risk,
            "confidence": record.confidence,
            "summary": record.summary or "",
            "findings": record.findings or [],
            "mergeable": record.mergeable,
            "merge": record.merge,
            "decision_reason": record.decision_reason or "",
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
            "updated_at": record.updated_at.isoformat(),
            "merged_at": record.merged_at.isoformat() if record.merged_at else None,
            "merge_commit_sha": record.merge_commit_sha,
            "review_actions": record.review_actions or [],
        }

    def close(self) -> None:
        self.engine.dispose()
