"""AWS Lambda entry point behind an API Gateway HTTP API.

Request body (JSON), no other keys:
    {"game": "overwatch" | "marvel_rivals",
     "image_base64": "<PNG or JPEG>"  or  "s3_key": "<object key>",
     "match_id": "<optional; rows are stored when present>"}

Response body (JSON):
    200: {"game", "rows", "persisted", "persistence", "request_id", "timing"}
    4xx and 5xx: {"error", "code", "request_id", "timing"}
    ``timing`` holds {"cold_start": bool, "init_ms": float, "invoke_ms": float}.
"""

from __future__ import annotations

# Start the init clock before the heavy imports below.
from .cold_start import RECORDER  # isort: skip

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol

from PIL import Image

from .config import Settings
from .errors import RequestError, StorageError, too_large
from .extractor import Recogniser, extract
from .fallback import FailedWriteQueue
from .imaging import open_image
from .inference import RECOGNISER
from .layouts import resolve_layout
from .logging_utils import configure_logging, log_event
from .s3io import fetch_object
from .storage import StatsWriter
from .validation import ParseRequest, decode_image_base64, parse_request

SETTINGS = Settings.from_env()
LOGGER = configure_logging(SETTINGS.log_level)
WRITER = StatsWriter(SETTINGS.table_name, region=SETTINGS.aws_region) if SETTINGS.table_name else None
QUEUE = (
    FailedWriteQueue(SETTINGS.failed_writes_queue_url, region=SETTINGS.aws_region)
    if SETTINGS.failed_writes_queue_url
    else None
)
RECORDER.mark_init_complete()

FetchS3 = Callable[[str, str, int], bytes]
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:=-]{1,128}")
_HEADERS = {
    "content-type": "application/json",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
}

__all__ = ["FetchS3", "RequestError", "handle", "handler"]


class RowWriter(Protocol):
    """Anything that stores rows like StatsWriter."""

    def put_rows(self, match_id: str, game: str, rows: list[dict[str, Any]]) -> int: ...


def _response(status: int, body: dict[str, Any], request_id: str) -> dict[str, Any]:
    return {"statusCode": status, "headers": {**_HEADERS, "x-request-id": request_id}, "body": json.dumps(body)}


def _valid_id(value: Any) -> str | None:
    return value if isinstance(value, str) and _REQUEST_ID.fullmatch(value) else None


def _request_id(event: Any, context: Any) -> str:
    request_context = event.get("requestContext") if isinstance(event, dict) else None
    from_event = _valid_id(request_context.get("requestId")) if isinstance(request_context, dict) else None
    return from_event or _valid_id(getattr(context, "aws_request_id", None)) or str(uuid.uuid4())


def _image_data(request: ParseRequest, settings: Settings, fetch_s3: FetchS3) -> bytes:
    if request.image_base64 is not None:
        return decode_image_base64(request.image_base64)
    if request.s3_key is None:  # pragma: no cover - parse_request sets exactly one source
        raise RequestError("provide exactly one of image_base64 or s3_key")
    return fetch_s3(settings.screenshot_bucket, request.s3_key, settings.max_image_bytes)


def _persist(
    request: ParseRequest,
    rows: list[dict[str, Any]],
    writer: RowWriter | None,
    queue: FailedWriteQueue | None,
    request_id: str,
) -> tuple[int, str]:
    if request.match_id is None or writer is None:
        return 0, "skipped"
    try:
        written = writer.put_rows(request.match_id, request.game, rows)
    except StorageError as exc:
        reason = "storage_retryable" if exc.retryable else "storage_failed"
        if queue is not None and queue.send(request.match_id, request.game, rows, request_id, reason):
            return 0, "queued"
        raise RequestError("storage unavailable", status=503, code="storage_unavailable") from exc
    return written, "stored" if written > 0 else "duplicate"


def handle(
    event: Any,
    recogniser: Recogniser | None,
    writer: RowWriter | None,
    settings: Settings,
    fetch_s3: FetchS3 = fetch_object,
    queue: FailedWriteQueue | None = None,
    context: Any = None,
) -> dict[str, Any]:
    """Process one API Gateway event with explicit dependencies."""
    started = time.perf_counter()
    cold = RECORDER.take_cold_flag()
    request_id = _request_id(event, context)
    fields: dict[str, Any] = {
        "game": None,
        "calibrated": None,
        "source": None,
        "image_bytes": None,
        "width": None,
        "height": None,
        "persisted": None,
        "persistence": None,
        "error_code": None,
    }
    status = 500
    fault: BaseException | None = None
    try:
        request = parse_request(event, settings)
        fields["game"] = request.game
        fields["source"] = "inline" if request.image_base64 is not None else "s3"
        if recogniser is None:
            raise RequestError("recogniser model is not loaded", status=503, code="model_unavailable")
        data = _image_data(request, settings, fetch_s3)
        fields["image_bytes"] = len(data)
        image: Image.Image = open_image(data, settings)
        fields["width"], fields["height"] = image.size
        try:
            layout = resolve_layout(request.game, image.width, image.height)
        except ValueError as exc:
            raise RequestError("no layout fits this image", code="bad_layout") from exc
        fields["calibrated"] = layout.calibrated
        rows = extract(image, request.game, recogniser, layout)
        persisted, persistence = _persist(request, rows, writer, queue, request_id)
        fields["persisted"], fields["persistence"] = persisted, persistence
        status = 200
        payload: dict[str, Any] = {
            "game": request.game,
            "rows": rows,
            "persisted": persisted,
            "persistence": persistence,
        }
    except RequestError as exc:
        status, fields["error_code"] = exc.status, exc.code
        payload = {"error": str(exc), "code": exc.code}
        if status >= 500:
            fields["error_type"] = type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__
    except MemoryError as exc:
        error = too_large("request needs too much memory")
        status, fields["error_code"], fields["error_type"] = error.status, error.code, type(exc).__name__
        payload = {"error": str(error), "code": error.code}
    except Exception as exc:
        status, fields["error_code"], fields["error_type"] = 500, "internal_error", type(exc).__name__
        payload = {"error": "internal error", "code": "internal_error"}
        fault = exc

    timing = {
        "cold_start": cold,
        "init_ms": round(RECORDER.init_ms or 0.0, 2),
        "invoke_ms": round((time.perf_counter() - started) * 1000.0, 2),
    }
    level = logging.ERROR if status >= 500 else logging.INFO
    log_event(LOGGER, "parse", level=level, exc_info=fault, request_id=request_id, status=status, **fields, **timing)
    payload["request_id"] = request_id
    payload["timing"] = timing
    return _response(status, payload, request_id)


def handler(event: Any, context: Any) -> dict[str, Any]:
    """Lambda entry point. Image CMD: tel_parser.handler.handler."""
    return handle(event, RECOGNISER, WRITER, SETTINGS, queue=QUEUE, context=context)
