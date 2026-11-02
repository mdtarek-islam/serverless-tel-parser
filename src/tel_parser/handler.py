"""AWS Lambda entry point behind an API Gateway HTTP API.

Request body (JSON):
    {"game": "overwatch" | "marvel_rivals",
     "image_base64": "<PNG or JPEG>"  or  "s3_key": "<object key>",
     "match_id": "<optional; rows are stored when present>"}

Response body (JSON):
    {"game": ..., "rows": [...], "persisted": int,
     "timing": {"cold_start": bool, "init_ms": float, "invoke_ms": float}}
"""

from __future__ import annotations

# Start the init clock before the heavy imports below.
from .cold_start import RECORDER  # isort: skip

import base64
import binascii
import io
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from PIL import Image, UnidentifiedImageError

from .config import Settings
from .extractor import Recogniser, extract
from .inference import RECOGNISER
from .layouts import GAMES
from .storage import StatsWriter

SETTINGS = Settings.from_env()
logging.basicConfig(level=SETTINGS.log_level)
LOGGER = logging.getLogger("tel_parser")
WRITER = StatsWriter(SETTINGS.table_name, region=SETTINGS.aws_region) if SETTINGS.table_name else None
RECORDER.mark_init_complete()

FetchS3 = Callable[[str, str], bytes]


class RequestError(Exception):
    """A client error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def _fetch_s3(bucket: str, key: str) -> bytes:
    import boto3

    return boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if not raw:
        raise RequestError("request body is empty")
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        body = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError("request body is not valid JSON") from exc
    if not isinstance(body, dict):
        raise RequestError("request body must be a JSON object")
    return body


def _image_bytes(body: dict[str, Any], settings: Settings, fetch_s3: FetchS3) -> bytes:
    if "image_base64" in body:
        try:
            data = base64.b64decode(str(body["image_base64"]), validate=True)
        except binascii.Error as exc:
            raise RequestError("image_base64 is not valid base64") from exc
    elif "s3_key" in body:
        if not settings.screenshot_bucket:
            raise RequestError("s3_key given but no screenshot bucket is configured")
        data = fetch_s3(settings.screenshot_bucket, str(body["s3_key"]))
    else:
        raise RequestError("provide image_base64 or s3_key")
    if len(data) > settings.max_image_bytes:
        raise RequestError(f"image exceeds {settings.max_image_bytes} bytes", status=413)
    return data


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise RequestError("image could not be decoded") from exc
    return image


def handle(
    event: dict[str, Any],
    recogniser: Recogniser | None,
    writer: StatsWriter | None,
    settings: Settings,
    fetch_s3: FetchS3 = _fetch_s3,
) -> dict[str, Any]:
    """Process one API Gateway event with explicit dependencies."""
    started = time.perf_counter()
    cold = RECORDER.take_cold_flag()
    status = 500
    try:
        body = _parse_body(event)
        game = body.get("game")
        if game not in GAMES:
            raise RequestError(f"game must be one of {list(GAMES)}")
        data = _image_bytes(body, settings, fetch_s3)
        image = _open_image(data)
        if recogniser is None:
            raise RequestError("recogniser model is not loaded", status=503)
        rows = extract(image, game, recogniser)
        match_id = body.get("match_id")
        persisted = writer.put_rows(str(match_id), game, rows) if match_id and writer else 0
        status = 200
        payload: dict[str, Any] = {"game": game, "rows": rows, "persisted": persisted}
    except RequestError as exc:
        status = exc.status
        payload = {"error": str(exc)}
    except Exception:
        LOGGER.exception("unhandled error")
        payload = {"error": "internal error"}

    timing = {
        "cold_start": cold,
        "init_ms": round(RECORDER.init_ms or 0.0, 2),
        "invoke_ms": round((time.perf_counter() - started) * 1000.0, 2),
    }
    LOGGER.info(json.dumps({"event": "parse", "status": status, **timing}))
    payload["timing"] = timing
    return _response(status, payload)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point. Image CMD: tel_parser.handler.handler."""
    return handle(event, RECOGNISER, WRITER, SETTINGS)
