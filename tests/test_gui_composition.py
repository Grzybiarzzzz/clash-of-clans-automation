"""BotGUI is assembled from mixins; these tests guard the composition."""

import itertools

from coc_bot.gui import BotGUI

# Methods that the bot thread calls on the GUI object.
USED_BY_BOT = [
    "log_message",
    "debug_message",
    "ocr_log",
    "get_settings",
    "update_loop_count",
    "update_bb_gold_state",
    "update_skipped_stats",
    "update_loot_stats",
    "update_settings_from_file",
    "apply_current_profile",
    "toggle_pause",
    "stop_bot",
    "run_bot",
    "set_control_callback",
    "schedule_auto_resume",
    "_sync_state_to_manager",
    "_on_state_change",
]


def own_methods(cls):
    return {name for name, value in vars(cls).items() if callable(value) or isinstance(value, staticmethod)}


def test_no_method_is_defined_by_two_classes():
    classes = [BotGUI, *BotGUI.__bases__]
    for a, b in itertools.combinations(classes, 2):
        assert not own_methods(a) & own_methods(b), f"{a.__name__} and {b.__name__} both define a method"


def test_gui_exposes_the_methods_the_bot_calls():
    for name in USED_BY_BOT:
        assert callable(getattr(BotGUI, name)), name


def test_all_mixins_contribute_109_methods_in_total():
    total = sum(len(own_methods(cls)) for cls in [BotGUI, *BotGUI.__bases__])
    assert total == 109
