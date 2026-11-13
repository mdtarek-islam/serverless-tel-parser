"""Handler wiring: status table, headers, request id and persistence."""

from __future__ import annotations

import base64
import json

import pytest

from tel_parser import handler as handler_module
from tel_parser import layouts
from tel_parser.config import Settings
from tel_parser.errors import RequestError, StorageError
from tel_parser.fallback import FailedWriteQueue
from tel_parser.handler import handle
from tel_parser.storage import StatsWriter

from .conftest import FakeClientError, FakeDynamoClient, FakeQueueClient, png_bytes

SETTINGS = Settings(model_path="m", table_name="tel-stats", screenshot_bucket="shots")
URL = "https://sqs.eu-west-2.amazonaws.com/123456789012/q"


def _event(body: dict, **extra) -> dict:
    return {"body": json.dumps(body), "isBase64Encoded": False, **extra}


def _inline(match_id: str | None = None, game: str = "overwatch") -> dict:
    body = {"game": game, "image_base64": base64.b64encode(png_bytes()).decode()}
    if match_id is not None:
        body["match_id"] = match_id
    return _event(body)


def _body(response: dict) -> dict:
    return json.loads(response["body"])


class FailingWriter:
    def put_rows(self, match_id, game, rows):
        raise StorageError("write failed", retryable=True)


def test_security_headers_and_request_id_from_event(fake_recogniser):
    event = _inline()
    event["requestContext"] = {"requestId": "abc-123=="}
    response = handle(event, fake_recogniser, None, SETTINGS)
    headers = response["headers"]
    assert headers["content-type"] == "application/json"
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-request-id"] == "abc-123=="


class Context:
    aws_request_id = "ctx-req-1"


@pytest.mark.parametrize("request_context", [None, {"requestId": "bad id!"}, {"requestId": 5}, "x", {}])
def test_request_id_falls_back_to_context(fake_recogniser, request_context):
    event = _inline()
    if request_context is not None:
        event["requestContext"] = request_context
    response = handle(event, fake_recogniser, None, SETTINGS, context=Context())
    assert response["headers"]["x-request-id"] == "ctx-req-1"


def test_request_id_falls_back_to_uuid(fake_recogniser):
    response = handle({"body": "{"}, fake_recogniser, None, SETTINGS)
    request_id = response["headers"]["x-request-id"]
    assert len(request_id) == 36
    assert response["statusCode"] == 400


def test_non_dict_event_is_400_not_500(fake_recogniser):
    response = handle(["not", "an", "event"], fake_recogniser, None, SETTINGS)
    assert response["statusCode"] == 400


def test_validation_runs_before_model_check():
    assert handle({"body": "{"}, None, None, SETTINGS)["statusCode"] == 400


def test_skipped_without_match_id(fake_recogniser, fake_dynamo):
    body = _body(handle(_inline(), fake_recogniser, StatsWriter("t", client=fake_dynamo), SETTINGS))
    assert (body["persisted"], body["persistence"]) == (0, "skipped")
    assert fake_dynamo.requests == []


def test_skipped_without_writer(fake_recogniser):
    body = _body(handle(_inline("m-1"), fake_recogniser, None, SETTINGS))
    assert (body["persisted"], body["persistence"]) == (0, "skipped")


def test_stored_then_duplicate(fake_recogniser, fake_dynamo):
    writer = StatsWriter("t", client=fake_dynamo)
    first = _body(handle(_inline("m-1"), fake_recogniser, writer, SETTINGS))
    second = _body(handle(_inline("m-1"), fake_recogniser, writer, SETTINGS))
    assert (first["persisted"], first["persistence"]) == (10, "stored")
    assert (second["persisted"], second["persistence"]) == (0, "duplicate")


def test_write_failure_is_queued(fake_recogniser):
    client = FakeQueueClient()
    queue = FailedWriteQueue(URL, client=client)
    event = _inline("m-1")
    event["requestContext"] = {"requestId": "req-9"}
    response = handle(event, fake_recogniser, FailingWriter(), SETTINGS, queue=queue)
    body = _body(response)
    assert response["statusCode"] == 200
    assert (body["persisted"], body["persistence"]) == (0, "queued")
    message = json.loads(client.messages[0]["MessageBody"])
    assert message["request_id"] == "req-9"
    assert len(message["rows"]) == 10


def test_write_failure_without_queue_is_503(fake_recogniser):
    response = handle(_inline("m-1"), fake_recogniser, FailingWriter(), SETTINGS)
    assert response["statusCode"] == 503
    assert _body(response)["error"] == "storage unavailable"


