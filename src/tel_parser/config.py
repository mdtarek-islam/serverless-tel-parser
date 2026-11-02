"""Runtime settings read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_MODEL_PATH = "/var/task/model/glyphs_int8.onnx"
# Lambda caps a synchronous request payload at 6 MB. Base64 adds a third.
DEFAULT_MAX_IMAGE_BYTES = 4_000_000


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings for one Lambda container."""

    model_path: str = DEFAULT_MODEL_PATH
    table_name: str = ""
    screenshot_bucket: str = ""
    aws_region: str = "eu-west-2"
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            model_path=env.get("TEL_MODEL_PATH", DEFAULT_MODEL_PATH),
            table_name=env.get("TEL_TABLE_NAME", ""),
            screenshot_bucket=env.get("TEL_SCREENSHOT_BUCKET", ""),
            aws_region=env.get("AWS_REGION", "eu-west-2"),
            max_image_bytes=int(env.get("TEL_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES)),
            log_level=env.get("TEL_LOG_LEVEL", "INFO"),
        )
