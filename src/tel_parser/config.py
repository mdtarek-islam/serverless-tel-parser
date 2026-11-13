"""Runtime settings read and validated from environment variables."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from .errors import ConfigError

DEFAULT_MODEL_PATH = "/var/task/model/glyphs_int8.onnx"
# Lambda caps a synchronous request payload at 6 MB. Base64 adds a third.
DEFAULT_MAX_IMAGE_BYTES = 4_000_000
DEFAULT_MAX_IMAGE_PIXELS = 16_000_000

MIN_IMAGE_SIDE = 64
MAX_BODY_CHARS = 6_291_456
ALLOWED_FORMATS: tuple[str, ...] = ("PNG", "JPEG")
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_TABLE = re.compile(r"[A-Za-z0-9_.-]{3,255}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_REGION = re.compile(r"[a-z]{2}(-[a-z]+)+-[0-9]")
_DIGITS = re.compile(r"[0-9]{1,9}")
_URL_REST = re.compile(r"[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")


def _optional(env: Mapping[str, str], name: str, pattern: re.Pattern[str]) -> str:
    value = env.get(name, "")
    if value and not pattern.fullmatch(value):
        raise ConfigError(f"{name} has an invalid format")
    return value


def _bounded_int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    if not _DIGITS.fullmatch(raw):
        raise ConfigError(f"{name} must be a whole number")
    value = int(raw)
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}")
    return value


def _queue_url(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        return value
    prefix = "https://"
    if not value.startswith(prefix) or not _URL_REST.fullmatch(value[len(prefix) :]):
        raise ConfigError(f"{name} must be an https URL")
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings for one Lambda container."""

    model_path: str = DEFAULT_MODEL_PATH
    table_name: str = ""
    screenshot_bucket: str = ""
    aws_region: str = "eu-west-2"
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS
    failed_writes_queue_url: str = ""
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Read and validate settings. Raise ConfigError on the first bad value."""
        env = os.environ if env is None else env
        model_path = env.get("TEL_MODEL_PATH", DEFAULT_MODEL_PATH)
        if not model_path:
            raise ConfigError("TEL_MODEL_PATH must not be empty")
        region = env.get("AWS_REGION", "eu-west-2")
        if not _REGION.fullmatch(region):
            raise ConfigError("AWS_REGION has an invalid format")
        log_level = env.get("TEL_LOG_LEVEL", "INFO")
        if log_level not in LOG_LEVELS:
            raise ConfigError(f"TEL_LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}")
        return cls(
            model_path=model_path,
            table_name=_optional(env, "TEL_TABLE_NAME", _TABLE),
            screenshot_bucket=_optional(env, "TEL_SCREENSHOT_BUCKET", _BUCKET),
            aws_region=region,
            max_image_bytes=_bounded_int(env, "TEL_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES, 1024, 20_000_000),
            max_image_pixels=_bounded_int(env, "TEL_MAX_IMAGE_PIXELS", DEFAULT_MAX_IMAGE_PIXELS, 4096, 89_478_485),
            failed_writes_queue_url=_queue_url(env, "TEL_FAILED_WRITES_QUEUE_URL"),
            log_level=log_level,
        )
