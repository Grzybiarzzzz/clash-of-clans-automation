"""
Debug Queen Giant Arrow Glow Detection

This helper program lets you test the arrow glow detection in real-time:
1. Manually load into a battle in Clash of Clans
2. Deploy your Queen and activate her ability
3. Press 'N' to capture and analyze the glow trail
4. View the annotated screenshot showing detected glow regions
5. Press 'Q' to quit

The program will:
- Show detected glow segments in GREEN boxes
- Draw the calculated arrow path in RED
- Display statistics about detection
- Save annotated screenshots for analysis
"""

import sys
import os
import time
import cv2
import numpy as np
import keyboard
from PIL import ImageGrab
from datetime import datetime

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# Output directories
BASE_DEBUG_DIR = os.path.join("debug_screenshots", "giant_arrow_debug")
MASK_DIR = os.path.join(BASE_DEBUG_DIR, "1_masks")
ANNOTATED_DIR = os.path.join(BASE_DEBUG_DIR, "2_annotated")
COMBINED_DIR = os.path.join(BASE_DEBUG_DIR, "3_combined")

# Create directories if they don't exist
for directory in [BASE_DEBUG_DIR, MASK_DIR, ANNOTATED_DIR, COMBINED_DIR]:
    os.makedirs(directory, exist_ok=True)

# Global counter for numbering screenshots
capture_counter = 0

# Detection settings - CALIBRATED VALUES
# Calibrated using the interactive HSV calibration tool
# These values reduce false positives by requiring high brightness (194+)
LOWER_CYAN = np.array([77, 0, 194])     # H=77-95 (cyan), S=0+ (any), V=194+ (very bright)
UPPER_CYAN = np.array([95, 255, 255])   # High V threshold filters out dark buildings/effects

def analyze_hsv_values(hsv, mask):
    """
    Analyze HSV values in detected regions to help tune detection.
    """
    if np.sum(mask) == 0:
        print("⚠️ No pixels detected - cannot analyze HSV values")
        return

    # Get HSV values of detected pixels
    detected_pixels = hsv[mask == 255]

    if len(detected_pixels) == 0:
        return

    # Calculate statistics
    h_values = detected_pixels[:, 0]
    s_values = detected_pixels[:, 1]
    v_values = detected_pixels[:, 2]

    print(f"\n[HSV ANALYSIS] Statistics of detected glow pixels:")
    print(f"  Hue (H):        min={np.min(h_values):3d} max={np.max(h_values):3d} avg={np.mean(h_values):3.0f}")
    print(f"  Saturation (S): min={np.min(s_values):3d} max={np.max(s_values):3d} avg={np.mean(s_values):3.0f}")
    print(f"  Value (V):      min={np.min(v_values):3d} max={np.max(v_values):3d} avg={np.mean(v_values):3.0f}")
    print(f"\n  Suggested range based on detected pixels:")
    print(f"  LOWER = [{max(0, np.min(h_values)-5):3d}, {max(0, np.min(s_values)-30):3d}, {max(0, np.min(v_values)-30):3d}]")
    print(f"  UPPER = [{min(180, np.max(h_values)+5):3d}, 255, 255]")

