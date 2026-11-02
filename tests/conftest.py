"""Shared fixtures for the test suite."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image


def png_bytes(width: int = 1920, height: int = 1080) -> bytes:
    """Return a dark PNG screenshot of the given size."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (12, 14, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def screenshot() -> Image.Image:
    return Image.new("RGB", (1920, 1080), (12, 14, 20))


@pytest.fixture()
def png_b64() -> str:
    return base64.b64encode(png_bytes()).decode("ascii")


class FakeRecogniser:
    """Return a fixed string per cell and record the batch sizes it saw."""

    def __init__(self, texts: dict[str, str] | None = None) -> None:
        self.texts = texts or {
            "player_name": "TRACER",
            "eliminations": "21",
            "assists": "4",
            "deaths": "7",
            "damage": "12,345",
            "healing": "",
            "mitigation": "980",
        }
        self.fields: list[str] = []
        self.calls: list[int] = []

    def read(self, cells, fields):
        self.calls.append(len(cells))
        self.fields.extend(fields)
        return [self.texts[field] for field in fields]


class FakeDynamoClient:
    """Record put_item calls. Raise a conditional failure on duplicates."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self._keys: set[tuple[str, str]] = set()

    def put_item(self, **request):
        key = (request["Item"]["match_id"]["S"], request["Item"]["player_slot"]["N"])
        if key in self._keys:
            error = Exception("ConditionalCheckFailedException")
            error.response = {"Error": {"Code": "ConditionalCheckFailedException"}}
            raise error
        self._keys.add(key)
        self.requests.append(request)
        return {}


@pytest.fixture()
def fake_recogniser() -> FakeRecogniser:
    return FakeRecogniser()


@pytest.fixture()
def fake_dynamo() -> FakeDynamoClient:
    return FakeDynamoClient()
