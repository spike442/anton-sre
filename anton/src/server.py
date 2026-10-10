import logging
from contextlib import asynccontextmanager

from api.incidents import router as incidents_router
from api.webhooks import router as webhooks_router
from bootstrap.runtime import Runtime
from fastapi import FastAPI
from hive_common.cors import ConfiguredCORSMiddleware
from hive_common.logging import configure_logging
from hive_common.version import package_version
from infrastructure.config import Settings
from integrations.discord import send_ready

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = Settings.load()
        configure_logging(settings.logging.level, ("httpx", "httpcore", "openai", "openai._base_client"))
        logger.info("Anton SRE agent starting version=%s", package_version("anton"))
        runtime = Runtime.load(settings)
        app.state.runtime = runtime
        try:
            send_ready(runtime.settings, runtime.agent_status)
        except Exception:
            logger.exception("runtime loaded but Discord ready notification failed")
        try:
            yield
        finally:
            runtime.close()

    application = FastAPI(title="Anton SRE agent", lifespan=lifespan)

    def allowed_origins(request):
        runtime = getattr(request.app.state, "runtime", None)
        return runtime.settings.api.allowed_origins if runtime else ()

    application.add_middleware(
        ConfiguredCORSMiddleware,
        allowed_origins=allowed_origins,
        methods=("DELETE", "GET", "POST", "OPTIONS"),
        allowed_headers=("Authorization", "Content-Type"),
    )

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": package_version("anton")}

    application.include_router(incidents_router)
    application.include_router(webhooks_router)
    return application


app = create_app()
