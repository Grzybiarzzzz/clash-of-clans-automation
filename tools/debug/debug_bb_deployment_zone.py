"""
Debug tool for visualizing Builder Base deployment zone detection.
Uses contour-tracing approach for Baby Dragon deployment (close to red boundaries).

Press F3 while in a BB battle to capture and analyze the deployment zone.
Press ESC to exit.

Saves annotated screenshot showing:
- Red mask overlay (detected red boundary lines)
- Cyan contour lines (traced deployment boundary)
- Green dots (valid deployment coordinates following the boundary)
- Red overlays (filtered areas: unit bar, surrender button)

This tool generates coordinates that follow alongside the red boundary,
suitable for troops like Baby Dragons that need close-to-boundary placement.
"""

import keyboard
from PIL import ImageGrab
import cv2
import numpy as np
import os
from datetime import datetime


# Constants from main.py detect_bb_deployment_zone() and filter_out_unit_bar()
SCREEN_REGION = (200, 100, 2360, 1200)

# HSV red color ranges for deployment boundary detection
# Widened ranges to catch more red variations (lighting, shadows, base skins)
LOWER_RED1 = np.array([0, 70, 80])
UPPER_RED1 = np.array([12, 255, 255])
LOWER_RED2 = np.array([158, 70, 80])
UPPER_RED2 = np.array([180, 255, 255])

# Filter regions (in screen coordinates)
UNIT_BAR_X1 = 1
UNIT_BAR_Y1 = 1209
UNIT_BAR_X2 = 2553
UNIT_BAR_Y2 = 1431

SURRENDER_BTN_X1 = 4
SURRENDER_BTN_Y1 = 1006
SURRENDER_BTN_X2 = 301
SURRENDER_BTN_Y2 = 1151

# Output directory
OUTPUT_DIR = "tools/debug/screenshots"

