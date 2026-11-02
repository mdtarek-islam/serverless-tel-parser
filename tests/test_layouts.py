"""Layout templates scale to the screenshot resolution."""

from __future__ import annotations

import pytest

from tel_parser.layouts import FIELDS, GAMES, cell_boxes, resolve_layout


@pytest.mark.parametrize("game", GAMES)
def test_boxes_scale_linearly_with_resolution(game):
    small = cell_boxes(resolve_layout(game, 1920, 1080), 1920, 1080)
    large = cell_boxes(resolve_layout(game, 3840, 2160), 3840, 2160)
    assert len(small) == len(large)
    for row_small, row_large in zip(small, large):
        for field in FIELDS:
            for a, b in zip(row_small[field], row_large[field]):
                assert abs(2 * a - b) <= 1


@pytest.mark.parametrize("game", GAMES)
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1200), (2560, 1080), (1024, 768)])
def test_boxes_stay_inside_the_image(game, size):
    width, height = size
    for row in cell_boxes(resolve_layout(game, width, height), width, height):
        for left, top, right, bottom in row.values():
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height


def test_row_counts_match_team_size():
    assert len(cell_boxes(resolve_layout("overwatch", 1920, 1080), 1920, 1080)) == 10
    assert len(cell_boxes(resolve_layout("marvel_rivals", 1920, 1080), 1920, 1080)) == 12


def test_ultrawide_is_pillarboxed_around_the_16_9_template():
    base = cell_boxes(resolve_layout("overwatch", 1920, 1080), 1920, 1080)
    wide = cell_boxes(resolve_layout("overwatch", 2560, 1080), 2560, 1080)
    for field in FIELDS:
        assert wide[0][field][0] == base[0][field][0] + 320
        assert wide[0][field][1] == base[0][field][1]


def test_16_10_selects_its_own_template():
    assert resolve_layout("overwatch", 1920, 1200).aspect == "16:10"
    assert resolve_layout("overwatch", 1920, 1080).aspect == "16:9"


def test_templates_are_marked_uncalibrated():
    assert resolve_layout("marvel_rivals", 1920, 1080).calibrated is False


def test_unknown_game_raises():
    with pytest.raises(ValueError):
        resolve_layout("chess", 1920, 1080)
