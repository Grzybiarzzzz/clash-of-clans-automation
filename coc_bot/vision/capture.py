"""The single entry point for reading the screen.

Every detector captures through ``grab``. That gives two things the scattered
``ImageGrab.grab`` calls could not:

* ``frozen_frame()`` captures the screen once and serves every ``grab`` inside the
  block from that capture. A detector that checks several regions then sees one
  consistent frame and pays for one capture.
* ``set_source()`` replaces the screen with any callable, so saved screenshots can be
  replayed through the detectors in tests.

Every capture is also a checkpoint where the bot thread stops when the connection monitor
has taken over (see ``coc_bot.interrupts``).
"""

import threading
from contextlib import contextmanager

from PIL import ImageGrab

from coc_bot import interrupts

_source = None  # callable(region or None) -> PIL image; None means the real screen
_frozen = threading.local()


def set_source(source):
    """Replace the screen with ``source(region)``; pass None to restore it. Returns the previous source."""
    global _source
    previous, _source = _source, source
    return previous


def grab(region=None):
    """Capture ``region`` as (x1, y1, x2, y2) in screen coordinates, or the whole screen. Returns a PIL image."""
    interrupts.checkpoint()
    frame = getattr(_frozen, "frame", None)
    if frame is not None:
        return frame.crop(region) if region else frame
    if _source is not None:
        return _source(region)
    return ImageGrab.grab(bbox=region) if region else ImageGrab.grab()


@contextmanager
def frozen_frame():
    """Serve every ``grab`` in this block (on this thread) from one capture of the whole screen."""
    if getattr(_frozen, "frame", None) is not None:
        yield
        return
    _frozen.frame = grab()
    try:
        yield
    finally:
        _frozen.frame = None
