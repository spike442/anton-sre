"""Provider-neutral application logging helpers."""

import json
import logging
from collections.abc import Iterable
from typing import Any

_SECRET_FIELDS = {
    "api_key",
    "authorization",
    "cookie",
    "password",
    "private_key",
    "secret",
    "secret_access_key",
    "token",
    "access_token",
    "bot_token",
}


def log_payload(value: Any, max_chars: int = 12_000) -> str:
    """Serialize operational data without emitting secret fields."""

    def safe(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                str(key): "<omitted>" if any(part in str(key).lower() for part in _SECRET_FIELDS) else safe(val)
                for key, val in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [safe(value) for value in item]
        return item

    encoded = json.dumps(safe(value), default=str, ensure_ascii=False)
    return encoded if len(encoded) <= max_chars else f"{encoded[:max_chars]}…"


def configure_logging(level: str, quiet_loggers: Iterable[str] = ()) -> None:
    """Configure the application root logger and optional noisy dependencies."""
    resolved_level = level.upper()
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger().setLevel(resolved_level)
    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
