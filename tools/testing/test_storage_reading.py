# test_storage_reading.py
"""
Simple test script for storage reading functions.
Press F2 to test main base storage reading.
Press F3 to test builder base storage reading.
Press ESC to exit.
"""

import sys
import os

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import keyboard
import time
import config
from PIL import ImageGrab
import pytesseract
import numpy as np
import cv2

# Set tesseract path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

# Default max storage values (can be adjusted)
MAX_GOLD_STORAGE = 18000000
MAX_ELIXIR_STORAGE = 14000000
MAX_DARK_ELIXIR_STORAGE = 240000


def ocr_attack_resource_template_digits(img, debug=False, context='base_screen'):
    """
    OCR for resource numbers using digit template matching.
    Loads digit templates from Reference Screenshots/digits/ based on context.
    """
    try:
        # Require context to be specified
        if context is None:
            raise ValueError("Context must be specified")

        # 1. Load & binarize templates for the specific context
        templates = {}
        digits_dir = os.path.join('Reference Screenshots', 'digits', context)
        if not os.path.exists(digits_dir):
            if debug:
                print(f"[Template OCR] Context directory not found: {digits_dir}")
            # Fallback to base context if specific context not found
            digits_dir = os.path.join('Reference Screenshots', 'digits', 'base_screen')
            if not os.path.exists(digits_dir):
                if debug:
                    print(f"[Template OCR] Fallback directory not found: {digits_dir}")
                return 0

        for digit in range(10):
            tpl_path = os.path.join(digits_dir, f'{digit}.png')
            tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                if debug:
                    print(f"[Template OCR] Cannot load template: {tpl_path}")
                continue
            _, tpl_bin = cv2.threshold(
                tpl, 0, 255,
                cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
            )
            templates[digit] = tpl_bin

        if not templates:
            if debug:
                print(f"[Template OCR] No templates loaded for context: {context}")
            return 0

        # 2. Convert input PIL image to OpenCV BGR, then gray + binary-invert
        img_np = np.array(img.convert('RGB'))
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
        )

        # 3. Template matching for each digit
        detections = []
        # Lower threshold for base resources
        if context in ('base_screen', 'base_dark_elixir'):
            match_threshold = 0.65
        else:
            match_threshold = 0.7

        for digit, tpl in templates.items():
            result = cv2.matchTemplate(thresh, tpl, cv2.TM_CCOEFF_NORMED)
            locs = np.where(result >= match_threshold)

            for pt in zip(*locs[::-1]):
                x, y = pt
                h, w = tpl.shape
                detections.append({
                    'digit': digit,
                    'x': x,
                    'confidence': result[y, x]
                })

        if not detections:
            if debug:
                print("[Template OCR] No digits detected")
            return 0

        # 4. Sort by x position (left to right) and build number
        detections.sort(key=lambda d: d['x'])

        # Remove duplicates (same digit detected multiple times in close proximity)
        filtered = []
        for det in detections:
            if not filtered or det['x'] - filtered[-1]['x'] > 10:
                filtered.append(det)

        # Build the number string
        number_str = ''.join(str(d['digit']) for d in filtered)

        if debug:
            print(f"[Template OCR] Detected: {number_str}")

        return int(number_str) if number_str else 0

    except Exception as e:
        if debug:
            print(f"[Template OCR] Error: {e}")
        return 0


def read_own_base_storages():
    """
    Read own base storage percentages.
    """
    result = {
        'gold_percent': 0,
        'elixir_percent': 0,
        'de_percent': 0,
        'gold_absolute': 0,
        'elixir_absolute': 0,
        'de_absolute': 0,
        'success': False
    }

    try:
        # Read absolute storage values (with debug=True to see what's happening)
        base_gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
        print("  Reading gold...")
        gold_absolute = ocr_attack_resource_template_digits(base_gold_img, debug=True, context='base_screen')

        base_elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
        print("  Reading elixir...")
        elixir_absolute = ocr_attack_resource_template_digits(base_elixir_img, debug=True, context='base_screen')

        de_absolute = 0
        if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
            base_dark_elixir_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
            print("  Reading dark elixir...")
            de_absolute = ocr_attack_resource_template_digits(base_dark_elixir_img, debug=True, context='base_dark_elixir')

        # Calculate percentages
        gold_percent = min(100, int((gold_absolute / MAX_GOLD_STORAGE) * 100)) if MAX_GOLD_STORAGE > 0 else 0
        elixir_percent = min(100, int((elixir_absolute / MAX_ELIXIR_STORAGE) * 100)) if MAX_ELIXIR_STORAGE > 0 else 0
        de_percent = min(100, int((de_absolute / MAX_DARK_ELIXIR_STORAGE) * 100)) if MAX_DARK_ELIXIR_STORAGE > 0 else 0

        # Update result
        result['gold_absolute'] = gold_absolute
        result['elixir_absolute'] = elixir_absolute
        result['de_absolute'] = de_absolute
        result['gold_percent'] = gold_percent
        result['elixir_percent'] = elixir_percent
        result['de_percent'] = de_percent
        result['success'] = True

        return result

    except Exception as e:
        print(f"ERROR reading storages: {e}")
        import traceback
        traceback.print_exc()
        return result


