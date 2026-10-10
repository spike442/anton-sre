import asyncio
from types import SimpleNamespace

import server


def test_app_starts(monkeypatch):
    config = SimpleNamespace(
        logging=SimpleNamespace(level="INFO"),
        health=SimpleNamespace(timeout_seconds=3),
        agents=[],
        api=SimpleNamespace(allowed_origins=[]),
        database_dsn="",
    )

    class Store:
        def __init__(self, database_dsn, agent_names):
            pass

        def ensure_agents(self):
            pass

        def close(self):
            pass

    class Health:
        def __init__(self, timeout_seconds):
            pass

        def close(self):
            pass

    monkeypatch.setattr(server.Settings, "load", lambda: config)
    monkeypatch.setattr(server, "AgentStore", Store)
    monkeypatch.setattr(server, "AgentHealth", Health)

    application = server.create_app()

    async def exercise_lifespan() -> None:
        async with application.router.lifespan_context(application):
            assert application.state.settings is config
            assert application.state.agent_service is not None

    asyncio.run(exercise_lifespan())
