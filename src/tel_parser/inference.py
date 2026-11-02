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

import numpy as np
from PIL import Image

from .config import Settings
from .model import BLANK_INDEX, CLASSES, GLYPH_SIZE
from .preprocess import cell_to_glyphs

LOGGER = logging.getLogger(__name__)
INPUT_NAME = "glyphs"
_DIGITS = re.compile(r"\d")
# Glyphs the classifier tends to confuse with digits on numeric columns.
_DIGIT_LOOKALIKES = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8"})


def create_session(model_path: str):
    """Build an InferenceSession tuned for a single-vCPU Lambda slice."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])


def _load_session(model_path: str):
    if not os.path.exists(model_path):
        LOGGER.warning("model file not found at %s; recogniser disabled", model_path)
        return None
    try:
        return create_session(model_path)
    except ImportError:
        LOGGER.warning("onnxruntime is not installed; recogniser disabled")
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
    """Read an integer from a recognised cell. Return None for an empty cell."""
    digits = "".join(_DIGITS.findall(text.upper().translate(_DIGIT_LOOKALIKES)))
    return int(digits) if digits else None


class OnnxRecogniser:
    """Read text from many cells with one session.run call."""

    def __init__(self, session) -> None:
        self.session = session

    def read(self, cells: Sequence[Image.Image], fields: Sequence[str]) -> list[str]:
        batches = [cell_to_glyphs(cell) for cell in cells]
        counts = [batch.shape[0] for batch in batches]
        if sum(counts) == 0:
            return [""] * len(cells)
        stacked = np.concatenate(batches, axis=0).astype(np.float32, copy=False)
        logits = self.session.run(None, {INPUT_NAME: stacked})[0]
        return logits_to_texts(np.asarray(logits), counts)


SESSION = _load_session(Settings.from_env().model_path)
RECOGNISER = OnnxRecogniser(SESSION) if SESSION is not None else None

__all__ = ["GLYPH_SIZE", "INPUT_NAME", "OnnxRecogniser", "RECOGNISER", "SESSION", "create_session", "decode_int", "logits_to_texts"]
