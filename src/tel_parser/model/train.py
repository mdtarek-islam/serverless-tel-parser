"""Training skeleton for the glyph classifier.

Dataset layout for ``FolderGlyphDataset``::

    data/glyphs/<label>/*.png

``<label>`` is one character from CHARSET, or ``_blank`` for noise and
separators. Each PNG holds one glyph crop. Build crops with
``tel_parser.preprocess.segment_glyphs`` so training sees the same
segmentation as inference.

Usage::

    python -m tel_parser.model.train --data data/glyphs --out model/glyphs.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from ..preprocess import binarise, normalise_glyph, to_gray
from . import CHARSET, CLASSES


class GlyphDataset(Protocol):
    """Any indexable source of (glyph tensor, class index) pairs."""

    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> tuple[np.ndarray, int]: ...


class FolderGlyphDataset:
    """Read labelled glyph PNGs from one folder per class."""

    def __init__(self, root: str | Path) -> None:
        self.items: list[tuple[Path, int]] = []
        for folder in sorted(Path(root).iterdir()):
            if not folder.is_dir():
                continue
            label = "<blank>" if folder.name == "_blank" else folder.name.upper()
            if label != "<blank>" and label not in CHARSET:
                continue
            index = CLASSES.index(label)
            self.items.extend((path, index) for path in sorted(folder.glob("*.png")))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> tuple[np.ndarray, int]:
        path, label = self.items[index]
        with Image.open(path) as image:
            mask = binarise(to_gray(image)).astype(np.float32)
        return normalise_glyph(mask), label


def train(dataset: GlyphDataset, out_path: str, epochs: int = 20, batch_size: int = 256, lr: float = 1e-3) -> None:
    """Fit the classifier and save a state dict to ``out_path``."""
    import torch
    from torch.utils.data import DataLoader

    from .net import build_model

    if len(dataset) == 0:
        raise ValueError("dataset is empty")
    model = build_model()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    optimiser = torch.optim.AdamW(model.parameters(), lr=lr)
    loss_fn = torch.nn.CrossEntropyLoss()
    for epoch in range(epochs):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0
        for glyphs, labels in loader:
            optimiser.zero_grad()
            logits = model(glyphs.float())
            loss = loss_fn(logits, labels)
            loss.backward()
            optimiser.step()
            loss_sum += float(loss) * labels.shape[0]
            correct += int((logits.argmax(1) == labels).sum())
            total += labels.shape[0]
        print(f"epoch {epoch + 1}/{epochs} loss {loss_sum / total:.4f} train_acc {correct / total:.4f}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", default="model/glyphs.pt")
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    train(FolderGlyphDataset(args.data), args.out, epochs=args.epochs)


if __name__ == "__main__":
    main()
