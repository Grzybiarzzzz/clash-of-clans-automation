"""Reading numbers and short texts from the screen.

Resource numbers (scouting loot, own storages, end-screen loot) go through the digit
reader in ``coc_bot.vision.digits``. A read that cannot be trusted returns ``None``;
it is never reported as 0, so callers can tell "unreadable" from "empty".

Troop counts, the destruction percentage and the Builder Base "Attacker" label still
use Tesseract.
"""

import os
import re
import time

import cv2
import numpy as np
import pytesseract

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log, send_discord_ocr_log
from coc_bot.overlay import overlay_clear, overlay_draw_ocr
from coc_bot.vision import digits
from coc_bot.vision.capture import frozen_frame, grab as grab_screen
from coc_bot.vision.ocr_corpus import OcrCorpus

_RESOURCE_EMOJI = {"gold": "🪙", "elixir": "💧", "dark_elixir": "⚫"}
_corpus = None


def _get_corpus():
    """The crop recorder, or None when recording is switched off in config."""
    global _corpus
    if not getattr(config, "OCR_CORPUS_ENABLED", True):
        return None
    if _corpus is None:
        _corpus = OcrCorpus(
            getattr(config, "OCR_CORPUS_DIR", os.path.join("data", "ocr_corpus")),
            max_files=getattr(config, "OCR_CORPUS_MAX_FILES", 5000),
            keep_every=getattr(config, "OCR_CORPUS_KEEP_EVERY", 20),
        )
    return _corpus


def _read(image, context, resource_type=None):
    """Read one number. Returns (value or None, DigitReading)."""
    label = resource_type or context
    bgr = digits.to_bgr(image)
    reading = digits.read_number(bgr, context, check_grouping=getattr(config, "OCR_CHECK_GROUPING", True))
    use_legacy = getattr(config, "OCR_ENGINE", "segmented") == "legacy"
    corpus = _get_corpus()

    legacy_value = None
    if use_legacy or corpus is not None:
        try:
            legacy_value = digits.legacy_read(bgr, context)
        except Exception as e:
            print(f"[OCR] Legacy reader failed: {e}")
    value = legacy_value if use_legacy else reading.value

    if corpus is not None:
        try:
            corpus.record(bgr, context, label, reading, legacy_value)
        except OSError as e:
            print(f"[OCR] Could not save crop to the corpus: {e}")

    emoji = _RESOURCE_EMOJI.get(resource_type, "📊")
    if value is None:
        send_discord_ocr_log(f"{emoji} **{label.upper()}**: unreadable ({reading.reason})")
        shown = f"unreadable ({reading.reason})"
    else:
        scores = " ".join(f"{g.digit}({g.score * 100:.0f}%)" for g in reading.glyphs)
        send_discord_ocr_log(f"{emoji} **{label.upper()}**: {value}  [{scores}]")
        shown = value
    if runtime.gui is not None:
        runtime.gui.ocr_log(label.upper(), shown, raw_value=reading.text or None, confidence=reading.confidence * 100)
    return value, reading


def read_resource(image, context, resource_type=None):
    """Read a resource number from a crop (PIL image or BGR array).

    ``context`` selects the digit templates: 'attack_screen', 'base_screen',
    'base_dark_elixir', 'bb_base_screen' or 'loot_screen'. ``resource_type`` ('gold',
    'elixir', 'dark_elixir') only labels the logs. Returns the integer, or None when
    the number could not be read with confidence.
    """
    return _read(image, context, resource_type)[0]


def read_region(region, context, resource_type=None, attempts=1, delay=0.2):
    """Capture a screen region and read its number, retrying while it is unreadable."""
    for attempt in range(attempts):
        value = read_resource(grab_screen(region), context, resource_type)
        if value is not None:
            return value
        if attempt < attempts - 1:
            time.sleep(delay)
    return None


