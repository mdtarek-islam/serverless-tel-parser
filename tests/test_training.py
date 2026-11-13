"""Training and export entry points on tiny synthetic data."""

from __future__ import annotations

import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tel_parser.model import CLASSES, GLYPH_SIZE


def _glyph_png(path, offset: int) -> None:
    image = Image.new("L", (12, 16), 0)
    ImageDraw.Draw(image).rectangle([2 + offset, 2, 6 + offset, 13], fill=255)
    image.save(path)


@pytest.fixture()
def glyph_root(tmp_path):
    root = tmp_path / "glyphs"
    for name in ("0", "a", "_blank", "not-a-char"):
        folder = root / name
        folder.mkdir(parents=True)
        for index in range(3):
            _glyph_png(folder / f"{index}.png", index)
    (root / "README.txt").write_text("not a folder", encoding="utf-8")
    return root


def test_folder_dataset_reads_labels(glyph_root):
    from tel_parser.model.train import FolderGlyphDataset

    dataset = FolderGlyphDataset(glyph_root)
    assert len(dataset) == 9
    labels = sorted({label for _path, label in dataset.items})
    assert labels == sorted([CLASSES.index("0"), CLASSES.index("A"), CLASSES.index("<blank>")])
    glyph, label = dataset[0]
    assert glyph.shape == (1, GLYPH_SIZE, GLYPH_SIZE)
    assert glyph.dtype == np.float32
    assert label in labels


def test_train_writes_state_dict(glyph_root, tmp_path, capsys):
    torch = pytest.importorskip("torch")
    from tel_parser.model.train import FolderGlyphDataset, train

    out = tmp_path / "out" / "glyphs.pt"
    train(FolderGlyphDataset(glyph_root), str(out), epochs=2, batch_size=4)
    state = torch.load(str(out), map_location="cpu", weights_only=True)
    assert any(key.endswith("weight") for key in state)
    assert "epoch 2/2" in capsys.readouterr().out


def test_train_rejects_empty_dataset(tmp_path):
    pytest.importorskip("torch")
    from tel_parser.model.train import train

    class Empty:
        def __len__(self):
            return 0

        def __getitem__(self, index):
            raise IndexError(index)

    with pytest.raises(ValueError):
        train(Empty(), str(tmp_path / "x.pt"))


def test_train_main_parses_arguments(glyph_root, tmp_path, monkeypatch):
    pytest.importorskip("torch")
    from tel_parser.model import train as train_module

    out = tmp_path / "main.pt"
    monkeypatch.setattr(sys, "argv", ["train", "--data", str(glyph_root), "--out", str(out), "--epochs", "1"])
    train_module.main()
    assert out.exists()


def test_export_main_writes_both_graphs(tmp_path, monkeypatch, capsys):
    torch = pytest.importorskip("torch")
    pytest.importorskip("onnx")
    ort = pytest.importorskip("onnxruntime")
    from tel_parser.model import export_onnx
    from tel_parser.model.net import build_model

    weights = tmp_path / "glyphs.pt"
    torch.save(build_model().state_dict(), str(weights))
    fp32, int8 = tmp_path / "f.onnx", tmp_path / "i.onnx"
    monkeypatch.setattr(sys, "argv", ["export", "--weights", str(weights), "--fp32", str(fp32), "--int8", str(int8)])
    export_onnx.main()
    assert "wrote" in capsys.readouterr().out
    session = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"])
    out = session.run(None, {"glyphs": np.zeros((3, 1, GLYPH_SIZE, GLYPH_SIZE), dtype=np.float32)})[0]
    assert out.shape == (3, len(CLASSES))
