from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from api.auth import require_control_auth
from application.workflow import handle_alert
from integrations.shell import run_approved_action
from domain.enums import AgentStatus, AlertSource, IncidentStatus

router = APIRouter(tags=["incidents"])


class ReplayRequest(BaseModel):
    prompt: str | None = None


class ManualActionRequest(BaseModel):
    action_index: int


@router.get("/incidents")
def incidents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    source: AlertSource | None = Query(default=None),
    status: IncidentStatus | None = Query(default=None),
) -> dict:
    found = request.app.state.runtime.state.list_incidents(
        limit=limit,
        source=source,
        status=status,
    )
    return {"incidents": [incident.as_dict() for incident in found]}


@router.get("/incidents/{incident_id}")
def incident(incident_id: str, request: Request) -> dict:
    found = request.app.state.runtime.state.get_incident(incident_id)
    if not found:
        raise HTTPException(status_code=404, detail="incident not found")
    return found.as_dict()


@router.post("/incidents/replay/{incident_id}")
def replay_one(
    incident_id: str,
    request: Request,
    replay: ReplayRequest | None = None,
    authorization: str | None = Header(default=None),
) -> dict:
    require_control_auth(request, authorization)
    runtime = request.app.state.runtime
    if runtime.agent_status == AgentStatus.IDLE:
        raise HTTPException(status_code=409, detail="Anton is idle")
    found = runtime.state.get_incident(incident_id)
    if not found:
        raise HTTPException(status_code=404, detail="incident not found")
    if found.status not in {IncidentStatus.ACKNOWLEDGED, IncidentStatus.FAILED, IncidentStatus.BLOCKED}:
        raise HTTPException(status_code=409, detail=f"incident cannot be replayed from {found.status.value}")
    prompt = (replay.prompt.strip() if replay and replay.prompt else "")
    if found.status == IncidentStatus.BLOCKED and not prompt:
        raise HTTPException(status_code=400, detail="a replay prompt is required for blocked incidents")
    try:
        runtime.state.mark_replayed(found.id, prompt or None)
        return handle_alert(runtime, found.alert, prompt or None, prior_incident=found).as_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"incident replay failed: {type(exc).__name__}") from exc


@router.post("/incidents/{incident_id}/ignore")
def ignore_incident(
    incident_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    require_control_auth(request, authorization)
    try:
        return request.app.state.runtime.state.ignore_incident(incident_id).as_dict()
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc


@router.post("/incidents/{incident_id}/manual-actions/execute")
def execute_manual_action(
    incident_id: str,
    request: Request,
    action: ManualActionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    require_control_auth(request, authorization)
    runtime = request.app.state.runtime
    found = runtime.state.get_incident(incident_id)
    if not found:
        raise HTTPException(status_code=404, detail="incident not found")
    if found.status != IncidentStatus.BLOCKED:
        raise HTTPException(status_code=409, detail="manual actions are only available for blocked incidents")
    if action.action_index < 0 or action.action_index >= len(found.diagnosis.manual_actions):
        raise HTTPException(status_code=400, detail="manual action does not exist")
    selected = found.diagnosis.manual_actions[action.action_index]
    try:
        result = run_approved_action(selected.command, cwd=str(runtime.settings.repo_path))
    except (ValueError, OSError, TimeoutError) as exc:
        result = {"action_index": action.action_index, "title": selected.title,
                  "command": selected.command, "status": "rejected", "error": str(exc)}
        return runtime.state.record_manual_action(incident_id, result).as_dict()
    result.update({"action_index": action.action_index, "title": selected.title,
                   "validation": selected.validation,
                   "status": "succeeded" if result["exit_code"] == 0 else "failed"})
    return runtime.state.record_manual_action(incident_id, result).as_dict()


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(
    incident_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    require_control_auth(request, authorization)
    try:
        request.app.state.runtime.state.delete_incident(incident_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc
