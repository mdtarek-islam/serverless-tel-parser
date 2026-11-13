"""ONNX Runtime glyph recogniser.

The session is created once at module import. Lambda keeps the module in
memory between invokes, so warm requests reuse it. When the model file or
onnxruntime is missing, ``SESSION`` is None and the handler returns 503.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from typing import Any

import numpy as np
from PIL import Image

from .config import Settings
from .logging_utils import configure_logging, log_event
from .model import BLANK_INDEX, CLASSES, GLYPH_SIZE
from .preprocess import cell_to_glyphs

LOGGER = logging.getLogger(__name__)
INPUT_NAME = "glyphs"
# A scoreboard number never needs more digits. Longer reads are noise.
MAX_DIGITS = 12
# A wider cell is noise or an attack. It also bounds one batch to 84 * 24 glyphs.
MAX_GLYPHS_PER_CELL = 24
_DIGITS = re.compile(r"\d")
# Glyphs the classifier tends to confuse with digits on numeric columns.
_DIGIT_LOOKALIKES = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8"})


def create_session(model_path: str) -> Any:
    """Build an InferenceSession tuned for a single-vCPU Lambda slice."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])


def _load_session(model_path: str) -> Any:
    if not os.path.exists(model_path):
        log_event(LOGGER, "recogniser_disabled", level=logging.WARNING, reason="model_file_missing")
        return None
    try:
        return create_session(model_path)
    except ImportError:
        log_event(LOGGER, "recogniser_disabled", level=logging.WARNING, reason="onnxruntime_missing")
        return None


def logits_to_texts(logits: np.ndarray, counts: Sequence[int]) -> list[str]:
    """Argmax each glyph, drop blanks and join glyphs back into cell strings."""
    if sum(counts) != logits.shape[0]:
        raise ValueError(f"counts sum to {sum(counts)} but logits hold {logits.shape[0]} glyphs")
    labels = logits.argmax(axis=1) if logits.size else np.zeros(0, dtype=int)
    texts: list[str] = []
    offset = 0
    for count in counts:
        chunk = labels[offset : offset + count]
        texts.append("".join(CLASSES[i] for i in chunk if i != BLANK_INDEX))
        offset += count
    return texts


def decode_int(text: str) -> int | None:
    """Read an integer from a recognised cell.

    Return None for an empty cell or one with more than MAX_DIGITS digits.
    """
    digits = "".join(_DIGITS.findall(text.upper().translate(_DIGIT_LOOKALIKES)))
    if not digits or len(digits) > MAX_DIGITS:
        return None
    return int(digits)


class OnnxRecogniser:
    """Read text from many cells with one session.run call."""

    def __init__(self, session: Any) -> None:
        self.session = session

    def read(self, cells: Sequence[Image.Image], fields: Sequence[str]) -> list[str]:
        batches = [cell_to_glyphs(cell) for cell in cells]
        empty = np.zeros((0, 1, GLYPH_SIZE, GLYPH_SIZE), dtype=np.float32)
        batches = [batch if batch.shape[0] <= MAX_GLYPHS_PER_CELL else empty for batch in batches]
        counts = [batch.shape[0] for batch in batches]
        if sum(counts) == 0:
            return [""] * len(cells)
        stacked = np.concatenate(batches, axis=0).astype(np.float32, copy=False)
        logits = self.session.run(None, {INPUT_NAME: stacked})[0]
        return logits_to_texts(np.asarray(logits), counts)


_SETTINGS = Settings.from_env()
# Configure the JSON logger here too: this module logs while it imports.
configure_logging(_SETTINGS.log_level)
SESSION = _load_session(_SETTINGS.model_path)
RECOGNISER = OnnxRecogniser(SESSION) if SESSION is not None else None

__all__ = [
    "GLYPH_SIZE",
    "INPUT_NAME",
    "MAX_DIGITS",
    "MAX_GLYPHS_PER_CELL",
    "OnnxRecogniser",
    "RECOGNISER",
    "SESSION",
    "create_session",
    "decode_int",
    "logits_to_texts",
]
