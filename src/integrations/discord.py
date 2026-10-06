from typing import Any

import httpx

from infrastructure.config import Settings
from domain.enums import AgentStatus, IncidentStatus


_INCIDENT_STYLE = {
    IncidentStatus.PR_CREATED: ("✅ Anton created a pull request", 0x2ECC71),
    IncidentStatus.BLOCKED: ("⚠️ Anton blocked the proposed fix", 0xF1C40F),
    "error": ("🚨 Anton workflow failed", 0xE74C3C),
    "deduplicated": ("ℹ️ Anton updated an existing incident", 0x3498DB),
}


def _clip(value: object, limit: int) -> str:
    text = str(value or "N/A")
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _send(settings: Settings, payload: dict[str, Any]) -> bool:
    if not settings.discord_webhook_url:
        return False
    response = httpx.post(
        settings.discord_webhook_url,
        json={"username": "Anton", **payload},
        timeout=15,
    )
    if response.is_error:
        detail = _clip(response.text, 300)
        raise RuntimeError(f"Discord webhook rejected status={response.status_code} detail={detail}")
    return True


def send_status(settings: Settings, stage: str, alert: dict[str, Any], incident: str,
                hypothesis: str = "", pull_request_url: str | None = None,
                confidence: str = "unknown", risk: str = "unknown") -> bool:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    title, color = _INCIDENT_STYLE.get(stage, (f"🔎 Anton: {stage}", 0x5865F2))
    fields = [
        {"name": "Alert", "value": f"`{_clip(labels.get('alertname', 'unknown'), 256)}`", "inline": True},
        {"name": "Severity", "value": _clip(labels.get("severity", "unknown"), 256), "inline": True},
        {"name": "Confidence", "value": _clip(confidence, 256), "inline": True},
        {"name": "Risk", "value": _clip(risk, 256), "inline": True},
        {"name": "Incident", "value": _clip(incident, 1024), "inline": False},
    ]
    if labels.get("namespace") or labels.get("pod"):
        fields.append({
            "name": "Workload",
            "value": _clip(f"namespace={labels.get('namespace', 'N/A')} pod={labels.get('pod', 'N/A')}", 1024),
            "inline": False,
        })
    if hypothesis:
        fields.append({"name": "Hypothesis", "value": _clip(hypothesis, 1024), "inline": False})
    if annotations.get("description"):
        fields.append({"name": "Alert details", "value": _clip(annotations["description"], 1024), "inline": False})
    if pull_request_url:
        fields.append({"name": "Pull request", "value": f"[Open the PR]({pull_request_url})", "inline": False})
    return _send(settings, {"embeds": [{
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {"text": "Anton SRE Agent"},
    }]})


def send_ready(settings: Settings, status: AgentStatus) -> bool:
    idle = status == AgentStatus.IDLE
    return _send(settings, {"embeds": [{
        "title": "🟠 I'm idle" if idle else "🟢 I'm up",
        "color": 0xF1C40F if idle else 0x2ECC71,
    }]})
