"""Thin wrappers that draw on the detection overlay when it is enabled."""

import config
from coc_bot import runtime

def overlay_clear():
    """Clear the overlay canvas if enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print("[OVERLAY] Clearing overlay")
        runtime.gui.overlay.clear()


def overlay_update():
    """Update/refresh the overlay display if enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print("[OVERLAY] Updating overlay")
        runtime.gui.overlay.update()


def overlay_draw_ocr(region, value, confidence, resource_type=''):
    """Draw an OCR region visualization if overlay is enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print(f"[OVERLAY] Drawing OCR: {resource_type} = {value} ({confidence}%)")
        runtime.gui.overlay.draw_ocr_region(region, str(value), confidence, resource_type)


def overlay_draw_detection(x, y, w, h, building_type, level, confidence, color):
    """Draw a building detection box if overlay is enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print(f"[OVERLAY] Drawing detection: {building_type} at ({x},{y})")
        runtime.gui.overlay.draw_detection(x, y, w, h, building_type, level, confidence, color)


def overlay_draw_side(side):
    """Draw the attack side indicator if overlay is enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print(f"[OVERLAY] Drawing attack side: {side}")
        runtime.gui.overlay.highlight_side(side, config.OVERLAY_COLORS.get('side_indicator', '#00FF00'))


def overlay_draw_spell_target(x, y, spell_name):
    """Draw a spell target crosshair if overlay is enabled."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        print(f"[OVERLAY] Drawing spell target: {spell_name} at ({x},{y})")
        runtime.gui.overlay.draw_crosshair(x, y, 25, config.OVERLAY_COLORS.get('spell_target', '#FF00FF'), spell_name)


def clear_overlay_hotkey():
    """Clear all overlay drawings (F7 hotkey)."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        runtime.gui.overlay.clear()
        runtime.gui.overlay.update()
        print("[OVERLAY] Cleared via F7 hotkey")


def save_overlay_screenshot_hotkey():
    """Save overlay screenshot with black background (F8 hotkey)."""
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        runtime.gui.overlay.save_screenshot()
    else:
        print("[OVERLAY] Cannot save - overlay not enabled")
