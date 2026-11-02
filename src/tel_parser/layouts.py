"""Scoreboard regions of interest per game and aspect ratio.

CALIBRATION TEMPLATES. Every coordinate below is a starting estimate in
normalised screen units (0.0 to 1.0). Measure each value against real
scoreboard screenshots at the target resolution before trusting output.
Set ``calibrated=True`` on a template only after that check.

A template covers one aspect ratio. ``resolve_layout`` picks the nearest
template, then ``cell_boxes`` scales it to pixels. A screen wider than the
template is treated as pillarboxed: the template sits in a centred region
of the template aspect ratio. A taller screen is letterboxed the same way.
This pillarbox rule is an assumption about the game UI, not a measurement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

FIELDS: tuple[str, ...] = (
    "player_name",
    "eliminations",
    "assists",
    "deaths",
    "damage",
    "healing",
    "mitigation",
)
NUMERIC_FIELDS: tuple[str, ...] = FIELDS[1:]
GAMES: tuple[str, ...] = ("overwatch", "marvel_rivals")

PixelBox = tuple[int, int, int, int]


@dataclass(frozen=True)
class Span:
    """Normalised horizontal extent of one column."""

    start: float
    end: float


@dataclass(frozen=True)
class LayoutTemplate:
    """Row and column geometry for one game at one aspect ratio."""

    game: str
    aspect: str
    aspect_ratio: float
    team_tops: tuple[float, float]
    rows_per_team: int
    row_pitch: float
    row_height: float
    columns: Mapping[str, Span] = field(default_factory=dict)
    calibrated: bool = False

    @property
    def row_count(self) -> int:
        return self.rows_per_team * len(self.team_tops)

    def team_of(self, slot: int) -> str:
        return "ally" if slot < self.rows_per_team else "enemy"


# Overwatch: 5 versus 5. Allied team in the upper block, enemy team below.
# The mitigation column holds "damage mitigated".
_OW_COLUMNS = {
    "player_name": Span(0.245, 0.370),
    "eliminations": Span(0.470, 0.505),
    "assists": Span(0.510, 0.545),
    "deaths": Span(0.550, 0.585),
    "damage": Span(0.600, 0.660),
    "healing": Span(0.670, 0.730),
    "mitigation": Span(0.740, 0.800),
}

# Marvel Rivals: 6 versus 6. The mitigation column holds "damage blocked".
_MR_COLUMNS = {
    "player_name": Span(0.200, 0.330),
    "eliminations": Span(0.420, 0.455),
    "assists": Span(0.460, 0.495),
    "deaths": Span(0.500, 0.535),
    "damage": Span(0.555, 0.615),
    "healing": Span(0.625, 0.685),
    "mitigation": Span(0.695, 0.755),
}

TEMPLATES: tuple[LayoutTemplate, ...] = (
    LayoutTemplate("overwatch", "16:9", 16 / 9, (0.205, 0.555), 5, 0.058, 0.045, _OW_COLUMNS),
    LayoutTemplate("overwatch", "16:10", 16 / 10, (0.225, 0.560), 5, 0.054, 0.042, _OW_COLUMNS),
    LayoutTemplate("marvel_rivals", "16:9", 16 / 9, (0.180, 0.560), 6, 0.050, 0.042, _MR_COLUMNS),
    LayoutTemplate("marvel_rivals", "16:10", 16 / 10, (0.195, 0.565), 6, 0.047, 0.039, _MR_COLUMNS),
)


def resolve_layout(game: str, width: int, height: int) -> LayoutTemplate:
    """Return the template for ``game`` with the nearest aspect ratio."""
    candidates = [t for t in TEMPLATES if t.game == game]
    if not candidates:
        raise ValueError(f"unknown game {game!r}; expected one of {GAMES}")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    ratio = width / height
    return min(candidates, key=lambda t: abs(t.aspect_ratio - ratio))


def _content_region(template: LayoutTemplate, width: int, height: int) -> tuple[float, float, float, float]:
    """Return (x0, y0, w, h) of the area that holds the template."""
    ratio = width / height
    if ratio > template.aspect_ratio:
        content_w = height * template.aspect_ratio
        return (width - content_w) / 2, 0.0, content_w, float(height)
    content_h = width / template.aspect_ratio
    return 0.0, (height - content_h) / 2, float(width), content_h


def cell_boxes(template: LayoutTemplate, width: int, height: int) -> list[dict[str, PixelBox]]:
    """Return one dict per scoreboard row mapping field to a pixel box.

    Boxes use the PIL convention (left, top, right, bottom).
    """
    x0, y0, cw, ch = _content_region(template, width, height)
    rows: list[dict[str, PixelBox]] = []
    for team_top in template.team_tops:
        for index in range(template.rows_per_team):
            top_n = team_top + index * template.row_pitch
            top = round(y0 + top_n * ch)
            bottom = round(y0 + (top_n + template.row_height) * ch)
            rows.append(
                {
                    name: (round(x0 + span.start * cw), top, round(x0 + span.end * cw), bottom)
                    for name, span in template.columns.items()
                }
            )
    return rows
