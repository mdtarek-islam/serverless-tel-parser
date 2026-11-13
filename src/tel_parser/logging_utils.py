"""One JSON object per line on stdout for the ``tel_parser`` logger tree.

Callers pass only safe fields: ids, counts, sizes, codes and class names.
Never pass a request body, image data, an S3 key or an exception message
built from input.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

LOGGER_NAME = "tel_parser"
_FIELDS_ATTR = "tel_fields"


class JsonFormatter(logging.Formatter):
    """Render a record as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, _FIELDS_ATTR, None)
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
        }
        if isinstance(fields, dict):
            payload["event"] = record.msg
            payload.update(fields)
        else:
            payload["event"] = "log"
            payload["logger"] = record.name
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["stack"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


class StdoutHandler(logging.Handler):
    """Write to the current ``sys.stdout`` at emit time."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:  # pragma: no cover - logging must never break a request
            self.handleError(record)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Attach one JSON handler to ``tel_parser``. Safe to call again."""
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(handler, StdoutHandler) for handler in logger.handlers):
        handler = StdoutHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: bool | BaseException | None = None,
    **fields: Any,
) -> None:
    """Log one named event with structured fields. ``exc_info`` adds a stack."""
    logger.log(level, event, exc_info=exc_info, extra={_FIELDS_ATTR: fields})
