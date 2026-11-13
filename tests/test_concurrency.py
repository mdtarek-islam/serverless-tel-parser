"""Many threads against one handler: one store, no 5xx, no 500."""

from __future__ import annotations

import base64
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor

from tel_parser.config import Settings
from tel_parser.handler import handle
from tel_parser.storage import StatsWriter

from .conftest import FakeDynamoClient, FakeRecogniser, image_bytes, png_bytes

SETTINGS = Settings(model_path="m", table_name="t", screenshot_bucket="shots", max_image_bytes=200_000)


def _event(body: object) -> dict:
    return {"body": body if isinstance(body, str) else json.dumps(body)}


def test_same_match_id_from_32_threads_stores_once():
    dynamo = FakeDynamoClient()
    writer = StatsWriter("t", client=dynamo)
    recogniser = FakeRecogniser()
    event = _event({"game": "overwatch", "image_base64": base64.b64encode(png_bytes()).decode(), "match_id": "m-1"})
    barrier = threading.Barrier(32)

    def call(_index: int) -> dict:
        barrier.wait()
        return handle(event, recogniser, writer, SETTINGS)

    with ThreadPoolExecutor(max_workers=32) as pool:
        responses = list(pool.map(call, range(32)))
    statuses = [r["statusCode"] for r in responses]
    outcomes = sorted(json.loads(r["body"])["persistence"] for r in responses)
    assert statuses == [200] * 32
    assert outcomes.count("stored") == 1
    assert outcomes.count("duplicate") == 31
    assert len(dynamo.items) == 10


def _mixed_events() -> list[dict]:
    good = base64.b64encode(image_bytes("PNG", 320, 180)).decode()
    jpeg = base64.b64encode(image_bytes("JPEG", 320, 200)).decode()
    gif = base64.b64encode(image_bytes("GIF")).decode()
    tiny = base64.b64encode(image_bytes("PNG", 32, 32)).decode()
    truncated = base64.b64encode(image_bytes("PNG", 320, 180)[:40]).decode()
    hostile = [
        "not json",
        "[" * 50_000,
        "[]",
        {"game": ["overwatch"], "image_base64": good},
        {"game": "overwatch"},
        {"game": "overwatch", "image_base64": good, "s3_key": "k"},
        {"game": "overwatch", "image_base64": "%%%"},
        {"game": "overwatch", "image_base64": gif},
        {"game": "overwatch", "image_base64": tiny},
        {"game": "overwatch", "image_base64": truncated},
        {"game": "overwatch", "image_base64": "A" * 300_000},
        {"game": "overwatch", "s3_key": "../etc/passwd"},
        {"game": "overwatch", "image_base64": good, "match_id": {"x": 1}},
        {"game": "overwatch", "image_base64": good, "extra": 1},
    ]
    goods = [
        {"game": "overwatch", "image_base64": good},
        {"game": "marvel_rivals", "image_base64": jpeg, "match_id": "m-2"},
    ]
    rng = random.Random(7)  # noqa: S311 - test data only
    pool = hostile + goods
    return [_event(rng.choice(pool)) for _ in range(200)] + [_event({"bad": "event"})] + [{"no": "body"}]


def test_200_mixed_requests_give_no_500():
    writer = StatsWriter("t", client=FakeDynamoClient())
    recogniser = FakeRecogniser()
    events = _mixed_events()
    with ThreadPoolExecutor(max_workers=16) as pool:
        responses = list(pool.map(lambda e: handle(e, recogniser, writer, SETTINGS), events))
    statuses = {r["statusCode"] for r in responses}
    assert 500 not in statuses
    assert statuses <= {200, 400, 413}
