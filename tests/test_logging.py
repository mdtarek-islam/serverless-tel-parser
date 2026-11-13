"""JSON line logs with required fields and no input echo."""

from __future__ import annotations

import base64
import json
import logging

from tel_parser.config import Settings
from tel_parser.errors import RequestError
from tel_parser.handler import handle
from tel_parser.logging_utils import StdoutHandler, configure_logging, log_event

from .conftest import png_bytes

PARSE_FIELDS = {
    "ts",
    "level",
    "event",
    "request_id",
    "status",
    "game",
    "calibrated",
    "source",
    "image_bytes",
    "width",
    "height",
    "persisted",
    "persistence",
    "cold_start",
    "init_ms",
    "invoke_ms",
    "error_code",
}


def _lines(capsys) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


def test_logger_has_own_handler_and_no_propagation():
    logger = configure_logging("INFO")
    assert logger.name == "tel_parser"
    assert logger.propagate is False
    assert sum(isinstance(h, StdoutHandler) for h in logger.handlers) == 1
    assert configure_logging("DEBUG") is logger
    assert sum(isinstance(h, StdoutHandler) for h in logger.handlers) == 1
    assert logger.level == logging.DEBUG
    configure_logging("INFO")


def test_log_event_writes_one_json_line(capsys):
    logger = configure_logging("INFO")
    log_event(logger, "probe", request_id="r-1", count=3, odd=object())
    (record,) = _lines(capsys)
    assert record["event"] == "probe"
    assert record["level"] == "INFO"
    assert record["request_id"] == "r-1"
    assert record["count"] == 3
    assert record["ts"].endswith("Z")
    assert isinstance(record["odd"], str)


def test_plain_child_logger_records_are_json(capsys):
    configure_logging("INFO")
    logging.getLogger("tel_parser.inference").warning("model file not found; recogniser disabled")
    (record,) = _lines(capsys)
    assert record["event"] == "log"
    assert record["level"] == "WARNING"
    assert "recogniser disabled" in record["message"]


def test_log_event_with_stack(capsys):
    logger = configure_logging("INFO")
    try:
        raise KeyError("x")
    except KeyError:
        log_event(logger, "fault", level=logging.ERROR, exc_info=True)
    (record,) = _lines(capsys)
    assert record["level"] == "ERROR"
    assert "Traceback" in record["stack"]


def test_parse_event_has_required_fields(capsys, fake_recogniser):
    settings = Settings(model_path="m")
    event = {"body": json.dumps({"game": "overwatch", "image_base64": base64.b64encode(png_bytes()).decode()})}
    handle(event, fake_recogniser, None, settings)
    parse = [r for r in _lines(capsys) if r["event"] == "parse"][-1]
    assert set(parse) >= PARSE_FIELDS
    assert parse["status"] == 200
    assert parse["source"] == "inline"
    assert (parse["width"], parse["height"]) == (1920, 1080)
    assert parse["image_bytes"] == len(png_bytes())
    assert parse["persistence"] == "skipped"
    assert parse["error_code"] is None


def test_no_input_echo_in_logs(capsys, fake_recogniser):
    settings = Settings(model_path="m", screenshot_bucket="shots")
    secrets = ["SECRETKEYVALUE", "SECRETMATCHVALUE", "SECRETFIELDVALUE"]
    events = [
        {"body": json.dumps({"game": "overwatch", "s3_key": "a/SECRETKEYVALUE.png", "match_id": "SECRETMATCHVALUE"})},
        {"body": json.dumps({"game": "overwatch", "s3_key": "k", "SECRETFIELDVALUE": 1})},
        {"body": json.dumps({"game": "SECRETFIELDVALUE", "s3_key": "k"})},
        {"body": "SECRETFIELDVALUE"},
    ]

    def fetch(bucket, key, max_bytes):
        raise RequestError("screenshot store unavailable", status=503, code="s3_unavailable")

    responses = [handle(event, fake_recogniser, None, settings, fetch_s3=fetch) for event in events]
    out = capsys.readouterr().out
    assert [r["statusCode"] for r in responses] == [503, 400, 400, 400]
    for secret in secrets:
        assert secret not in out
        for response in responses:
            assert secret not in response["body"]
