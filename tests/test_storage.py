"""DynamoDB writer builds idempotent put_item requests."""

from __future__ import annotations

import pytest

from tel_parser.errors import StorageError
from tel_parser.storage import StatsWriter

ROW = {
    "player_slot": 3,
    "team": "ally",
    "player_name": "ANA",
    "eliminations": 5,
    "assists": 11,
    "deaths": 2,
    "damage": 1500,
    "healing": 9800,
    "mitigation": None,
}


def test_put_request_shape(fake_dynamo):
    writer = StatsWriter("tel-stats", client=fake_dynamo)
    request = writer.build_put_request("m-42", "overwatch", ROW, captured_at="2026-11-02T10:00:00Z")
    assert request["TableName"] == "tel-stats"
    item = request["Item"]
    assert item["match_id"] == {"S": "m-42"}
    assert item["player_slot"] == {"N": "3"}
    assert item["player_name"] == {"S": "ANA"}
    assert item["healing"] == {"N": "9800"}
    assert item["game"] == {"S": "overwatch"}
    assert "mitigation" not in item
    assert request["ConditionExpression"] == (
        "attribute_not_exists(match_id) AND attribute_not_exists(player_slot)"
    )


def test_duplicate_put_is_skipped_not_raised(fake_dynamo):
    writer = StatsWriter("tel-stats", client=fake_dynamo)
    assert writer.put_rows("m-1", "overwatch", [ROW]) == 1
    assert writer.put_rows("m-1", "overwatch", [ROW]) == 0
    assert len(fake_dynamo.items) == 1


def test_other_client_errors_become_retryable_storage_errors():
    class Broken:
        def transact_write_items(self, **request):
            raise RuntimeError("throttled")

    with pytest.raises(StorageError) as info:
        StatsWriter("t", client=Broken()).put_rows("m", "overwatch", [ROW])
    assert info.value.retryable is True


def test_empty_match_id_rejected(fake_dynamo):
    with pytest.raises(ValueError):
        StatsWriter("t", client=fake_dynamo).build_put_request("", "overwatch", ROW)
