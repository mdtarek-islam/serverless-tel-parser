"""Shared fixtures and fakes for the test suite."""

from __future__ import annotations

import base64
import io
import threading
from typing import Any

import pytest
from PIL import Image


def png_bytes(width: int = 1920, height: int = 1080) -> bytes:
    """Return a dark PNG screenshot of the given size."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (12, 14, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


def image_bytes(fmt: str, width: int = 64, height: int = 64) -> bytes:
    """Return a small grey image encoded in ``fmt``."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (90, 90, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture()
def screenshot() -> Image.Image:
    return Image.new("RGB", (1920, 1080), (12, 14, 20))


@pytest.fixture()
def png_b64() -> str:
    return base64.b64encode(png_bytes()).decode("ascii")


class FakeClientError(Exception):
    """Mimic a botocore ClientError: a ``response`` dict with an error code."""

    def __init__(self, code: str, message: str = "", **extra: Any) -> None:
        super().__init__(message or code)
        self.response: dict[str, Any] = {"Error": {"Code": code, "Message": message}, **extra}


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
    """Thread-safe fake of ``transact_write_items`` with conditional puts.

    ``failures`` holds exceptions to raise, one per call, before the
    transaction is applied.
    """

    def __init__(self, failures: list[BaseException] | None = None) -> None:
        self.requests: list[dict] = []
        self.items: dict[tuple[str, str], dict] = {}
        self.failures = list(failures or [])
        self._lock = threading.Lock()

    def transact_write_items(self, **request):
        with self._lock:
            self.requests.append(request)
            if self.failures:
                raise self.failures.pop(0)
            puts = [entry["Put"] for entry in request["TransactItems"]]
            keys = [(put["Item"]["match_id"]["S"], put["Item"]["player_slot"]["N"]) for put in puts]
            reasons = [{"Code": "ConditionalCheckFailed" if key in self.items else "None"} for key in keys]
            if any(reason["Code"] != "None" for reason in reasons):
                raise FakeClientError("TransactionCanceledException", "cancelled", CancellationReasons=reasons)
            for key, put in zip(keys, puts, strict=True):
                self.items[key] = put["Item"]
            return {}


class FakeQueueClient:
    """Record ``send_message`` calls. Raise ``error`` when it is set."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.messages: list[dict] = []
        self.error = error

    def send_message(self, **request):
        if self.error is not None:
            raise self.error
        self.messages.append(request)
        return {"MessageId": "1"}


@pytest.fixture()
def fake_recogniser() -> FakeRecogniser:
    return FakeRecogniser()


@pytest.fixture()
def fake_dynamo() -> FakeDynamoClient:
    return FakeDynamoClient()
