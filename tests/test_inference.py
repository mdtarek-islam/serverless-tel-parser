"""Decode logic and the ONNX Runtime session wrapper."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tel_parser import inference
from tel_parser.model import BLANK_INDEX, CLASSES, GLYPH_SIZE


def _onehot(labels: list[str]) -> np.ndarray:
    logits = np.zeros((len(labels), len(CLASSES)), dtype=np.float32)
    for row, label in enumerate(labels):
        logits[row, CLASSES.index(label)] = 5.0
    return logits


def test_logits_to_texts_splits_by_counts():
    logits = _onehot(["1", "2", "A", "N", "A"])
    assert inference.logits_to_texts(logits, [2, 0, 3]) == ["12", "", "ANA"]


def test_blank_class_is_dropped():
    logits = _onehot(["4", CLASSES[BLANK_INDEX], "2"])
    assert inference.logits_to_texts(logits, [3]) == ["42"]


def test_counts_must_cover_logits():
    with pytest.raises(ValueError):
        inference.logits_to_texts(_onehot(["1"]), [2])


@pytest.mark.parametrize(
    ("text", "expected"),
    [("21", 21), ("12,345", 12345), ("1 024", 1024), ("", None), ("--", None), ("O7", 7)],
)
def test_decode_int(text, expected):
    assert inference.decode_int(text) == expected


def test_recogniser_batches_all_cells_into_one_run():
    class FakeSession:
        def __init__(self):
            self.batches = []

        def run(self, outputs, feeds):
            batch = feeds[inference.INPUT_NAME]
            self.batches.append(batch.shape)
            return [_onehot(["7"] * batch.shape[0])]

    cell = Image.new("RGB", (60, 24), (0, 0, 0))
    ImageDraw.Draw(cell).rectangle([5, 4, 12, 19], fill=(255, 255, 255))
    ImageDraw.Draw(cell).rectangle([25, 4, 32, 19], fill=(255, 255, 255))
    session = FakeSession()
    texts = inference.OnnxRecogniser(session).read([cell, cell, Image.new("RGB", (20, 20))], ["kills"] * 3)
    assert texts == ["77", "77", ""]
    assert session.batches == [(4, 1, GLYPH_SIZE, GLYPH_SIZE)]


def test_real_session_runs_tiny_graph(tmp_path):
    ort = pytest.importorskip("onnxruntime")
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper, numpy_helper

    weights = np.zeros((GLYPH_SIZE * GLYPH_SIZE, len(CLASSES)), dtype=np.float32)
    graph = helper.make_graph(
        [
            helper.make_node("Flatten", ["glyphs"], ["flat"], axis=1),
            helper.make_node("MatMul", ["flat", "w"], ["logits"]),
        ],
        "tiny",
        [helper.make_tensor_value_info("glyphs", TensorProto.FLOAT, ["batch", 1, GLYPH_SIZE, GLYPH_SIZE])],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", len(CLASSES)])],
        [numpy_helper.from_array(weights, "w")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
    path = tmp_path / "tiny.onnx"
    onnx.save(model, str(path))

    session = inference.create_session(str(path))
    assert isinstance(session, ort.InferenceSession)
    out = session.run(None, {"glyphs": np.zeros((3, 1, GLYPH_SIZE, GLYPH_SIZE), dtype=np.float32)})[0]
    assert out.shape == (3, len(CLASSES))