def evaluate_base_resources(timeout=0.0, poll=0.2):
    """Read the loot offered by the base being scouted.

    Polls until both numbers are readable or ``timeout`` seconds have passed, which
    also covers the clouds between two bases. Returns (gold, elixir); a value that
    stayed unreadable is None.
    """
    send_discord_ocr_log("━━━━━━ **BASE SEARCH** ━━━━━━")
    deadline = time.time() + timeout
    while True:
        with frozen_frame():
            gold, gold_reading = _read(grab_screen(config.GOLD_REGION), "attack_screen", "gold")
            elixir, elixir_reading = _read(grab_screen(config.ELIXIR_REGION), "attack_screen", "elixir")
        if gold is not None and elixir is not None:
            break
        if time.time() >= deadline or not runtime.running:
            break
        time.sleep(poll)

    overlay_clear()
    for region, value, reading, name in (
        (config.GOLD_REGION, gold, gold_reading, "GOLD"),
        (config.ELIXIR_REGION, elixir, elixir_reading, "ELIXIR"),
    ):
        text = f"{value:,}" if value is not None else "?"
        overlay_draw_ocr(region, text, round(reading.confidence * 100), name)

    print(f"OCR -> Gold: {gold}, Elixir: {elixir}")
    send_discord_debug_log(f"Resource OCR: Gold {gold}, Elixir {elixir}")
    return gold, elixir


def ocr_loot():
    """Read the loot shown after a battle.

    Returns {'gold', 'elixir', 'dark_elixir'}. A value that cannot be read, or that is
    implausibly large (over 4 million), is recorded as 0 and logged.
    """
    loot = {"gold": 0, "elixir": 0, "dark_elixir": 0}
    regions = (
        ("gold", config.LOOT_GOLD_REGION),
        ("elixir", config.LOOT_ELIXIR_REGION),
        ("dark_elixir", config.LOOT_DARK_ELIXIR_REGION),
    )
    try:
        send_discord_ocr_log("━━━━━━ **LOOT OCR** ━━━━━━")
        with frozen_frame():
            for key, region in regions:
                value, reading = _read(grab_screen(region), "loot_screen", key)
                if value is None:
                    if reading.reason != "no_digits":  # an empty row simply means none of that resource
                        message = f"[OCR] Loot {key} unreadable ({reading.reason}); recorded as 0"
                        print(message)
                        runtime.gui.log_message(message)
                elif value > 4_000_000:
                    message = f"[OCR FAILSAFE] Loot {key} value {value} > 4 million. Ignoring this value."
                    print(message)
                    runtime.gui.log_message(message)
                    send_discord_debug_log(f"OCR failsafe: Loot {key} value {value} > 4 million, ignoring", "WARNING")
                else:
                    loot[key] = value
        print(
            f"Loot captured - Gold: {loot['gold']:,}, Elixir: {loot['elixir']:,}, Dark Elixir: {loot['dark_elixir']:,}"
        )
        runtime.gui.log_message(f"Loot: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}")
        send_discord_debug_log(
            f"Loot captured: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}"
        )
        return loot
    except Exception as e:
        print(f"Error capturing loot: {e}")
        runtime.gui.log_message(f"Error capturing loot: {e}")
        send_discord_debug_log(f"Error capturing loot: {e}", "ERROR")
        return loot


def ocr_remaining_troop_count():
    """
    OCR the remaining troop count during attack from the troop count region.
    Format: "xN" where N is the number of remaining troops (e.g., "x2", "x50", "x0")

    Returns:
        int: Number of remaining troops (0-64), or -1 if OCR fails
    """
    try:
        # Capture the troop count region
        screenshot = grab_screen(config.TROOP_COUNT_REGION)

        # Convert to grayscale and apply thresholding for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 150, 255, cv2.THRESH_BINARY)

        # OCR the text (expect format "xN" where N is 0-64)
        text = pytesseract.image_to_string(screenshot_cv, config="--psm 7")
        text = text.strip().replace(" ", "").replace("O", "0")  # Fix common OCR mistakes

        # Remove 'x' prefix if present
        if text.startswith("x"):
            text = text[1:]

        # Try to parse the number
        if text.isdigit():
            count = int(text)
            if 0 <= count <= 64:  # Validate range
                print(f"[TROOP COUNT OCR] Remaining troops: {count}")
                return count
            else:
                print(f"[TROOP COUNT OCR] Invalid count {count} (out of range 0-64)")
                return -1
        else:
            print(f"[TROOP COUNT OCR] Failed to parse: '{text}'")
            return -1

    except Exception as e:
        print(f"[TROOP COUNT OCR] Exception: {e}")
        return -1


