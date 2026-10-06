from datetime import datetime, timedelta, timezone
from typing import Any

from domain.diagnosis import Diagnosis
from domain.enums import AgentStatus, AlertSource, DiagnosisStatus, IncidentStatus
from domain.incident import Incident
from integrations.sql.models import AgentStateRecord, IncidentRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_STALE_PROCESSING_AFTER = timedelta(minutes=30)


class SqlManager:
    def __init__(self, database_dsn: str, agent_name: str):
        self.agent_name = agent_name
        self.engine = create_engine(
            database_dsn,
            connect_args={"connect_timeout": 10},
            pool_pre_ping=True,
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _incident(record: IncidentRecord) -> Incident:
        return Incident(
            id=record.incident_id,
            status=record.status,
            alert=record.alert,
            diagnosis=Diagnosis.model_validate(record.diagnosis),
            pull_request_url=record.pr_url,
            attempts=record.attempts,
            updated_at=record.updated_at.isoformat(),
            replayed_at=record.replayed_at.isoformat() if record.replayed_at else None,
            replay_prompts=record.replay_prompts or [],
            manual_actions=record.manual_actions or [],
            diagnosis_history=record.diagnosis_history or [],
            timeline=record.timeline,
        )

    @staticmethod
    def _event(now: datetime, name: str) -> dict[str, str]:
        return {"at": now.isoformat(), "event": name}

    def agent_status(self) -> dict[str, str]:
        with self._sessions.begin() as session:
            record = session.get(AgentStateRecord, self.agent_name)
            if not record:
                record = AgentStateRecord(
                    agent_name=self.agent_name,
                    active=False,
                    updated_at=self._now(),
                )
                session.add(record)
        return {
            "agent": record.agent_name,
            "status": AgentStatus.ACTIVE.value if record.active else AgentStatus.IDLE.value,
            "updated_at": record.updated_at.isoformat(),
        }

    def set_agent_status(self, status: AgentStatus) -> dict[str, str]:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.get(AgentStateRecord, self.agent_name)
            if not record:
                record = AgentStateRecord(agent_name=self.agent_name, active=status == AgentStatus.ACTIVE,
                                          updated_at=now)
                session.add(record)
            else:
                record.active = status == AgentStatus.ACTIVE
                record.updated_at = now
        return {
            "agent": self.agent_name,
            "status": status.value,
            "updated_at": now.isoformat(),
        }

    def acknowledge_incident(self, incident_id: str, alert: dict[str, Any]) -> Incident:
        now = self._now()
        diagnosis = Diagnosis(
            status=DiagnosisStatus.OBSERVED,
            incident="",
            hypothesis="",
            evidence=[],
            validation=[],
            rollback="",
        )
        with self._sessions.begin() as session:
            record = session.scalar(
                select(IncidentRecord).where(IncidentRecord.incident_id == incident_id)
            )
            if not record:
                record = IncidentRecord(
                    incident_id=incident_id,
                    status=IncidentStatus.ACKNOWLEDGED,
                    alert=alert,
                    diagnosis=diagnosis.model_dump(mode="json"),
                    attempts=0,
                    updated_at=now,
                    timeline=[self._event(now, "acknowledged")],
                )
                session.add(record)
            else:
                record.alert = alert
                record.diagnosis = diagnosis.model_dump(mode="json")
                record.updated_at = now
                if record.status != IncidentStatus.ACKNOWLEDGED:
                    record.status = IncidentStatus.ACKNOWLEDGED
                    record.timeline = [*record.timeline, self._event(now, "acknowledged")]
        return self._incident(record)

    def claim_incident(
            self,
            incident_id: str,
            alert: dict[str, Any],
    ) -> Incident | None:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.scalar(
                select(IncidentRecord)
                .where(IncidentRecord.incident_id == incident_id)
                .with_for_update()
            )
            if record:
                terminal = record.status in {
                    IncidentStatus.PR_CREATED,
                    IncidentStatus.IGNORED,
                }
                active = record.status in {
                    IncidentStatus.PROCESSING,
                } and record.updated_at > now - _STALE_PROCESSING_AFTER
                if terminal or active:
                    return self._incident(record)
                record.status = IncidentStatus.PROCESSING
                record.alert = alert
                record.attempts += 1
                record.updated_at = now
                record.timeline = [*record.timeline, self._event(now, "reopened")]
                return None

            session.add(IncidentRecord(
                incident_id=incident_id,
                status=IncidentStatus.PROCESSING,
                alert=alert,
                diagnosis=Diagnosis().model_dump(mode="json"),
                attempts=1,
                updated_at=now,
                timeline=[self._event(now, "created")],
            ))
        return None

    def new_incident(self, incident_id: str, alert: dict[str, Any], diagnosis: Diagnosis,
                     status: IncidentStatus) -> Incident:
        with self._sessions() as session:
            record = session.scalar(
                select(IncidentRecord).where(IncidentRecord.incident_id == incident_id)
            )
        incident = self._incident(record)
        incident.alert = alert
        incident.diagnosis = diagnosis
        incident.status = status
        return incident

    def save_incident(self, incident: Incident) -> None:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.get(IncidentRecord, incident.id)
            if not record:
                raise RuntimeError(f"incident not found: {incident.id}")
            record.status = incident.status
            record.alert = incident.alert
            diagnosis = incident.diagnosis.model_dump(mode="json")
            record.diagnosis = diagnosis
            record.diagnosis_history = [
                *(record.diagnosis_history or []),
                {"at": now.isoformat(), "diagnosis": diagnosis},
            ]
            record.pr_url = incident.pull_request_url
            record.updated_at = now
            record.timeline = [*(record.timeline or []), self._event(now, incident.status.value)]

    def mark_replayed(self, incident_id: str, prompt: str | None = None) -> None:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.get(IncidentRecord, incident_id)
            if prompt:
                record.replay_prompts = [*(record.replay_prompts or []), prompt]
            record.status = IncidentStatus.ACKNOWLEDGED
            event = self._event(now, "replayed")
            if prompt:
                event["prompt"] = prompt
            record.replayed_at = now
            record.updated_at = now
            record.timeline = [*record.timeline, event]

    def record_manual_action(self, incident_id: str, result: dict[str, Any]) -> Incident:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.get(IncidentRecord, incident_id)
            if not record:
                raise RuntimeError(f"incident not found: {incident_id}")
            record.manual_actions = [*(record.manual_actions or []), {"at": now.isoformat(), **result}]
            if result.get("status") == "succeeded":
                diagnosis = Diagnosis.model_validate(record.diagnosis)
                diagnosis.evidence = [
                    item for item in diagnosis.evidence
                    if "retried because no completed treatment" not in item
                ]
                diagnosis.status = DiagnosisStatus.VERIFIED
                diagnosis.hypothesis = (
                    f"Manual action completed successfully: {result.get('title', 'operator action')}. "
                    "Waiting for Alertmanager to confirm recovery."
                )
                diagnosis.validation = [
                    *diagnosis.validation,
                    f"Command exited successfully: {result.get('command', 'manual action')}",
                    str(result.get("validation", "Manual action completed successfully.")),
                ]
                record.diagnosis = diagnosis.model_dump(mode="json")
                record.status = IncidentStatus.PENDING
            record.updated_at = now
            record.timeline = [*record.timeline, self._event(now, "manual_action_executed")]
            return self._incident(record)

    def mark_failed(self, incident_id: str, alert: dict[str, Any], error: Exception) -> None:
        now = self._now()
        diagnosis = Diagnosis(
            status=DiagnosisStatus.BLOCKED,
            incident="alert investigation failed",
            hypothesis=f"The investigation could not complete: {type(error).__name__}.",
            evidence=["The incident can be retried because no completed treatment was recorded."],
            validation=["No fix was proposed."],
            rollback="No change was made.",
        )
        with self._sessions.begin() as session:
            record = session.scalar(
                select(IncidentRecord).where(IncidentRecord.incident_id == incident_id)
            )
            if not record:
                raise RuntimeError("incident disappeared before failure was saved")
            previous_diagnosis = Diagnosis.model_validate(record.diagnosis)
            record.status = IncidentStatus.FAILED
            record.alert = alert
            diagnosis.manual_actions = previous_diagnosis.manual_actions
            record.diagnosis = diagnosis.model_dump(mode="json")
            record.diagnosis_history = [
                *(record.diagnosis_history or []),
                {"at": now.isoformat(), "diagnosis": record.diagnosis},
            ]
            record.updated_at = now
            record.timeline = [*record.timeline, self._event(now, "failed")]

    def resolve_incident(self, incident_id: str, alert: dict[str, Any]) -> Incident | None:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.scalar(
                select(IncidentRecord).where(IncidentRecord.incident_id == incident_id)
            )
            if not record:
                return None
            record.status = IncidentStatus.RESOLVED
            record.alert = alert
            record.updated_at = now
            record.timeline = [*record.timeline, self._event(now, "resolved")]
            return self._incident(record)

    def ignore_incident(self, incident_id: str) -> Incident:
        now = self._now()
        with self._sessions.begin() as session:
            record = session.get(IncidentRecord, incident_id)
            if not record:
                raise RuntimeError(f"incident not found: {incident_id}")
            record.status = IncidentStatus.IGNORED
            record.updated_at = now
            record.timeline = [*record.timeline, self._event(now, "ignored")]
            return self._incident(record)

    def delete_incident(self, incident_id: str) -> None:
        with self._sessions.begin() as session:
            record = session.get(IncidentRecord, incident_id)
            if not record:
                raise RuntimeError(f"incident not found: {incident_id}")
            session.delete(record)

    def list_incidents(
            self,
            limit: int = 50,
            source: AlertSource | None = None,
            status: IncidentStatus | None = None,
    ) -> list[Incident]:
        with self._sessions() as session:
            query = select(IncidentRecord)
            if source:
                query = query.where(IncidentRecord.alert.op("->>")("source") == source.value)
            if status:
                query = query.where(IncidentRecord.status == status)
            records = session.scalars(
                query.order_by(IncidentRecord.updated_at.desc()).limit(max(1, min(limit, 200)))
            ).all()
        return [self._incident(record) for record in records]

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._sessions() as session:
            record = session.get(IncidentRecord, incident_id)
            return self._incident(record) if record else None

    def close(self) -> None:
        self.engine.dispose()
