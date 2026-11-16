"""How the evaluating routines (normal attack, Super Goblin farm) report skips, and how the loop counts them."""

import pytest

from coc_bot import loop, runtime
from coc_bot.attacks import common, normal, sgoblin_farm

SETTINGS = {"min_resources": 800_000, "current_profile": "Farming", "troop_counts": [0] * 7}


@pytest.fixture
def scouting(bot, monkeypatch):
    """A base on the scouting screen. ``scouting.loot`` is what the OCR will return; skips are counted."""
    bot.get_settings.return_value = dict(SETTINGS)

    class Scouting:
        loot = (900_000, 900_000)
        screen_ready = True
        skips = 0
        reads = 0

    state = Scouting()

    def read(timeout=0.0, poll=0.2):
        state.reads += 1
        return state.loot

    def skip():
        state.skips += 1

    monkeypatch.setattr(common, "evaluate_base_resources", read)
    monkeypatch.setattr(common, "_unreadable_bases", 0)
    for module in (normal, sgoblin_farm):
        monkeypatch.setattr(module, "skip_base", skip)
        monkeypatch.setattr(module, "wait_for_attack_screen_ready", lambda timeout=10: state.screen_ready)
    monkeypatch.setattr(common, "skip_base", skip)
    monkeypatch.setattr(normal, "reading_pause", lambda *a, **k: None)
    monkeypatch.setattr(normal, "thinking_pause", lambda *a, **k: None)
    monkeypatch.setattr(normal, "detect_air_defenses", lambda: [(100, 100, 10, 0.9)] * 4)
    monkeypatch.setattr(common, "get_global_reinforcements_enabled", lambda: False)
    monkeypatch.setattr(sgoblin_farm.time, "sleep", lambda seconds: None)
    return state


# --- normal attack ---------------------------------------------------------------------------


def test_a_base_with_too_little_loot_is_reported_as_skipped(scouting):
    scouting.loot = (100_000, 100_000)

    assert normal.perform_normal_attack() == "skipped"
    assert scouting.skips == 1


def test_a_base_whose_loot_cannot_be_read_is_skipped(scouting):
    scouting.loot = (None, 900_000)

    assert normal.perform_normal_attack() == "skipped"
    assert scouting.skips == 1


def test_the_normal_attack_does_not_read_loot_before_the_attack_screen_is_there(scouting):
    scouting.screen_ready = False

    assert normal.perform_normal_attack() == "skipped"
    assert scouting.reads == 0


# --- Super Goblin farm -----------------------------------------------------------------------


def test_sgoblin_skips_a_base_whose_loot_stays_unreadable_instead_of_retrying_forever(scouting):
    scouting.loot = (None, None)

    assert sgoblin_farm.perform_sgoblin_farm_attack() == "skipped"
    assert scouting.reads == 1
    assert scouting.skips == 1


def test_sgoblin_skips_a_base_with_too_little_loot(scouting):
    scouting.loot = (300_000, 0)

    assert sgoblin_farm.perform_sgoblin_farm_attack() == "skipped"


# --- too many unreadable bases in a row ------------------------------------------------------


def test_the_bot_pauses_when_base_after_base_is_unreadable(scouting, bot):
    scouting.loot = (None, None)

    results = [sgoblin_farm.perform_sgoblin_farm_attack() for _ in range(common.MAX_UNREADABLE_BASES)]

    assert results[:-1] == ["skipped"] * (common.MAX_UNREADABLE_BASES - 1)
    assert results[-1] == "paused"
    assert runtime.paused is True
    assert scouting.skips == common.MAX_UNREADABLE_BASES - 1  # the last base is left on screen for inspection


def test_a_readable_base_resets_the_unreadable_count(scouting):
    scouting.loot = (None, None)
    for _ in range(common.MAX_UNREADABLE_BASES - 1):
        normal.perform_normal_attack()
    scouting.loot = (10_000, 10_000)
    normal.perform_normal_attack()
    scouting.loot = (None, None)

    assert normal.perform_normal_attack() == "skipped"
    assert runtime.paused is False


# --- the loop --------------------------------------------------------------------------------


@pytest.fixture
def evaluated_cycle(bot, monkeypatch):
    """Run the evaluation loop over scripted attack results."""
    monkeypatch.setattr(loop, "is_base_search_ready", lambda: True)
    monkeypatch.setattr(loop.time, "sleep", lambda seconds: None)

    def run(results, sgoblin=False):
        script = iter(results)
        name = "perform_sgoblin_farm_attack" if sgoblin else "perform_normal_attack"
        monkeypatch.setattr(loop, name, lambda: next(script))
        loop._run_evaluated_attack_cycle(sgoblin)

    return run


@pytest.mark.parametrize("sgoblin", [False, True])
def test_skipped_bases_are_not_counted_as_attacks(evaluated_cycle, sgoblin):
    evaluated_cycle(["skipped", "skipped", False], sgoblin=sgoblin)

    assert runtime.skipped_bases == 2
    assert runtime.attacked_bases == 1
    assert runtime.loop_count == 1


def test_full_storages_pause_the_bot_without_counting_an_attack(evaluated_cycle):
    evaluated_cycle([True])

    assert runtime.paused is True
    assert runtime.attacked_bases == 0


def test_a_pause_requested_by_the_routine_ends_the_cycle(evaluated_cycle):
    evaluated_cycle(["paused"])

    assert runtime.attacked_bases == 0
    assert runtime.skipped_bases == 0
