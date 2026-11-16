"""Shared fakes for tests that drive bot code without a game, a GUI or Windows input."""

from unittest.mock import MagicMock

import cv2
import pytest
from PIL import Image

import config
from coc_bot import runtime
from coc_bot.vision import capture


def to_pil(bgr):
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


class FakeScreen:
    """A 2560x1440 screen showing queued images at given regions; the last image of a region stays."""

    SIZE = (2560, 1440)

    def __init__(self):
        self.frames = {}
        self.grabs = []

    def show(self, region, *images_bgr):
        self.frames[tuple(region)] = list(images_bgr)

    def _next(self, region):
        queue = self.frames[region]
        return to_pil(queue.pop(0) if len(queue) > 1 else queue[0])

    def __call__(self, region):
        self.grabs.append(region)
        if region is None:
            frame = Image.new("RGB", self.SIZE)
            for shown in self.frames:
                frame.paste(self._next(shown), shown[:2])
            return frame
        if tuple(region) in self.frames:
            return self._next(tuple(region))
        return Image.new("RGB", (region[2] - region[0], region[3] - region[1]))


@pytest.fixture
def screen():
    fake = FakeScreen()
    previous = capture.set_source(fake)
    yield fake
    capture.set_source(previous)


@pytest.fixture
def bot(monkeypatch, tmp_path):
    """A running bot session with mocked GUI objects and no OCR corpus on disk."""
    gui = MagicMock(name="gui")
    gui.overlay = None
    gui.overlay_enabled = False
    monkeypatch.setattr(runtime, "gui", gui)
    monkeypatch.setattr(runtime, "root", MagicMock(name="root"))
    monkeypatch.setattr(runtime, "state_manager", MagicMock(name="state_manager"))
    monkeypatch.setattr(runtime, "running", True)
    monkeypatch.setattr(runtime, "paused", False)
    monkeypatch.setattr(runtime, "loop_count", 0)
    monkeypatch.setattr(runtime, "skipped_bases", 0)
    monkeypatch.setattr(runtime, "attacked_bases", 0)
    monkeypatch.setattr(config, "OCR_CORPUS_DIR", str(tmp_path / "ocr_corpus"), raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", None, raising=False)
    monkeypatch.setattr(config, "DISCORD_OCR_WEBHOOK_URL", None, raising=False)
    from coc_bot.vision import ocr

    monkeypatch.setattr(ocr, "_corpus", None, raising=False)
    return gui
