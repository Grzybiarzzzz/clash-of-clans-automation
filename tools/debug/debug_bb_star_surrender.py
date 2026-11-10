"""
BB Gold Star Detection & Surrender Debug Tool

This program ONLY monitors for 2/3 stars and handles surrender accordingly.
You manually handle: searching, deploying troops, returning home.

Usage:
1. Start a BB Gold attack and deploy all troops manually
2. Run this program immediately after deployment
3. Program will monitor for stars and surrender when appropriate
4. Manually click return home after battle ends

This isolates the star detection and surrender logic for testing.
"""

import cv2
import numpy as np
from PIL import ImageGrab
import pytesseract
import time
import os
import sys
import keyboard

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# Configure tesseract
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

def fast_click(x, y):
    """Fast click without humanization (for testing)"""
    import pyautogui
    pyautogui.click(x, y)
    print(f"   Clicked at ({x}, {y})")


def detect_two_stars(verbose=False):
    """Detect 2 stars on screen"""
    try:
        # Bottom-right region (matches main bot)
        region = (1500, 1000, 2560, 1440)
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Path relative to parent directory (since script is in helperPrograms/)
        template_dir = os.path.join("..", "Reference Screenshots", "builder_base")
        template_path = os.path.join(template_dir, "2_stars.png")

        if not os.path.exists(template_path):
            if verbose:
                print(f"\n   ✗ 2-star template not found: {template_path}")
            return False

        template = cv2.imread(template_path)
        if template is None:
            if verbose:
                print(f"\n   ✗ Failed to load 2-star template")
            return False

        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if verbose:
            print(f"\n   2-star confidence: {max_val:.4f} (threshold: 0.7) {'✓' if max_val >= 0.7 else '✗'}")

        return max_val >= 0.7

    except Exception as e:
        print(f"\n   Error detecting 2 stars: {e}")
        return False


def detect_three_stars(verbose=False):
    """Detect 3 stars on screen"""
    try:
        # Bottom-right region (matches main bot)
        region = (1500, 1000, 2560, 1440)
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Path relative to parent directory (since script is in helperPrograms/)
        template_dir = os.path.join("..", "Reference Screenshots", "builder_base")
        template_path = os.path.join(template_dir, "3_stars.png")

        if not os.path.exists(template_path):
            if verbose:
                print(f"\n   ✗ 3-star template not found: {template_path}")
            return False

        template = cv2.imread(template_path)
        if template is None:
            if verbose:
                print(f"\n   ✗ Failed to load 3-star template")
            return False

        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if verbose:
            print(f"\n   3-star confidence: {max_val:.4f} (threshold: 0.7) {'✓' if max_val >= 0.7 else '✗'}")

        return max_val >= 0.7

    except Exception as e:
        print(f"\n   Error detecting 3 stars: {e}")
        return False


def detect_surrender_button():
    """Detect surrender button (appears during battle)"""
    try:
        region = (0, 1000, 600, 1440)
        screen_img = ImageGrab.grab(bbox=region)
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Path relative to parent directory (since script is in helperPrograms/)
        template_dir = os.path.join("..", "Reference Screenshots", "builder_base")
        template_path = os.path.join(template_dir, "surrender.png")

        if not os.path.exists(template_path):
            return None

        template = cv2.imread(template_path)
        if template is None:
            return None

        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2 + region[0]
            center_y = max_loc[1] + template_height // 2 + region[1]
            return (center_x, center_y)

        return None

    except Exception as e:
        print(f"   Error detecting surrender button: {e}")
        return None


def detect_end_battle_button():
    """Detect end battle button (appears when 3 stars achieved)"""
    try:
        region = (0, 1000, 600, 1440)
        screen_img = ImageGrab.grab(bbox=region)
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Path relative to parent directory (since script is in helperPrograms/)
        template_dir = os.path.join("..", "Reference Screenshots", "attack")
        template_path = os.path.join(template_dir, "end_battle.png")

        if not os.path.exists(template_path):
            return None

        template = cv2.imread(template_path)
        if template is None:
            return None

        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2 + region[0]
            center_y = max_loc[1] + template_height // 2 + region[1]
            return (center_x, center_y)

        return None

    except Exception as e:
        print(f"   Error detecting end battle button: {e}")
        return None


