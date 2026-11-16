"""After a battle: loot, storage read, full-storage pause and the loot cross-check."""

import pytest

from coc_bot import storages
from coc_bot.attacks import common

LOOT = {"gold": 400_000, "elixir": 380_000, "dark_elixir": 2_000}
SETTINGS = {
    "current_profile": "Farming",
    "max_gold_storage": 18_000_000,
    "max_elixir_storage": 14_000_000,
    "max_dark_elixir_storage": 240_000,
}


@pytest.fixture
def post_battle(bot, monkeypatch):
    """Run handle_post_battle with a given storage reading; collects Discord notifications."""
    bot.get_settings.return_value = dict(SETTINGS)
    notifications = []
    monkeypatch.setattr(common, "ocr_loot", lambda: dict(LOOT))
    monkeypatch.setattr(common, "save_loot_data", lambda *a, **k: None)
    monkeypatch.setattr(common, "human_like_move_click", lambda *a, **k: None)
    monkeypatch.setattr(common, "wait_for_base_screen", lambda **k: True)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(common, "get_global_reinforcements_enabled", lambda: False)
    monkeypatch.setattr(common, "send_discord_notification", notifications.append)
    monkeypatch.setattr(storages, "last_3_resources", {"main_base": [], "builder_base": []})
    monkeypatch.setattr(storages, "_previous_values", {"main_base": None, "builder_base": None})

    def run(values, before=None):
        storages._previous_values["main_base"] = before

        def read(base_type="main_base", **kwargs):
            if values is not None:
                storages._previous_values[base_type] = dict(values)
            return values

        monkeypatch.setattr(common, "read_storage_values", read)
        return common.handle_post_battle()

    run.notifications = notifications
    run.gui = bot
    return run


def test_no_pause_at_storage_values_that_used_to_be_hard_coded(post_battle):
    paused = post_battle({"gold": 11_000_000, "elixir": 5_000_000, "dark_elixir": 10_000})
    assert paused is False
    assert post_battle.notifications == []


def test_the_farming_profile_pauses_when_two_storages_reached_their_configured_maximum(post_battle):
    paused = post_battle({"gold": 18_000_000, "elixir": 14_000_000, "dark_elixir": 10_000})
    assert paused is True
    assert len(post_battle.notifications) == 1


def test_one_full_storage_is_not_enough_to_pause(post_battle):
    assert post_battle({"gold": 18_000_000, "elixir": 5_000_000, "dark_elixir": 10_000}) is False


def test_other_profiles_do_not_pause_on_full_storages(post_battle):
    post_battle.gui.get_settings.return_value = dict(SETTINGS, current_profile="Trophy Pushing")
    assert post_battle({"gold": 18_000_000, "elixir": 14_000_000, "dark_elixir": 240_000}) is False


def test_unreadable_storages_do_not_pause_or_count_as_a_reading(post_battle):
    assert post_battle(None) is False
    assert storages.last_3_resources["main_base"] == []


def test_storage_growth_that_contradicts_the_loot_screen_is_reported(post_battle):
    before = {"gold": 11_900_000, "elixir": 5_000_000, "dark_elixir": 50_000}
    post_battle({"gold": 1_230_000, "elixir": 5_380_000, "dark_elixir": 52_000}, before=before)

    messages = [call.args[0] for call in post_battle.gui.log_message.call_args_list]
    (audit,) = [m for m in messages if m.startswith("[OCR AUDIT]")]
    assert "gold" in audit and "-10,670,000" in audit and "400,000" in audit


def test_matching_growth_is_not_reported(post_battle):
    before = {"gold": 5_000_000, "elixir": 5_000_000, "dark_elixir": 50_000}
    post_battle({"gold": 5_400_000, "elixir": 5_380_000, "dark_elixir": 52_000}, before=before)

    messages = [call.args[0] for call in post_battle.gui.log_message.call_args_list]
    assert not [m for m in messages if m.startswith("[OCR AUDIT]")]
