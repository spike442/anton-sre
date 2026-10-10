"""CORS policy helpers and middleware shared by Hive services."""

from collections.abc import Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def headers_for(
    origin: str | None,
    allowed_origins: Iterable[str],
    methods: Iterable[str],
    allowed_headers: Iterable[str],
) -> dict[str, str] | None:
    """Return CORS response headers when *origin* is explicitly allowed."""
    if not origin or origin not in set(allowed_origins):
        return None
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": ", ".join(methods),
        "Access-Control-Allow-Headers": ", ".join(allowed_headers),
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


class ConfiguredCORSMiddleware(BaseHTTPMiddleware):
    """Apply a runtime-provided, allow-list CORS policy to a service."""

    def __init__(
        self,
        app,
        allowed_origins: Callable[[Request], Iterable[str]],
        methods: Iterable[str],
        allowed_headers: Iterable[str],
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins
        self.methods = tuple(methods)
        self.allowed_headers = tuple(allowed_headers)

    async def dispatch(self, request: Request, call_next) -> Response:
        cors_headers = headers_for(
            request.headers.get("origin"),
            self.allowed_origins(request),
            self.methods,
            self.allowed_headers,
        )
        if request.method == "OPTIONS" and cors_headers:
            response = Response(status_code=204)
        else:
            response = await call_next(request)
        if cors_headers:
            response.headers.update(cors_headers)
        return response
