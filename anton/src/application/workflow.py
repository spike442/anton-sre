import logging
import re
from typing import Any

from bootstrap.runtime import Runtime
from domain.diagnosis import Diagnosis
from domain.enums import DiagnosisStatus, IncidentStatus
from domain.incident import Incident, alert_id
from hive_common.logging import log_payload
from infrastructure.config import Settings
from integrations.discord import send_status
from integrations.github import GitHubApp

from application.agent import diagnose

logger = logging.getLogger(__name__)


def _sync_repository(settings: Settings, alert_id: str) -> None:
    logger.info("agent.step input alert_id=%s step=repository_sync", alert_id)
    github = GitHubApp(settings)
    try:
        result = github.sync_repository()
    finally:
        github.close()
    logger.info("agent.step output alert_id=%s step=repository_sync result=%s", alert_id, log_payload(result))


def _notify(
    settings: Settings,
    stage: str,
    alert: dict[str, Any],
    incident: str,
    hypothesis: str = "",
    pull_request_url: str | None = None,
    confidence: str = "unknown",
    risk: str = "unknown",
) -> None:
    try:
        send_status(settings, stage, alert, incident, hypothesis, pull_request_url, confidence, risk)
    except Exception:
        # Discord failure must not turn a successfully created PR into a failed run.
        pass


def _alert_text(alert: dict[str, Any]) -> str:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    lines = [
        "Investigate this monitoring alert.",
        "",
        f"Source: {alert.get('source', labels.get('source', 'unknown'))}",
        f"Status: {alert.get('status', 'unknown')}",
        "",
        "Labels:",
    ]
    lines.extend(f"- {name}: {value}" for name, value in sorted(labels.items()))
    if not labels:
        lines.append("- none")
    lines.append("")
    lines.append("Annotations:")
    lines.extend(f"- {name}: {value}" for name, value in sorted(annotations.items()))
    if not annotations:
        lines.append("- none")
    for name in ("startsAt", "endsAt", "generatorURL"):
        if alert.get(name):
            lines.append(f"{name}: {alert[name]}")
    return "\n".join(lines)


def _valid_change(settings: Settings, diagnosis: Diagnosis) -> bool:
    changes = diagnosis.proposed_changes
    if not changes or diagnosis.status != DiagnosisStatus.PROPOSED:
        return False
    if not diagnosis.validation or not diagnosis.rollback or not diagnosis.evidence:
        return False
    secret_material = re.compile("|".join(f"(?:{pattern})" for pattern in settings.secret_material_patterns))
    for change in changes:
        if secret_material.search(change.content):
            return False
    return True


def _replay_history(incident: Incident) -> str:
    """Build a compact, explicit context block for an operator replay."""
    lines = ["Previous attempts for this incident:"]
    for prompt in incident.replay_prompts:
        lines.append(f"- Operator replay instruction: {prompt}")
    for entry in incident.diagnosis_history[-5:]:
        diagnosis = entry.get("diagnosis", {})
        lines.append(f"- Diagnosis at {entry.get('at', 'unknown')}: status={diagnosis.get('status', 'unknown')}")
        if diagnosis.get("hypothesis"):
            lines.append(f"  hypothesis: {diagnosis['hypothesis']}")
        if diagnosis.get("proposed_files"):
            lines.append(f"  proposed files: {', '.join(diagnosis['proposed_files'])}")
        if diagnosis.get("manual_actions"):
            lines.append("  manual actions were proposed")
    return "\n".join(lines)


def _block_incident(runtime: Runtime, incident: Incident, alert: dict[str, Any], diagnosis: Diagnosis) -> Incident:
    incident.status = IncidentStatus.BLOCKED
    logger.info("incident updated incident_id=%s status=%s", incident.id, incident.status)
    runtime.state.save_incident(incident)
    _notify(
        runtime.settings,
        incident.status,
        alert,
        diagnosis.incident,
        diagnosis.hypothesis,
        confidence=diagnosis.confidence,
        risk=diagnosis.risk,
    )
    return incident


def _create_pull_request(settings: Settings, diagnosis: Diagnosis) -> str:
    changes = diagnosis.proposed_changes
    labels = [f"confidence:{diagnosis.confidence}", f"risk:{diagnosis.risk}"]
    logger.info(
        "alert.step input step=create_pr changes=%s labels=%s",
        log_payload(
            [
                {
                    "file_path": change.file_path,
                    "content_length": len(change.content),
                    "title": change.title,
                    "body_length": len(change.body),
                }
                for change in changes
            ]
        ),
        labels,
    )
    github = GitHubApp(settings)
    try:
        pull_request = github.create_pull_request(
            changes,
            changes[0].title,
            changes[0].body,
            labels=labels,
        )
    finally:
        github.close()
    return pull_request["html_url"]


def handle_alert(
    runtime: Runtime,
    alert: dict[str, Any],
    replay_prompt: str | None = None,
    prior_incident: Incident | None = None,
) -> Incident:
    settings = runtime.settings
    prompt_store = runtime.prompts
    current_alert_id = alert_id(alert)
    existing = runtime.state.claim_incident(current_alert_id, alert)
    if existing:
        logger.info(
            "alert deduplicated fingerprint=%s incident_id=%s status=%s", current_alert_id, existing.id, existing.status
        )
        _notify(
            settings,
            "deduplicated",
            alert,
            existing.diagnosis.incident,
            existing.diagnosis.hypothesis,
            existing.pull_request_url,
            existing.diagnosis.confidence,
            existing.diagnosis.risk,
        )
        return existing

    logger.info("alert.step input alert_id=%s step=received alert=%s", current_alert_id, log_payload(alert))
    question = _alert_text(alert)
    if replay_prompt:
        question = f"{question}\n\n{_replay_history(prior_incident) if prior_incident else ''}"
    logger.info("alert.step output alert_id=%s step=received question=%s", current_alert_id, question)
    try:
        _sync_repository(settings, current_alert_id)
        diagnosis = diagnose(
            settings,
            question,
            prompt_store,
            runtime.agent,
            current_alert_id,
            replay_prompt=replay_prompt,
        )
        logger.info(
            "alert.step output alert_id=%s step=diagnosis result=%s",
            current_alert_id,
            log_payload(diagnosis.model_dump()),
        )
        logger.info(
            "alert investigated incident=%s risk=%s confidence=%s",
            diagnosis.incident,
            diagnosis.risk,
            diagnosis.confidence,
        )
        incident = runtime.state.new_incident(current_alert_id, alert, diagnosis, IncidentStatus.PROCESSING)
        if not _valid_change(settings, diagnosis):
            return _block_incident(runtime, incident, alert, diagnosis)
        incident.pull_request_url = _create_pull_request(settings, diagnosis)
        incident.status = IncidentStatus.PR_CREATED
        logger.info("incident updated incident_id=%s status=%s", incident.id, incident.status)
        runtime.state.save_incident(incident)
        _notify(
            settings,
            incident.status,
            alert,
            diagnosis.incident,
            diagnosis.hypothesis,
            incident.pull_request_url,
            diagnosis.confidence,
            diagnosis.risk,
        )
        return incident
    except Exception as exc:
        runtime.state.mark_failed(current_alert_id, alert, exc)
        raise
