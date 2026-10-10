from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthz")
@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    runtime = request.app.state.runtime
    return {"status": "ok", "version": runtime.settings.version}
