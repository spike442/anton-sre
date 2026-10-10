import asyncio
from types import SimpleNamespace

import sensei.server as server


def test_app_starts(monkeypatch):
    config = SimpleNamespace(
        logging=SimpleNamespace(level="INFO"),
        api=SimpleNamespace(allowed_origins=[]),
        version="1.0.0",
    )

    async def run_forever():
        await asyncio.Event().wait()

    runtime = SimpleNamespace(
        settings=config,
        poller=SimpleNamespace(run_forever=run_forever),
        close=lambda: None,
    )
    monkeypatch.setattr(server.Settings, "load", lambda: config)
    monkeypatch.setattr(server.Runtime, "load", lambda settings: runtime)
    application = server.create_app()

    async def exercise_lifespan() -> None:
        async with application.router.lifespan_context(application):
            assert application.state.runtime is runtime

    asyncio.run(exercise_lifespan())