def check_bb_attacker_text():
    """
    Check if 'Attacker' text is visible on screen to confirm BB base has loaded.
    Returns True if text detected, False otherwise.
    """
    try:
        # Capture the attacker text region
        screenshot = grab_screen(config.BB_ATTACKER_TEXT_REGION)

        # Convert to grayscale for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

        # Apply thresholding (white text on dark background)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 150, 255, cv2.THRESH_BINARY)

        # OCR the text
        text = pytesseract.image_to_string(screenshot_cv, config="--psm 7")
        text = text.strip().lower()

        # Check if "attacker" is in the text
        if "attacker" in text:
            return True
        return False
    except Exception as e:
        print(f"[BB] Error checking Attacker text: {e}")
        send_discord_debug_log(f"BB: Error checking Attacker text: {e}", "WARNING")
        return False


def debug_save_ocr_regions():
    """Save screenshots of the OCR regions for debugging bounding boxes."""
    try:
        folder = "debug_ocr_regions"
        os.makedirs(folder, exist_ok=True)
        # Count images in folder
        images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if len(images) >= 500:
            return
        gold_img = grab_screen(config.GOLD_REGION)
        gold_img.save(os.path.join(folder, "debug_gold_region_{:03d}.png".format(len(images) + 1)))
        elixir_img = grab_screen(config.ELIXIR_REGION)
        elixir_img.save(os.path.join(folder, "debug_elixir_region_{:03d}.png".format(len(images) + 1)))
        if hasattr(config, "DARK_ELIXIR_REGION"):
            dark_img = grab_screen(config.DARK_ELIXIR_REGION)
            dark_img.save(os.path.join(folder, "debug_dark_elixir_region_{:03d}.png".format(len(images) + 1)))
        runtime.gui.log_message("OCR region screenshots saved for debugging.")
    except Exception as e:
        print(f"Error saving OCR region screenshots: {e}")
        runtime.gui.log_message(f"Error saving OCR region screenshots: {e}")


def parse_destruction_text(text, previous=None):
    """Turn the OCR text of the destruction box into a percentage, or None.

    The "%" sign is often read as extra digits ("50%" as "5096"), so normally only the
    first two digits count. "100" is believed only when the previous reading was already
    75 or more; early in a battle it is far more likely a misread "10%".
    """
    found = "".join(re.findall(r"\d", text.replace("O", "0")))
    if not found:
        return None
    if found.startswith("100") and previous is not None and previous >= 75:
        return 100
    return int(found[:2])


def detect_destruction_percentage(save_debug_screenshots=True):
    """
    Detect current destruction percentage during attack using OCR.
    Returns percentage as integer (0-100), or None if detection fails.
    Reads from bottom-right destruction percentage box.
    Includes jump detection to reject impossible changes between two checks.

    Args:
        save_debug_screenshots: If True, saves debug screenshots on abnormal jumps. Set to False for SBarb Farm mode.
    """
    try:
        screenshot = grab_screen(config.DESTRUCTION_REGION)

        # Convert to grayscale and apply thresholding for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 200, 255, cv2.THRESH_BINARY)

        text = pytesseract.image_to_string(screenshot_cv, config="--psm 7 digits").strip()
        previous = getattr(detect_destruction_percentage, "last_valid", None)
        percentage = parse_destruction_text(text, previous)
        if percentage is None:
            if config.DEBUG_DESTRUCTION_PERCENTAGE:
                print(f"[DESTRUCTION DEBUG] Failed to parse: raw_text='{text}'")
            return None

        if previous is not None:
            jump = percentage - previous
            # More than +25% between two checks is impossible; a drop beyond OCR noise is too
            if jump > 25 or jump < -5:
                kind = "impossible jump" if jump > 25 else "negative jump"
                saved = ""
                if save_debug_screenshots:
                    os.makedirs("debug_screenshots", exist_ok=True)
                    timestamp = int(time.time())
                    screenshot.save(f"debug_screenshots/destruction_abnormal_raw_{timestamp}_{percentage}pct.png")
                    cv2.imwrite(
                        f"debug_screenshots/destruction_abnormal_threshold_{timestamp}_{percentage}pct.png",
                        screenshot_cv,
                    )
                    saved = " (screenshots saved to debug_screenshots/)"
                print(f"[DESTRUCTION DEBUG] REJECTED {percentage}% - {kind} of {jump:+d}% from {previous}%{saved}")
                return None

        detect_destruction_percentage.last_valid = percentage
        if config.DEBUG_DESTRUCTION_PERCENTAGE:
            print(f"[DESTRUCTION DEBUG] Detected: {percentage}% (from '{text}')")
        return percentage
    except Exception as e:
        print(f"[DESTRUCTION] Error detecting percentage: {e}")
        return None
