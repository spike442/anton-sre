import asyncio
from types import SimpleNamespace

import server


def test_application_starts(monkeypatch) -> None:
    runtime = SimpleNamespace(
        settings=SimpleNamespace(
            api=SimpleNamespace(allowed_origins=[]),
        ),
        agent_status="idle",
        closed=False,
    )

    def close() -> None:
        runtime.closed = True

    runtime.close = close
    monkeypatch.setattr(server.Settings, "load", lambda: SimpleNamespace(logging=SimpleNamespace(level="INFO")))
    monkeypatch.setattr(server.Runtime, "load", lambda settings=None: runtime)
    monkeypatch.setattr(server, "send_ready", lambda *args: True)

    application = server.create_app()
    health_route = next(route for route in application.routes if route.path == "/healthz")

    async def exercise_lifespan() -> None:
        async with application.router.lifespan_context(application):
            assert health_route.endpoint() == {"status": "ok", "version": "1.0.0"}

    asyncio.run(exercise_lifespan())

    assert runtime.closed is True
