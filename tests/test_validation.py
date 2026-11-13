"""Request validation runs before any decode, fetch or model work."""

from __future__ import annotations

import base64
import json
import math

import pytest

from tel_parser.config import MAX_BODY_CHARS, Settings
from tel_parser.errors import RequestError
from tel_parser.validation import ParseRequest, parse_request

SETTINGS = Settings(model_path="m", screenshot_bucket="shots", max_image_bytes=3000)
NO_BUCKET = Settings(model_path="m", max_image_bytes=3000)


def _event(body: object, is_b64: bool = False) -> dict:
    raw = body if isinstance(body, str) else json.dumps(body)
    if is_b64:
        raw = base64.b64encode(raw.encode()).decode()
    return {"body": raw, "isBase64Encoded": is_b64}


def _status(event: object, settings: Settings = SETTINGS) -> int:
    with pytest.raises(RequestError) as info:
        parse_request(event, settings)
    return info.value.status


def test_inline_request_is_frozen_and_typed():
    request = parse_request(_event({"game": "overwatch", "image_base64": "aGVsbG8=", "match_id": "m-1"}), SETTINGS)
    assert request == ParseRequest("overwatch", "aGVsbG8=", None, "m-1")
    with pytest.raises(AttributeError):
        request.game = "x"  # type: ignore[misc]


def test_s3_request_and_null_match_id():
    request = parse_request(_event({"game": "marvel_rivals", "s3_key": "a/b.png", "match_id": None}), SETTINGS)
    assert request == ParseRequest("marvel_rivals", None, "a/b.png", None)


def test_base64_wrapped_body():
    request = parse_request(_event({"game": "overwatch", "s3_key": "k.png"}, is_b64=True), SETTINGS)
    assert request.s3_key == "k.png"


@pytest.mark.parametrize(
    "event",
    [
        None,
        "body",
        ["body"],
        {},
        {"body": None},
        {"body": ""},
        {"body": 42},
        {"body": b"{}"},
        {"body": {"game": "overwatch"}},
    ],
)
def test_malformed_event_or_body_is_400(event):
    assert _status(event) == 400


def test_body_over_cap_is_413():
    assert _status({"body": " " * (MAX_BODY_CHARS + 1)}) == 413


@pytest.mark.parametrize("raw", ["%%%", "e30", "/w==", base64.b64encode(b"\xff\xfe").decode()])
def test_bad_base64_wrapper_is_400(raw):
    assert _status({"body": raw, "isBase64Encoded": True}) == 400


@pytest.mark.parametrize(
    "raw",
    ["not json", "{", "[" * 100_000 + "]" * 100_000, "1" * 5000, "[]", '"x"', "null"],
    ids=["text", "open", "deep", "big-int", "array", "string", "null"],
)
def test_bad_or_non_object_json_is_400(raw):
    assert _status({"body": raw}) == 400


def test_unknown_key_is_400_without_echo():
    with pytest.raises(RequestError) as info:
        parse_request(_event({"game": "overwatch", "s3_key": "k", "secret_field": "secret_value"}), SETTINGS)
    assert info.value.status == 400
    assert "secret" not in str(info.value)
    assert "1" in str(info.value)


@pytest.mark.parametrize("game", [None, 1, ["overwatch"], {"a": 1}, "chess", "Overwatch", True])
def test_bad_game_is_400(game):
    with pytest.raises(RequestError) as info:
        parse_request(_event({"game": game, "s3_key": "k"}), SETTINGS)
    assert info.value.status == 400
    assert "chess" not in str(info.value)


@pytest.mark.parametrize("value", [None, 1, ["a"], {"a": 1}, "", True])
def test_bad_image_base64_type_is_400(value):
    assert _status(_event({"game": "overwatch", "image_base64": value})) == 400


@pytest.mark.parametrize("value", [None, 1, ["a"], {"a": 1}, "", True])
def test_bad_s3_key_type_is_400(value):
    assert _status(_event({"game": "overwatch", "s3_key": value})) == 400


@pytest.mark.parametrize("value", [1, 1.5, ["a"], {"a": 1}, "", True, " lead", "-lead", "a" * 129, "a b", "a/b"])
def test_bad_match_id_is_400(value):
    assert _status(_event({"game": "overwatch", "s3_key": "k", "match_id": value})) == 400


def test_match_id_at_length_cap_is_ok():
    request = parse_request(_event({"game": "overwatch", "s3_key": "k", "match_id": "a" * 128}), SETTINGS)
    assert request.match_id == "a" * 128


def test_both_sources_is_400():
    assert _status(_event({"game": "overwatch", "s3_key": "k", "image_base64": "aGVsbG8="})) == 400


def test_neither_source_is_400():
    assert _status(_event({"game": "overwatch"})) == 400


def test_base64_length_cap_boundary():
    cap = 4 * math.ceil(SETTINGS.max_image_bytes / 3)
    parse_request(_event({"game": "overwatch", "image_base64": "A" * cap}), SETTINGS)
    assert _status(_event({"game": "overwatch", "image_base64": "A" * (cap + 1)})) == 413


@pytest.mark.parametrize(
    "key",
    [
        "/abs.png",
        "a/../b.png",
        "..",
        "a//b.png",
        "a/",
        "a\\b.png",
        "a\x00b",
        "a\nb",
        "a\x7fb",
        "a\x85b",
        "\ud800",
        "a" * 1025,
        "é" * 513,
        ".",
        "a/./b",
    ],
)
def test_bad_s3_key_is_400(key):
    assert _status(_event({"game": "overwatch", "s3_key": key})) == 400


def test_s3_key_byte_cap_boundary():
    request = parse_request(_event({"game": "overwatch", "s3_key": "é" * 512}), SETTINGS)
    assert request.s3_key is not None
    assert len(request.s3_key.encode()) == 1024


def test_s3_key_without_bucket_is_400():
    assert _status(_event({"game": "overwatch", "s3_key": "k.png"}), NO_BUCKET) == 400


def test_error_codes_are_stable():
    with pytest.raises(RequestError) as info:
        parse_request({"body": " " * (MAX_BODY_CHARS + 1)}, SETTINGS)
    assert info.value.code == "payload_too_large"
    with pytest.raises(RequestError) as info:
        parse_request(None, SETTINGS)
    assert info.value.code == "bad_request"