def monitor_and_surrender():
    """
    Monitor for 2/3 stars and surrender accordingly.
    Matches the exact logic from BB Gold state machine.
    """
    print("\n" + "=" * 80)
    print("MONITORING FOR STARS")
    print("=" * 80)
    print("Press ESC at any time to abort\n")

    max_wait_time = 180  # 3 minutes maximum
    start_time = time.time()
    stars_detected = 0
    battle_machine_ability_time = time.time()  # Track for re-activation

    print("[MONITOR] Starting star detection loop...")
    print("[MONITOR] Will check for 2 or 3 stars every 0.5 seconds")
    print("[MONITOR] Note: the bot now uses Return Home button detection instead of 80s timeout")
    print("[MONITOR] This debug tool uses 80s timeout for simplicity")
    print()

    check_count = 0

    while (time.time() - start_time) < max_wait_time:
        # Check for ESC to abort
        if keyboard.is_pressed('esc'):
            print("\n[ABORT] ESC pressed - exiting")
            return

        elapsed = time.time() - start_time
        check_count += 1

        # 80-second timeout (battle lost)
        if elapsed >= 80 and stars_detected == 0:
            print(f"\n[TIMEOUT] 80 seconds elapsed without stars - battle lost")
            print("[ACTION] You should manually return home now")
            return

        # Re-activate Battle Machine ability every 15 seconds
        if time.time() - battle_machine_ability_time >= 15:
            print(f"\n[{elapsed:.1f}s] Re-activating Battle Machine ability (Q key)...")
            keyboard.send('q')
            battle_machine_ability_time = time.time()

        # Log each check cycle
        verbose_mode = (check_count % 10 == 1)  # Show details every 10th check
        print(f"[{elapsed:.1f}s] Check #{check_count}: Looking for stars...", end='')

        # Check for 2 stars (with triple verification)
        two_star_checks = sum(1 for _ in range(3) if detect_two_stars(verbose=verbose_mode))
        print(f" 2-star checks: {two_star_checks}/3", end='')

        if two_star_checks >= 2 and stars_detected == 0:  # At least 2 out of 3 checks passed
            stars_detected = 2
            print(f"\n" + "=" * 80)
            print(f"[{elapsed:.1f}s] ★★ 2 STARS DETECTED! (verified {two_star_checks}/3 checks)")
            print("=" * 80)
            print("\n[ACTION] Surrendering immediately...")

            # Click surrender button
            surrender_pos = detect_surrender_button()
            if surrender_pos:
                print(f"[SURRENDER] Clicking surrender button at {surrender_pos}")
                fast_click(*surrender_pos)
            else:
                print(f"[SURRENDER] Surrender button not detected - using fallback position")
                fast_click(144, 1080)

            time.sleep(1.5)

            # Click confirm
            print(f"[SURRENDER] Clicking confirmation button")
            fast_click(1483, 898)
            time.sleep(1.5)

            # Check if 3 stars appeared during surrender (race condition)
            print(f"\n[VERIFY] Checking if 3 stars appeared during surrender...")
            three_star_checks = sum(1 for _ in range(3) if detect_three_stars())

            if three_star_checks >= 2:
                print(f"[RACE CONDITION] 3 stars appeared during surrender! (verified {three_star_checks}/3)")
                print(f"[INFO] Surrender was negated by 3 stars - must click end battle")
                stars_detected = 3

                # Wait for end battle button
                print(f"[WAITING] Waiting for end battle button...")
                end_battle_pos = None
                for _ in range(10):
                    end_battle_pos = detect_end_battle_button()
                    if end_battle_pos:
                        break
                    time.sleep(0.5)

                if end_battle_pos:
                    print(f"[END BATTLE] Clicking end battle button at {end_battle_pos}")
                    fast_click(*end_battle_pos)
                else:
                    print(f"[END BATTLE] Button not detected - using fallback position")
                    fast_click(144, 1080)

                time.sleep(1.5)

                # Click confirm
                print(f"[END BATTLE] Clicking confirmation button")
                fast_click(1483, 898)
                time.sleep(1.5)

            print(f"\n" + "=" * 80)
            print(f"BATTLE ENDED WITH {stars_detected} STARS")
            print("=" * 80)
            print("\n[ACTION] Manually click return home now")
            return

        # Check for 3 stars (rare - Builder Hall destroyed last)
        three_star_checks = sum(1 for _ in range(3) if detect_three_stars(verbose=verbose_mode))
        print(f", 3-star checks: {three_star_checks}/3")

        if three_star_checks >= 2 and stars_detected == 0:
            stars_detected = 3
            print(f"\n" + "=" * 80)
            print(f"[{elapsed:.1f}s] ★★★ 3 STARS DETECTED! (verified {three_star_checks}/3 checks)")
            print("=" * 80)
            print("\n[INFO] Builder Hall was destroyed last")
            print("[ACTION] Waiting 7 seconds before ending battle...")

            time.sleep(7)

            # Click end battle button
            end_battle_pos = detect_end_battle_button()
            if end_battle_pos:
                print(f"[END BATTLE] Clicking end battle button at {end_battle_pos}")
                fast_click(*end_battle_pos)
            else:
                print(f"[END BATTLE] Button not detected - using fallback position")
                fast_click(144, 1080)

            time.sleep(1.5)

            # Click confirm
            print(f"[END BATTLE] Clicking confirmation button")
            fast_click(1483, 898)
            time.sleep(1.5)

            print(f"\n" + "=" * 80)
            print(f"BATTLE ENDED WITH 3 STARS")
            print("=" * 80)
            print("\n[ACTION] Manually click return home now")
            return

        time.sleep(0.5)

    # Max wait time exceeded (3 minutes)
    print(f"\n\n[TIMEOUT] Maximum wait time ({max_wait_time}s) exceeded")
    print("[WARNING] 2/3 stars not detected - ending battle anyway")
    print("[ACTION] Manually return home now")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("BB GOLD STAR DETECTION & SURRENDER DEBUG TOOL")
    print("=" * 80)
    print("\nThis program ONLY handles star detection and surrender.")
    print("You must manually:")
    print("  1. Start a BB Gold attack")
    print("  2. Deploy all troops (Battle Machine + Night Witches)")
    print("  3. Run this program immediately after deployment")
    print("  4. This program will monitor and surrender automatically")
    print("  5. Manually click return home when done")
    print("\n" + "=" * 80)

    print("\nReady to start monitoring?")
    print("Make sure you've deployed troops and battle is active!")
    print("Press Enter to begin monitoring (or Ctrl+C to cancel)...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)

    monitor_and_surrender()

    print("\n\nDebug session complete.")
    print("Check the console output above for the exact sequence of events.")
