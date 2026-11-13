"""Failed-write queue never raises and caps the message size."""

from __future__ import annotations

import json

import pytest

from tel_parser.fallback import MAX_MESSAGE_BYTES, FailedWriteQueue

from .conftest import FakeClientError, FakeQueueClient

URL = "https://sqs.eu-west-2.amazonaws.com/123456789012/tel-failed-writes"
ROWS = [{"player_slot": 0, "player_name": "ANA", "damage": 10}]


def test_send_writes_versioned_body():
    client = FakeQueueClient()
    queue = FailedWriteQueue(URL, client=client)
    assert queue.send("m-1", "overwatch", ROWS, "req-1", "storage_error") is True
    (message,) = client.messages
    assert message["QueueUrl"] == URL
    body = json.loads(message["MessageBody"])
    assert body["v"] == 1
    assert body["match_id"] == "m-1"
    assert body["game"] == "overwatch"
    assert body["rows"] == ROWS
    assert body["request_id"] == "req-1"
    assert body["reason"] == "storage_error"
    assert body["captured_at"].endswith("Z")


@pytest.mark.parametrize("error", [FakeClientError("AccessDenied"), TimeoutError("t"), RuntimeError("x")])
def test_client_fault_returns_false(error, capsys):
    queue = FailedWriteQueue(URL, client=FakeQueueClient(error=error))
    assert queue.send("m-1", "overwatch", ROWS, "req-1", "storage_error") is False
    assert type(error).__name__ in capsys.readouterr().out


def test_oversize_message_is_not_sent(capsys):
    client = FakeQueueClient()
    rows = [{"player_name": "x" * (MAX_MESSAGE_BYTES + 1)}]
    assert FailedWriteQueue(URL, client=client).send("m", "overwatch", rows, "r", "storage_error") is False
    assert client.messages == []
    assert "queue_message_too_large" in capsys.readouterr().out


def test_unserialisable_rows_return_false():
    client = FakeQueueClient()
    rows = [{"bad": object()}]
    assert FailedWriteQueue(URL, client=client).send("m", "overwatch", rows, "r", "x") is False
    assert client.messages == []


def test_client_build_failure_returns_false(monkeypatch):
    boto3 = pytest.importorskip("boto3")

    def broken(*args, **kwargs):
        raise RuntimeError("no region")

    monkeypatch.setattr(boto3, "client", broken)
    assert FailedWriteQueue(URL, region="eu-west-2").send("m", "overwatch", ROWS, "r", "x") is False


def test_lazy_client_uses_region(monkeypatch):
    boto3 = pytest.importorskip("boto3")
    seen = {}

    def fake_client(name, region_name=None, config=None):
        seen["args"] = (name, region_name)
        return FakeQueueClient()

    monkeypatch.setattr(boto3, "client", fake_client)
    queue = FailedWriteQueue(URL, region="eu-west-2")
    assert queue.send("m", "overwatch", ROWS, "r", "x") is True
    assert seen["args"] == ("sqs", "eu-west-2")
