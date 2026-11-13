"""Pure request validation. Runs before any decode, fetch or model work.

Error messages are fixed strings. They never echo request values.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .config import MAX_BODY_CHARS, Settings
from .errors import RequestError, too_large
from .layouts import GAMES

ALLOWED_KEYS = frozenset({"game", "image_base64", "s3_key", "match_id"})
MAX_S3_KEY_BYTES = 1024
_MATCH_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


@dataclass(frozen=True)
class ParseRequest:
    """One validated parse request. Exactly one image source is set."""

    game: str
    image_base64: str | None
    s3_key: str | None
    match_id: str | None


def max_base64_chars(max_image_bytes: int) -> int:
    """Return the longest base64 text that can decode to ``max_image_bytes``."""
    return 4 * math.ceil(max_image_bytes / 3)


def _body_text(event: Any) -> str:
    if not isinstance(event, dict):
        raise RequestError("event must be an object")
    raw = event.get("body")
    if not isinstance(raw, str) or not raw:
        raise RequestError("request body is empty or not text")
    if len(raw) > MAX_BODY_CHARS:
        raise too_large("request body exceeds the size cap")
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (binascii.Error, ValueError) as exc:
            raise RequestError("request body is not valid base64 text") from exc
    return raw


def _body_object(raw: str) -> dict[str, Any]:
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise RequestError("request body is not valid JSON") from exc
    if not isinstance(body, dict):
        raise RequestError("request body must be a JSON object")
    unknown = len(set(body) - ALLOWED_KEYS)
    if unknown:
        raise RequestError(f"request body has {unknown} unknown key(s)")
    return body


def _image_base64(value: Any, settings: Settings) -> str:
    if not isinstance(value, str) or not value:
        raise RequestError("image_base64 must be a non-empty string")
    if len(value) > max_base64_chars(settings.max_image_bytes):
        raise too_large("image_base64 exceeds the size cap")
    return value


def _s3_key(value: Any, settings: Settings) -> str:
    if not isinstance(value, str) or not value:
        raise RequestError("s3_key must be a non-empty string")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise RequestError("s3_key is not valid UTF-8") from exc
    if size > MAX_S3_KEY_BYTES:
        raise RequestError("s3_key is too long")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise RequestError("s3_key holds a control character")
    if "\\" in value or value.startswith("/"):
        raise RequestError("s3_key has an invalid form")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise RequestError("s3_key has an invalid path segment")
    if not settings.screenshot_bucket:
        raise RequestError("s3_key given but no screenshot bucket is configured")
    return value


def _match_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _MATCH_ID.fullmatch(value):
        raise RequestError("match_id has an invalid format")
    return value


def parse_request(event: Any, settings: Settings) -> ParseRequest:
    """Validate an API Gateway event. Raise RequestError on the first fault."""
    body = _body_object(_body_text(event))
    game = body.get("game")
    if not isinstance(game, str) or game not in GAMES:
        raise RequestError(f"game must be one of {list(GAMES)}")
    has_inline, has_s3 = "image_base64" in body, "s3_key" in body
    if has_inline == has_s3:
        raise RequestError("provide exactly one of image_base64 or s3_key")
    image_b64 = _image_base64(body["image_base64"], settings) if has_inline else None
    s3_key = _s3_key(body["s3_key"], settings) if has_s3 else None
    return ParseRequest(game, image_b64, s3_key, _match_id(body.get("match_id")))


def decode_image_base64(value: str) -> bytes:
    """Decode validated base64 image text. Raise RequestError on bad input."""
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RequestError("image_base64 is not valid base64") from exc
