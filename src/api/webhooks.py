import hashlib
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request

from api.auth import require_control_auth
from application.workflow import _alert_text, handle_alert
from domain.enums import AgentStatus, AlertSource, AlertStatus, GatusEventStatus
from domain.incident import alert_id, normalize_alert
from integrations.discord import send_status


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _gatus_alert(payload: dict) -> dict:
    try:
        status = GatusEventStatus(str(payload.get("status", "")).upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid Gatus alert status")
    group = str(payload.get("endpoint_group", "unknown"))
    name = str(payload.get("endpoint_name", "unknown"))
    description = str(payload.get("description", "Gatus endpoint alert"))
    url = str(payload.get("endpoint_url", ""))
    summary = f"Gatus endpoint {name} is {status.value.lower()}"
    identity = f"gatus:{group}:{name}".encode()
    return {
        "status": AlertStatus.RESOLVED if status == GatusEventStatus.RESOLVED else AlertStatus.FIRING,
        "labels": {"alertname": "GatusEndpointAlert", "source": "gatus", "group": group, "name": name, "severity": "critical"},
        "annotations": {"summary": summary, "description": f"{description} URL={url}".strip()},
        "fingerprint": hashlib.sha256(identity).hexdigest()[:32],
    }


@router.post("/alerts")
def alerts(request: Request, payload: dict, source: AlertSource = Query(...), authorization: str | None = Header(default=None)) -> dict:
    runtime = request.app.state.runtime
    settings = runtime.settings
    require_control_auth(request, authorization)
    if source == AlertSource.GATUS:
        incoming_alerts = [_gatus_alert(payload)]
    elif source == AlertSource.ALERTMANAGER:
        incoming_alerts = payload.get("alerts")
        if not isinstance(incoming_alerts, list):
            raise HTTPException(status_code=400, detail="Alertmanager payload must contain alerts")
    else:
        raise HTTPException(status_code=400, detail="unsupported alert source")
    incoming_alerts = [
        {**normalize_alert(alert), "source": source.value}
        for alert in incoming_alerts
    ]
    results = []
    acknowledged = []
    resolved = []
    for alert in incoming_alerts:
        if alert.get("status") == AlertStatus.RESOLVED:
            incident = runtime.state.resolve_incident(alert_id(alert), alert)
            if incident:
                resolved.append(incident.as_dict())
            continue
        if runtime.agent_status == AgentStatus.IDLE:
            acknowledged.append(runtime.state.acknowledge_incident(alert_id(alert), alert).as_dict())
            continue
        try:
            results.append(handle_alert(runtime, alert).as_dict())
        except Exception as exc:
            logger.exception("alert workflow failed")
            try:
                send_status(settings, "error", alert, _alert_text(alert), str(exc)[:500])
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Anton workflow failed: {type(exc).__name__}") from exc
    return {
        "processed": len(results),
        "acknowledged": len(acknowledged),
        "resolved": len(resolved),
        "mode": "idle" if acknowledged and not results else "active",
        "incidents": [*acknowledged, *resolved, *results],
    }
