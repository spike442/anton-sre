import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from hive_common.cors import ConfiguredCORSMiddleware
from hive_common.logging import configure_logging
from hive_common.version import package_version

from sensei.api.health import router as health_router
from sensei.api.reviews import router as reviews_router
from sensei.bootstrap.runtime import Runtime
from sensei.infrastructure.config import Settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resolved_settings = Settings.load()
        configure_logging(
            resolved_settings.logging.level, ("httpx", "httpcore", "boto3", "botocore", "openai", "openai._base_client")
        )
        runtime = Runtime.load(resolved_settings)
        app.state.runtime = runtime
        poller_task = asyncio.create_task(runtime.poller.run_forever())
        try:
            yield
        finally:
            poller_task.cancel()
            await asyncio.gather(poller_task, return_exceptions=True)
            runtime.close()

    application = FastAPI(title="Sensei", version=package_version("sensei"), lifespan=lifespan)
    application.include_router(health_router)
    application.include_router(reviews_router)
    return application


app = create_app()


def allowed_origins(request):
    runtime = getattr(request.app.state, "runtime", None)
    return runtime.settings.api.allowed_origins if runtime else ()


app.add_middleware(
    ConfiguredCORSMiddleware,
    allowed_origins=allowed_origins,
    methods=("DELETE", "GET", "POST", "OPTIONS"),
    allowed_headers=("Authorization", "Content-Type"),
)
