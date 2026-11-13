"""Exception types shared by the parser modules."""

from __future__ import annotations


class RequestError(Exception):
    """A client or dependency error that maps to one HTTP status.

    The message goes into the response body. Keep it a fixed string and
    never put request values in it.
    """

    def __init__(self, message: str, status: int = 400, code: str = "bad_request") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class ConfigError(ValueError):
    """An environment variable holds a bad value. The message starts with its name."""


class StorageError(Exception):
    """A stats write failed. ``retryable`` marks faults worth queueing."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def too_large(message: str) -> RequestError:
    """Return a 413 error."""
    return RequestError(message, status=413, code="payload_too_large")
