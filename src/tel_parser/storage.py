"""Write scoreboard rows to DynamoDB, all or nothing.

Table key: ``match_id`` (string, partition) and ``player_slot`` (number,
sort). All rows go in one transaction of conditional puts, so a retried
request can neither overwrite a stored row nor leave a partial match.
boto3 loads only when no client is injected.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .errors import StorageError
from .layouts import NUMERIC_FIELDS

CONDITION = "attribute_not_exists(match_id) AND attribute_not_exists(player_slot)"
MAX_ROWS = 100
MAX_CONFLICT_RETRIES = 2
_CANCELLED = "TransactionCanceledException"
_CONDITION_FAILED = "ConditionalCheckFailed"
_CONFLICT = "TransactionConflict"
_CONFLICT_CODES = frozenset({"TransactionConflictException", "TransactionInProgressException"})
_REASON_LIST = re.compile(r"\[([A-Za-z, ]{0,2000})\]")


def _error_code(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        error = response.get("Error")
        if isinstance(error, Mapping):
            code = error.get("Code")
            return str(code) if code is not None else None
    return None


def _cancellation_reasons(exc: BaseException) -> list[str]:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return []
    reasons = response.get("CancellationReasons")
    if isinstance(reasons, list):
        return [str(reason.get("Code", "")) for reason in reasons if isinstance(reason, Mapping)]
    error = response.get("Error")
    message = error.get("Message", "") if isinstance(error, Mapping) else ""
    found = _REASON_LIST.search(str(message))
    return [part.strip() for part in found.group(1).split(",")] if found else []


class StatsWriter:
    """Idempotent, all-or-nothing DynamoDB writer for one table."""

    def __init__(
        self,
        table_name: str,
        client: Any = None,
        region: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.table_name = table_name
        self._client = client
        self._region = region
        self._sleep = sleep

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            from botocore.config import Config

            config = Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2})
            self._client = boto3.client("dynamodb", region_name=self._region, config=config)
        return self._client

    def build_put_request(
        self,
        match_id: str,
        game: str,
        row: Mapping[str, Any],
        captured_at: str | None = None,
    ) -> dict[str, Any]:
        """Return one conditional ``Put`` for a transaction item."""
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

    def put_rows(self, match_id: str, game: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """Write every row or none. Return the row count, or 0 for a duplicate.

        Raise ValueError above MAX_ROWS rows and StorageError when the
        store fails.
        """
        rows = list(rows)
        if len(rows) > MAX_ROWS:
            raise ValueError(f"at most {MAX_ROWS} rows fit in one transaction")
        if not rows:
            return 0
        captured_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        # No explicit ClientRequestToken: the per-row condition alone decides a
        # duplicate, so a failed attempt can never mask a later retry. The SDK
        # still adds its own token, which covers its internal retries.
        request = {
            "TransactItems": [{"Put": self.build_put_request(match_id, game, row, captured_at)} for row in rows],
        }
        for attempt in range(MAX_CONFLICT_RETRIES + 1):
            try:
                self.client.transact_write_items(**request)
                return len(rows)
            except Exception as exc:
                code = _error_code(exc)
                reasons = _cancellation_reasons(exc) if code == _CANCELLED else []
                if _CONDITION_FAILED in reasons:
                    return 0
                conflict = _CONFLICT in reasons or code in _CONFLICT_CODES
                if not conflict or attempt == MAX_CONFLICT_RETRIES:
                    raise StorageError(f"stats write failed: {type(exc).__name__}", retryable=True) from exc
                self._sleep(0.05 * (2**attempt))
        raise AssertionError("unreachable")  # pragma: no cover
