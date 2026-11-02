"""Lambda handler: good and bad API Gateway events."""

from __future__ import annotations

import base64
import json

import pytest

from tel_parser import handler as handler_module
from tel_parser.config import Settings
from tel_parser.handler import handle
from tel_parser.storage import StatsWriter

from .conftest import png_bytes


def _event(body, is_b64=False):
    raw = json.dumps(body) if isinstance(body, dict) else body
    if is_b64:
        raw = base64.b64encode(raw.encode()).decode()
    return {"body": raw, "isBase64Encoded": is_b64}


@pytest.fixture()
def settings():
    return Settings(model_path="missing.onnx", table_name="tel-stats", max_image_bytes=2_000_000)


def test_good_event_returns_rows_and_timing(png_b64, fake_recogniser, settings):
    response = handle(_event({"image_base64": png_b64, "game": "overwatch"}), fake_recogniser, None, settings)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body["rows"]) == 10
    assert body["persisted"] == 0
    assert set(body["timing"]) == {"cold_start", "init_ms", "invoke_ms"}


def test_base64_wrapped_body_is_accepted(png_b64, fake_recogniser, settings):
    response = handle(_event({"image_base64": png_b64, "game": "marvel_rivals"}, is_b64=True), fake_recogniser, None, settings)
    assert response["statusCode"] == 200


def test_match_id_persists_rows(png_b64, fake_recogniser, fake_dynamo, settings):
    writer = StatsWriter("tel-stats", client=fake_dynamo)
    event = _event({"image_base64": png_b64, "game": "overwatch", "match_id": "m-9"})
    body = json.loads(handle(event, fake_recogniser, writer, settings)["body"])
    assert body["persisted"] == 10


def test_s3_key_uses_fetcher(fake_recogniser, settings):
    seen = {}

    def fetch(bucket, key):
        seen["args"] = (bucket, key)
        return png_bytes()

    s3_settings = Settings(model_path="m", table_name="t", screenshot_bucket="shots")
    response = handle(_event({"s3_key": "a/b.png", "game": "overwatch"}), fake_recogniser, None, s3_settings, fetch_s3=fetch)
    assert response["statusCode"] == 200
    assert seen["args"] == ("shots", "a/b.png")


@pytest.mark.parametrize(
    "event",
    [
        {"body": "not json"},
        {"body": None},
        _event({"game": "overwatch"}),
        _event({"image_base64": "%%%", "game": "overwatch"}),
        _event({"image_base64": base64.b64encode(b"not an image").decode(), "game": "overwatch"}),
        _event({"image_base64": "aGVsbG8=", "game": "chess"}),
        _event({"s3_key": "a.png", "game": "overwatch"}),
    ],
)
def test_bad_events_return_400(event, fake_recogniser, settings):
    response = handle(event, fake_recogniser, None, settings)
    assert response["statusCode"] == 400
    assert "error" in json.loads(response["body"])


def test_oversized_image_returns_413(fake_recogniser):
    tiny = Settings(model_path="m", table_name="t", max_image_bytes=10)
    event = _event({"image_base64": base64.b64encode(png_bytes()).decode(), "game": "overwatch"})
    assert handle(event, fake_recogniser, None, tiny)["statusCode"] == 413


def test_missing_model_returns_503(png_b64, settings):
    event = _event({"image_base64": png_b64, "game": "overwatch"})
    assert handle(event, None, None, settings)["statusCode"] == 503


def test_lambda_entrypoint_without_model_returns_503(png_b64, monkeypatch):
    monkeypatch.setattr(handler_module, "RECOGNISER", None)
    response = handler_module.handler(_event({"image_base64": png_b64, "game": "overwatch"}), None)
    assert response["statusCode"] == 503
