"""The segmented digit reader: background independence, structure checks and honest failures."""

import cv2
import numpy as np
import pytest

from coc_bot.vision import digits
from tests import ocr_synth

CONTEXTS = ["attack_screen", "base_screen", "base_dark_elixir", "loot_screen"]
NUMBERS = [0, 7, 42, 905, 1_234, 67_890, 432_118, 1_234_567, 10_011_101, 18_000_000]


def read(context, image):
    return digits.read_number(image, context)


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("number", NUMBERS)
def test_reads_numbers_on_a_dark_background(context, number):
    image = ocr_synth.compose(context, number, ocr_synth.uniform((60, 80, 60)))
    reading = read(context, image)
    assert reading.value == number, reading.reason


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize(
    "background",
    [
        ocr_synth.uniform((200, 200, 200)),
        ocr_synth.uniform((250, 250, 250)),
        ocr_synth.gradient(40, 220),
        ocr_synth.gradient(230, 30),
    ],
    ids=["light", "white", "gradient-up", "gradient-down"],
)
def test_bright_and_uneven_backgrounds_do_not_change_the_reading(context, background):
    for number in (1_234_567, 908_172, 5_660):
        reading = read(context, ocr_synth.compose(context, number, background))
        assert reading.value == number, reading.reason


@pytest.mark.parametrize("context", CONTEXTS)
def test_a_bright_patch_behind_some_digits_does_not_drop_them(context):
    rng = np.random.default_rng(3)
    for number in rng.integers(100_000, 9_999_999, size=25):
        image = ocr_synth.compose(context, int(number), ocr_synth.bright_patch(70, 0.3, rng))
        reading = read(context, image)
        assert reading.value == int(number), reading.reason


@pytest.mark.parametrize("bar_bgr", [(40, 215, 255), (210, 60, 220)], ids=["gold-bar", "elixir-bar"])
def test_white_storage_digits_are_read_over_a_coloured_storage_bar(bar_bgr):
    image = ocr_synth.compose("base_screen", 17_950_432, ocr_synth.uniform(bar_bgr))
    assert read("base_screen", image).value == 17_950_432


def test_an_image_without_digits_is_a_failure_not_zero():
    reading = read("attack_screen", ocr_synth.uniform((90, 120, 90))(52, 240))
    assert reading.value is None
    assert reading.reason == "no_digits"


def test_a_displayed_zero_reads_as_zero():
    reading = read("base_dark_elixir", ocr_synth.compose("base_dark_elixir", 0, ocr_synth.uniform((50, 50, 50))))
    assert reading.value == 0
    assert reading.ok


@pytest.mark.parametrize("missing", [1, 2, 3, 4, 5, 6])
def test_a_missing_digit_inside_the_number_is_rejected_instead_of_shrinking_it(missing):
    image = ocr_synth.compose("attack_screen", 1_234_567, ocr_synth.uniform((60, 80, 60)), skip_index=missing)
    reading = read("attack_screen", image)
    assert reading.value is None
    assert reading.reason == "bad_grouping"


@pytest.mark.parametrize("context", CONTEXTS)
def test_a_missing_digit_is_rejected_in_every_typeface_size(context):
    for missing in range(1, 7):
        image = ocr_synth.compose(context, 7_654_321, ocr_synth.uniform((60, 80, 60)), skip_index=missing)
        assert read(context, image).value is None, missing


def test_the_grouping_check_can_be_switched_off():
    image = ocr_synth.compose("attack_screen", 1_234_567, ocr_synth.uniform((60, 80, 60)), skip_index=3)
    assert digits.read_number(image, "attack_screen", check_grouping=False).value == 123_567


def test_a_digit_cut_off_by_the_region_edge_is_rejected():
    image = ocr_synth.compose("attack_screen", 1_234_567, ocr_synth.uniform((60, 80, 60)), x0=-6)
    reading = read("attack_screen", image)
    assert reading.value is None
    assert reading.reason == "clipped"


def test_half_pixel_shifts_and_blur_do_not_change_the_reading():
    for context in CONTEXTS:
        image = ocr_synth.compose(context, 9_876_543, ocr_synth.uniform((70, 70, 90)))
        for dx, dy in [(0.5, 0), (0, 0.5), (0.5, 0.5), (0.3, 0.7)]:
            shifted = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (image.shape[1], image.shape[0]))
            assert read(context, shifted).value == 9_876_543, (context, dx, dy)


def test_confidence_is_reported_per_reading_and_per_glyph():
    reading = read("loot_screen", ocr_synth.compose("loot_screen", 305_117, ocr_synth.uniform((40, 40, 40))))
    assert reading.text == "305117"
    assert [g.digit for g in reading.glyphs] == [3, 0, 5, 1, 1, 7]
    assert 0.9 <= reading.confidence <= 1.0
    assert all(g.score > g.runner_up for g in reading.glyphs)


def test_pil_images_are_accepted():
    from PIL import Image

    bgr = ocr_synth.compose("base_screen", 2_500_000, ocr_synth.uniform((60, 60, 60)))
    image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    assert read("base_screen", image).value == 2_500_000


def test_builder_base_storage_uses_the_main_base_glyphs():
    image = ocr_synth.compose("base_screen", 4_812_300, ocr_synth.uniform((60, 60, 60)))
    assert read("bb_base_screen", image).value == 4_812_300


def test_an_unknown_context_is_a_failure():
    reading = read("no_such_screen", ocr_synth.uniform((0, 0, 0))(40, 100))
    assert reading.value is None
    assert reading.reason == "no_templates"
