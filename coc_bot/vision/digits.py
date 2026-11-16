"""Reading the game's outlined digits from a small screen crop.

The game draws numbers in one typeface at a fixed size: a bright fill, a dark
outline and a space between groups of three digits. The reader relies on that
instead of on the background behind the number:

1. Fill mask. A pixel belongs to a glyph when its darkest colour channel is
   above a threshold taken from the digit templates. Using the darkest channel
   keeps saturated backgrounds (a gold or elixir storage bar) out of the mask.
2. Segmentation. Each connected blob of fill that has the height of a digit and
   is surrounded by the dark outline is one digit. The outline separates
   neighbouring digits, and bright scenery has no outline, so it is ignored.
3. Classification. The blob is compared with the fill of every template glyph.
4. Structure. Digits must sit on one line, and the wide gaps between them must
   be exactly the thousands separators. A digit that went missing shifts those
   gaps, so the reading is rejected instead of silently becoming a smaller number.

A failed reading has ``value is None`` and a ``reason``; it is never reported as 0.

This module has no screen, GUI or logging dependencies, so it runs on saved crops.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

DIGITS_ROOT = os.path.join("screenshots", "reference", "digits")

# Screens that show their numbers in the glyphs of another screen
CONTEXT_ALIASES = {"bb_base_screen": "base_screen"}

MIN_GLYPH_SCORE = 0.6  # below this a digit-sized, outlined blob is an unknown glyph
MIN_GLYPH_MARGIN = 0.05  # the best template glyph must beat the second best by this much
SHIFT_SEARCH = 3  # pixels of misalignment tolerated between a blob and a template glyph
_KERNEL = np.ones((3, 3), np.uint8)


@dataclass(frozen=True)
class Glyph:
    digit: int
    x: int
    y: int
    w: int
    h: int
    score: float  # similarity to the chosen template glyph, 1.0 is identical
    runner_up: float  # similarity to the second-best template glyph


@dataclass(frozen=True)
class DigitReading:
    value: Optional[int]
    reason: str = "ok"
    glyphs: Tuple[Glyph, ...] = ()

    @property
    def ok(self) -> bool:
        return self.value is not None

    @property
    def text(self) -> str:
        return "".join(str(g.digit) for g in self.glyphs)

    @property
    def confidence(self) -> float:
        """Lowest glyph score of a successful reading, 0.0 for a failed one."""
        if not self.ok or not self.glyphs:
            return 0.0
        return min(g.score for g in self.glyphs)


def _darkest_channel(bgr):
    return bgr.min(axis=2)


def _largest_blob(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count < 2:
        return None
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = stats[best, :4]
    return (labels[y : y + h, x : x + w] == best).astype(np.uint8)


def _similarity(blob, glyph):
    """Best zero-mean correlation of two binary shapes over small shifts (1.0 = identical)."""
    height = max(blob.shape[0], glyph.shape[0]) + 2
    width = max(blob.shape[1], glyph.shape[1]) + 2
    search = np.zeros((height + 2 * SHIFT_SEARCH, width + 2 * SHIFT_SEARCH), np.float32)
    search[1 + SHIFT_SEARCH : 1 + SHIFT_SEARCH + blob.shape[0], 1 + SHIFT_SEARCH : 1 + SHIFT_SEARCH + blob.shape[1]] = blob
    window = np.zeros((height, width), np.float32)
    window[1 : 1 + glyph.shape[0], 1 : 1 + glyph.shape[1]] = glyph
    return float(cv2.matchTemplate(search, window, cv2.TM_CCOEFF_NORMED).max())


class DigitReader:
    """Reads numbers drawn with one set of template glyphs."""

    def __init__(self, templates: Dict[int, np.ndarray]):
        if not templates:
            raise ValueError("no digit templates")
        thresholds = [
            cv2.threshold(_darkest_channel(t), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[0]
            for t in templates.values()
        ]
        self.fill_threshold = float(np.median(thresholds))
        self.dark_threshold = 0.75 * self.fill_threshold
        self.glyphs = {}
        for digit, template in templates.items():
            blob = _largest_blob((_darkest_channel(template) > self.fill_threshold).astype(np.uint8))
            if blob is not None:
                self.glyphs[digit] = blob
        self.glyph_height = float(np.median([g.shape[0] for g in self.glyphs.values()]))
        self.max_glyph_width = max(g.shape[1] for g in self.glyphs.values())

    @classmethod
    def from_directory(cls, directory):
        templates = {}
        for digit in range(10):
            template = cv2.imread(os.path.join(directory, f"{digit}.png"))
            if template is not None:
                templates[digit] = template
        return cls(templates)

    def read(self, bgr, check_grouping=True) -> DigitReading:
        fill = (_darkest_channel(bgr) > self.fill_threshold).astype(np.uint8)
        brightest = bgr.max(axis=2)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(fill, connectivity=8)
        image_h, image_w = fill.shape

        confident, doubtful = [], []
        for label in range(1, count):
            x, y, w, h = (int(v) for v in stats[label, :4])
            if h < 0.6 * self.glyph_height or h > 1.35 * self.glyph_height:
                continue  # specks and large bright areas are not text
            blob = (labels[y : y + h, x : x + w] == label).astype(np.uint8)
            if not self._has_outline(labels, label, brightest, x, y, w, h):
                continue  # bright scenery: digits always carry the dark outline
            if x == 0 or y == 0 or x + w == image_w or y + h == image_h:
                return DigitReading(None, "clipped")
            if w > 1.3 * self.max_glyph_width:
                return DigitReading(None, "merged_glyphs")
            digit, score, runner_up = self._classify(blob)
            glyph = Glyph(digit, x, y, w, h, score, runner_up)
            if score >= MIN_GLYPH_SCORE and score - runner_up >= MIN_GLYPH_MARGIN:
                confident.append(glyph)
            else:
                doubtful.append(glyph)

        for glyph in doubtful:
            # Bright background caught between the outlines of two neighbouring digits looks
            # like an outlined blob, but it sits inside their horizontal extent. A real digit
            # never does, so anything else that could not be recognised fails the reading.
            covered = sum(max(0, min(glyph.x + glyph.w, g.x + g.w) - max(glyph.x, g.x)) for g in confident)
            if covered < 0.5 * glyph.w:
                return DigitReading(None, "unknown_glyph")
        glyphs = confident

        if not glyphs:
            return DigitReading(None, "no_digits")
        glyphs.sort(key=lambda g: g.x)
        glyphs = tuple(glyphs)

        centres = [g.y + g.h / 2 for g in glyphs]
        if max(abs(c - float(np.median(centres))) for c in centres) > 0.35 * self.glyph_height:
            return DigitReading(None, "not_one_line", glyphs)
        if check_grouping and not self._grouping_is_plausible(glyphs):
            return DigitReading(None, "bad_grouping", glyphs)
        return DigitReading(int("".join(str(g.digit) for g in glyphs)), "ok", glyphs)

    def _has_outline(self, labels, label, brightest, x, y, w, h):
        """True when most pixels just outside the blob are dark, as around every glyph."""
        y0, y1 = max(0, y - 2), min(labels.shape[0], y + h + 2)
        x0, x1 = max(0, x - 2), min(labels.shape[1], x + w + 2)
        blob = (labels[y0:y1, x0:x1] == label).astype(np.uint8)
        near = cv2.dilate(blob, _KERNEL)
        far = cv2.dilate(near, _KERNEL)
        dark = brightest[y0:y1, x0:x1] < self.dark_threshold
        fractions = []
        for ring in ((near > 0) & (blob == 0), (far > 0) & (near == 0)):
            if ring.any():
                fractions.append(float(dark[ring].mean()))
        return bool(fractions) and max(fractions) >= 0.5

    def _classify(self, blob):
        scores = sorted(((_similarity(blob, glyph), digit) for digit, glyph in self.glyphs.items()), reverse=True)
        best_score, best_digit = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else 0.0
        return best_digit, best_score, runner_up

    def _grouping_is_plausible(self, glyphs):
        """Wide gaps, where there are any, must be exactly the thousands separators.

        The gaps are split into narrow and wide at their largest jump, and only when that
        jump is clear; evenly spaced digits carry no evidence and are accepted. Each of the
        two kinds must be uniform and the wide ones must be the separators. Spacing is
        measured twice, between glyph edges and between glyph centres, and the reading is
        accepted when either agrees, so the check does not depend on whether the typeface
        gives every digit the same advance width.
        """
        n = len(glyphs)
        if n < 2:
            return True
        expected = {i for i in range(n - 1) if (n - 1 - i) % 3 == 0}
        clear_jump = max(3.0, 0.2 * self.glyph_height)
        edge_gaps = [glyphs[i + 1].x - (glyphs[i].x + glyphs[i].w) for i in range(n - 1)]
        centre_gaps = [(glyphs[i + 1].x + glyphs[i + 1].w / 2) - (glyphs[i].x + glyphs[i].w / 2) for i in range(n - 1)]
        for gaps in (edge_gaps, centre_gaps):
            ordered = sorted(gaps)
            jumps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
            if not jumps or max(jumps) < clear_jump:
                return True
            cut = jumps.index(max(jumps))
            narrow, wide = ordered[: cut + 1], ordered[cut + 1 :]
            # A hole left by a lost digit is a third kind of gap: it stretches one of the groups
            if narrow[-1] - narrow[0] >= clear_jump or wide[-1] - wide[0] >= clear_jump:
                continue
            if {i for i, gap in enumerate(gaps) if gap > narrow[-1]} == expected:
                return True
        return False


@lru_cache(maxsize=None)
def get_reader(context) -> Optional[DigitReader]:
    """The reader for a screen context, or None when it has no digit templates."""
    directory = os.path.join(DIGITS_ROOT, CONTEXT_ALIASES.get(context, context))
    try:
        return DigitReader.from_directory(directory)
    except ValueError:
        return None


def to_bgr(image):
    """Accept a PIL image (RGB) or an OpenCV array (BGR)."""
    if isinstance(image, np.ndarray):
        return image
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def read_number(image, context, check_grouping=True) -> DigitReading:
    reader = get_reader(context)
    if reader is None:
        return DigitReading(None, "no_templates")
    return reader.read(to_bgr(image), check_grouping=check_grouping)


# The original reader, kept so its answers can be compared with the segmented one on
# recorded crops (and selected with config.OCR_ENGINE = "legacy"). It thresholds the
# whole crop with Otsu and slides every digit template over the result, which makes it
# depend on the background behind the number and lets it lose digits without noticing.


@lru_cache(maxsize=None)
def _legacy_templates(context):
    directory = os.path.join(DIGITS_ROOT, CONTEXT_ALIASES.get(context, context))
    templates = {}
    for digit in range(10):
        template = cv2.imread(os.path.join(directory, f"{digit}.png"), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            templates[digit] = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    return templates


def legacy_read(image, context) -> Optional[int]:
    """Sliding template match with non-maximum suppression. None when nothing matched."""
    from imutils.object_detection import non_max_suppression

    templates = _legacy_templates(context)
    if not templates:
        return None
    gray = cv2.cvtColor(to_bgr(image), cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    lenient = context in ("base_screen", "base_dark_elixir", "bb_base_screen", "loot_screen")
    base_threshold = 0.68 if lenient else 0.72

    detections = []
    for digit, template in templates.items():
        if template.shape[0] > binary.shape[0] or template.shape[1] > binary.shape[1]:
            continue
        threshold = base_threshold - 0.03 if digit in (0, 4, 7) else base_threshold
        scores = cv2.matchTemplate(binary, template, cv2.TM_CCOEFF_NORMED)
        height, width = template.shape
        for y, x in zip(*np.where(scores >= threshold)):
            detections.append((x, y, x + width, y + height, float(scores[y, x]), digit))
    if not detections:
        return None

    boxes = np.array([d[:4] for d in detections])
    kept = non_max_suppression(boxes, probs=np.array([d[4] for d in detections]), overlapThresh=0.2)
    digits_found = []
    for box in kept:
        candidates = [(d[4], d[5]) for d in detections if tuple(d[:4]) == tuple(box)]
        if candidates:
            digits_found.append((box[0], max(candidates)[1]))
    if not digits_found:
        return None
    return int("".join(str(digit) for _, digit in sorted(digits_found)))
