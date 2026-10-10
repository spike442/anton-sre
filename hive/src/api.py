from domain import AgentStatus
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/agents", tags=["agents"])


def _service(request: Request):
    return request.app.state.agent_service


def _control_auth(request: Request, authorization: str | None) -> None:
    token = request.app.state.settings.control_token
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="invalid Hive control authorization")


@router.get("")
def list_agents(request: Request) -> dict[str, list[dict]]:
    return {"agents": [agent.model_dump(mode="json") for agent in _service(request).list_agents()]}


@router.get("/{name}")
def agent_status(name: str, request: Request) -> dict:
    try:
        return _service(request).status(name).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not configured") from exc


@router.post("/{name}/idle")
def set_idle(name: str, request: Request, authorization: str | None = Header(default=None)) -> dict:
    _control_auth(request, authorization)
    try:
        return _service(request).set_status(name, AgentStatus.IDLE).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not configured") from exc


@router.post("/{name}/active")
def set_active(name: str, request: Request, authorization: str | None = Header(default=None)) -> dict:
    _control_auth(request, authorization)
    try:
        return _service(request).set_status(name, AgentStatus.ACTIVE).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not configured") from exc
