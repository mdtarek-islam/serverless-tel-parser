"""Pre-processing produces fixed-shape glyph tensors."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from tel_parser.model import GLYPH_SIZE
from tel_parser.preprocess import (
    cell_to_glyphs,
    normalise_glyph,
    otsu_threshold,
    segment_glyphs,
    to_gray,
)


def _bars(count: int, dark_text: bool = False) -> Image.Image:
    background, ink = ((240, 240, 240), (10, 10, 10)) if dark_text else ((10, 10, 10), (240, 240, 240))
    image = Image.new("RGB", (20 * count + 10, 24), background)
    draw = ImageDraw.Draw(image)
    for index in range(count):
        left = 6 + index * 20
        draw.rectangle([left, 4, left + 8, 19], fill=ink)
    return image


def test_to_gray_returns_unit_range_float():
    gray = to_gray(_bars(2))
    assert gray.dtype == np.float32
    assert gray.shape == (24, 50)
    assert gray.min() >= 0.0 and gray.max() <= 1.0


def test_otsu_splits_two_levels():
    gray = to_gray(_bars(3))
    threshold = otsu_threshold(gray)
    assert 0.05 < threshold < 0.95


def test_segment_counts_separate_glyphs():
    assert len(segment_glyphs(to_gray(_bars(3)))) == 3


def test_segment_handles_dark_text_on_light_background():
    assert len(segment_glyphs(to_gray(_bars(4, dark_text=True)))) == 4


def test_segment_blank_cell_returns_nothing():
    assert segment_glyphs(np.zeros((20, 40), dtype=np.float32)) == []


def test_normalise_glyph_shape_and_range():
    out = normalise_glyph(np.ones((15, 5), dtype=np.float32))
    assert out.shape == (1, GLYPH_SIZE, GLYPH_SIZE)
    assert out.dtype == np.float32
    assert out.min() >= -1.0 and out.max() <= 1.0


def test_cell_to_glyphs_stacks_batch():
    batch = cell_to_glyphs(_bars(5))
    assert batch.shape == (5, 1, GLYPH_SIZE, GLYPH_SIZE)


def test_cell_to_glyphs_empty_cell_has_zero_batch():
    batch = cell_to_glyphs(Image.new("RGB", (40, 20), (0, 0, 0)))
    assert batch.shape == (0, 1, GLYPH_SIZE, GLYPH_SIZE)
