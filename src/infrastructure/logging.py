"""Application logging configuration."""

import json
import logging
from typing import Any


_SECRET_FIELDS = {
    "api_key", "authorization", "cookie", "password", "private_key", "secret",
    "secret_access_key", "token", "access_token", "bot_token",
}


def log_payload(value: Any, max_chars: int = 12_000) -> str:
    """Serialize operational data for logs without emitting secret fields."""
    def safe(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                str(key): "<omitted>" if any(part in str(key).lower() for part in _SECRET_FIELDS)
                else safe(val)
                for key, val in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [safe(value) for value in item]
        return item

    encoded = json.dumps(safe(value), default=str, ensure_ascii=False)
    return encoded if len(encoded) <= max_chars else f"{encoded[:max_chars]}…"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for logger_name in ("httpx", "httpcore", "openai", "openai._base_client"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
