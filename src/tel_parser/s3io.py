"""Bounded S3 object reads. boto3 loads on first use only."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .errors import RequestError, too_large
from .logging_utils import log_event

LOGGER = logging.getLogger("tel_parser.s3io")
_MISSING_CODES = frozenset({"NoSuchKey", "404", "AccessDenied", "403"})

_client: Any = None
_lock = threading.Lock()


def _build_client() -> Any:
    import boto3
    from botocore.config import Config

    config = Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2})
    return boto3.client("s3", config=config)


def get_client() -> Any:
    """Return the module client. Build it once, on first use."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _build_client()
    return _client


def set_client(client: Any) -> None:
    """Replace the module client. Pass None to rebuild on next use."""
    global _client
    with _lock:
        _client = client


def _error_code(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict):
            code = error.get("Code")
            return str(code) if code is not None else None
    return None


def _declared_length(response: dict[str, Any]) -> int | None:
    length = response.get("ContentLength")
    return length if isinstance(length, int) and not isinstance(length, bool) else None


def fetch_object(bucket: str, key: str, max_bytes: int, client: Any = None) -> bytes:
    """Return the object bytes. Never read more than ``max_bytes + 1`` bytes.

    Raise RequestError: 413 over the cap, 404 missing or denied, 503 for
    any other store or network fault.
    """
    try:
        response = (client if client is not None else get_client()).get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            length = _declared_length(response)
            if length is not None and length > max_bytes:
                raise too_large("screenshot exceeds the byte cap")
            data = body.read(max_bytes + 1)
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()
    except RequestError:
        raise
    except Exception as exc:
        if _error_code(exc) in _MISSING_CODES:
            raise RequestError("screenshot not found", status=404, code="not_found") from exc
        log_event(LOGGER, "s3_fetch_failed", level=logging.WARNING, error_type=type(exc).__name__)
        raise RequestError("screenshot store unavailable", status=503, code="s3_unavailable") from exc
    if len(data) > max_bytes:
        raise too_large("screenshot exceeds the byte cap")
    return bytes(data)
