# debug_storage_regions.py
"""
Debug script to visualize what's being captured in storage regions.
This helps identify if regions are correctly positioned.
"""

import sys
import os
# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import keyboard
import time
import config
from PIL import ImageGrab
import datetime

def save_region_screenshot(region, name):
    """Capture and save a region screenshot"""
    # Create debug_screenshots folder if it doesn't exist
    debug_dir = "debug_screenshots"
    if not os.path.exists(debug_dir):
        os.makedirs(debug_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(debug_dir, f"debug_{name}_{timestamp}.png")

    img = ImageGrab.grab(bbox=region)
    img.save(filename)

    print(f"Saved: {filename}")
    print(f"  Region: {region}")
    print(f"  Size: {img.size}")

    return filename

def test_main_base_regions():
    """Capture main base storage regions"""
    print("\n" + "="*70)
    print("CAPTURING MAIN BASE STORAGE REGIONS")
    print("="*70)
    print("Make sure you are at your Main Base home screen!")
    print("Capturing in 2 seconds...")
    time.sleep(2)

    print("\nCapturing regions...")

    gold_file = save_region_screenshot(config.BASE_GOLD_REGION, "main_gold")
    elixir_file = save_region_screenshot(config.BASE_ELIXIR_REGION, "main_elixir")
    de_file = save_region_screenshot(config.BASE_DARK_ELIXIR_REGION, "main_de")

    print("\n" + "="*70)
    print("SCREENSHOTS SAVED!")
    print("="*70)
    print("\nPlease check the saved images:")
    print(f"  - {gold_file}")
    print(f"  - {elixir_file}")
    print(f"  - {de_file}")
    print("\nWhat to look for:")
    print("  ✓ Image should contain ONLY the resource number")
    print("  ✓ Should be clear and readable")
    print("  ✓ Should NOT include icons, bars, or other UI elements")
    print("\nIf images look wrong:")
    print("  1. Run: python helperPrograms/screenshot_region.py")
    print("  2. Recapture the correct regions")
    print("  3. Update BASE_GOLD_REGION, BASE_ELIXIR_REGION, BASE_DARK_ELIXIR_REGION in config.py")
    print("="*70 + "\n")

def test_bb_regions():
    """Capture BB storage regions"""
    print("\n" + "="*70)
    print("CAPTURING BUILDER BASE STORAGE REGIONS")
    print("="*70)

    if not hasattr(config, 'BB_BASE_GOLD_REGION') or not hasattr(config, 'BB_BASE_ELIXIR_REGION'):
        print("\n⚠ WARNING: BB storage regions not defined in config.py!")
        print("Please add BB_BASE_GOLD_REGION and BB_BASE_ELIXIR_REGION to config.py first.")
        print("="*70 + "\n")
        return

    print("Make sure you are at your Builder Base home screen!")
    print("Capturing in 2 seconds...")
    time.sleep(2)

    print("\nCapturing regions...")

    gold_file = save_region_screenshot(config.BB_BASE_GOLD_REGION, "bb_gold")
    elixir_file = save_region_screenshot(config.BB_BASE_ELIXIR_REGION, "bb_elixir")

    print("\n" + "="*70)
    print("SCREENSHOTS SAVED!")
    print("="*70)
    print("\nPlease check the saved images:")
    print(f"  - {gold_file}")
    print(f"  - {elixir_file}")
    print("\nWhat to look for:")
    print("  ✓ Image should contain ONLY the resource number")
    print("  ✓ Should be clear and readable")
    print("  ✓ Should NOT include icons, bars, or other UI elements")
    print("\nIf images look wrong:")
    print("  1. Run: python helperPrograms/screenshot_region.py")
    print("  2. Capture the correct BB storage regions")
    print("  3. Update BB_BASE_GOLD_REGION and BB_BASE_ELIXIR_REGION in config.py")
    print("="*70 + "\n")

def main():
    """Main debug loop"""
    print("\n" + "="*70)
    print("STORAGE REGION DEBUG SCRIPT")
    print("="*70)
    print("\nThis script captures what your storage regions are seeing.")
    print("It will save PNG images so you can visually verify the regions.")
    print("\nControls:")
    print("  F2 - Capture Main Base storage regions")
    print("  F3 - Capture Builder Base storage regions")
    print("  ESC - Exit")
    print("\nInstructions:")
    print("1. Open Clash of Clans and go to your base")
    print("2. Press F2 to capture what the bot sees")
    print("3. Check the saved images")
    print("4. If wrong, recalibrate regions using screenshot_region.py")
    print("="*70 + "\n")

    print("Waiting for input...\n")

    # Set up keyboard hooks
    keyboard.add_hotkey('f2', test_main_base_regions)
    keyboard.add_hotkey('f3', test_bb_regions)

    # Wait for ESC to exit
    keyboard.wait('esc')

    print("\nExiting debug script...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        keyboard.unhook_all()
        print("Keyboard hooks cleaned up.")
