"""Small, vendor-neutral logging helpers for evaluator lifecycle events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
import json
import logging
from pathlib import Path
import sys
from typing import Any, Literal, TextIO
from uuid import UUID


PACKAGE_LOGGER_NAME = "single_pass_parsing_ranker"
SERVICE_NAME = "single-pass-parsing-model-ranker"
LogFormat = Literal["human", "json"]

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
_RESERVED_FIELDS = {"timestamp", "level", "service", "event", "message"}

logging.getLogger(PACKAGE_LOGGER_NAME).addHandler(logging.NullHandler())


def configure_logging(
    *,
    level: str = "INFO",
    log_format: LogFormat | str = "human",
    stream: TextIO | None = None,
) -> None:
    """Configure this package's logs without changing the root logger."""

    normalized_level = level.upper()
    if normalized_level not in _LOG_LEVELS:
        raise ValueError(f"Unknown log level: {level}")

    normalized_format = log_format.lower()
    if normalized_format not in ("human", "json"):
        raise ValueError(f"Unknown log format: {log_format}")

    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    for handler in tuple(package_logger.handlers):
        if getattr(handler, "_sppr_managed", False):
            package_logger.removeHandler(handler)
            handler.close()

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler._sppr_managed = True  # type: ignore[attr-defined]
    if normalized_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    package_logger.addHandler(handler)
    package_logger.setLevel(_LOG_LEVELS[normalized_level])
    package_logger.propagate = False


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **fields: Any,
) -> None:
    """Emit one named event with explicitly selected structured fields."""

    collisions = _RESERVED_FIELDS.intersection(fields)
    if collisions:
        names = ", ".join(sorted(collisions))
        raise ValueError(f"Event fields use reserved names: {names}")

    logger.log(
        level,
        message,
        extra={
            "event": event,
            "event_fields": {
                key: _json_value(value)
                for key, value in fields.items()
                if value is not None
            },
        },
    )


class JsonFormatter(logging.Formatter):
    """Format one log record as a compact JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = _base_payload(record)
        payload.update(getattr(record, "event_fields", {}))
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Format the same event contract for local terminal use."""

    def format(self, record: logging.LogRecord) -> str:
        payload = _base_payload(record)
        fields = getattr(record, "event_fields", {})
        suffix = " ".join(
            f"{key}={json.dumps(value, sort_keys=True, ensure_ascii=False)}"
            for key, value in fields.items()
        )
        line = (
            f"{payload['timestamp']} {payload['level']} "
            f"{payload['event']} {payload['message']}"
        )
        return f"{line} {suffix}" if suffix else line


def _base_payload(record: logging.LogRecord) -> dict[str, Any]:
    timestamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
    return {
        "timestamp": timestamp.replace("+00:00", "Z"),
        "level": record.levelname,
        "service": SERVICE_NAME,
        "event": getattr(record, "event", "log.message"),
        "message": record.getMessage(),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, (UUID, Path, Enum)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(child) for key, child in value.items()}
    return value
