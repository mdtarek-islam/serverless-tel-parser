"""Hostile image bytes map to 400 or 413, never to 500."""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from PIL import Image, ImageFile

from tel_parser.config import Settings
from tel_parser.errors import RequestError
from tel_parser.imaging import open_image

from .conftest import image_bytes, png_bytes

SETTINGS = Settings(model_path="m", max_image_bytes=4_000_000, max_image_pixels=16_000_000)


def _noisy(fmt: str, width: int = 200, height: int = 200) -> bytes:
    image = Image.effect_noise((width, height), 64).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _forged_png(width: int, height: int) -> bytes:
    """Return a small real PNG whose IHDR claims ``width`` x ``height``."""
    data = bytearray(png_bytes(64, 64))
    ihdr = bytearray(data[16:29])
    ihdr[0:8] = struct.pack(">II", width, height)
    data[16:29] = ihdr
    data[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + bytes(ihdr)) & 0xFFFFFFFF)
    return bytes(data)


def _status(data: bytes, settings: Settings = SETTINGS) -> int:
    with pytest.raises(RequestError) as info:
        open_image(data, settings)
    return info.value.status


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_allowed_formats_open(fmt):
    image = open_image(image_bytes(fmt, 80, 64), SETTINGS)
    assert image.size == (80, 64)


def test_zero_bytes_is_400():
    assert _status(b"") == 400


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_truncated_file_is_400(fmt):
    data = _noisy(fmt)
    assert _status(data[: len(data) // 2]) == 400
    assert ImageFile.LOAD_TRUNCATED_IMAGES is False


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_formats_are_400(fmt):
    assert _status(image_bytes(fmt)) == 400


def test_garbage_is_400():
    assert _status(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64) == 400


def test_forged_huge_header_is_413_without_decode():
    assert _status(_forged_png(50_000, 50_000)) == 413


def test_forged_header_within_pixel_cap_but_broken_is_400():
    assert _status(_forged_png(2000, 2000)) == 400


def test_pixel_cap_boundary():
    settings = Settings(model_path="m", max_image_pixels=64 * 80)
    assert open_image(image_bytes("PNG", 64, 80), settings).size == (64, 80)
    assert _status(image_bytes("PNG", 64, 81), settings) == 413


def test_byte_cap_boundary():
    data = image_bytes("PNG", 64, 64)
    assert open_image(data, Settings(model_path="m", max_image_bytes=len(data))).size == (64, 64)
    assert _status(data, Settings(model_path="m", max_image_bytes=len(data) - 1)) == 413


@pytest.mark.parametrize(("width", "height", "status"), [(63, 200, 400), (200, 63, 400)])
def test_side_below_minimum_is_400(width, height, status):
    assert _status(image_bytes("PNG", width, height)) == status


def test_side_at_minimum_is_ok():
    assert open_image(image_bytes("PNG", 64, 64), SETTINGS).size == (64, 64)


def test_decompression_bomb_warning_is_an_error(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 3000)
    assert _status(image_bytes("PNG", 64, 64)) == 413


def test_decompression_bomb_error_is_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    assert _status(image_bytes("PNG", 64, 64)) == 413


@pytest.mark.parametrize("error", [OSError("x"), ValueError("x"), SyntaxError("x"), EOFError("x"), struct.error("x")])
def test_decoder_faults_are_400(monkeypatch, error):
    def broken(self):
        raise error

    monkeypatch.setattr(ImageFile.ImageFile, "load", broken)
    assert _status(image_bytes("PNG", 64, 64)) == 400


def test_memory_error_is_413(monkeypatch):
    def broken(self):
        raise MemoryError

    monkeypatch.setattr(ImageFile.ImageFile, "load", broken)
    assert _status(image_bytes("PNG", 64, 64)) == 413
