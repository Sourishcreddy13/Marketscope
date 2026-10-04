from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

request_correlation_id: ContextVar[str] = ContextVar("request_correlation_id", default="-")

# Native structured attributes that callers pass through `logger.info(msg, extra={...})`.
STRUCTURED_FIELDS = ("method", "path", "status_code", "duration_ms", "actor_id", "event")
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = request_correlation_id.get()
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id,
            "request_correlation_id": correlation_id,
        }
        for name in STRUCTURED_FIELDS:
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def sanitize_correlation_id(candidate: str | None) -> str:
    """Accept a caller-supplied request ID only if it is short and log-safe; otherwise mint one."""
    if candidate and _SAFE_CORRELATION_ID.fullmatch(candidate):
        return candidate
    return new_correlation_id()