def test_write_failure_and_queue_failure_is_503(fake_recogniser):
    queue = FailedWriteQueue(URL, client=FakeQueueClient(error=RuntimeError("down")))
    response = handle(_inline("m-1"), fake_recogniser, FailingWriter(), SETTINGS, queue=queue)
    assert response["statusCode"] == 503


def test_real_writer_throttled_is_queued(fake_recogniser):
    dynamo = FakeDynamoClient(failures=[FakeClientError("ThrottlingException")])
    queue = FailedWriteQueue(URL, client=FakeQueueClient())
    writer = StatsWriter("t", client=dynamo, sleep=lambda _s: None)
    body = _body(handle(_inline("m-1"), fake_recogniser, writer, SETTINGS, queue=queue))
    assert body["persistence"] == "queued"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (RequestError("screenshot not found", status=404, code="not_found"), 404),
        (RequestError("screenshot store unavailable", status=503, code="s3_unavailable"), 503),
        (RequestError("screenshot exceeds byte cap", status=413, code="payload_too_large"), 413),
    ],
)
def test_s3_errors_pass_through(fake_recogniser, error, status):
    def fetch(bucket, key, max_bytes):
        raise error

    event = _event({"game": "overwatch", "s3_key": "a.png"})
    assert handle(event, fake_recogniser, None, SETTINGS, fetch_s3=fetch)["statusCode"] == status


def test_s3_fetch_gets_byte_cap(fake_recogniser):
    seen = {}

    def fetch(bucket, key, max_bytes):
        seen["args"] = (bucket, key, max_bytes)
        return png_bytes()

    event = _event({"game": "overwatch", "s3_key": "a.png"})
    assert handle(event, fake_recogniser, None, SETTINGS, fetch_s3=fetch)["statusCode"] == 200
    assert seen["args"] == ("shots", "a.png", SETTINGS.max_image_bytes)


def test_bad_inline_base64_is_400(fake_recogniser):
    event = _event({"game": "overwatch", "image_base64": "%%%%"})
    assert handle(event, fake_recogniser, None, SETTINGS)["statusCode"] == 400


def test_layout_value_error_is_400(fake_recogniser, monkeypatch):
    def broken(game, width, height):
        raise ValueError("no layout")

    monkeypatch.setattr(handler_module, "resolve_layout", broken)
    assert handle(_inline(), fake_recogniser, None, SETTINGS)["statusCode"] == 400


def test_calibrated_flag_is_read_from_layout(fake_recogniser, capsys):
    expected = layouts.resolve_layout("overwatch", 1920, 1080).calibrated
    handle(_inline(), fake_recogniser, None, SETTINGS)
    record = [json.loads(line) for line in capsys.readouterr().out.splitlines() if '"parse"' in line][-1]
    assert record["calibrated"] is expected


def test_memory_error_is_413(monkeypatch):
    class Hungry:
        def read(self, cells, fields):
            raise MemoryError

    assert handle(_inline(), Hungry(), None, SETTINGS)["statusCode"] == 413


def test_unhandled_error_is_500_with_fixed_body_and_stack(capsys):
    class Broken:
        def read(self, cells, fields):
            raise RuntimeError("internal detail")

    response = handle(_inline(), Broken(), None, SETTINGS)
    body = _body(response)
    assert response["statusCode"] == 500
    assert body["error"] == "internal error"
    assert "internal detail" not in response["body"]
    assert set(body) <= {"error", "code", "request_id", "timing"}
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    parse = [r for r in records if r.get("event") == "parse"][-1]
    assert parse["status"] == 500
    assert parse["error_type"] == "RuntimeError"
    assert "Traceback" in parse["stack"]


def test_4xx_has_no_stack(capsys, fake_recogniser):
    handle({"body": "{"}, fake_recogniser, None, SETTINGS)
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    parse = [r for r in records if r.get("event") == "parse"][-1]
    assert "stack" not in parse
    assert parse["error_code"] == "bad_request"


def test_lambda_entrypoint_passes_context(monkeypatch, fake_recogniser):
    monkeypatch.setattr(handler_module, "RECOGNISER", fake_recogniser)
    response = handler_module.handler(_inline(), Context())
    assert response["statusCode"] == 200
    assert response["headers"]["x-request-id"] == "ctx-req-1"


def test_request_error_is_reexported():
    assert handler_module.RequestError is RequestError
