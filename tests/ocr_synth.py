"""Synthetic number images built from the real digit templates.

The repository has no full captures of resource numbers, so these helpers paste
the fill of each template glyph, surrounded by the game's dark outline, onto a
generated background. They exercise segmentation and structure checks; they are
not a substitute for replaying real crops (see tools/ocr/replay_corpus.py).
"""

import os

import cv2
import numpy as np

DIGITS_ROOT = os.path.join("screenshots", "reference", "digits")

# Canvas size per context, roughly the configured screen regions (wide enough for 8 digits)
CANVAS = {
    "attack_screen": (240, 52),
    "base_screen": (310, 47),
    "base_dark_elixir": (310, 53),
    "loot_screen": (420, 78),
}


def _fill_threshold(templates):
    values = [
        cv2.threshold(t.min(axis=2), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[0] for t in templates.values()
    ]
    return float(np.median(values))


def load_templates(context):
    return {d: cv2.imread(os.path.join(DIGITS_ROOT, context, f"{d}.png")) for d in range(10)}


def uniform(bgr):
    return lambda h, w: np.full((h, w, 3), bgr, np.uint8)


def gradient(a, b):
    def make(h, w):
        row = np.linspace(a, b, w).astype(np.uint8)
        return np.repeat(np.repeat(row[None, :, None], h, 0), 3, 2)

    return make


def bright_patch(base, width_fraction, rng):
    def make(h, w):
        canvas = np.full((h, w, 3), base, np.uint8)
        patch = int(w * width_fraction)
        x = int(rng.integers(0, w - patch))
        canvas[:, x : x + patch] = 235
        return canvas

    return make


def compose(context, number, background, gap=None, group_gap=None, skip_index=None, x0=None, size=None):
    """Render ``number`` with thousands grouping. ``skip_index`` leaves out one digit but keeps its space.

    Spacing scales with the glyph height: 3 px between digits and 11 px between groups at 25 px.
    """
    templates = load_templates(context)
    threshold = _fill_threshold(templates)
    width, height = size or CANVAS[context]
    pad = 60  # work on a wider canvas so a number may run past the region edge
    canvas = cv2.copyMakeBorder(background(height, width), 0, 0, pad, pad, cv2.BORDER_REPLICATE)
    text = f"{number:,}"
    glyphs = []
    for ch in text:
        if ch == ",":
            glyphs.append(None)
            continue
        tpl = templates[int(ch)]
        fill = (tpl.min(axis=2) > threshold).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(fill, connectivity=8)
        best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, h = stats[best, :4]
        glyphs.append((tpl[y : y + h, x : x + w], labels[y : y + h, x : x + w] == best))

    glyph_height = float(np.median([g[1].shape[0] for g in glyphs if g is not None]))
    if gap is None:
        gap = round(0.12 * glyph_height)
    if group_gap is None:
        group_gap = gap + round(0.33 * glyph_height)
    total = sum(group_gap - gap if g is None else g[1].shape[1] + gap for g in glyphs)
    x = pad + ((width - total) // 2 if x0 is None else x0)
    baseline = (height + max(g[1].shape[0] for g in glyphs if g is not None)) // 2
    digit_index = 0
    for g in glyphs:
        if g is None:
            x += group_gap - gap
            continue
        pixels, mask = g
        h, w = mask.shape
        if digit_index != skip_index:
            y = baseline - h
            roi = canvas[y - 3 : y + h + 3, x - 3 : x + w + 3]
            padded = np.zeros((h + 6, w + 6), np.uint8)
            padded[3 : 3 + h, 3 : 3 + w] = mask
            outline = cv2.dilate(padded, np.ones((5, 5), np.uint8)) > 0
            roi[outline] = (12, 12, 12)
            inner = roi[3 : 3 + h, 3 : 3 + w]
            inner[mask] = pixels[mask]
        digit_index += 1
        x += w + gap
    return np.ascontiguousarray(canvas[:, pad : pad + width])


def compose_for_region(context, number, region, background=None, **kwargs):
    """Render ``number`` on a canvas exactly as large as the screen ``region`` (x1, y1, x2, y2)."""
    size = (region[2] - region[0], region[3] - region[1])
    return compose(context, number, background or uniform((60, 80, 60)), size=size, **kwargs)
