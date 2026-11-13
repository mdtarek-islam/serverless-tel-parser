"""Turn scoreboard cells into fixed-size glyph tensors with PIL and numpy.

Pipeline per cell: grayscale, Otsu binarisation, polarity fix, column
projection to split glyphs, tight crop, pad to square, resize, normalise.
Training uses ``normalise_glyph`` as well, so both paths match.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .model import GLYPH_SIZE

_MIN_GLYPH_WIDTH = 1
_MIN_CONTRAST = 0.08


def to_gray(image: Image.Image) -> np.ndarray:
    """Return a float32 array in 0.0 to 1.0 with shape (height, width)."""
    return np.asarray(image.convert("L"), dtype=np.float32) / 255.0


def otsu_threshold(gray: np.ndarray) -> float:
    """Return the Otsu threshold of a unit-range grayscale array."""
    hist, edges = np.histogram(gray, bins=256, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    centres = (edges[:-1] + edges[1:]) / 2
    weight_bg = np.cumsum(hist)
    weight_fg = weight_bg[-1] - weight_bg
    sum_bg = np.cumsum(hist * centres)
    mean_bg = np.divide(sum_bg, weight_bg, out=np.zeros_like(sum_bg), where=weight_bg > 0)
    mean_fg = np.divide(sum_bg[-1] - sum_bg, weight_fg, out=np.zeros_like(sum_bg), where=weight_fg > 0)
    between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    # Clean HUD text gives a flat maximum. Take the centre of that plateau.
    best = np.flatnonzero(np.isclose(between, between.max()))
    return float(centres[best].mean())


def binarise(gray: np.ndarray) -> np.ndarray:
    """Return a boolean ink mask. Ink is the minority class."""
    if gray.size == 0 or float(gray.max() - gray.min()) < _MIN_CONTRAST:
        return np.zeros(gray.shape, dtype=bool)
    mask = gray > otsu_threshold(gray)
    if mask.mean() > 0.5:
        mask = ~mask
    return mask


def segment_glyphs(gray: np.ndarray) -> list[np.ndarray]:
    """Split a cell into glyph masks, left to right, by column projection."""
    mask = binarise(gray)
    columns = mask.any(axis=0)
    glyphs: list[np.ndarray] = []
    start = None
    for x, inked in enumerate([*columns.tolist(), False]):
        if inked and start is None:
            start = x
        elif not inked and start is not None:
            if x - start >= _MIN_GLYPH_WIDTH:
                piece = mask[:, start:x]
                rows = np.flatnonzero(piece.any(axis=1))
                glyphs.append(piece[rows[0] : rows[-1] + 1].astype(np.float32))
            start = None
    return glyphs


def normalise_glyph(glyph: np.ndarray, size: int = GLYPH_SIZE) -> np.ndarray:
    """Pad a glyph mask to a square, resize and scale to -1.0 to 1.0.

    Return shape (1, size, size), dtype float32.
    """
    height, width = glyph.shape
    side = max(height, width) + 2
    canvas = np.zeros((side, side), dtype=np.float32)
    top, left = (side - height) // 2, (side - width) // 2
    canvas[top : top + height, left : left + width] = glyph
    resized = Image.fromarray((canvas * 255).astype(np.uint8)).resize((size, size), Image.Resampling.BILINEAR)
    scaled = np.asarray(resized, dtype=np.float32) / 255.0
    return ((scaled - 0.5) / 0.5)[None, :, :]


def cell_to_glyphs(cell: Image.Image, size: int = GLYPH_SIZE) -> np.ndarray:
    """Return a (n, 1, size, size) batch for every glyph in one cell."""
    glyphs = [normalise_glyph(g, size) for g in segment_glyphs(to_gray(cell))]
    if not glyphs:
        return np.zeros((0, 1, size, size), dtype=np.float32)
    return np.stack(glyphs).astype(np.float32)
