"""Small CNN glyph classifier. torch loads only when a model is built."""

from __future__ import annotations

from typing import Any

from . import GLYPH_SIZE, NUM_CLASSES


def build_model(num_classes: int = NUM_CLASSES) -> Any:
    """Return a CNN that maps (n, 1, 32, 32) glyphs to (n, num_classes) logits.

    Three conv blocks and a global pool keep the weight count near 25k,
    which keeps the int8 file small and the session load short.
    """
    from torch import nn

    def block(c_in: int, c_out: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(c_in, c_out, kernel_size=3, padding=1),
            nn.BatchNorm2d(c_out),
            nn.ReLU(inplace=True),
        )

    return nn.Sequential(
        block(1, 16),
        nn.MaxPool2d(2),
        block(16, 32),
        nn.MaxPool2d(2),
        block(32, 64),
        nn.AdaptiveAvgPool2d(1),
        nn.Flatten(),
        nn.Dropout(0.2),
        nn.Linear(64, num_classes),
    )


INPUT_SHAPE = (1, GLYPH_SIZE, GLYPH_SIZE)
