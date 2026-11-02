"""Extractor builds player rows through a pluggable recogniser."""

from __future__ import annotations

import pytest

from tel_parser.extractor import extract
from tel_parser.layouts import FIELDS


def test_rows_have_decoded_stats(screenshot, fake_recogniser):
    rows = extract(screenshot, "overwatch", fake_recogniser)
    assert len(rows) == 10
    first = rows[0]
    assert first == {
        "player_slot": 0,
        "team": "ally",
        "player_name": "TRACER",
        "eliminations": 21,
        "assists": 4,
        "deaths": 7,
        "damage": 12345,
        "healing": None,
        "mitigation": 980,
    }
    assert rows[5]["team"] == "enemy"
    assert [row["player_slot"] for row in rows] == list(range(10))


def test_recogniser_called_once_with_every_cell(screenshot, fake_recogniser):
    extract(screenshot, "marvel_rivals", fake_recogniser)
    assert fake_recogniser.calls == [12 * len(FIELDS)]
    assert fake_recogniser.fields[: len(FIELDS)] == list(FIELDS)


def test_recogniser_length_mismatch_raises(screenshot):
    class Short:
        def read(self, cells, fields):
            return ["1"]

    with pytest.raises(ValueError):
        extract(screenshot, "overwatch", Short())