def read_bb_storages():
    """
    Read Builder Base storage percentages.
    """
    result = {
        'gold_percent': 0,
        'elixir_percent': 0,
        'gold_absolute': 0,
        'elixir_absolute': 0,
        'success': False
    }

    try:
        # Check if BB storage regions are defined
        if not hasattr(config, 'BB_BASE_GOLD_REGION') or not hasattr(config, 'BB_BASE_ELIXIR_REGION'):
            print("BB storage regions not defined in config.py")
            return result

        # Read absolute storage values
        bb_gold_img = ImageGrab.grab(bbox=config.BB_BASE_GOLD_REGION)
        gold_absolute = ocr_attack_resource_template_digits(bb_gold_img, context='bb_base_screen')

        bb_elixir_img = ImageGrab.grab(bbox=config.BB_BASE_ELIXIR_REGION)
        elixir_absolute = ocr_attack_resource_template_digits(bb_elixir_img, context='bb_base_screen')

        # BB max storage values (BH10)
        max_bb_gold = 5000000
        max_bb_elixir = 5000000

        # Calculate percentages
        gold_percent = min(100, int((gold_absolute / max_bb_gold) * 100)) if max_bb_gold > 0 else 0
        elixir_percent = min(100, int((elixir_absolute / max_bb_elixir) * 100)) if max_bb_elixir > 0 else 0

        # Update result
        result['gold_absolute'] = gold_absolute
        result['elixir_absolute'] = elixir_absolute
        result['gold_percent'] = gold_percent
        result['elixir_percent'] = elixir_percent
        result['success'] = True

        return result

    except Exception as e:
        print(f"ERROR reading BB storages: {e}")
        import traceback
        traceback.print_exc()
        return result


def test_main_base_storages():
    """Test main base storage reading"""
    print("\n" + "="*70)
    print("TESTING MAIN BASE STORAGE READING")
    print("="*70)
    print("Make sure you are at your Main Base home screen!")
    print("Reading storages in 2 seconds...")
    time.sleep(2)

    print("\nCapturing regions:")
    print(f"  Gold Region: {config.BASE_GOLD_REGION}")
    print(f"  Elixir Region: {config.BASE_ELIXIR_REGION}")
    print(f"  DE Region: {config.BASE_DARK_ELIXIR_REGION}")

    result = read_own_base_storages()

    print("\n--- RESULTS ---")
    print(f"Success: {result['success']}")

    if result['success']:
        print(f"\nGold:")
        print(f"  Absolute: {result['gold_absolute']:,}")
        print(f"  Percentage: {result['gold_percent']}%")

        print(f"\nElixir:")
        print(f"  Absolute: {result['elixir_absolute']:,}")
        print(f"  Percentage: {result['elixir_percent']}%")

        print(f"\nDark Elixir:")
        print(f"  Absolute: {result['de_absolute']:,}")
        print(f"  Percentage: {result['de_percent']}%")

        print("\n--- SETTINGS ---")
        print(f"Max Gold Storage: {MAX_GOLD_STORAGE:,}")
        print(f"Max Elixir Storage: {MAX_ELIXIR_STORAGE:,}")
        print(f"Max Dark Elixir Storage: {MAX_DARK_ELIXIR_STORAGE:,}")

        print("\n--- STORAGE STATUS ---")
        if result['gold_percent'] >= 100:
            print("✓ Gold storage is FULL")
        elif result['gold_percent'] >= 90:
            print(f"⚠ Gold storage is {result['gold_percent']}% full (almost full)")
        else:
            print(f"○ Gold storage is {result['gold_percent']}% full")

        if result['elixir_percent'] >= 100:
            print("✓ Elixir storage is FULL")
        elif result['elixir_percent'] >= 90:
            print(f"⚠ Elixir storage is {result['elixir_percent']}% full (almost full)")
        else:
            print(f"○ Elixir storage is {result['elixir_percent']}% full")

        if result['de_percent'] >= 100:
            print("✓ Dark Elixir storage is FULL")
        elif result['de_percent'] >= 90:
            print(f"⚠ Dark Elixir storage is {result['de_percent']}% full (almost full)")
        else:
            print(f"○ Dark Elixir storage is {result['de_percent']}% full")

        print("\n--- QUEUE SYSTEM CHECK ---")
        if result['gold_percent'] >= 100 and result['elixir_percent'] >= 100:
            print("✓ Main base storages ready - Queue would switch to BB")
        else:
            print(f"○ Queue would continue farming (need gold={100-result['gold_percent']}%, elixir={100-result['elixir_percent']}%)")

    else:
        print("❌ ERROR: Storage reading failed!")
        print("Possible issues:")
        print("1. Not at main base home screen")
        print("2. Storage regions miscalibrated")
        print("3. OCR failed to read values")

    print("="*70 + "\n")


