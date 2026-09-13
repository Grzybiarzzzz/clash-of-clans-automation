"""
Visual debug tool for star detection - saves screenshots to analyze why confidence is low.

This will capture:
1. The current screen region where stars should be
2. The templates being used
3. Heatmaps showing match confidence
4. Side-by-side comparison

Run this during a battle when 2 stars are visible.
"""

import cv2
import numpy as np
from PIL import ImageGrab
import os
import time

def debug_star_detection():
    """Capture and analyze star detection with visual output"""

    print("\n" + "=" * 80)
    print("VISUAL STAR DETECTION DEBUG")
    print("=" * 80)
    print("\nMake sure 2 stars are visible on screen right now!")
    print("Press Enter when ready...")
    input()

    # Create debug directory
    os.makedirs("helperPrograms/debug_screenshots", exist_ok=True)

    # Region where stars should appear (bottom-right, matches main bot)
    region = (1500, 1000, 2560, 1440)
    print(f"\n1. Capturing star region: {region}")
    print(f"   Size: {region[2]-region[0]}x{region[3]-region[1]} pixels")

    # Capture current screen
    screenshot = ImageGrab.grab(bbox=region)
    screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Save captured region
    cv2.imwrite("helperPrograms/debug_screenshots/stars_screen_capture.png", screenshot_cv)
    print(f"   ✓ Saved: stars_screen_capture.png ({screenshot_cv.shape[1]}x{screenshot_cv.shape[0]})")

    # Load templates
    template_2_path = os.path.join("..", "Reference Screenshots", "builder_base", "2_stars.png")
    template_3_path = os.path.join("..", "Reference Screenshots", "builder_base", "3_stars.png")

    print(f"\n2. Loading templates:")

    # Test 2-star template
    if os.path.exists(template_2_path):
        template_2 = cv2.imread(template_2_path)
        cv2.imwrite("helperPrograms/debug_screenshots/template_2_stars.png", template_2)
        print(f"   ✓ 2-star template: {template_2.shape[1]}x{template_2.shape[0]} pixels")

        # Check if template fits in search region
        if template_2.shape[0] > screenshot_cv.shape[0] or template_2.shape[1] > screenshot_cv.shape[1]:
            print(f"   ⚠ WARNING: 2-star template is LARGER than search region!")
            print(f"     Template: {template_2.shape[1]}x{template_2.shape[0]}")
            print(f"     Region:   {screenshot_cv.shape[1]}x{screenshot_cv.shape[0]}")

        # Perform template matching with multiple methods
        print(f"\n3. Testing 2-star detection with multiple methods:")

        methods = [
            ('TM_CCOEFF_NORMED', cv2.TM_CCOEFF_NORMED),
            ('TM_CCORR_NORMED', cv2.TM_CCORR_NORMED),
            ('TM_SQDIFF_NORMED', cv2.TM_SQDIFF_NORMED),
        ]

        best_confidence = 0
        best_method_name = None
        best_result = None

        for method_name, method in methods:
            try:
                result = cv2.matchTemplate(screenshot_cv, template_2, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                # For SQDIFF, lower is better (invert)
                if method == cv2.TM_SQDIFF_NORMED:
                    confidence = 1 - min_val
                    match_loc = min_loc
                else:
                    confidence = max_val
                    match_loc = max_loc

                status = "✓ PASS" if confidence >= 0.7 else "✗ FAIL"
                print(f"   {method_name}: {confidence:.4f} {status}")

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_method_name = method_name
                    best_result = (result, match_loc, method)

            except Exception as e:
                print(f"   {method_name}: ERROR - {e}")

        if best_result:
            result, match_loc, method = best_result

            # Create visualization with rectangle
            screen_with_box = screenshot_cv.copy()
            h, w = template_2.shape[:2]
            top_left = match_loc
            bottom_right = (top_left[0] + w, top_left[1] + h)

            color = (0, 255, 0) if best_confidence >= 0.7 else (0, 0, 255)
            cv2.rectangle(screen_with_box, top_left, bottom_right, color, 3)

            # Add confidence text
            text = f"{best_method_name}: {best_confidence:.4f}"
            cv2.putText(screen_with_box, text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.imwrite("helperPrograms/debug_screenshots/stars_detection_result.png", screen_with_box)
            print(f"\n   ✓ Best method: {best_method_name} with confidence {best_confidence:.4f}")
            print(f"   ✓ Saved: stars_detection_result.png")

            # Create heatmap
            result_normalized = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            heatmap = cv2.applyColorMap(result_normalized, cv2.COLORMAP_JET)
            cv2.imwrite("helperPrograms/debug_screenshots/stars_heatmap.png", heatmap)
            print(f"   ✓ Saved: stars_heatmap.png")

    else:
        print(f"   ✗ 2-star template not found at: {template_2_path}")

    # Test 3-star template
    if os.path.exists(template_3_path):
        template_3 = cv2.imread(template_3_path)
        cv2.imwrite("helperPrograms/debug_screenshots/template_3_stars.png", template_3)
        print(f"\n4. Testing 3-star template:")
        print(f"   Template size: {template_3.shape[1]}x{template_3.shape[0]} pixels")

        result = cv2.matchTemplate(screenshot_cv, template_3, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        status = "✓ PASS" if max_val >= 0.7 else "✗ FAIL"
        print(f"   Confidence: {max_val:.4f} {status}")

    # Diagnostic analysis
    print("\n" + "=" * 80)
    print("DIAGNOSTIC ANALYSIS")
    print("=" * 80)

    if best_confidence < 0.3:
        print("\n⚠ CRITICAL: Very low confidence (<0.3)")
        print("\nMost likely causes:")
        print("  1. Stars appear in DIFFERENT LOCATION than search region")
        print("  2. Template is from MAIN VILLAGE, not Builder Base")
        print("  3. Template captured at different RESOLUTION")
        print("\nSolutions:")
        print("  - Check stars_screen_capture.png - are stars visible?")
        print("  - Recapture template at current resolution from BB battle")
        print("  - Try different search region (stars might be elsewhere)")

    elif best_confidence < 0.5:
        print("\n⚠ WARNING: Low confidence (0.3-0.5)")
        print("\nMost likely causes:")
        print("  1. Template includes VARYING BACKGROUND")
        print("  2. Stars are ANIMATING (template captured at different frame)")
        print("  3. Minor resolution/scaling differences")
        print("\nSolutions:")
        print("  - Crop template tighter (only the stars, no background)")
        print("  - Capture template when stars are fully visible (not fading)")
        print("  - Use helperPrograms/screenshot_region.py to recapture")

    elif best_confidence < 0.7:
        print("\n⚠ CLOSE: Moderate confidence (0.5-0.7)")
        print("\nMost likely causes:")
        print("  1. Small compression artifacts or anti-aliasing differences")
        print("  2. Template slightly too large (includes some background)")
        print("\nSolutions:")
        print("  - Lower threshold to 0.6 if visual match looks correct")
        print("  - Recapture template more tightly cropped")
        print(f"  - Try {best_method_name} method in main code")

    else:
        print("\n✓ SUCCESS: Good confidence (>0.7)")
        print("  Template matching should work reliably!")

    # Region verification
    print("\n" + "=" * 80)
    print("REGION VERIFICATION")
    print("=" * 80)
    print("\nCheck these files to verify:")
    print("1. stars_screen_capture.png - Shows what bot sees")
    print("2. template_2_stars.png - Shows template being matched")
    print("3. stars_detection_result.png - Shows where match was found (green=pass, red=fail)")
    print("4. stars_heatmap.png - Shows match confidence across region (red=high, blue=low)")
    print("\nIf stars are NOT visible in stars_screen_capture.png:")
    print("  → Search region (1500, 1000, 2560, 1440) is WRONG")
    print("  → Use helperPrograms/screenshot_region.py to find correct coordinates")
    print("\nIf stars ARE visible but confidence is low:")
    print("  → Template doesn't match (wrong resolution, different appearance, etc.)")
    print("  → Recapture template using screenshot_region.py at region (1500, 1000, 2560, 1440)")
    print("=" * 80)


if __name__ == "__main__":
    print("\nThis tool will capture the star region and analyze template matching.")
    print("Make sure you're in a BB battle with 2 stars visible on screen!")
    print("\nFiles will be saved to: helperPrograms/debug_screenshots/")

    try:
        debug_star_detection()
        print("\n✓ Debug complete! Check the saved images in helperPrograms/debug_screenshots/")
    except Exception as e:
        print(f"\n✗ Error during debug: {e}")
        import traceback
        traceback.print_exc()