def detect_and_visualize_arrow_glow():
    """
    Capture screenshot, detect arrow glow, and save annotated image showing results.
    """
    global capture_counter
    capture_counter += 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*70}")
    print(f"[CAPTURE #{capture_counter}] [{timestamp}] Starting arrow glow detection...")

    try:
        # Capture screenshot of base region
        base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
        img = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        print(f"Captured base region: {config.BASE_VIEW_REGION}")
        print(f"Current HSV range: {LOWER_CYAN} to {UPPER_CYAN}")

        # Find cyan/green glow pixels
        mask = cv2.inRange(hsv, LOWER_CYAN, UPPER_CYAN)

        # Save the mask for debugging
        mask_filename = f"mask_{capture_counter:03d}_{timestamp}.png"
        mask_path = os.path.join(MASK_DIR, mask_filename)
        cv2.imwrite(mask_path, mask)
        print(f"✓ Saved color mask: {mask_path}")

        # Calculate how much of the image is white (detected glow)
        total_pixels = mask.shape[0] * mask.shape[1]
        white_pixels = np.sum(mask == 255)
        detection_percentage = (white_pixels / total_pixels) * 100
        print(f"Mask coverage: {white_pixels}/{total_pixels} pixels ({detection_percentage:.2f}%)")

        # Analyze HSV values of detected pixels
        analyze_hsv_values(hsv, mask)

        # Find contours of glow trail
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"\nFound {len(contours)} total contours")

        # Create annotated image
        annotated = img.copy()

        # Track valid glow segments
        valid_glow_points = []
        filtered_count = 0

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Check filters (same as main.py)
            is_valid = True
            filter_reason = ""

            # Filter 1: Minimum area
            if area < 50:
                is_valid = False
                filter_reason = f"too small (area={area:.0f})"
                filtered_count += 1

            # Filter 2: Maximum area (filters out large water/terrain false positives)
            elif area > 1000:
                is_valid = False
                filter_reason = f"too large (area={area:.0f})"
                filtered_count += 1

            # Filter 3: Thickness (arrow is THICK, not thin lines)
            # Thin wall lines are 2-5px, arrow glow is 10-30px thick
            elif w < 8 and h < 8:
                is_valid = False
                filter_reason = f"too thin (w={w}, h={h})"
                filtered_count += 1

            # Filter 4: Position (exclude UI areas)
            elif x < 200 or x > 2100 or y < 200 or y > 1000:
                is_valid = False
                filter_reason = f"outside game area (x={x}, y={y})"
                filtered_count += 1

            if is_valid:
                # Calculate center of this glow segment
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert to global screen coordinates
                    global_x = cx + config.BASE_VIEW_REGION[0]
                    global_y = cy + config.BASE_VIEW_REGION[1]

                    valid_glow_points.append((global_x, global_y, area))

                    # Draw GREEN box for valid glow segments
                    cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 255, 0), 2)

                    # Draw center point
                    cv2.circle(annotated, (cx, cy), 5, (0, 255, 0), -1)

                    # Add label with area
                    label = f"#{len(valid_glow_points)} ({area:.0f}px)"
                    cv2.putText(annotated, label, (x, y-5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            else:
                # Draw RED box for filtered segments (for debugging)
                cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 255), 1)

        print(f"Valid glow segments: {len(valid_glow_points)}")
        print(f"Filtered segments: {filtered_count}")

        # Calculate arrow path if we have valid glow points
        if len(valid_glow_points) >= 2:
            # IMPROVED: Find densest cluster first, then fit line
            # Convert to local coordinates for processing
            x_coords_all = np.array([p[0] - config.BASE_VIEW_REGION[0] for p in valid_glow_points])
            y_coords_all = np.array([p[1] - config.BASE_VIEW_REGION[1] for p in valid_glow_points])

            # Find the densest cluster: points with at least 3 neighbors within specified radius
            cluster_radius = 200  # pixels - reduced for tighter clustering
            min_neighbors = 3

            clustered_indices = []
            for i, (x1, y1) in enumerate(zip(x_coords_all, y_coords_all)):
                neighbor_count = 0
                for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                    if i != j:
                        dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                        if dist <= cluster_radius:
                            neighbor_count += 1

                if neighbor_count >= min_neighbors:
                    clustered_indices.append(i)

            if len(clustered_indices) < 3:
                print(f"  No dense cluster found ({len(clustered_indices)} points), using all {len(valid_glow_points)} points")
                clustered_indices = list(range(len(valid_glow_points)))
            else:
                print(f"  Found cluster: {len(clustered_indices)}/{len(valid_glow_points)} points (filtered {len(valid_glow_points) - len(clustered_indices)} outliers)")

            # Mark clustered points differently in visualization
            for i in range(len(valid_glow_points)):
                x_local = int(x_coords_all[i])
                y_local = int(y_coords_all[i])
                if i in clustered_indices:
                    # Clustered points: bright cyan circle
                    cv2.circle(annotated, (x_local, y_local), 8, (255, 255, 0), 2)
                else:
                    # Outliers: red X
                    cv2.drawMarker(annotated, (x_local, y_local), (0, 0, 255),
                                  cv2.MARKER_CROSS, 10, 2)

            # Use only clustered points for line fitting
            x_coords = x_coords_all[clustered_indices]
            y_coords = y_coords_all[clustered_indices]

            # Check if line is more vertical than horizontal
            x_range = np.max(x_coords) - np.min(x_coords)
            y_range = np.max(y_coords) - np.min(y_coords)

            if x_range > y_range:
                # Horizontal-ish line: fit y = mx + b
                coeffs = np.polyfit(x_coords, y_coords, 1)
                m, b = coeffs
                x_min, x_max = np.min(x_coords), np.max(x_coords)
                start_point = (int(x_min), int(m * x_min + b))
                end_point = (int(x_max), int(m * x_max + b))
                print(f"  Fitted line: y = {m:.3f}x + {b:.1f} (horizontal-ish)")
            else:
                # Vertical-ish line: fit x = my + b
                coeffs = np.polyfit(y_coords, x_coords, 1)
                m, b = coeffs
                y_min, y_max = np.min(y_coords), np.max(y_coords)
                start_point = (int(m * y_min + b), int(y_min))
                end_point = (int(m * y_max + b), int(y_max))
                print(f"  Fitted line: x = {m:.3f}y + {b:.1f} (vertical-ish)")

            max_distance = ((end_point[0] - start_point[0])**2 + (end_point[1] - start_point[1])**2)**0.5

            if start_point and end_point:
                # Draw arrow path in BLUE (thick line)
                cv2.line(annotated, start_point, end_point, (255, 0, 0), 3)

                # Draw start/end points in YELLOW
                cv2.circle(annotated, start_point, 10, (0, 255, 255), -1)
                cv2.circle(annotated, end_point, 10, (0, 255, 255), -1)

                # Extrapolate path (30% extension)
                dx = end_point[0] - start_point[0]
                dy = end_point[1] - start_point[1]
                extension_factor = 1.3
                extrapolated_end = (
                    int(start_point[0] + dx * extension_factor),
                    int(start_point[1] + dy * extension_factor)
                )

                # Draw extrapolated path in RED (dashed-looking via dots)
                for t in np.linspace(0, 1, 20):
                    pt_x = int(end_point[0] + t * (extrapolated_end[0] - end_point[0]))
                    pt_y = int(end_point[1] + t * (extrapolated_end[1] - end_point[1]))
                    cv2.circle(annotated, (pt_x, pt_y), 3, (0, 0, 255), -1)

                # Draw spell casting positions (11 spells)
                start = start_point
                end = extrapolated_end
                for i in range(11):
                    t = i / 10
                    spell_x = int(start[0] + t * (end[0] - start[0]))
                    spell_y = int(start[1] + t * (end[1] - start[1]))

                    # Draw spell position as magenta X
                    cv2.drawMarker(annotated, (spell_x, spell_y), (255, 0, 255),
                                  cv2.MARKER_TILTED_CROSS, 15, 2)

                print(f"\n✓ Arrow path detected!")
                print(f"  Start: ({start_point[0]}, {start_point[1]})")
                print(f"  End: ({end_point[0]}, {end_point[1]})")
                print(f"  Trail length: {max_distance:.1f}px")
                print(f"  Extrapolated end: ({extrapolated_end[0]}, {extrapolated_end[1]})")
                print(f"  Fitted through {len(valid_glow_points)} points (outliers ignored by linear regression)")

                # Validation check
                min_trail_length = 200
                if max_distance < min_trail_length:
                    print(f"  ⚠️ WARNING: Trail too short ({max_distance:.1f}px < {min_trail_length}px)")
                else:
                    print(f"  ✓ Trail length valid (>{min_trail_length}px)")
        else:
            print(f"\n✗ Insufficient glow points ({len(valid_glow_points)}) - need at least 2")

        # Add legend to image
        legend_y = 30
        cv2.putText(annotated, "QUEEN ARROW GLOW DETECTION DEBUG", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        legend_y += 30
        cv2.putText(annotated, f"Valid glow segments: {len(valid_glow_points)}", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        legend_y += 25
        cv2.putText(annotated, f"Filtered segments: {filtered_count}", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        if len(valid_glow_points) >= 2:
            legend_y += 25
            cv2.putText(annotated, f"Trail length: {max_distance:.1f}px", (10, legend_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

        legend_y += 30
        cv2.rectangle(annotated, (10, legend_y), (30, legend_y+20), (0, 255, 0), -1)
        cv2.putText(annotated, "= Valid glow", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        legend_y += 25
        cv2.rectangle(annotated, (10, legend_y), (30, legend_y+20), (0, 0, 255), -1)
        cv2.putText(annotated, "= Filtered (small/large/thin/UI)", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        legend_y += 25
        cv2.line(annotated, (10, legend_y+10), (30, legend_y+10), (255, 0, 0), 3)
        cv2.putText(annotated, "= Detected arrow path", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        legend_y += 25
        cv2.circle(annotated, (20, legend_y+10), 8, (255, 255, 0), 2)
        cv2.putText(annotated, "= Clustered (used for line fit)", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        legend_y += 25
        cv2.drawMarker(annotated, (20, legend_y+10), (0, 0, 255),
                      cv2.MARKER_CROSS, 10, 2)
        cv2.putText(annotated, "= Outlier (ignored)", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        legend_y += 25
        cv2.drawMarker(annotated, (20, legend_y+10), (255, 0, 255),
                      cv2.MARKER_TILTED_CROSS, 15, 2)
        cv2.putText(annotated, "= Spell cast positions", (35, legend_y+15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Save annotated image
        annotated_filename = f"annotated_{capture_counter:03d}_{timestamp}.png"
        annotated_path = os.path.join(ANNOTATED_DIR, annotated_filename)
        cv2.imwrite(annotated_path, annotated)
        print(f"\n✓ Saved annotated image: {annotated_path}")

        # Create a combined view: Original + Mask overlay + Annotated
        # Resize mask to match annotated size
        mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        mask_colored[mask == 255] = [0, 255, 255]  # Make white pixels cyan for visibility

        # Create overlay of mask on original
        overlay = img.copy()
        overlay[mask == 255] = [0, 255, 255]  # Highlight detected areas in cyan

        # Stack images horizontally
        combined = np.hstack([img, mask_colored, overlay, annotated])
        combined_filename = f"combined_{capture_counter:03d}_{timestamp}.png"
        combined_path = os.path.join(COMBINED_DIR, combined_filename)
        cv2.imwrite(combined_path, combined)
        print(f"✓ Saved combined view: {combined_path}")

        # Display annotated image
        cv2.imshow("Queen Arrow Detection Debug - Annotated", annotated)

        # Display mask overlay
        cv2.imshow("Queen Arrow Detection Debug - Mask Overlay", overlay)

        cv2.waitKey(5000)  # Show for 5 seconds
        cv2.destroyAllWindows()

        print(f"\n[CAPTURE #{capture_counter}] Summary:")
        print(f"  All 3 images saved with number: {capture_counter:03d}")
        print(f"  - Mask:      {MASK_DIR}/")
        print(f"  - Annotated: {ANNOTATED_DIR}/")
        print(f"  - Combined:  {COMBINED_DIR}/")
        print(f"{'='*70}\n")

    except Exception as e:
        print(f"✗ Error during detection: {e}")
        import traceback
        traceback.print_exc()

def main():
    """
    Main program loop - listens for 'N' key to trigger detection.
    """
    print("="*70)
    print("QUEEN GIANT ARROW DETECTION DEBUGGER")
    print("="*70)
    print("\nInstructions:")
    print("1. Load into a Clash of Clans battle")
    print("2. Deploy your Archer Queen")
    print("3. Activate her Giant Arrow ability")
    print("4. Press 'N' to capture and analyze the glow trail")
    print("5. Press 'Q' to quit this program")
    print("\nOutput Files:")
    print(f"  Screenshots saved to: {BASE_DEBUG_DIR}/")
    print(f"  - 1_masks/      : Black/white color detection masks")
    print(f"  - 2_annotated/  : Images with detection boxes and spell positions")
    print(f"  - 3_combined/   : Side-by-side comparison of all stages")
    print(f"  Each capture numbered sequentially (001, 002, 003, ...)")
    print("\nDetection Settings:")
    print(f"  Base View Region: {config.BASE_VIEW_REGION}")
    print(f"  HSV Lower Bound: {LOWER_CYAN}")
    print(f"  HSV Upper Bound: {UPPER_CYAN}")
    print(f"  Min Glow Area: 50 pixels (reduced for better detection)")
    print(f"  Min Trail Length: 200 pixels")
    print(f"\nNote: HSV ranges have been widened from the original [75,100,150]-[95,255,255]")
    print(f"      to help detect more of the glow trail.")
    print("\nWaiting for input...")
    print("="*70 + "\n")

    def on_n_pressed(e):
        """Callback when 'N' is pressed"""
        if e.event_type == 'down':  # Only on key down, not up
            print("\n[N] Key pressed - Starting detection...")
            detect_and_visualize_arrow_glow()
            print("Ready for next detection (press 'N' again or 'Q' to quit)...")

    def on_q_pressed(e):
        """Callback when 'Q' is pressed"""
        if e.event_type == 'down':
            print("\n[Q] Quit key pressed - Exiting...")
            keyboard.unhook_all()
            sys.exit(0)

    # Register hotkeys
    keyboard.hook_key('n', on_n_pressed)
    keyboard.hook_key('q', on_q_pressed)

    print("Listening for keypresses... (N = detect, Q = quit)")

    try:
        # Keep program running
        keyboard.wait()  # Wait indefinitely
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    finally:
        keyboard.unhook_all()
        cv2.destroyAllWindows()
        print("Cleanup complete. Goodbye!")

if __name__ == "__main__":
    main()