def test_bb_storages():
    """Test builder base storage reading"""
    print("\n" + "="*70)
    print("TESTING BUILDER BASE STORAGE READING")
    print("="*70)
    print("Make sure you are at your Builder Base home screen!")
    print("Reading storages in 2 seconds...")
    time.sleep(2)

    # Check if BB regions are configured
    if not hasattr(config, 'BB_BASE_GOLD_REGION') or not hasattr(config, 'BB_BASE_ELIXIR_REGION'):
        print("\n⚠ WARNING: BB storage regions not defined in config.py!")
        print("\nTo calibrate BB storage regions:")
        print("1. Switch to Builder Base in game")
        print("2. Run: python helperPrograms/screenshot_region.py")
        print("3. Capture gold and elixir storage regions")
        print("4. Update BB_BASE_GOLD_REGION and BB_BASE_ELIXIR_REGION in config.py")
        print("="*70 + "\n")
        return

    print("\nCapturing regions:")
    print(f"  BB Gold Region: {config.BB_BASE_GOLD_REGION}")
    print(f"  BB Elixir Region: {config.BB_BASE_ELIXIR_REGION}")

    result = read_bb_storages()

    print("\n--- RESULTS ---")
    print(f"Success: {result['success']}")

    if result['success']:
        print(f"\nGold:")
        print(f"  Absolute: {result['gold_absolute']:,}")
        print(f"  Percentage: {result['gold_percent']}%")

        print(f"\nElixir:")
        print(f"  Absolute: {result['elixir_absolute']:,}")
        print(f"  Percentage: {result['elixir_percent']}%")

        print("\n--- SETTINGS ---")
        print(f"Max BB Gold Storage: 5,000,000 (BH10)")
        print(f"Max BB Elixir Storage: 5,000,000 (BH10)")

        print("\n--- STORAGE STATUS ---")
        if result['gold_percent'] >= 100:
            print("✓ BB Gold storage is FULL")
        elif result['gold_percent'] >= 90:
            print(f"⚠ BB Gold storage is {result['gold_percent']}% full (almost full)")
        else:
            print(f"○ BB Gold storage is {result['gold_percent']}% full")

        if result['elixir_percent'] >= 100:
            print("✓ BB Elixir storage is FULL")
        elif result['elixir_percent'] >= 90:
            print(f"⚠ BB Elixir storage is {result['elixir_percent']}% full (almost full)")
        else:
            print(f"○ BB Elixir storage is {result['elixir_percent']}% full")

        print("\n--- QUEUE SYSTEM CHECK ---")
        if result['gold_percent'] >= 100 and result['elixir_percent'] >= 100:
            print("✓ BB storages ready - Queue would complete or run Achievement Farm")
        else:
            print(f"○ Queue would continue BB farming (need gold={100-result['gold_percent']}%, elixir={100-result['elixir_percent']}%)")

    else:
        print("❌ ERROR: BB storage reading failed!")
        print("\nPossible issues:")
        print("1. Not at Builder Base home screen")
        print("2. BB storage regions not calibrated correctly")
        print("3. OCR failed to read values")

    print("="*70 + "\n")


def main():
    """Main test loop"""
    print("\n" + "="*70)
    print("STORAGE READING TEST SCRIPT")
    print("="*70)
    print("\nMax Storage Settings:")
    print(f"  Gold: {MAX_GOLD_STORAGE:,}")
    print(f"  Elixir: {MAX_ELIXIR_STORAGE:,}")
    print(f"  Dark Elixir: {MAX_DARK_ELIXIR_STORAGE:,}")
    print("\nControls:")
    print("  F2 - Test Main Base storage reading")
    print("  F3 - Test Builder Base storage reading")
    print("  ESC - Exit")
    print("\nInstructions:")
    print("1. Open Clash of Clans and go to your main base")
    print("2. Make sure storage bars are visible on screen")
    print("3. Press F2 to test main base storage reading")
    print("4. Switch to Builder Base (click boat)")
    print("5. Press F3 to test BB storage reading")
    print("="*70 + "\n")

    print("Waiting for input...\n")

    # Set up keyboard hooks
    keyboard.add_hotkey('f2', test_main_base_storages)
    keyboard.add_hotkey('f3', test_bb_storages)

    # Wait for ESC to exit
    keyboard.wait('esc')

    print("\nExiting test script...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        keyboard.unhook_all()
        print("Keyboard hooks cleaned up.")
