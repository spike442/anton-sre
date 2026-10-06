from fastapi import APIRouter, Header, Request

from api.auth import require_control_auth
from domain.enums import AgentStatus


router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
def agent_status(request: Request) -> dict[str, str]:
    status = request.app.state.runtime.agent_status
    return {
        "agent": request.app.state.runtime.settings.agent_name,
        "status": status.value,
    }


@router.post("/idle")
def set_agent_idle(request: Request, authorization: str | None = Header(default=None)) -> dict[str, str]:
    require_control_auth(request, authorization)
    return request.app.state.runtime.set_agent_status(AgentStatus.IDLE)


@router.post("/active")
def set_agent_active(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    require_control_auth(request, authorization)
    return request.app.state.runtime.set_agent_status(AgentStatus.ACTIVE)
