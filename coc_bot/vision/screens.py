"""Detection of screens, buttons and battle states from screenshots."""

import os
import time

import cv2
import numpy as np
from PIL import ImageGrab

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.vision.ocr import check_bb_attacker_text

# BB Gold template cache (eliminates disk I/O during attacks)
_bb_gold_template_cache = {}


def detect_army_button():
    """
    Detect the army button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Capture the search region
    screen_img = ImageGrab.grab(bbox=config.ARMY_BUTTON_SEARCH_REGION)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    if not os.path.exists(config.ARMY_BUTTON_TEMPLATE_DIR):
        print(f"Army button templates directory not found: {config.ARMY_BUTTON_TEMPLATE_DIR}")
        send_discord_debug_log(
            f"Army button templates directory not found: {config.ARMY_BUTTON_TEMPLATE_DIR}", "WARNING"
        )
        return None

    # Load the army button template
    template_path = os.path.join(config.ARMY_BUTTON_TEMPLATE_DIR, "army_button.png")
    if not os.path.exists(template_path):
        print(f"Army button template not found: {template_path}")
        send_discord_debug_log(f"Army button template not found: {template_path}", "WARNING")
        return None

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load army button template: {template_path}")
        send_discord_debug_log(f"Failed to load army button template: {template_path}", "WARNING")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= config.ARMY_BUTTON_DETECTION_THRESHOLD:
        # Calculate center of the button
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + config.ARMY_BUTTON_SEARCH_REGION[0]
        center_y = max_loc[1] + template_height // 2 + config.ARMY_BUTTON_SEARCH_REGION[1]

        print(f"Army button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"Army button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"Army button not detected (best match confidence: {max_val:.2f})")
        send_discord_debug_log(f"Army button not detected (best match confidence: {max_val:.2f})", "WARNING")
        return None


def detect_surrender_button():
    """
    Detect the surrender button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Full screen search
    screen_img = ImageGrab.grab()
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    surrender_template_dir = "screenshots/reference/attack/"
    if not os.path.exists(surrender_template_dir):
        print(f"Surrender button templates directory not found: {surrender_template_dir}")
        send_discord_debug_log(f"Surrender button templates directory not found: {surrender_template_dir}", "WARNING")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get("surrender")
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(surrender_template_dir, "surrender.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load surrender button template: {template_path}")
        send_discord_debug_log(f"Failed to load surrender button template: {template_path}", "WARNING")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.65:  # 65% confidence threshold (lowered for better detection)
        # Calculate center of the button
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2
        center_y = max_loc[1] + template_height // 2

        print(f"Surrender button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"Surrender button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"Surrender button not detected (best match confidence: {max_val:.2f})")
        send_discord_debug_log(f"Surrender button not detected (best match confidence: {max_val:.2f})", "WARNING")
        return None


def wait_for_attack_screen_ready(timeout=10):
    """
    Wait for attack screen to be ready by detecting the End Battle button.
    Checks every 0.1 seconds until button is detected or timeout is reached.

    Args:
        timeout: Maximum time to wait in seconds (default: 10)

    Returns:
        True if attack screen is ready, False if timeout reached
    """
    print(f"[ATTACK SCREEN] Waiting for End Battle button (timeout: {timeout}s)...")
    send_discord_debug_log(f"Waiting for attack screen ready (End Battle detection, timeout={timeout}s)")

    start_time = time.time()
    check_count = 0

    while time.time() - start_time < timeout:
        check_count += 1

        # Capture screen
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load End Battle template
        template_path = "screenshots/reference/attack/end_battle.png"
        if not os.path.exists(template_path):
            print(f"[ATTACK SCREEN] End Battle template not found: {template_path}")
            send_discord_debug_log(f"End Battle template not found: {template_path}", "ERROR")
            return False

        template = cv2.imread(template_path)
        if template is None:
            print(f"[ATTACK SCREEN] Failed to load End Battle template: {template_path}")
            send_discord_debug_log(f"Failed to load End Battle template: {template_path}", "ERROR")
            return False

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            elapsed = time.time() - start_time
            print(
                f"[ATTACK SCREEN] End Battle button detected! (confidence: {max_val:.2f}, checks: {check_count}, time: {elapsed:.2f}s)"
            )
            send_discord_debug_log(
                f"Attack screen ready - End Battle detected (conf={max_val:.2f}, {check_count} checks, {elapsed:.2f}s)"
            )
            return True

        # Wait 0.1 seconds before next check
        time.sleep(0.1)

    # Timeout reached
    elapsed = time.time() - start_time
    print(f"[ATTACK SCREEN] TIMEOUT after {elapsed:.2f}s and {check_count} checks (best confidence: {max_val:.2f})")
    send_discord_debug_log(
        f"Attack screen timeout - End Battle not detected ({check_count} checks, best conf={max_val:.2f})", "WARNING"
    )
    return False


