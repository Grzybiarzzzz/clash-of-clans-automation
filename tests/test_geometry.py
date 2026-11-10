"""Characterisation tests for the pure helpers in coc_bot.geometry."""
import config
from coc_bot.geometry import (
    calculate_deployment_step,
    calculate_lightning_spells_needed,
    find_building_clusters,
    get_air_defense_proximity_sorter,
    get_cluster_center,
    get_lightning_spell_targets,
    get_opposite_side,
    interpolate_points,
)


def building(x, y):
    """A detection tuple with an unknown type, so the default 70x70 size applies."""
    return (x, y, 0.9, "unknown_type")


def test_interpolate_points_includes_both_endpoints():
    points = interpolate_points((0, 0), (10, 20), 5)
    assert len(points) == 5
    assert points[0] == (0, 0)
    assert points[2] == (5, 10)
    assert points[-1] == (10, 20)


def test_interpolate_points_single_point_is_start():
    assert interpolate_points((3, 4), (10, 20), 1) == [(3, 4)]


def test_get_opposite_side_is_involution():
    for side in ("up", "down", "left", "right"):
        assert get_opposite_side(get_opposite_side(side)) == side


def test_get_opposite_side_unknown_defaults_to_right():
    assert get_opposite_side("diagonal") == "right"


def test_calculate_deployment_step_is_clamped_between_1_and_10():
    assert calculate_deployment_step(10, 50) == 5
    assert calculate_deployment_step(1, 500) == 10
    assert calculate_deployment_step(50, 10) == 1
    assert calculate_deployment_step(0, 10) == 1
    assert calculate_deployment_step(10, 0) == 1


def test_lightning_targets_sorted_by_level_descending():
    air_defenses = [(100, 100, 5, 0.9), (200, 200, 9, 0.8), (300, 300, 7, 0.95)]
    assert get_lightning_spell_targets(air_defenses) == [(200, 200), (300, 300), (100, 100)]
    assert get_lightning_spell_targets([]) == []


def test_air_defense_proximity_sorter_orders_by_distance_to_side():
    air_defenses = [(500, 100), (100, 900), (900, 500)]
    assert sorted(air_defenses, key=get_air_defense_proximity_sorter("left"))[0] == (100, 900)
    assert sorted(air_defenses, key=get_air_defense_proximity_sorter("right"))[0] == (900, 500)
    assert sorted(air_defenses, key=get_air_defense_proximity_sorter("up"))[0] == (500, 100)
    assert sorted(air_defenses, key=get_air_defense_proximity_sorter("down"))[0] == (100, 900)
    assert sorted(air_defenses, key=get_air_defense_proximity_sorter("nowhere")) == air_defenses


def test_lightning_spells_needed_is_ceiling_division():
    level, hp = next(iter(config.AIR_DEFENSE_HP.items()))
    assert calculate_lightning_spells_needed(level, hp) == 1
    assert calculate_lightning_spells_needed(level, hp - 1) == 2
    assert calculate_lightning_spells_needed(level, hp * 10) == 1


def test_lightning_spells_needed_unknown_level_assumes_1000_hp():
    assert calculate_lightning_spells_needed(-1, 300) == 4


def test_cluster_center_averages_building_centers():
    assert get_cluster_center([building(0, 0), building(100, 0)]) == (85, 35)
    assert get_cluster_center([]) is None


def test_clusters_use_complete_linkage():
    # A-B and B-C are 100 px apart, A-C is 200 px: with max_distance=125
    # A and C must never share a cluster, even though B links them.
    a, b, c = building(0, 0), building(100, 0), building(200, 0)
    clusters = find_building_clusters([a, b, c], max_distance=125)
    assert clusters
    for cluster in clusters:
        assert not (a in cluster and c in cluster)


def test_clusters_empty_input():
    assert find_building_clusters([]) == []
