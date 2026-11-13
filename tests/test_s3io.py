"""Bounded S3 reads with mapped error statuses."""

from __future__ import annotations

import pytest

from tel_parser import s3io
from tel_parser.errors import RequestError
from tel_parser.logging_utils import configure_logging

from .conftest import FakeClientError


class FakeBody:
    def __init__(self, data: bytes, error: BaseException | None = None) -> None:
        self.data = data
        self.error = error
        self.reads: list[int | None] = []
        self.closed = False

    def read(self, amt=None):
        self.reads.append(amt)
        if self.error is not None:
            raise self.error
        return self.data if amt is None else self.data[:amt]

    def close(self):
        self.closed = True


class FakeS3:
    def __init__(
        self,
        data: bytes = b"x" * 10,
        length: object = "auto",
        error: BaseException | None = None,
        body_error: BaseException | None = None,
    ) -> None:
        self.body = FakeBody(data, body_error)
        self.length = len(data) if length == "auto" else length
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def get_object(self, Bucket, Key):  # noqa: N803
        self.calls.append((Bucket, Key))
        if self.error is not None:
            raise self.error
        response = {"Body": self.body}
        if self.length is not None:
            response["ContentLength"] = self.length
        return response


class ReadTimeoutError(Exception):
    """Stand-in for a botocore read timeout."""


@pytest.fixture(autouse=True)
def _reset_client():
    s3io.set_client(None)
    yield
    s3io.set_client(None)


def _status(client, max_bytes: int = 100) -> int:
    with pytest.raises(RequestError) as info:
        s3io.fetch_object("shots", "k.png", max_bytes, client=client)
    return info.value.status


def test_reads_object_within_cap():
    client = FakeS3(b"abc")
    assert s3io.fetch_object("shots", "a/b.png", 3, client=client) == b"abc"
    assert client.calls == [("shots", "a/b.png")]
    assert client.body.reads == [4]
    assert client.body.closed


def test_oversize_content_length_never_reads_body():
    client = FakeS3(b"x" * 10, length=101)
    assert _status(client) == 413
    assert client.body.reads == []
    assert client.body.closed


@pytest.mark.parametrize("length", [None, 1, "junk", -5])
def test_lying_or_missing_length_is_caught_by_bounded_read(length):
    client = FakeS3(b"x" * 101, length=length)
    assert _status(client) == 413
    assert client.body.reads == [101]


@pytest.mark.parametrize("code", ["NoSuchKey", "404", "AccessDenied", "403"])
def test_missing_or_denied_is_404(code):
    with pytest.raises(RequestError) as info:
        s3io.fetch_object("shots", "k", 100, client=FakeS3(error=FakeClientError(code)))
    assert info.value.status == 404
    assert str(info.value) == "screenshot not found"


@pytest.mark.parametrize(
    "error",
    [FakeClientError("SlowDown"), FakeClientError("InternalError"), ReadTimeoutError("t"), ConnectionError("x")],
)
def test_other_faults_are_503_and_log_type_only(error, capsys):
    configure_logging("INFO")
    with pytest.raises(RequestError) as info:
        s3io.fetch_object("shots", "secret/key.png", 100, client=FakeS3(error=error))
    assert info.value.status == 503
    assert str(info.value) == "screenshot store unavailable"
    out = capsys.readouterr().out
    assert type(error).__name__ in out
    assert "secret" not in out


def test_body_read_timeout_is_503():
    client = FakeS3(body_error=ReadTimeoutError("t"))
    assert _status(client) == 503
    assert client.body.closed


def test_client_is_built_once_and_cached(monkeypatch):
    built: list[object] = []

    def build():
        client = FakeS3(b"ok")
        built.append(client)
        return client

    monkeypatch.setattr(s3io, "_build_client", build)
    assert s3io.fetch_object("b", "k", 10) == b"ok"
    first = s3io.get_client()
    s3io.fetch_object("b", "k", 10)
    assert s3io.get_client() is first
    assert len(built) == 1


def test_injected_client_is_used():
    client = FakeS3(b"ok")
    s3io.set_client(client)
    assert s3io.get_client() is client
    assert s3io.fetch_object("b", "k", 10) == b"ok"


def test_real_client_has_timeouts_and_bounded_retries(monkeypatch):
    pytest.importorskip("boto3")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")
    client = s3io._build_client()
    config = client.meta.config
    assert config.connect_timeout == 2
    assert config.read_timeout == 5
    # botocore counts the first try: max_attempts=2 retries means 3 calls in total.
    assert config.retries["total_max_attempts"] == 3
