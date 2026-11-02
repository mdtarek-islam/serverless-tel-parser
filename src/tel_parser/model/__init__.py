"""Glyph classifier constants shared by training and inference.

This module stays free of torch so the Lambda runtime can import it.
"""

from __future__ import annotations

GLYPH_SIZE = 32
BLANK_INDEX = 0
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Class 0 is "blank": noise, separators and anything outside the charset.
CLASSES: tuple[str, ...] = ("<blank>", *CHARSET)
NUM_CLASSES = len(CLASSES)
