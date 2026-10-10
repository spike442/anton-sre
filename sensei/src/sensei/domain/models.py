from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    MERGED = "merged"


class CheckResult(BaseModel):
    name: str
    passed: bool
    output: str = ""


class PullRequest(BaseModel):
    owner: str
    repository: str
    number: int = Field(gt=0)
    base_sha: str
    head_sha: str
    clone_url: str
    html_url: str = ""
    updated_at: str = ""
    title: str = ""
    author: str = ""
    head_ref: str = ""
    labels: list[str] = Field(default_factory=list)


class ReviewContext(BaseModel):
    project: str
    context: str
    version: str = ""


class ReviewResult(BaseModel):
    risk: RiskLevel
    confidence: ConfidenceLevel
    summary: str
    findings: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    merge: bool
    reason: str


class PullRequestReview(BaseModel):
    pull_request: PullRequest
    checks: list[CheckResult]
    review: ReviewResult
    mergeable: bool
    decision: ReviewDecision
    review_actions: list[dict] = Field(default_factory=list)
    merged_at: datetime | None = None
    merge_commit_sha: str = ""
    status: ReviewStatus = ReviewStatus.FAILED
