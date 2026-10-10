from sensei.application.policy import decide_merge
from sensei.domain.models import ConfidenceLevel, ReviewResult, RiskLevel


def review(risk=RiskLevel.LOW, confidence=ConfidenceLevel.MEDIUM):
    return ReviewResult(risk=risk, confidence=confidence, summary="valid")


def allowed(review_result):
    return decide_merge(
        review_result,
        checks_passed=True,
        mergeable=True,
        merge_enabled=True,
        allowed_risk_levels={"low", "medium"},
        allowed_confidence_levels={"low", "medium"},
    )


def test_policy_allows_low_risk_medium_confidence():
    assert allowed(review()).merge is True


def test_policy_blocks_high_risk():
    assert allowed(review(risk=RiskLevel.HIGH)).merge is False


def test_policy_blocks_high_confidence_per_requested_rule():
    assert allowed(review(confidence=ConfidenceLevel.HIGH)).merge is False
