import logging
from contextlib import asynccontextmanager
from pathlib import Path

from api import router as agents_router
from application import AgentService
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from health import AgentHealth
from hive_common.cors import ConfiguredCORSMiddleware
from hive_common.logging import configure_logging
from hive_common.version import package_version
from infrastructure import Settings
from sql import AgentStore

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        settings = Settings.load()
        configure_logging(settings.logging.level)
        store = AgentStore(settings.database_dsn, [agent.name for agent in settings.agents])
        health = AgentHealth(settings.health.timeout_seconds)
        application.state.settings = settings
        application.state.agent_service = AgentService(settings.agents, store, health)
        try:
            logger.info("Hive loaded version=%s agents=%s", package_version("hive"), len(settings.agents))
            yield
        finally:
            health.close()
            store.close()

    application = FastAPI(title="Hive", version=package_version("hive"), lifespan=lifespan)

    def allowed_origins(request):
        settings = getattr(request.app.state, "settings", None)
        return settings.api.allowed_origins if settings else ()

    application.add_middleware(
        ConfiguredCORSMiddleware,
        allowed_origins=allowed_origins,
        methods=("GET", "POST", "OPTIONS"),
        allowed_headers=("Authorization", "Content-Type"),
    )

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": package_version("hive")}

    @application.get("/version")
    def version() -> dict[str, str]:
        return {"version": package_version("hive")}

    application.include_router(agents_router)
    static_dir = Path(__file__).resolve().parents[1] / "ui" / "dist"
    if static_dir.is_dir():
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return application


app = create_app()
