"""One capture entry point: injectable for tests and replay, and able to freeze a frame."""

import pytest
from PIL import Image

from coc_bot.vision import capture


@pytest.fixture
def screen():
    """A fake 200x100 screen whose pixel value encodes how many times it was captured."""
    calls = []

    def source(region):
        calls.append(region)
        image = Image.new("RGB", (200, 100), (len(calls), 0, 0))
        return image.crop(region) if region else image

    previous = capture.set_source(source)
    yield calls
    capture.set_source(previous)


def test_grab_asks_the_source_for_the_region(screen):
    image = capture.grab((10, 20, 60, 50))
    assert image.size == (50, 30)
    assert screen == [(10, 20, 60, 50)]


def test_grab_without_a_region_captures_the_whole_screen(screen):
    assert capture.grab().size == (200, 100)
    assert screen == [None]


def test_a_frozen_frame_is_captured_once_and_cropped_for_every_region(screen):
    with capture.frozen_frame():
        first = capture.grab((0, 0, 10, 10))
        second = capture.grab((50, 50, 80, 70))
        whole = capture.grab()
    assert screen == [None]
    assert first.size == (10, 10) and second.size == (30, 20) and whole.size == (200, 100)
    assert first.getpixel((0, 0)) == second.getpixel((0, 0)) == (1, 0, 0)


def test_nested_frozen_frames_share_the_outer_capture(screen):
    with capture.frozen_frame():
        with capture.frozen_frame():
            capture.grab((0, 0, 5, 5))
        capture.grab((0, 0, 5, 5))
    assert screen == [None]


def test_capture_is_live_again_after_the_frozen_block(screen):
    with capture.frozen_frame():
        capture.grab((0, 0, 5, 5))
    assert capture.grab((0, 0, 5, 5)).getpixel((0, 0)) == (2, 0, 0)


def test_the_frame_is_released_when_the_block_raises(screen):
    with pytest.raises(RuntimeError):
        with capture.frozen_frame():
            raise RuntimeError("detector failed")
    capture.grab()
    assert len(screen) == 2
