"""Model definition and ONNX export. Skipped when torch is absent."""

from __future__ import annotations

import numpy as np
import pytest

from tel_parser.model import CLASSES, GLYPH_SIZE


def test_model_package_imports_without_torch():
    import tel_parser.model.export_onnx  # noqa: F401
    import tel_parser.model.net  # noqa: F401
    import tel_parser.model.train  # noqa: F401


def test_forward_shape():
    torch = pytest.importorskip("torch")
    from tel_parser.model.net import build_model

    model = build_model()
    out = model(torch.zeros(4, 1, GLYPH_SIZE, GLYPH_SIZE))
    assert tuple(out.shape) == (4, len(CLASSES))


def test_export_has_dynamic_batch_and_quantises(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("onnx")
    ort = pytest.importorskip("onnxruntime")
    from tel_parser.model.export_onnx import export, quantise
    from tel_parser.model.net import build_model

    fp32 = tmp_path / "glyphs_fp32.onnx"
    int8 = tmp_path / "glyphs_int8.onnx"
    export(build_model(), str(fp32))
    quantise(str(fp32), str(int8))
    session = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    for batch in (1, 7):
        out = session.run(None, {"glyphs": np.zeros((batch, 1, GLYPH_SIZE, GLYPH_SIZE), dtype=np.float32)})[0]
        assert out.shape == (batch, len(CLASSES))