def detect_star_bonus_screen():
    """
    Detect the star bonus screen using template matching.
    Searches in the top-middle portion of the screen.
    Returns True if star bonus screen detected, False otherwise.
    """
    # Check if templates directory exists
    star_bonus_template_dir = "screenshots/reference/attack/"
    if not os.path.exists(star_bonus_template_dir):
        print(f"Star bonus templates directory not found: {star_bonus_template_dir}")
        return False

    # Load the star bonus template
    template_path = os.path.join(star_bonus_template_dir, "home_star_bonus.png")
    if not os.path.exists(template_path):
        print(f"Star bonus template not found: {template_path}")
        return False

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load star bonus template: {template_path}")
        return False

    # Get template dimensions
    template_height, template_width = template.shape[:2]
    print(f"[SBARB FARM] Star bonus template size: {template_width}x{template_height}")

    # Define search region (top-middle portion of screen)
    # Make sure region is larger than template
    star_bonus_region = (600, 50, 1900, 700)

    # Capture the search region
    screen_img = ImageGrab.grab(bbox=star_bonus_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Get search region dimensions
    region_height, region_width = screen_cv.shape[:2]
    print(f"[SBARB FARM] Search region size: {region_width}x{region_height}")

    # Verify template is smaller than search region
    if template_width > region_width or template_height > region_height:
        print(
            f"[SBARB FARM] Template ({template_width}x{template_height}) is larger than search region ({region_width}x{region_height}), using full screen"
        )
        # Fall back to full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Perform template matching
    try:
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.70:  # 70% confidence threshold
            print(f"Star bonus screen detected with confidence {max_val:.2f}")
            send_discord_debug_log(f"Star bonus screen detected (confidence: {max_val:.2f})")
            return True
        else:
            print(f"Star bonus screen not detected (best match confidence: {max_val:.2f})")
            return False
    except cv2.error as e:
        print(f"[SBARB FARM] Error during template matching: {e}")
        send_discord_debug_log(f"SBarb Farm: Star bonus detection error - {e}", "WARNING")
        return False


def detect_two_stars():
    """
    Detect 2 stars on screen during Builder Base attack using template matching.
    Returns True if 2 stars detected, False otherwise.
    Searches bottom-right region of screen where stars appear.
    """
    # Search bottom-right region where stars appear
    search_region = (1500, 1000, 2560, 1440)  # Bottom-right corner
    screen_img = ImageGrab.grab(bbox=search_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    stars_template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(stars_template_dir):
        print(f"2 stars templates directory not found: {stars_template_dir}")
        send_discord_debug_log(f"2 stars templates directory not found: {stars_template_dir}", "WARNING")
        return False

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get("2_stars")
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(stars_template_dir, "2_stars.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load 2 stars template: {template_path}")
        send_discord_debug_log(f"Failed to load 2 stars template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.85:  # 85% confidence threshold (higher to avoid false positives)
        print(f"2 stars detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"2 stars detected with confidence {max_val:.2f}")
        return True
    else:
        return False


def detect_three_stars():
    """
    Detect 3 stars on screen during Builder Base attack using template matching.
    Returns True if 3 stars detected, False otherwise.
    Searches bottom-right region of screen where stars appear.
    This happens when Builder Hall is destroyed last (goes from 1 star to 3 stars directly).
    """
    # Search bottom-right region where stars appear
    search_region = (1500, 1000, 2560, 1440)  # Bottom-right corner
    screen_img = ImageGrab.grab(bbox=search_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    stars_template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(stars_template_dir):
        print(f"3 stars templates directory not found: {stars_template_dir}")
        send_discord_debug_log(f"3 stars templates directory not found: {stars_template_dir}", "WARNING")
        return False

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get("3_stars")
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(stars_template_dir, "3_stars.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load 3 stars template: {template_path}")
        send_discord_debug_log(f"Failed to load 3 stars template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.85:  # 70% confidence threshold
        print(f"3 stars detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"3 stars detected with confidence {max_val:.2f}")
        return True
    else:
        return False


def detect_star_bonus():
    """
    Detect star bonus screen in Builder Base using template matching.
    Returns True if star bonus screen detected, False otherwise.
    Searches center region of screen where the bonus screen appears.
    """
    # Search center region where star bonus screen appears (it's quite big)
    screen_img = ImageGrab.grab()  # Full screen capture
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(template_dir):
        print(f"Star bonus templates directory not found: {template_dir}")
        send_discord_debug_log(f"Star bonus templates directory not found: {template_dir}", "WARNING")
        return False

    # Load the star bonus template
    template_path = os.path.join(template_dir, "star_bonus.png")
    if not os.path.exists(template_path):
        print(f"Star bonus template not found: {template_path}")
        send_discord_debug_log(f"Star bonus template not found: {template_path}", "WARNING")
        return False

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load star bonus template: {template_path}")
        send_discord_debug_log(f"Failed to load star bonus template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        print(f"Star bonus screen detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"Star bonus screen detected with confidence {max_val:.2f}")
        return True
    else:
        return False


def load_bb_gold_templates():
    """
    Pre-load all BB Gold templates into memory to eliminate disk I/O during attacks.
    Called once at bot startup. Provides 20-40% speedup by caching frequently used templates.
    """
    global _bb_gold_template_cache

    templates = {
        "2_stars": "screenshots/reference/builder_base/2_stars.png",
        "3_stars": "screenshots/reference/builder_base/3_stars.png",
        "surrender": "screenshots/reference/attack/surrender.png",  # Fixed: attack/ not builder_base/
        "end_battle": "screenshots/reference/attack/end_battle.png",
        "return_home": "screenshots/reference/builder_base/return_home.png",
        "army_button": "screenshots/reference/reinforcements/army_button.png",
        "connection_lost": "screenshots/reference/general/connection_lost.png",
        "try_again": "screenshots/reference/general/try_again.png",
    }

    for name, path in templates.items():
        if os.path.exists(path):
            template = cv2.imread(path)
            if template is not None:
                _bb_gold_template_cache[name] = template
                print(f"[CACHE] Loaded BB Gold template: {name}")
        else:
            print(f"[CACHE] Warning: Template not found: {path}")

    print(f"[CACHE] BB Gold templates loaded: {len(_bb_gold_template_cache)}/8")


def detect_in_base_state():
    """
    Detect if bot is at home base using army_button.png template matching.

    Returns:
        bool: True if army button detected (in base), False otherwise

    Template: screenshots/reference/reinforcements/army_button.png
    Region: Full screen (config.ARMY_BUTTON_SEARCH_REGION)
    Threshold: 0.8 (config.ARMY_BUTTON_DETECTION_THRESHOLD)
    """
    try:
        # Use full screen if region not specified
        search_region = getattr(config, "ARMY_BUTTON_SEARCH_REGION", None)
        if search_region:
            screenshot = ImageGrab.grab(bbox=search_region)
        else:
            screenshot = ImageGrab.grab()  # Full screen

        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Load from cache (or fallback to disk)
        template = _bb_gold_template_cache.get("army_button")
        if template is None:
            # Cache miss - load from disk as fallback
            template_dir = getattr(config, "ARMY_BUTTON_TEMPLATE_DIR", "screenshots/reference/reinforcements")
            template_path = os.path.join(template_dir, "army_button.png")
            if os.path.exists(template_path):
                template = cv2.imread(template_path)

        if template is None:
            return False

        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        threshold = getattr(config, "ARMY_BUTTON_DETECTION_THRESHOLD", 0.8)
        detected = max_val >= threshold

        if detected:
            print(f"[BASE DETECT] Army button detected (confidence: {max_val:.2f})")

        return detected

    except Exception as e:
        print(f"[BASE DETECT] Error detecting base: {e}")
        return False


def detect_connection_lost():
    """
    Detect if "Connection lost" popup is showing using template matching.
    First detects the popup, then finds the "TRY AGAIN" button.

    Returns:
        tuple: (x, y) coordinates of "TRY AGAIN" button center if found, None otherwise

    Templates:
        - screenshots/reference/general/connection_lost.png (popup detection)
        - screenshots/reference/general/try_again.png (button detection)
    """
    try:
        screenshot = ImageGrab.grab()
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Step 1: Detect the connection lost popup
        popup_template = _bb_gold_template_cache.get("connection_lost")
        if popup_template is None:
            template_path = "screenshots/reference/general/connection_lost.png"
            if os.path.exists(template_path):
                popup_template = cv2.imread(template_path)

        if popup_template is None:
            return None

        result = cv2.matchTemplate(screenshot_cv, popup_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        threshold = 0.75  # 75% confidence threshold
        if max_val < threshold:
            return None  # Popup not found

        print(f"[CONNECTION] Connection lost popup detected (confidence: {max_val:.2f})")

        # Step 2: Find the "TRY AGAIN" button using template matching
        try_again_template = _bb_gold_template_cache.get("try_again")
        if try_again_template is None:
            template_path = "screenshots/reference/general/try_again.png"
            if os.path.exists(template_path):
                try_again_template = cv2.imread(template_path)

        if try_again_template is None:
            print("[CONNECTION] Warning: try_again.png template not found, using fallback position")
            # Fallback: estimate position based on popup location
            popup_height = popup_template.shape[0]
            return (max_loc[0] + 60, max_loc[1] + popup_height - 20)

        # Search for TRY AGAIN button on the full screen
        btn_result = cv2.matchTemplate(screenshot_cv, try_again_template, cv2.TM_CCOEFF_NORMED)
        btn_min_val, btn_max_val, btn_min_loc, btn_max_loc = cv2.minMaxLoc(btn_result)

        if btn_max_val >= 0.7:  # 70% threshold for button
            # Calculate center of the button
            btn_height, btn_width = try_again_template.shape[:2]
            try_again_x = btn_max_loc[0] + btn_width // 2
            try_again_y = btn_max_loc[1] + btn_height // 2

            print(
                f"[CONNECTION] TRY AGAIN button found at ({try_again_x}, {try_again_y}) (confidence: {btn_max_val:.2f})"
            )
            return (try_again_x, try_again_y)
        else:
            print(f"[CONNECTION] TRY AGAIN button not found (best: {btn_max_val:.2f}), using fallback")
            # Fallback position
            popup_height = popup_template.shape[0]
            return (max_loc[0] + 60, max_loc[1] + popup_height - 20)

    except Exception as e:
        print(f"[CONNECTION] Error detecting connection lost: {e}")
        return None


def wait_for_base_screen(timeout=15):
    """
    Wait for home base screen to load using army_button.png template matching.
    Used after returning home to ensure base is fully loaded before OCR.

    Args:
        timeout: Maximum wait time in seconds (default 15)

    Returns:
        bool: True if base detected within timeout, False otherwise
    """
    print(f"[BASE DETECT] Waiting for base screen (timeout: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if detect_in_base_state():
            elapsed = time.time() - start_time
            print(f"[BASE DETECT] ✓ Base screen loaded ({elapsed:.1f}s)")
            return True
        time.sleep(0.3)

    print(f"[BASE DETECT] ✗ Timeout - base not detected after {timeout}s")
    return False


def detect_end_screen_state():
    """
    Detect if battle ended and end screen is displayed (post-battle screen with resources).
    End screen indicators:
    - Return home button visible (primary indicator), OR
    - Battle UI elements are GONE (no surrender button, no end_battle button) as fallback

    NOTE: This detects the post-battle screen AFTER clicking surrender/end battle,
    showing the resources earned screen with the return home button.

    Returns:
        dict: {'detected': bool, 'stars': int, 'star_bonus': bool, 'return_button_visible': bool}
                stars = 0/1/2/3, star_bonus = True if bonus screen present
    """
    try:
        result = {
            "detected": False,
            "stars": 0,
            "star_bonus": False,
            "return_button_visible": False,
            "return_button_pos": None,
        }

        # Primary indicator: Return home button (appears on post-battle screen)
        return_button = detect_return_home_button()
        if return_button:
            result["detected"] = True
            result["return_button_visible"] = True
            result["return_button_pos"] = return_button
            print(f"[BB STATE] END_SCREEN confirmed (return home button at {return_button})")

        # Fallback: Check if battle UI elements are gone (if template doesn't exist yet)
        if not result["detected"]:
            surrender_visible = detect_surrender_button() is not None
            end_battle_visible = detect_end_battle_button() is not None

            # If battle UI is gone, we're likely at end screen
            if not surrender_visible and not end_battle_visible:
                result["detected"] = True
                print("[BB STATE] END_SCREEN confirmed (battle UI elements gone - fallback method)")

        # Check for star bonus (appears AFTER end screen when user clicks through)
        if detect_star_bonus():
            result["star_bonus"] = True
            print("[BB STATE] END_SCREEN: Star bonus visible")

        # Check star count (may still be visible on end screen)
        if detect_three_stars():
            result["stars"] = 3
            print("[BB STATE] END_SCREEN: 3 stars detected")
        elif detect_two_stars():
            result["stars"] = 2
            print("[BB STATE] END_SCREEN: 2 stars detected")

        return result

    except Exception as e:
        print(f"[BB STATE] Error detecting END_SCREEN: {e}")
        return {"detected": False, "stars": 0, "star_bonus": False, "return_button_visible": False}


def detect_ghost_attack():
    """
    Detect ghost attack state - search initiated but no base loaded.
    Ghost attack occurs when:
    - Not in base (army button NOT visible)
    - Not in attack ready (no "Attacker" text)
    - Not in battle (no surrender button)
    - Not at end screen (no end battle button)

    Returns:
        bool: True if ghost attack detected, False otherwise
    """
    try:
        in_base = detect_in_base_state()
        attack_ready = check_bb_attacker_text()
        surrender_exists = detect_surrender_button() is not None
        end_button_exists = detect_end_battle_button() is not None

        # Ghost = not in any known valid state
        is_ghost = not (in_base or attack_ready or surrender_exists or end_button_exists)

        if is_ghost:
            print("[BB STATE] GHOST ATTACK detected (no valid state indicators)")
            send_discord_debug_log("BB Gold: Ghost attack detected - no valid state", "WARNING")

        return is_ghost

    except Exception as e:
        print(f"[BB STATE] Error detecting ghost attack: {e}")
        return False


def detect_return_home_button(quiet=False):
    """
    Detect return home button on post-battle screen using template matching.
    This button appears after battle ends (on the screen showing resources earned).

    Args:
        quiet (bool): If True, suppress "not detected" log messages (useful for continuous monitoring)

    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Search in bottom-center area where return home button appears
    # Button location: X=1070-1496, Y=1116-1328
    region = (1000, 1050, 1550, 1400)
    screen_img = ImageGrab.grab(bbox=region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(template_dir):
        print(f"Return home button templates directory not found: {template_dir}")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get("return_home")
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(template_dir, "return_home.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"[BB STATE] Failed to load return home button template: {template_path}")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        # Calculate center of the button (convert to global coordinates)
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + region[0]
        center_y = max_loc[1] + template_height // 2 + region[1]

        print(f"[BB STATE] ✓ Return home button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        if not quiet:
            print(f"[BB STATE] ✗ Return home button not detected (best match: {max_val:.2f}, threshold: 0.70)")
        return None


def detect_end_battle_button():
    """
    Detect end battle button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Search in bottom-left area where end_battle button appears
    region = (0, 1000, 600, 1440)
    screen_img = ImageGrab.grab(bbox=region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/attack/"
    if not os.path.exists(template_dir):
        print(f"End battle button templates directory not found: {template_dir}")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get("end_battle")
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(template_dir, "end_battle.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load end battle button template: {template_path}")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        # Calculate center of the button (convert to global coordinates)
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + region[0]
        center_y = max_loc[1] + template_height // 2 + region[1]

        print(f"End battle button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"End battle button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"End battle button not detected (best match confidence: {max_val:.2f})")
        return None


def detect_surrender_or_end_battle():
    """
    Detect either surrender button OR end battle button on screen.
    Returns tuple (button_type, x, y) where button_type is 'surrender' or 'end_battle',
    or (None, None, None) if neither found.
    """
    # First try to detect surrender button
    surrender_pos = detect_surrender_button()
    if surrender_pos:
        return ("surrender", surrender_pos[0], surrender_pos[1])

    # If surrender not found, try end battle button
    end_battle_pos = detect_end_battle_button()
    if end_battle_pos:
        return ("end_battle", end_battle_pos[0], end_battle_pos[1])

    # Neither found
    return (None, None, None)


def detect_current_game_state():
    """
    Detect current game state when uncertain (for error recovery and fallback handling).

    Returns:
        str: One of 'in_base', 'battle_active', 'end_screen', 'unknown'

    Detection order:
    1. Check if at base (army button visible)
    2. Check if at end screen (return home button visible)
    3. Check if in active battle (surrender button visible)
    4. Unknown state if none match
    """
    print("[STATE DETECT] Attempting to detect current game state...")

    # 1. Check if we're at base
    if detect_in_base_state():
        print("[STATE DETECT] ✓ Detected: IN_BASE (army button visible)")
        return "in_base"

    # 2. Check if we're at end screen
    if detect_return_home_button():
        print("[STATE DETECT] ✓ Detected: END_SCREEN (return home button visible)")
        return "end_screen"

    # 3. Check if we're in active battle
    button_type, x, y = detect_surrender_or_end_battle()
    if button_type == "surrender":
        print("[STATE DETECT] ✓ Detected: BATTLE_ACTIVE (surrender button visible)")
        return "battle_active"
    elif button_type == "end_battle":
        print("[STATE DETECT] ✓ Detected: BATTLE_ENDING (end battle button visible)")
        return "battle_ending"

    # 4. Unknown state
    print("[STATE DETECT] ✗ Could not determine state (no recognizable UI elements)")
    return "unknown"


def is_base_search_ready():
    """Check if base search screen is ready by detecting end_battle button"""
    template_path = "screenshots/reference/attack/end_battle.png"
    # Search in bottom-left area where end_battle button appears
    region = (0, 1100, 600, 1440)
    threshold = 0.75
    try:
        template = cv2.imread(template_path)
        if template is None:
            print(f"Warning: Could not load template at {template_path}")
            return False

        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            print(f"Base search screen detected (confidence: {max_val:.2f})")
            return True
        return False
    except Exception as e:
        print(f"Error in is_base_search_ready: {e}")
        return False


def is_attack_screen_ready():
    # Use the alt hotkey template and region as the cue
    template_path = "assets/alt_hotkey_template.png"
    region = (522, 1273, 664, 1412)
    try:
        template = cv2.imread(template_path)
        if template is None:
            return False
        h, w, _ = template.shape
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        if screenshot_cv.shape[0] == h and screenshot_cv.shape[1] == w:
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            return max_val >= 0.8
        else:
            return False
    except Exception as e:
        print(f"[DERANK] Error in is_attack_screen_ready: {e}")
        return False


def detect_main_base_boat():
    """
    Detect boat on Main Base using template matching.
    Returns (x, y) coordinates of the boat center if found, None otherwise.
    """
    try:
        # Full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load the boat template
        template_path = "screenshots/reference/main_base/boat.png"
        if not os.path.exists(template_path):
            print(f"[MAIN BOAT] Boat template not found: {template_path}")
            send_discord_debug_log(f"Main Base boat template not found: {template_path}", "WARNING")
            return None

        template = cv2.imread(template_path)
        if template is None:
            print(f"[MAIN BOAT] Failed to load boat template: {template_path}")
            send_discord_debug_log(f"Failed to load boat template: {template_path}", "WARNING")
            return None

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            # Calculate center of the boat
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2
            center_y = max_loc[1] + template_height // 2

            print(f"[MAIN BOAT] Boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            send_discord_debug_log(f"Main Base boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            return (center_x, center_y)
        else:
            print(f"[MAIN BOAT] Boat not detected (best match confidence: {max_val:.2f})")
            send_discord_debug_log(f"Main Base boat not detected (best match confidence: {max_val:.2f})", "WARNING")
            return None
    except Exception as e:
        print(f"[MAIN BOAT] Error detecting boat: {e}")
        send_discord_debug_log(f"Main Base boat detection error: {e}", "ERROR")
        return None


def detect_bb_boat():
    """
    Detect Builder Base boat using template matching.
    Returns (x, y, is_cart_fallback) tuple if found, None otherwise.
    is_cart_fallback is True when using trees fallback (returns elixir cart position).
    """
    try:
        # Full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load the boat template
        template_path = "screenshots/reference/builder_base/boat.png"
        if not os.path.exists(template_path):
            print(f"[BB BOAT] Boat template not found: {template_path}")
            send_discord_debug_log(f"BB boat template not found: {template_path}", "WARNING")
            return None

        template = cv2.imread(template_path)
        if template is None:
            print(f"[BB BOAT] Failed to load boat template: {template_path}")
            send_discord_debug_log(f"Failed to load boat template: {template_path}", "WARNING")
            return None

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            # Calculate center of the boat
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2
            center_y = max_loc[1] + template_height // 2

            print(f"[BB BOAT] Boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            send_discord_debug_log(f"BB boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            return (center_x, center_y, False)

        # Boat not found - try trees fallback to find elixir cart
        print(f"[BB BOAT] Boat not detected (best match confidence: {max_val:.2f}), trying trees fallback...")
        trees_template_path = "screenshots/reference/builder_base/trees.png"
        if os.path.exists(trees_template_path):
            trees_template = cv2.imread(trees_template_path)
            if trees_template is not None:
                trees_result = cv2.matchTemplate(screen_cv, trees_template, cv2.TM_CCOEFF_NORMED)
                _, trees_max_val, _, trees_max_loc = cv2.minMaxLoc(trees_result)

                if trees_max_val >= 0.7:
                    trees_h, trees_w = trees_template.shape[:2]
                    trees_center_x = trees_max_loc[0] + trees_w // 2
                    trees_center_y = trees_max_loc[1] + trees_h // 2

                    # Calculate elixir cart position from trees (offset +248, +200)
                    cart_x = trees_center_x + 248
                    cart_y = trees_center_y + 200

                    print(
                        f"[BB BOAT] Trees detected at ({trees_center_x}, {trees_center_y}), using elixir cart at ({cart_x}, {cart_y})"
                    )
                    send_discord_debug_log(
                        f"BB boat fallback: trees at ({trees_center_x}, {trees_center_y}), elixir cart at ({cart_x}, {cart_y})"
                    )
                    return (cart_x, cart_y, True)
                else:
                    print(f"[BB BOAT] Trees fallback failed (confidence: {trees_max_val:.2f})")

        send_discord_debug_log("BB boat not detected, trees fallback also failed", "WARNING")
        return None
    except Exception as e:
        print(f"[BB BOAT] Error detecting boat: {e}")
        send_discord_debug_log(f"BB boat detection error: {e}", "ERROR")
        return None


def detect_alt_hotkeys():
    """Detect if alternate hotkeys should be used based on template matching"""
    template_path = "assets/alt_hotkey_template.png"
    region = (522, 1273, 664, 1412)

    try:
        template = cv2.imread(template_path)
        if template is None:
            print(f"[DEBUG] Failed to load template: {template_path}")
            return False

        h, w, _ = template.shape
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Ensure screenshot and template are the same size
        if screenshot_cv.shape[0] == h and screenshot_cv.shape[1] == w:
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= 0.8:
                runtime.gui.log_message("Alternate hotkeys enabled (template matched in region 522,1273,664,1412)")
                runtime.gui.debug_message("USING ALTERNATE HOTKEY SETUP (template matched)")
                print("Alternate hotkeys enabled (template matched in region 522,1273,664,1412)")
                send_discord_debug_log("Alternate hotkeys enabled (template matched)")
                return True
            else:
                runtime.gui.log_message("Default hotkeys enabled (template not matched in region 522,1273,664,1412)")
                runtime.gui.debug_message("USING DEFAULT HOTKEY SETUP (template not matched)")
                print("Default hotkeys enabled (template not matched in region 522,1273,664,1412)")
                send_discord_debug_log("Default hotkeys enabled (template not matched)")
                return False
        else:
            runtime.gui.log_message("Default hotkeys enabled (screenshot/template size mismatch)")
            runtime.gui.debug_message("USING DEFAULT HOTKEY SETUP (screenshot/template size mismatch)")
            print("Default hotkeys enabled (screenshot/template size mismatch)")
            send_discord_debug_log("Default hotkeys enabled (screenshot/template size mismatch)")
            return False

    except Exception as e:
        runtime.gui.log_message(f"Default hotkeys enabled (template matching error: {e})")
        runtime.gui.debug_message(f"USING DEFAULT HOTKEY SETUP (template matching error: {e})")
        print(f"Default hotkeys enabled (template matching error: {e})")
        send_discord_debug_log(f"Default hotkeys enabled (template matching error: {e})", "WARNING")
        return False
