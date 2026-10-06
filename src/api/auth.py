from fastapi import Header, HTTPException, Request


def require_control_auth(request: Request, authorization: str | None = Header(default=None)) -> None:
    token = request.app.state.runtime.settings.alert_token
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="invalid alert authorization")
