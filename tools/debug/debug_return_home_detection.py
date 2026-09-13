"""
Debug tool for return home button detection issues.
Helps diagnose why template matching confidence is low (0.36-0.37 vs 0.7 threshold).

Usage:
1. Navigate to BB post-battle screen (where return home button is visible)
2. Run this script
3. Review saved debug images and console output
"""

import cv2
import numpy as np
from PIL import ImageGrab
import os
import sys

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

def debug_return_home_detection():
    """Debug return home button detection with multiple matching methods and visualizations."""

    print("=" * 80)
    print("RETURN HOME BUTTON DETECTION DEBUG")
    print("=" * 80)

    # Search region from detect_return_home_button()
    region = (0, 1000, 600, 1440)
    print(f"\n1. Search Region: {region}")
    print(f"   Size: {region[2] - region[0]}x{region[3] - region[1]} pixels")

    # Capture current screen
    print("\n2. Capturing current screen region...")
    screen_img = ImageGrab.grab(bbox=region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)
    print(f"   Screen captured: {screen_cv.shape[1]}x{screen_cv.shape[0]} pixels")

    # Save screen capture
    cv2.imwrite("helperPrograms/debug_screenshots/return_home_screen.png", screen_cv)
    print(f"   ✓ Saved: helperPrograms/debug_screenshots/return_home_screen.png")

    # Load template
    template_dir = "Reference Screenshots/builder_base/"
    template_path = os.path.join(template_dir, "return_home.png")

    print(f"\n3. Loading template: {template_path}")
    if not os.path.exists(template_path):
        print(f"   ✗ ERROR: Template not found!")
        return

    template = cv2.imread(template_path)
    if template is None:
        print(f"   ✗ ERROR: Failed to load template!")
        return

    print(f"   ✓ Template loaded: {template.shape[1]}x{template.shape[0]} pixels")

    # Copy template to debug folder for comparison
    cv2.imwrite("helperPrograms/debug_screenshots/return_home_template.png", template)
    print(f"   ✓ Saved: helperPrograms/debug_screenshots/return_home_template.png")

    # Check if template is larger than search region
    if template.shape[0] > screen_cv.shape[0] or template.shape[1] > screen_cv.shape[1]:
        print(f"\n   ⚠ WARNING: Template is larger than search region!")
        print(f"   Template: {template.shape[1]}x{template.shape[0]}")
        print(f"   Screen:   {screen_cv.shape[1]}x{screen_cv.shape[0]}")
        print(f"   This will cause template matching to fail!")
        return

    # Try multiple template matching methods
    print("\n4. Testing different matching methods:")
    print("-" * 80)

    methods = [
        ('TM_CCOEFF_NORMED', cv2.TM_CCOEFF_NORMED),      # Current method
        ('TM_CCORR_NORMED', cv2.TM_CCORR_NORMED),        # Alternative 1
        ('TM_SQDIFF_NORMED', cv2.TM_SQDIFF_NORMED),      # Alternative 2 (inverted)
    ]

    best_method = None
    best_confidence = 0

    for method_name, method in methods:
        result = cv2.matchTemplate(screen_cv, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_SQDIFF_NORMED, lower is better (invert for comparison)
        if method == cv2.TM_SQDIFF_NORMED:
            confidence = 1 - min_val
            match_loc = min_loc
        else:
            confidence = max_val
            match_loc = max_loc

        print(f"\n   {method_name}:")
        print(f"   Confidence: {confidence:.4f} {'✓ PASS' if confidence >= 0.7 else '✗ FAIL'}")
        print(f"   Location: {match_loc}")

        if confidence > best_confidence:
            best_confidence = confidence
            best_method = (method_name, method, match_loc, result)

    # Use best method for visualization
    if best_method:
        method_name, method, match_loc, result = best_method

        print(f"\n5. Best Method: {method_name} (confidence: {best_confidence:.4f})")

        # Draw rectangle on screen image at match location
        h, w = template.shape[:2]
        top_left = match_loc
        bottom_right = (top_left[0] + w, top_left[1] + h)

        # Create visualization
        screen_with_match = screen_cv.copy()
        color = (0, 255, 0) if best_confidence >= 0.7 else (0, 0, 255)  # Green if pass, red if fail
        cv2.rectangle(screen_with_match, top_left, bottom_right, color, 3)

        # Add confidence text
        text = f"Confidence: {best_confidence:.4f}"
        cv2.putText(screen_with_match, text, (top_left[0], top_left[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Save visualization
        cv2.imwrite("helperPrograms/debug_screenshots/return_home_match.png", screen_with_match)
        print(f"   ✓ Saved: helperPrograms/debug_screenshots/return_home_match.png")

        # Create heatmap of match confidence
        result_display = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        result_color = cv2.applyColorMap(result_display, cv2.COLORMAP_JET)

        cv2.imwrite("helperPrograms/debug_screenshots/return_home_heatmap.png", result_color)
        print(f"   ✓ Saved: helperPrograms/debug_screenshots/return_home_heatmap.png")

    # Provide diagnostic suggestions
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUGGESTIONS:")
    print("=" * 80)

    if best_confidence < 0.5:
        print("\n⚠ CRITICAL: Very low confidence (<0.5)")
        print("   Likely causes:")
        print("   1. Template captured from different screen resolution")
        print("   2. Template includes varying background colors")
        print("   3. Button appearance changed (game update, different state)")
        print("\n   Solutions:")
        print("   - Recapture template at current resolution")
        print("   - Capture only the button icon/text (crop tighter)")
        print("   - Use screenshot_region.py to capture new template")

    elif best_confidence < 0.7:
        print("\n⚠ WARNING: Low confidence (0.5-0.7)")
        print("   Likely causes:")
        print("   1. Template includes some background that varies")
        print("   2. Minor resolution/scaling differences")
        print("   3. Anti-aliasing or compression artifacts")
        print("\n   Solutions:")
        print("   - Try cropping template tighter (less background)")
        print("   - Lower threshold to 0.6 if matches look correct")
        print(f"   - Current best method: {best_method[0] if best_method else 'None'}")

    else:
        print("\n✓ SUCCESS: Good confidence (>0.7)")
        print("   Template matching should work reliably!")

    print("\n" + "=" * 80)
    print("FILES SAVED:")
    print("=" * 80)
    print("1. return_home_screen.png   - Current screen region")
    print("2. return_home_template.png - Your template (for comparison)")
    print("3. return_home_match.png    - Best match location (green=pass, red=fail)")
    print("4. return_home_heatmap.png  - Match confidence heatmap (red=high, blue=low)")
    print("\nReview these images to identify the mismatch!")
    print("=" * 80)


if __name__ == "__main__":
    # Create debug directory if it doesn't exist
    os.makedirs("helperPrograms/debug_screenshots", exist_ok=True)

    print("\nMake sure you're on the BB post-battle screen (return home button visible)!")
    print("Press Enter when ready...")
    input()

    debug_return_home_detection()

    print("\n\nDone! Check helperPrograms/debug_screenshots/ for results.")
