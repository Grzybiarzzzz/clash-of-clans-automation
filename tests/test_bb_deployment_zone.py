"""Characterisation tests for the screenshot-free parts of the Builder Base zone detector."""
import math

import pytest

from coc_bot.vision import bb_deployment_zone as zone


@pytest.fixture(autouse=True)
def no_discord(monkeypatch):
    monkeypatch.setattr(zone, "send_discord_debug_log", lambda *args, **kwargs: None)


def line_data(line):
    return zone.filter_lines_by_length([line], min_length=0)[0]


def test_filter_lines_by_length_drops_short_lines_and_annotates_the_rest():
    result = zone.filter_lines_by_length([(0, 0, 30, 0), (0, 0, 100, 0)], min_length=50)
    assert len(result) == 1
    assert result[0]["line"] == (0, 0, 100, 0)
    assert result[0]["length"] == pytest.approx(100)
    assert result[0]["angle"] == pytest.approx(0)


def test_collinear_when_same_angle_and_small_perpendicular_offset():
    assert zone.are_lines_collinear(line_data((0, 0, 100, 0)), line_data((150, 5, 250, 5)))


def test_not_collinear_when_parallel_but_far_apart():
    offset = zone.BB_DRAGON_LINE_MERGE_DIST + 20
    assert not zone.are_lines_collinear(line_data((0, 0, 100, 0)), line_data((150, offset, 250, offset)))


def test_not_collinear_when_perpendicular():
    assert not zone.are_lines_collinear(line_data((0, 0, 100, 0)), line_data((50, -50, 50, 50)))


def test_endpoint_distance_is_the_closest_pair_of_endpoints():
    assert zone.get_endpoint_distance((0, 0, 100, 0), (150, 0, 250, 0)) == pytest.approx(50)


def test_merge_joins_collinear_segments_within_the_gap():
    gap = zone.BB_DRAGON_LINE_MERGE_GAP - 50
    lines = [line_data((0, 0, 100, 0)), line_data((100 + gap, 0, 300, 0))]
    assert zone.merge_collinear_lines(lines) == [(0, 0, 300, 0)]


def test_merge_keeps_segments_separated_by_more_than_the_gap():
    gap = zone.BB_DRAGON_LINE_MERGE_GAP + 50
    lines = [line_data((0, 0, 100, 0)), line_data((100 + gap, 0, 400, 0))]
    assert zone.merge_collinear_lines(lines) == [(0, 0, 100, 0), (100 + gap, 0, 400, 0)]


def test_merge_empty_input():
    assert zone.merge_collinear_lines([]) == []


def test_ring_fallback_is_centred_on_the_capture_region():
    coords = zone.generate_ring_fallback_coords()
    assert len(coords) == 8
    assert coords[0] == (1680, 650)
    assert coords[4] == (880, 650)


def test_ring_fallback_is_clamped_to_the_playable_area():
    for x, y in zone.generate_ring_fallback_coords(radius=5000):
        assert 250 <= x <= 2300
        assert 150 <= y <= 1150


def test_select_equally_spaced_returns_input_when_few_points():
    coords = [(0, 0), (10, 10)]
    assert zone.select_equally_spaced_coords(coords, num_points=6) == coords


def test_select_equally_spaced_respects_minimum_distance():
    circle = [(int(1000 + 500 * math.cos(2 * math.pi * i / 12)), int(600 + 500 * math.sin(2 * math.pi * i / 12)))
              for i in range(12)]
    selected = zone.select_equally_spaced_coords(circle, num_points=6, min_distance=150)
    assert len(selected) == 6
    assert set(selected) <= set(circle)
    for i, p in enumerate(selected):
        for q in selected[i + 1:]:
            assert math.dist(p, q) >= 150


def test_filter_out_unit_bar_removes_unit_bar_and_surrender_button_areas():
    coords = [(100, 1300), (100, 1100), (1000, 500)]
    assert zone.filter_out_unit_bar(coords) == [(1000, 500)]
