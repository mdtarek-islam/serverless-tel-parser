"""Park failed stats writes on an SQS queue for a later replay."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .logging_utils import log_event

LOGGER = logging.getLogger("tel_parser.fallback")
MAX_MESSAGE_BYTES = 200_000
MESSAGE_VERSION = 1


class FailedWriteQueue:
    """Send one message per failed write. ``send`` never raises."""

    def __init__(self, queue_url: str, client: Any = None, region: str | None = None) -> None:
        self.queue_url = queue_url
        self._client = client
        self._region = region

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            from botocore.config import Config

            config = Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2})
            self._client = boto3.client("sqs", region_name=self._region, config=config)
        return self._client

    def send(
        self,
        match_id: str,
        game: str,
        rows: Sequence[Mapping[str, Any]],
        request_id: str,
        reason: str,
    ) -> bool:
        """Return True when the queue accepted the message."""
        try:
            body = json.dumps(
                {
                    "v": MESSAGE_VERSION,
                    "match_id": match_id,
                    "game": game,
                    "rows": [dict(row) for row in rows],
                    "request_id": request_id,
                    "captured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "reason": reason,
                },
                separators=(",", ":"),
            )
            size = len(body.encode("utf-8"))
            if size > MAX_MESSAGE_BYTES:
                log_event(LOGGER, "queue_message_too_large", level=logging.ERROR, request_id=request_id, bytes=size)
                return False
            self.client.send_message(QueueUrl=self.queue_url, MessageBody=body)
        except Exception as exc:
            log_event(
                LOGGER, "queue_send_failed", level=logging.ERROR, request_id=request_id, error_type=type(exc).__name__
            )
            return False
        return True