# Baby Dragon deployment settings
BOUNDARY_OFFSET = 25  # pixels to offset from red line (into deployable area)
SAMPLE_INTERVAL = 50  # pixels between sampled points along contour


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def detect_deployment_zone(screenshot_cv):
    """
    Detect Builder Base deployment zone using red boundary detection.
    Returns: (valid_coords, contours, red_mask)
    """
    # Convert to HSV
    screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

    # Create masks for red color
    mask1 = cv2.inRange(screenshot_hsv, LOWER_RED1, UPPER_RED1)
    mask2 = cv2.inRange(screenshot_hsv, LOWER_RED2, UPPER_RED2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Dilate to connect fragmented contours
    kernel = np.ones((5, 5), np.uint8)
    dilated_mask = cv2.dilate(red_mask, kernel, iterations=2)

    # Find contours of red lines
    contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        print("[DEBUG] No red deployment lines detected")
        return [], [], red_mask

    # Calculate base center for reference
    height, width = screenshot_cv.shape[:2]
    base_center_x = width // 2
    base_center_y = height // 2

    print(f"[DEBUG] Found {len(contours)} contours")

    # Filter contours by SHAPE - deployment boundary is a thin LINE
    # while buildings/decorations are blob-shaped
    # Use circularity: 4*pi*area/perimeter^2 (1.0 = circle, low = line-like)

    line_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        if perimeter == 0 or area < 100:  # Skip tiny contours
            continue

        # Circularity: 1.0 = perfect circle, lower = more line-like
        circularity = 4 * np.pi * area / (perimeter * perimeter)

        # Boundary lines have LOW circularity (< 0.15)
        # Buildings/blobs have HIGH circularity (> 0.3)
        if circularity < 0.15:
            line_contours.append((area, perimeter, circularity, contour))
            print(f"[DEBUG] LINE contour: area={area:.0f}, perim={perimeter:.0f}, circ={circularity:.3f}")
        else:
            print(f"[DEBUG] BLOB contour (rejected): area={area:.0f}, perim={perimeter:.0f}, circ={circularity:.3f}")

    if not line_contours:
        print("[DEBUG] No line-like contours found, falling back to largest")
        # Fallback: use largest contour
        contours_with_area = [(cv2.contourArea(c), c) for c in contours]
        contours_with_area.sort(reverse=True, key=lambda x: x[0])
        if contours_with_area:
            line_contours = [(contours_with_area[0][0], 0, 0, contours_with_area[0][1])]

    print(f"[DEBUG] Kept {len(line_contours)} line-like contours")

    # Use CONVEX HULL on line-like contours only
    # Combine points from line contours
    all_points = np.vstack([c[3] for c in line_contours])

    # Compute convex hull
    hull = cv2.convexHull(all_points)

    # Approximate the hull to reduce points while maintaining shape
    epsilon = 0.01 * cv2.arcLength(hull, True)
    hull_approx = cv2.approxPolyDP(hull, epsilon, True)

    contours = [hull_approx]
    print(f"[DEBUG] Using convex hull with {len(hull_approx)} vertices")
    print(f"[DEBUG] Base center: ({base_center_x}, {base_center_y})")

    # Sample points along contours and offset outward
    valid_coords = []

    for contour in contours:
        # Calculate contour perimeter to determine sampling count
        perimeter = cv2.arcLength(contour, closed=True)
        num_samples = max(int(perimeter / SAMPLE_INTERVAL), 3)

        print(f"[DEBUG] Contour perimeter: {perimeter:.1f}px, sampling {num_samples} points")

        # Sample points evenly along contour
        for i in range(num_samples):
            # Index along contour
            idx = int(i * len(contour) / num_samples)
            point = contour[idx][0]  # Extract [x, y] from [[x, y]]

            # Vector from base center to contour point
            dx = point[0] - base_center_x
            dy = point[1] - base_center_y

            # Normalize and scale by offset distance
            length = np.sqrt(dx * dx + dy * dy)
            if length > 0:
                offset_x = int(point[0] + (dx / length) * BOUNDARY_OFFSET)
                offset_y = int(point[1] + (dy / length) * BOUNDARY_OFFSET)

                # Convert to screen coordinates
                screen_x = offset_x + SCREEN_REGION[0]
                screen_y = offset_y + SCREEN_REGION[1]

                valid_coords.append((screen_x, screen_y))

    print(f"[DEBUG] Generated {len(valid_coords)} valid deployment coordinates")

    # Final filter: remove any coordinates that fall INSIDE the red boundary
    # (inside the no-deploy zone)
    # Dilate the red mask to create a "no-go" zone
    no_go_zone = cv2.dilate(red_mask, np.ones((15, 15), np.uint8), iterations=1)

    final_coords = []
    removed_count = 0
    for screen_x, screen_y in valid_coords:
        # Convert to region-relative coordinates
        region_x = screen_x - SCREEN_REGION[0]
        region_y = screen_y - SCREEN_REGION[1]

        # Check bounds
        if 0 <= region_x < no_go_zone.shape[1] and 0 <= region_y < no_go_zone.shape[0]:
            # If pixel is white in no-go zone, it's inside the boundary (invalid)
            if no_go_zone[region_y, region_x] > 0:
                removed_count += 1
                continue

        final_coords.append((screen_x, screen_y))

    if removed_count > 0:
        print(f"[DEBUG] Removed {removed_count} coords inside red boundary")

    print(f"[DEBUG] Final valid coordinates: {len(final_coords)}")

    return final_coords, contours, red_mask


def filter_coordinates(coordinates):
    """
    Filter out coordinates that fall within unit bar or surrender button areas.
    Returns: (filtered_coords, excluded_unit_bar, excluded_surrender)
    """
    filtered_coords = []
    excluded_unit_bar = []
    excluded_surrender = []

    for x, y in coordinates:
        # Check if coordinate is within unit bar bounds
        if UNIT_BAR_X1 <= x <= UNIT_BAR_X2 and UNIT_BAR_Y1 <= y <= UNIT_BAR_Y2:
            excluded_unit_bar.append((x, y))
            continue

        # Check if coordinate is within surrender button bounds
        if SURRENDER_BTN_X1 <= x <= SURRENDER_BTN_X2 and SURRENDER_BTN_Y1 <= y <= SURRENDER_BTN_Y2:
            excluded_surrender.append((x, y))
            continue

        filtered_coords.append((x, y))

    print(f"[DEBUG] Filtered out {len(excluded_unit_bar)} coords in unit bar, "
          f"{len(excluded_surrender)} in surrender button area")

    return filtered_coords, excluded_unit_bar, excluded_surrender


def create_visualization(screenshot_cv, valid_coords, filtered_coords,
                        excluded_unit_bar, excluded_surrender,
                        contours, red_mask):
    """
    Create annotated visualization showing all detection layers.
    """
    # Create a copy for annotation
    annotated = screenshot_cv.copy()
    height, width = annotated.shape[:2]

    # Layer 1: Red mask overlay (semi-transparent)
    red_overlay = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)
    red_overlay[:, :, 0] = 0  # Zero out blue channel
    red_overlay[:, :, 1] = 0  # Zero out green channel
    red_overlay[:, :, 2] = red_mask  # Keep red channel
    annotated = cv2.addWeighted(annotated, 0.8, red_overlay, 0.2, 0)

    # Layer 2: Cyan contour lines showing detected boundary
    if contours:
        cv2.drawContours(annotated, contours, -1, (255, 255, 0), 2)  # Cyan, medium thickness

    # Layer 3: Red semi-transparent overlays for filtered areas
    overlay = annotated.copy()

    # Unit bar area (relative to screen region)
    ub_x1 = max(0, UNIT_BAR_X1 - SCREEN_REGION[0])
    ub_y1 = max(0, UNIT_BAR_Y1 - SCREEN_REGION[1])
    ub_x2 = min(width, UNIT_BAR_X2 - SCREEN_REGION[0])
    ub_y2 = min(height, UNIT_BAR_Y2 - SCREEN_REGION[1])
    if ub_x2 > ub_x1 and ub_y2 > ub_y1:
        cv2.rectangle(overlay, (ub_x1, ub_y1), (ub_x2, ub_y2), (0, 0, 255), -1)

    # Surrender button area (relative to screen region)
    sb_x1 = max(0, SURRENDER_BTN_X1 - SCREEN_REGION[0])
    sb_y1 = max(0, SURRENDER_BTN_Y1 - SCREEN_REGION[1])
    sb_x2 = min(width, SURRENDER_BTN_X2 - SCREEN_REGION[0])
    sb_y2 = min(height, SURRENDER_BTN_Y2 - SCREEN_REGION[1])
    if sb_x2 > sb_x1 and sb_y2 > sb_y1:
        cv2.rectangle(overlay, (sb_x1, sb_y1), (sb_x2, sb_y2), (0, 0, 255), -1)

    # Blend the overlays
    annotated = cv2.addWeighted(annotated, 0.7, overlay, 0.3, 0)

    # Layer 4: Green circles for valid (filtered) deployment coordinates
    for x, y in filtered_coords:
        # Convert to region-relative coordinates
        region_x = x - SCREEN_REGION[0]
        region_y = y - SCREEN_REGION[1]
        cv2.circle(annotated, (region_x, region_y), 8, (0, 255, 0), -1)  # Green filled circle
        cv2.circle(annotated, (region_x, region_y), 10, (255, 255, 255), 1)  # White outline

    # Layer 5: Gray circles for excluded coordinates (for debugging)
    for x, y in excluded_unit_bar + excluded_surrender:
        region_x = x - SCREEN_REGION[0]
        region_y = y - SCREEN_REGION[1]
        cv2.circle(annotated, (region_x, region_y), 6, (128, 128, 128), -1)  # Gray filled circle

    # Layer 6: Text statistics overlay
    y_offset = 30
    line_height = 25

    texts = [
        f"Detection mode: Contour-tracing (Baby Dragons)",
        f"Total coords generated: {len(valid_coords)}",
        f"Filtered coords (valid): {len(filtered_coords)}",
        f"Excluded (unit bar): {len(excluded_unit_bar)}",
        f"Excluded (surrender): {len(excluded_surrender)}",
        f"Boundary offset: {BOUNDARY_OFFSET}px",
        f"Sample interval: {SAMPLE_INTERVAL}px",
    ]

    for i, text in enumerate(texts):
        y_pos = y_offset + i * line_height
        # Black background for text
        (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(annotated, (8, y_pos - text_height - 3),
                     (15 + text_width, y_pos + 3), (0, 0, 0), -1)
        # White text
        cv2.putText(annotated, text, (10, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return annotated


def capture_and_analyze():
    """Capture screen, detect deployment zone, and save annotated visualization."""
    print("\n[DEBUG] Capturing screen...")

    # Capture screenshot
    screenshot = ImageGrab.grab(bbox=SCREEN_REGION)
    screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Detect deployment zone
    valid_coords, contours, red_mask = detect_deployment_zone(screenshot_cv)

    # Filter coordinates
    filtered_coords, excluded_unit_bar, excluded_surrender = filter_coordinates(valid_coords)

    # Create visualization
    annotated = create_visualization(screenshot_cv, valid_coords, filtered_coords,
                                     excluded_unit_bar, excluded_surrender,
                                     contours, red_mask)

    # Save to file with timestamp
    ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bb_deploy_zone_{timestamp}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    cv2.imwrite(filepath, annotated)

    print(f"\n[SUCCESS] Annotated screenshot saved to: {filepath}")
    print(f"[INFO] Valid deployment coordinates: {len(filtered_coords)}")


def on_f3_pressed(event):
    """Callback for F3 key press."""
    if event.event_type == 'down':  # Only trigger on key down
        try:
            capture_and_analyze()
        except Exception as e:
            print(f"[ERROR] Failed to capture and analyze: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main loop - wait for F3 or ESC."""
    print("=" * 60)
    print("BB Deployment Zone Debug Tool")
    print("=" * 60)
    print("\nControls:")
    print("  F3  - Capture and analyze deployment zone")
    print("  ESC - Exit")
    print("\nWaiting for input...")

    # Hook F3 key
    keyboard.hook_key('f3', on_f3_pressed)

    # Wait for ESC to exit
    keyboard.wait('esc')

    print("\n[EXIT] ESC pressed - exiting")
    keyboard.unhook_all()


if __name__ == "__main__":
    main()
