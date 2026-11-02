"""Write scoreboard rows to DynamoDB.

Table key: ``match_id`` (string, partition) and ``player_slot`` (number,
sort). Each put is conditional, so a retried request cannot overwrite a
stored row. boto3 loads only when no client is injected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from .layouts import NUMERIC_FIELDS

CONDITION = "attribute_not_exists(match_id) AND attribute_not_exists(player_slot)"
_DUPLICATE = "ConditionalCheckFailedException"


def _error_code(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        return response.get("Error", {}).get("Code")
    return None


class StatsWriter:
    """Idempotent DynamoDB writer for one table."""

    def __init__(self, table_name: str, client: Any = None, region: str | None = None) -> None:
        self.table_name = table_name
        self._client = client
        self._region = region

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("dynamodb", region_name=self._region)
        return self._client

    def build_put_request(
        self,
        match_id: str,
        game: str,
        row: Mapping[str, Any],
        captured_at: str | None = None,
    ) -> dict[str, Any]:
        """Return keyword arguments for the low-level ``put_item`` call."""
        if not match_id:
            raise ValueError("match_id must be a non-empty string")
        captured_at = captured_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        item: dict[str, Any] = {
            "match_id": {"S": match_id},
            "player_slot": {"N": str(int(row["player_slot"]))},
            "game": {"S": game},
            "team": {"S": str(row.get("team", ""))},
            "player_name": {"S": str(row.get("player_name", ""))},
            "captured_at": {"S": captured_at},
        }
        for name in NUMERIC_FIELDS:
            value = row.get(name)
            if value is not None:
                item[name] = {"N": str(int(value))}
        return {"TableName": self.table_name, "Item": item, "ConditionExpression": CONDITION}

    def put_rows(self, match_id: str, game: str, rows: Iterable[Mapping[str, Any]]) -> int:
        """Write rows. Return how many were new. Skip rows already stored."""
        written = 0
        for row in rows:
            request = self.build_put_request(match_id, game, row)
            try:
                self.client.put_item(**request)
            except Exception as exc:
                if _error_code(exc) == _DUPLICATE:
                    continue
                raise
            written += 1
        return written
