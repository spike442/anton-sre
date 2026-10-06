from types import SimpleNamespace

from fastapi.testclient import TestClient

import server


def test_application_starts(monkeypatch) -> None:
    runtime = SimpleNamespace(settings=SimpleNamespace(), closed=False)

    def close() -> None:
        runtime.closed = True

    runtime.close = close
    monkeypatch.setattr(server.Runtime, "load", lambda: runtime)
    monkeypatch.setattr(server, "send_ready", lambda *args: True)

    with TestClient(server.app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert runtime.closed is True
