"""Digit and glyph caps on the model path."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tel_parser import inference
from tel_parser.model import CLASSES, GLYPH_SIZE


def test_twelve_digits_decode():
    assert inference.MAX_DIGITS == 12
    assert inference.decode_int("123456789012") == 123_456_789_012


@pytest.mark.parametrize("text", ["1234567890123", "9" * 5000, "1 2 3 4 5 6 7 8 9 0 1 2 3"])
def test_too_many_digits_is_null(text):
    assert inference.decode_int(text) is None


def _cell(glyphs: int) -> Image.Image:
    cell = Image.new("RGB", (glyphs * 4 + 4, 20), (0, 0, 0))
    draw = ImageDraw.Draw(cell)
    for index in range(glyphs):
        left = 2 + index * 4
        draw.rectangle([left, 4, left + 1, 15], fill=(255, 255, 255))
    return cell


class CountingSession:
    def __init__(self) -> None:
        self.batches: list[tuple[int, ...]] = []

    def run(self, outputs, feeds):
        batch = feeds[inference.INPUT_NAME]
        assert batch.dtype == np.float32
        assert batch.shape[1:] == (1, GLYPH_SIZE, GLYPH_SIZE)
        self.batches.append(batch.shape)
        logits = np.zeros((batch.shape[0], len(CLASSES)), dtype=np.float32)
        logits[:, CLASSES.index("7")] = 5.0
        return [logits]


def test_cell_over_glyph_cap_is_unreadable():
    assert inference.MAX_GLYPHS_PER_CELL == 24
    session = CountingSession()
    texts = inference.OnnxRecogniser(session).read([_cell(25), _cell(24)], ["damage", "damage"])
    assert texts == ["", "7" * 24]
    assert session.batches == [(24, 1, GLYPH_SIZE, GLYPH_SIZE)]


def test_only_over_cap_cells_skip_the_session():
    session = CountingSession()
    assert inference.OnnxRecogniser(session).read([_cell(25)], ["damage"]) == [""]
    assert session.batches == []


def test_missing_onnxruntime_disables_recogniser(monkeypatch, tmp_path):
    path = tmp_path / "m.onnx"
    path.write_bytes(b"x")

    def broken(model_path):
        raise ImportError("no onnxruntime")

    monkeypatch.setattr(inference, "create_session", broken)
    assert inference._load_session(str(path)) is None


def test_missing_model_file_disables_recogniser(tmp_path):
    assert inference._load_session(str(tmp_path / "absent.onnx")) is None
