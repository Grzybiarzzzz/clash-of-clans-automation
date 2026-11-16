"""Resource reads built on the digit reader: honest failures, waiting for a base, loot and destruction."""

import os

import numpy as np
import pytest

import config
from coc_bot.vision import ocr
from tests import ocr_synth
from tests.bot_fakes import to_pil

DARK = ocr_synth.uniform((60, 80, 60))


def blank(context):
    width, height = ocr_synth.CANVAS[context]
    return DARK(height, width)


def show_number(screen, region, context, *numbers, **kwargs):
    """Queue numbers for a region; None stands for an empty region (clouds, no such resource)."""
    size = (region[2] - region[0], region[3] - region[1])
    screen.show(
        region,
        *(
            DARK(size[1], size[0]) if n is None else ocr_synth.compose_for_region(context, n, region, **kwargs)
            for n in numbers
        ),
    )


def test_a_readable_crop_gives_its_value(bot):
    image = to_pil(ocr_synth.compose("attack_screen", 432_118, DARK))
    assert ocr.read_resource(image, "attack_screen", "gold") == 432_118


def test_an_unreadable_crop_gives_none_and_is_kept_for_review(bot):
    image = ocr_synth.compose("attack_screen", 1_234_567, DARK, skip_index=2)

    assert ocr.read_resource(image, "attack_screen", "gold") is None

    saved = os.listdir(os.path.join(config.OCR_CORPUS_DIR, "attack_screen"))
    assert len(saved) == 1 and saved[0].endswith("_gold_bad_grouping.png")


def test_the_reading_is_reported_to_the_ocr_log_with_its_confidence(bot):
    ocr.read_resource(ocr_synth.compose("base_screen", 5_000_000, DARK), "base_screen", "elixir")

    (args, kwargs) = bot.ocr_log.call_args
    assert args[:2] == ("ELIXIR", 5_000_000)
    assert kwargs["confidence"] > 90


def test_the_legacy_engine_can_be_selected(bot, monkeypatch):
    monkeypatch.setattr(config, "OCR_ENGINE", "legacy", raising=False)
    monkeypatch.setattr(ocr.digits, "legacy_read", lambda image, context: 777)

    assert ocr.read_resource(ocr_synth.compose("base_screen", 123, DARK), "base_screen") == 777


def test_no_corpus_is_written_when_recording_is_disabled(bot, monkeypatch):
    monkeypatch.setattr(config, "OCR_CORPUS_ENABLED", False, raising=False)

    ocr.read_resource(blank("attack_screen"), "attack_screen", "gold")
    ocr.read_resource(ocr_synth.compose("attack_screen", 1_234_567, DARK, skip_index=2), "attack_screen", "gold")

    assert not os.path.exists(config.OCR_CORPUS_DIR)


def test_scouting_loot_is_read_once_the_clouds_clear(bot, screen):
    show_number(screen, config.GOLD_REGION, "attack_screen", None, None, 612_004)
    show_number(screen, config.ELIXIR_REGION, "attack_screen", None, None, 0)

    assert ocr.evaluate_base_resources(timeout=5, poll=0) == (612_004, 0)


def test_scouting_loot_that_never_becomes_readable_times_out_as_unknown(bot, screen):
    show_number(screen, config.GOLD_REGION, "attack_screen", None)
    show_number(screen, config.ELIXIR_REGION, "attack_screen", 250_000)

    assert ocr.evaluate_base_resources(timeout=0.05, poll=0.01) == (None, 250_000)


def test_reading_enemy_loot_does_not_compare_it_with_the_players_storage_profiles(bot, screen, monkeypatch):
    lookups = []
    monkeypatch.setattr("coc_bot.profiles.find_best_matching_profile", lambda *a, **k: lookups.append(a) or (None, 0, None))
    show_number(screen, config.GOLD_REGION, "attack_screen", 900_000)
    show_number(screen, config.ELIXIR_REGION, "attack_screen", 900_000)

    assert ocr.evaluate_base_resources() == (900_000, 900_000)
    assert lookups == []


def test_loot_is_read_from_the_end_screen(bot, screen):
    show_number(screen, config.LOOT_GOLD_REGION, "loot_screen", 512_340)
    show_number(screen, config.LOOT_ELIXIR_REGION, "loot_screen", 498_001)
    show_number(screen, config.LOOT_DARK_ELIXIR_REGION, "loot_screen", 4_210)

    assert ocr.ocr_loot() == {"gold": 512_340, "elixir": 498_001, "dark_elixir": 4_210}


def test_loot_that_cannot_be_read_counts_as_zero_without_failing_the_others(bot, screen):
    show_number(screen, config.LOOT_GOLD_REGION, "loot_screen", 512_340, skip_index=1)
    show_number(screen, config.LOOT_ELIXIR_REGION, "loot_screen", 498_001)
    show_number(screen, config.LOOT_DARK_ELIXIR_REGION, "loot_screen", None)

    assert ocr.ocr_loot() == {"gold": 0, "elixir": 498_001, "dark_elixir": 0}


@pytest.mark.parametrize(
    "text, previous, expected",
    [
        ("50%", None, 50),
        ("7", None, 7),
        ("5096", 45, 50),  # the % sign read as digits
        ("100%", 88, 100),
        ("10096", 90, 100),
        ("100%", None, 10),  # an early "10%" misread: 100 is only believed near the end
        ("100", 12, 10),
        ("", None, None),
        ("%", 30, None),
    ],
)
def test_destruction_text_is_parsed_with_the_previous_value_in_mind(text, previous, expected):
    assert ocr.parse_destruction_text(text, previous) == expected


def test_destruction_reaches_one_hundred_percent(bot, screen, monkeypatch):
    texts = iter(["62%", "81%", "100%"])
    monkeypatch.setattr(ocr.pytesseract, "image_to_string", lambda *a, **k: next(texts))
    screen.show(config.DESTRUCTION_REGION, np.zeros((59, 130, 3), np.uint8))
    ocr.detect_destruction_percentage.last_valid = None

    readings = [ocr.detect_destruction_percentage(save_debug_screenshots=False) for _ in range(3)]

    assert readings == [62, 81, 100]
