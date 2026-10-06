from typing import Any

import httpx


def query_prometheus(prometheus_url: str, query: str, start: str | None = None,
                     end: str | None = None, step: str = "60s") -> dict[str, Any]:
    """Query the configured Prometheus endpoint; never accepts an arbitrary URL."""
    if len(query) > 2000:
        raise ValueError("PromQL query is too long")
    if start or end:
        params: dict[str, str] = {"query": query, "step": step}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        response = httpx.get(f"{prometheus_url.rstrip('/')}/api/v1/query_range", params=params, timeout=15)
    else:
        response = httpx.get(f"{prometheus_url.rstrip('/')}/api/v1/query", params={"query": query}, timeout=15)
    response.raise_for_status()
    payload = response.json()
    encoded = str(payload.get("data", payload))
    return {"status": payload.get("status"), "data": encoded[-12000:],
            "warnings": payload.get("warnings", [])}
