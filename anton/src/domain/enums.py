from enum import StrEnum


class DiagnosisStatus(StrEnum):
    OBSERVED = "observed"
    INVESTIGATING = "investigating"
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    VERIFIED = "verified"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSource(StrEnum):
    GATUS = "gatus"
    ALERTMANAGER = "alertmanager"


class AlertStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"


class GatusEventStatus(StrEnum):
    TRIGGERED = "TRIGGERED"
    RESOLVED = "RESOLVED"


class IncidentStatus(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    BLOCKED = "blocked"
    PR_CREATED = "pr_created"
    IGNORED = "ignored"
    RESOLVED = "resolved"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
