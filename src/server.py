from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from api.agent import router as agent_router
from api.incidents import router as incidents_router
from api.webhooks import router as webhooks_router
from bootstrap.runtime import Runtime, package_version
from infrastructure.logging import configure_logging
from integrations.discord import send_ready


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Anton SRE agent starting version=%s", package_version())
    runtime = Runtime.load()
    app.state.runtime = runtime
    try:
        send_ready(runtime.settings, runtime.agent_status)
    except Exception:
        logger.exception("runtime loaded but Discord ready notification failed")
    try:
        yield
    finally:
        runtime.close()


app = FastAPI(title="Anton SRE agent", lifespan=lifespan)


@app.middleware("http")
async def configured_cors(request, call_next):
    origin = request.headers.get("origin")
    runtime = getattr(request.app.state, "runtime", None)
    allowed = bool(origin and runtime and origin in runtime.settings.api.allowed_origins)
    if request.method == "OPTIONS" and allowed:
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "DELETE, GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Vary"] = "Origin"
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": package_version()}


app.include_router(agent_router)
app.include_router(incidents_router)
app.include_router(webhooks_router)

static_candidates = (
    Path(__file__).resolve().parent.parent / "static",
    Path.cwd() / "static",
    Path("/app/static"),
)
static_dir = next((candidate for candidate in static_candidates if candidate.is_dir()), None)
if static_dir:
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
