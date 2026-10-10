from sensei.domain.models import ReviewDecision, ReviewResult


def decide_merge(
    review: ReviewResult,
    *,
    checks_passed: bool,
    mergeable: bool,
    merge_enabled: bool,
    allowed_risk_levels: set[str],
    allowed_confidence_levels: set[str],
) -> ReviewDecision:
    """Apply deterministic merge rules after the review is validated."""
    if not merge_enabled:
        return ReviewDecision(merge=False, reason="automatic merging is disabled")
    if not checks_passed:
        return ReviewDecision(merge=False, reason="one or more validation checks failed")
    if not mergeable:
        return ReviewDecision(merge=False, reason="pull request is not mergeable")
    if review.risk.value not in allowed_risk_levels:
        return ReviewDecision(merge=False, reason=f"risk level is {review.risk.value}")
    if review.confidence.value not in allowed_confidence_levels:
        return ReviewDecision(merge=False, reason=f"confidence level is {review.confidence.value}")
    return ReviewDecision(merge=True, reason="validation passed and policy allows merge")
