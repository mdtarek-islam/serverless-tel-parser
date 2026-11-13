"""Every bad environment value raises ConfigError naming the variable."""

from __future__ import annotations

import pytest

from tel_parser.config import ALLOWED_FORMATS, MAX_BODY_CHARS, MIN_IMAGE_SIDE, Settings
from tel_parser.errors import ConfigError


def test_defaults():
    settings = Settings.from_env({})
    assert settings == Settings()
    assert settings.model_path == "/var/task/model/glyphs_int8.onnx"
    assert settings.aws_region == "eu-west-2"
    assert settings.max_image_bytes == 4_000_000
    assert settings.max_image_pixels == 16_000_000
    assert settings.failed_writes_queue_url == ""
    assert settings.log_level == "INFO"


def test_constants():
    assert MIN_IMAGE_SIDE == 64
    assert MAX_BODY_CHARS == 6_291_456
    assert ALLOWED_FORMATS == ("PNG", "JPEG")


def test_good_values_are_read():
    env = {
        "TEL_MODEL_PATH": "/opt/m.onnx",
        "TEL_TABLE_NAME": "tel-stats.v1_x",
        "TEL_SCREENSHOT_BUCKET": "my.shots-bucket",
        "AWS_REGION": "us-gov-west-1",
        "TEL_MAX_IMAGE_BYTES": "1024",
        "TEL_MAX_IMAGE_PIXELS": "89478485",
        "TEL_FAILED_WRITES_QUEUE_URL": "https://sqs.eu-west-2.amazonaws.com/1/q",
        "TEL_LOG_LEVEL": "DEBUG",
    }
    settings = Settings.from_env(env)
    assert settings.model_path == "/opt/m.onnx"
    assert settings.table_name == "tel-stats.v1_x"
    assert settings.screenshot_bucket == "my.shots-bucket"
    assert settings.aws_region == "us-gov-west-1"
    assert settings.max_image_bytes == 1024
    assert settings.max_image_pixels == 89_478_485
    assert settings.failed_writes_queue_url.startswith("https://")
    assert settings.log_level == "DEBUG"


def test_reads_os_environ_when_no_mapping(monkeypatch):
    monkeypatch.setenv("TEL_TABLE_NAME", "from-os")
    assert Settings.from_env().table_name == "from-os"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TEL_MODEL_PATH", ""),
        ("TEL_TABLE_NAME", "ab"),
        ("TEL_TABLE_NAME", "a" * 256),
        ("TEL_TABLE_NAME", "bad name"),
        ("TEL_SCREENSHOT_BUCKET", "Upper"),
        ("TEL_SCREENSHOT_BUCKET", "ab"),
        ("TEL_SCREENSHOT_BUCKET", "-lead"),
        ("TEL_SCREENSHOT_BUCKET", "trail-"),
        ("TEL_SCREENSHOT_BUCKET", "a" * 64),
        ("AWS_REGION", ""),
        ("AWS_REGION", "eu-west"),
        ("AWS_REGION", "EU-WEST-2"),
        ("AWS_REGION", "euwest2"),
        ("TEL_MAX_IMAGE_BYTES", "1023"),
        ("TEL_MAX_IMAGE_BYTES", "20000001"),
        ("TEL_MAX_IMAGE_BYTES", "lots"),
        ("TEL_MAX_IMAGE_BYTES", ""),
        ("TEL_MAX_IMAGE_BYTES", "1_000_000"),
        ("TEL_MAX_IMAGE_BYTES", " 5000"),
        ("TEL_MAX_IMAGE_BYTES", "-5000"),
        ("TEL_MAX_IMAGE_PIXELS", "4095"),
        ("TEL_MAX_IMAGE_PIXELS", "89478486"),
        ("TEL_MAX_IMAGE_PIXELS", "1e7"),
        ("TEL_FAILED_WRITES_QUEUE_URL", "http://sqs.example/q"),
        ("TEL_FAILED_WRITES_QUEUE_URL", "https://"),
        ("TEL_FAILED_WRITES_QUEUE_URL", "https://host/ q"),
        ("TEL_LOG_LEVEL", "VERBOSE"),
        ("TEL_LOG_LEVEL", "info"),
    ],
)
def test_bad_value_names_the_variable(name, value):
    with pytest.raises(ConfigError) as info:
        Settings.from_env({name: value})
    assert str(info.value).startswith(name)
    assert isinstance(info.value, ValueError)


@pytest.mark.parametrize(("name", "value"), [("TEL_MAX_IMAGE_BYTES", "20000000"), ("TEL_MAX_IMAGE_PIXELS", "4096")])
def test_integer_bounds_are_inclusive(name, value):
    settings = Settings.from_env({name: value})
    assert int(value) in (settings.max_image_bytes, settings.max_image_pixels)
