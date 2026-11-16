"""Own-storage reads: unreadable is not empty, retries, and the loot cross-check."""

import pytest

import config
from coc_bot import storages
from tests import ocr_synth

DARK = ocr_synth.uniform((60, 60, 60))
SETTINGS = {
    "max_gold_storage": 18_000_000,
    "max_elixir_storage": 14_000_000,
    "max_dark_elixir_storage": 240_000,
    "max_bb_gold_storage": 5_000_000,
    "max_bb_elixir_storage": 5_000_000,
}


@pytest.fixture(autouse=True)
def session(bot, monkeypatch):
    bot.get_settings.return_value = dict(SETTINGS)
    monkeypatch.setattr(storages, "last_3_resources", {"main_base": [], "builder_base": []})
    monkeypatch.setattr(storages, "_previous_values", {"main_base": None, "builder_base": None})
    monkeypatch.setattr(storages.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(storages, "auto_switch_profile_if_needed", lambda *a, **k: False)


def show(screen, region, context, *numbers, **kwargs):
    size = (region[2] - region[0], region[3] - region[1])
    screen.show(
        region,
        *(
            DARK(size[1], size[0]) if n is None else ocr_synth.compose_for_region(context, n, region, DARK, **kwargs)
            for n in numbers
        ),
    )


def show_main(screen, gold, elixir, dark):
    show(screen, config.BASE_GOLD_REGION, "base_screen", *gold)
    show(screen, config.BASE_ELIXIR_REGION, "base_screen", *elixir)
    show(screen, config.BASE_DARK_ELIXIR_REGION, "base_dark_elixir", *dark)


def test_main_base_storages_are_read_as_values_and_percentages(screen):
    show_main(screen, [9_000_000], [7_000_000], [60_000])

    result = storages.read_own_base_storages()

    assert result["success"]
    assert (result["gold_absolute"], result["elixir_absolute"], result["de_absolute"]) == (9_000_000, 7_000_000, 60_000)
    assert (result["gold_percent"], result["elixir_percent"], result["de_percent"]) == (50, 50, 25)


def test_an_unreadable_storage_is_a_failed_read_not_an_empty_storage(screen):
    show_main(screen, [None], [7_000_000], [60_000])

    result = storages.read_own_base_storages()

    assert not result["success"]
    assert storages.last_3_resources["main_base"] == []


def test_a_storage_read_is_retried_until_the_screen_settles(screen):
    show_main(screen, [None, 9_000_000], [None, 7_000_000], [None, 60_000])

    assert storages.read_storage_values("main_base") == {"gold": 9_000_000, "elixir": 7_000_000, "dark_elixir": 60_000}


def test_missing_dark_elixir_does_not_fail_the_read(screen):
    show_main(screen, [9_000_000], [7_000_000], [None])

    result = storages.read_own_base_storages()

    assert result["success"] and result["de_absolute"] == 0


def test_builder_base_storages_use_their_own_regions_and_capacity(screen):
    show(screen, config.BB_BASE_GOLD_REGION, "base_screen", 2_500_000)
    show(screen, config.BB_BASE_ELIXIR_REGION, "base_screen", 5_000_000)

    result = storages.read_bb_base_storages()

    assert result["success"]
    assert (result["gold_percent"], result["elixir_percent"]) == (50, 100)


def test_three_identical_successful_reads_still_pause_the_bot(screen, bot):
    show_main(screen, [9_000_000], [7_000_000], [60_000])

    for _ in range(3):
        storages.read_own_base_storages()

    bot.toggle_pause.assert_called_once()


CAPACITY = {"gold": 18_000_000, "elixir": 14_000_000, "dark_elixir": 240_000}


def audit(before, after, loot):
    names = ("gold", "elixir", "dark_elixir")
    return storages.find_loot_mismatches(dict(zip(names, before)), dict(zip(names, after)), dict(zip(names, loot)), CAPACITY)


def test_storage_growth_matching_the_loot_raises_no_flag():
    assert audit((5_000_000, 5_000_000, 50_000), (5_400_000, 5_380_000, 52_000), (400_000, 380_000, 2_000)) == []


def test_a_league_bonus_on_top_of_the_loot_is_tolerated():
    assert audit((5_000_000, 5_000_000, 50_000), (5_700_000, 5_650_000, 53_500), (400_000, 380_000, 2_000)) == []


def test_a_storage_that_shrank_by_a_digit_is_flagged():
    (flag,) = audit((11_900_000, 5_000_000, 50_000), (1_230_000, 5_380_000, 52_000), (400_000, 380_000, 2_000))
    assert flag["resource"] == "gold" and flag["gained"] == -10_670_000 and flag["loot"] == 400_000


def test_growth_far_beyond_loot_and_bonus_is_flagged():
    (flag,) = audit((5_000_000, 5_000_000, 50_000), (5_400_000, 9_400_000, 52_000), (400_000, 380_000, 2_000))
    assert flag["resource"] == "elixir"


def test_a_full_storage_cannot_show_the_loot_and_is_not_flagged():
    assert audit((17_900_000, 5_000_000, 50_000), (18_000_000, 5_380_000, 52_000), (400_000, 380_000, 2_000)) == []


def test_without_an_earlier_reading_there_is_nothing_to_compare():
    after = {"gold": 1, "elixir": 1, "dark_elixir": 1}
    assert storages.find_loot_mismatches(None, after, {"gold": 5, "elixir": 5, "dark_elixir": 5}, CAPACITY) == []
