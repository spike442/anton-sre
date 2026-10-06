from pydantic import BaseModel, Field

from domain.enums import ConfidenceLevel, DiagnosisStatus, RiskLevel


class ProposedChange(BaseModel):
    file_path: str
    content: str
    title: str
    body: str


class ManualAction(BaseModel):
    title: str
    command: str
    reason: str
    validation: str


class Diagnosis(BaseModel):
    status: DiagnosisStatus = DiagnosisStatus.BLOCKED
    incident: str = "unknown incident"
    hypothesis: str = "Insufficient evidence to determine the root cause."
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    evidence: list[str] = Field(default_factory=list)
    proposed_files: list[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW
    validation: list[str] = Field(default_factory=list)
    rollback: str = "No change was proposed."
    post_merge_checks: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    manual_actions: list[ManualAction] = Field(default_factory=list)
