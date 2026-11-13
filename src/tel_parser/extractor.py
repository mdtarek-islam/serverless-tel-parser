"""Screenshot to scoreboard rows through a pluggable recogniser."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from PIL import Image

from .inference import decode_int
from .layouts import FIELDS, NUMERIC_FIELDS, LayoutTemplate, cell_boxes, resolve_layout


class Recogniser(Protocol):
    """Read one string per cell. ``fields`` names the column of each cell."""

    def read(self, cells: Sequence[Image.Image], fields: Sequence[str]) -> list[str]: ...


def extract(
    image: Image.Image, game: str, recogniser: Recogniser, layout: LayoutTemplate | None = None
) -> list[dict[str, Any]]:
    """Return one stats dict per scoreboard slot, ordered by slot.

    All cells go to the recogniser in a single call so that inference
    runs as one batch. Pass ``layout`` to skip a second template lookup.
    """
    image = image.convert("RGB")
    layout = layout or resolve_layout(game, image.width, image.height)
    grid = cell_boxes(layout, image.width, image.height)

    cells: list[Image.Image] = []
    fields: list[str] = []
    for boxes in grid:
        for name in FIELDS:
            cells.append(image.crop(boxes[name]))
            fields.append(name)

    texts = recogniser.read(cells, fields)
    if len(texts) != len(cells):
        raise ValueError(f"recogniser returned {len(texts)} texts for {len(cells)} cells")

    rows: list[dict[str, Any]] = []
    width = len(FIELDS)
    for slot in range(len(grid)):
        values = dict(zip(FIELDS, texts[slot * width : (slot + 1) * width], strict=True))
        row: dict[str, Any] = {"player_slot": slot, "team": layout.team_of(slot)}
        row["player_name"] = values["player_name"].strip()
        for name in NUMERIC_FIELDS:
            row[name] = decode_int(values[name])
        rows.append(row)
    return rows
