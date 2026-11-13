"""All-or-nothing DynamoDB writes through one transaction."""

from __future__ import annotations

import pytest

from tel_parser.errors import StorageError
from tel_parser.storage import CONDITION, MAX_ROWS, StatsWriter

from .conftest import FakeClientError, FakeDynamoClient


def _rows(count: int, start: int = 0) -> list[dict]:
    return [
        {
            "player_slot": slot,
            "team": "ally",
            "player_name": f"P{slot}",
            "eliminations": slot,
            "assists": None,
            "deaths": 1,
            "damage": 100,
            "healing": 0,
            "mitigation": None,
        }
        for slot in range(start, start + count)
    ]


def _cancelled(*codes: str) -> FakeClientError:
    return FakeClientError(
        "TransactionCanceledException", "cancelled", CancellationReasons=[{"Code": code} for code in codes]
    )


class Sleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def test_one_transaction_with_one_conditional_put_per_row(fake_dynamo):
    writer = StatsWriter("tel-stats", client=fake_dynamo)
    assert writer.put_rows("m-1", "overwatch", _rows(10)) == 10
    assert len(fake_dynamo.requests) == 1
    request = fake_dynamo.requests[0]
    assert len(request["TransactItems"]) == 10
    for entry in request["TransactItems"]:
        assert entry["Put"]["ConditionExpression"] == CONDITION
        assert entry["Put"]["TableName"] == "tel-stats"
    assert "ClientRequestToken" not in request


def test_all_or_nothing_when_one_row_exists(fake_dynamo):
    writer = StatsWriter("t", client=fake_dynamo)
    assert writer.put_rows("m-1", "overwatch", _rows(1, start=4)) == 1
    assert writer.put_rows("m-1", "overwatch", _rows(10)) == 0
    assert len(fake_dynamo.items) == 1


def test_duplicate_returns_zero(fake_dynamo):
    writer = StatsWriter("t", client=fake_dynamo)
    writer.put_rows("m-1", "overwatch", _rows(10))
    assert writer.put_rows("m-1", "overwatch", _rows(10)) == 0


def test_idempotency_mismatch_is_a_storage_error_not_a_duplicate():
    client = FakeDynamoClient(failures=[FakeClientError("IdempotentParameterMismatchException")])
    with pytest.raises(StorageError):
        StatsWriter("t", client=client).put_rows("m", "overwatch", _rows(2))


def test_conflict_then_success_retries_with_sleep():
    client = FakeDynamoClient(failures=[_cancelled("None", "TransactionConflict")])
    sleeper = Sleeper()
    assert StatsWriter("t", client=client, sleep=sleeper).put_rows("m", "overwatch", _rows(2)) == 2
    assert len(client.requests) == 2
    assert len(sleeper.delays) == 1


def test_conflict_exhausted_is_retryable_storage_error():
    client = FakeDynamoClient(failures=[_cancelled("TransactionConflict")] * 3)
    sleeper = Sleeper()
    with pytest.raises(StorageError) as info:
        StatsWriter("t", client=client, sleep=sleeper).put_rows("m", "overwatch", _rows(2))
    assert info.value.retryable is True
    assert len(client.requests) == 3
    assert len(sleeper.delays) == 2


def test_conflict_exception_code_is_retried():
    client = FakeDynamoClient(failures=[FakeClientError("TransactionConflictException")])
    assert StatsWriter("t", client=client, sleep=Sleeper()).put_rows("m", "overwatch", _rows(1)) == 1


def test_condition_failure_wins_over_conflict():
    client = FakeDynamoClient(failures=[_cancelled("TransactionConflict", "ConditionalCheckFailed")])
    assert StatsWriter("t", client=client, sleep=Sleeper()).put_rows("m", "overwatch", _rows(2)) == 0
    assert len(client.requests) == 1


def test_reasons_parsed_from_message_when_list_absent():
    error = FakeClientError(
        "TransactionCanceledException", "Transaction cancelled, reasons [None, ConditionalCheckFailed]"
    )
    client = FakeDynamoClient(failures=[error])
    assert StatsWriter("t", client=client).put_rows("m", "overwatch", _rows(2)) == 0


@pytest.mark.parametrize(
    "error",
    [
        FakeClientError("ProvisionedThroughputExceededException"),
        FakeClientError("ThrottlingException"),
        _cancelled("ThrottlingError"),
        TimeoutError("slow"),
    ],
)
def test_throttling_and_faults_are_retryable(error):
    client = FakeDynamoClient(failures=[error])
    with pytest.raises(StorageError) as info:
        StatsWriter("t", client=client, sleep=Sleeper()).put_rows("m", "overwatch", _rows(2))
    assert info.value.retryable is True
    assert len(client.requests) == 1


def test_row_cap(fake_dynamo):
    writer = StatsWriter("t", client=fake_dynamo)
    assert writer.put_rows("m", "overwatch", _rows(MAX_ROWS)) == MAX_ROWS
    with pytest.raises(ValueError):
        writer.put_rows("m-2", "overwatch", _rows(MAX_ROWS + 1))
    assert len(fake_dynamo.requests) == 1


def test_empty_rows_write_nothing(fake_dynamo):
    assert StatsWriter("t", client=fake_dynamo).put_rows("m", "overwatch", []) == 0
    assert fake_dynamo.requests == []


def test_lazy_client_uses_region(monkeypatch):
    boto3 = pytest.importorskip("boto3")
    seen = {}

    def fake_client(name, region_name=None, config=None):
        seen["args"] = (name, region_name)
        return FakeDynamoClient()

    monkeypatch.setattr(boto3, "client", fake_client)
    writer = StatsWriter("t", region="eu-west-2")
    assert writer.client is writer.client
    assert seen["args"] == ("dynamodb", "eu-west-2")
