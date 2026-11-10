"""Giant Arrow projectile tracking and spell casting along its path."""

import time

import cv2
import keyboard
import numpy as np
import pyautogui
from PIL import ImageGrab

import config
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import fast_click

def detect_queen_arrow_projectile():
    """
    Detect the Queen's Giant Arrow by tracking its bright cyan/green glow trail.
    Uses color-based detection (HSV) to find the distinctive arrow trail across multiple frames.

    Returns:
        List of (x, y) coordinates along arrow path for spell casting, or None if detection failed
    """
    try:
        print(f"[QUEEN ARROW] Starting glow trail detection...")

        # Arrow glow trail color range (bright cyan/green beam)
        # CALIBRATED VALUES - tuned to reduce false positives
        lower_cyan = np.array([77, 0, 194])     # H=77-95 (cyan), S=0+ (any saturation), V=194+ (very bright only)
        upper_cyan = np.array([95, 255, 255])   # High brightness threshold filters out dark objects

        # Capture multiple frames to track arrow movement
        frame_count = config.QUEEN_ARROW_FRAME_COUNT
        frame_interval = config.QUEEN_ARROW_FRAME_INTERVAL
        glow_detections = []  # List of (frame_num, points_along_trail)

        print(f"[QUEEN ARROW] Capturing {frame_count} frames at {frame_interval}s intervals...")

        for frame_num in range(frame_count):
            # Capture screenshot of base region only
            base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
            img = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Find cyan/green glow pixels
            mask = cv2.inRange(hsv, lower_cyan, upper_cyan)

            # Find contours of glow trail
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            frame_glow_points = []

            for contour in contours:
                area = cv2.contourArea(contour)

                # Filter by size: glow trail segments should be reasonably sized
                # Not tiny noise pixels, but also not huge water/terrain reflections
                if area < 100:  # Minimum 100 pixels for glow trail segment
                    continue
                if area > 1000:  # Maximum 1000 pixels - filters out large false positives (water, terrain)
                    continue

                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by width/height: arrow glow is THICK, not thin lines
                # Thin wall lines are 2-5px wide, arrow glow is 10-30px wide
                min_thickness = 8  # pixels - minimum width or height
                if w < min_thickness and h < min_thickness:
                    # Both dimensions too thin - it's a line, not arrow glow
                    continue

                # Filter by position: exclude UI areas
                if x < 200 or x > 2100 or y < 200 or y > 1000:
                    continue

                # Calculate center of this glow segment
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert to global screen coordinates
                    global_x = cx + config.BASE_VIEW_REGION[0]
                    global_y = cy + config.BASE_VIEW_REGION[1]

                    frame_glow_points.append((global_x, global_y, area))

            if frame_glow_points:
                glow_detections.append((frame_num, frame_glow_points))
                print(f"[QUEEN ARROW] Frame {frame_num}: Detected {len(frame_glow_points)} glow segments")

            # Wait before next frame
            if frame_num < frame_count - 1:
                time.sleep(frame_interval)

        print(f"[QUEEN ARROW] Glow detected in {len(glow_detections)} frames")

        # Need glow in at least 2 frames to determine path
        if len(glow_detections) < 2:
            print(f"[QUEEN ARROW] Insufficient glow detections ({len(glow_detections)} frames) - need at least 2")
            return None

        # Collect all glow points from all frames
        all_glow_points = []
        for frame_num, points in glow_detections:
            all_glow_points.extend([(p[0], p[1]) for p in points])  # (x, y) only

        if len(all_glow_points) < 2:
            print(f"[QUEEN ARROW] Not enough glow points detected ({len(all_glow_points)})")
            return None

        print(f"[QUEEN ARROW] Total glow points across all frames: {len(all_glow_points)}")

        # IMPROVED: Find the densest cluster of points (main arrow trail)
        # Strategy: Use pairwise distances to find the largest group of nearby points
        x_coords_all = np.array([p[0] for p in all_glow_points])
        y_coords_all = np.array([p[1] for p in all_glow_points])

        if len(x_coords_all) < 3:
            print(f"[QUEEN ARROW] Not enough points for clustering")
            return None

        # IMPROVED: Find the densest LINE segment by starting from the densest point
        # and including only connected neighbors - prevents scattered points from skewing the line
        cluster_radius = 200  # pixels - connection radius
        min_neighbors = 2  # Reduced - we'll filter more later

        # Step 1: Count neighbors for each point
        neighbor_counts = []
        for i, (x1, y1) in enumerate(zip(x_coords_all, y_coords_all)):
            neighbor_count = 0
            for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                if i != j:
                    dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if dist <= cluster_radius:
                        neighbor_count += 1
            neighbor_counts.append(neighbor_count)

        # Step 2: Find ALL connected components, then choose the most LINEAR one
        # (Arrow paths are straight lines, not scattered clusters)
        if len(neighbor_counts) == 0 or max(neighbor_counts) == 0:
            print(f"[QUEEN ARROW] No clustered points found")
            clustered_indices = list(range(len(all_glow_points)))
        else:
            # Find all connected components
            visited = set()
            components = []

            for start_idx in range(len(x_coords_all)):
                if start_idx in visited:
                    continue

                # Build connected component from this point
                component = set([start_idx])
                queue = [start_idx]
                visited.add(start_idx)

                while queue:
                    current_idx = queue.pop(0)
                    x1, y1 = x_coords_all[current_idx], y_coords_all[current_idx]

                    for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                        if j not in visited:
                            dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                            if dist <= cluster_radius:
                                component.add(j)
                                queue.append(j)
                                visited.add(j)

                if len(component) >= 3:  # Only keep components with 3+ points
                    components.append(sorted(list(component)))

            print(f"[QUEEN ARROW] Found {len(components)} connected components")

            # Score each component by linearity (how well points form a straight line)
            best_component = None
            best_score = -1

            for comp_indices in components:
                comp_x = x_coords_all[comp_indices]
                comp_y = y_coords_all[comp_indices]

                # Fit a line through this component
                x_range = np.max(comp_x) - np.min(comp_x)
                y_range = np.max(comp_y) - np.min(comp_y)

                if x_range > y_range and x_range > 0:
                    coeffs = np.polyfit(comp_x, comp_y, 1)
                    m, b = coeffs
                    distances = np.abs(m * comp_x - comp_y + b) / np.sqrt(m**2 + 1)
                elif y_range > 0:
                    coeffs = np.polyfit(comp_y, comp_x, 1)
                    m, b = coeffs
                    distances = np.abs(m * comp_y - comp_x + b) / np.sqrt(m**2 + 1)
                else:
                    continue  # Skip degenerate components

                # Calculate linearity score: favor more points with lower deviation from line
                avg_distance = np.mean(distances)
                num_points = len(comp_indices)
                linearity_score = (num_points ** 2) / (avg_distance + 1)  # +1 to avoid division by zero

                print(f"[QUEEN ARROW] Component with {num_points} points: avg deviation={avg_distance:.1f}px, score={linearity_score:.1f}")

                if linearity_score > best_score:
                    best_score = linearity_score
                    best_component = comp_indices

            if best_component is None or len(best_component) < 3:
                print(f"[QUEEN ARROW] No good linear component found, using all points")
                clustered_indices = list(range(len(all_glow_points)))
            else:
                clustered_indices = best_component
                print(f"[QUEEN ARROW] Selected best linear component: {len(clustered_indices)} points")

        # Use only the connected component points for line fitting
        x_coords = x_coords_all[clustered_indices]
        y_coords = y_coords_all[clustered_indices]

        print(f"[QUEEN ARROW] Using {len(x_coords)} connected points (filtered {len(all_glow_points) - len(x_coords)} scattered points)")

        # IMPROVED: Iterative outlier removal based on perpendicular distance from line
        # Fit initial line, remove points far from it, refit - focuses on the main straight line
        max_iterations = 3
        max_perpendicular_distance = 50  # pixels - max distance from line

        for iteration in range(max_iterations):
            if len(x_coords) < 3:
                break

            # Check if line is more vertical than horizontal
            x_range = np.max(x_coords) - np.min(x_coords)
            y_range = np.max(y_coords) - np.min(y_coords)

            if x_range > y_range:
                # Horizontal-ish line: fit y = mx + b
                coeffs = np.polyfit(x_coords, y_coords, 1)
                m, b = coeffs

                # Calculate perpendicular distance for each point
                # For line y = mx + b, perpendicular distance = |mx - y + b| / sqrt(m^2 + 1)
                distances = np.abs(m * x_coords - y_coords + b) / np.sqrt(m**2 + 1)

            else:
                # Vertical-ish line: fit x = my + b
                coeffs = np.polyfit(y_coords, x_coords, 1)
                m, b = coeffs

                # For line x = my + b, perpendicular distance = |my - x + b| / sqrt(m^2 + 1)
                distances = np.abs(m * y_coords - x_coords + b) / np.sqrt(m**2 + 1)

            # Keep only points within max distance
            inlier_mask = distances <= max_perpendicular_distance
            inliers_before = len(x_coords)
            x_coords = x_coords[inlier_mask]
            y_coords = y_coords[inlier_mask]
            inliers_after = len(x_coords)

            if inliers_before == inliers_after:
                # No points removed, we're done
                break

            print(f"[QUEEN ARROW] Iteration {iteration+1}: Removed {inliers_before - inliers_after} points far from line")

        # Safety check: ensure we still have enough points after outlier removal
        if len(x_coords) < 2:
            print(f"[QUEEN ARROW] All points removed as outliers! Only {len(x_coords)} points remain.")
            print(f"[QUEEN ARROW] No clear arrow glow detected - detection failed")
            return None

        # Final line fit with refined points
        x_range = np.max(x_coords) - np.min(x_coords)
        y_range = np.max(y_coords) - np.min(y_coords)

        if x_range > y_range:
            # Horizontal-ish line: fit y = mx + b
            coeffs = np.polyfit(x_coords, y_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            x_min, x_max = np.min(x_coords), np.max(x_coords)
            start_point = (int(x_min), int(m * x_min + b))
            end_point = (int(x_max), int(m * x_max + b))

            print(f"[QUEEN ARROW] Final line: y = {m:.3f}x + {b:.1f} ({len(x_coords)} inliers)")
        else:
            # Vertical-ish line: fit x = my + b
            coeffs = np.polyfit(y_coords, x_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            y_min, y_max = np.min(y_coords), np.max(y_coords)
            start_point = (int(m * y_min + b), int(y_min))
            end_point = (int(m * y_max + b), int(y_max))

            print(f"[QUEEN ARROW] Final line: x = {m:.3f}y + {b:.1f} ({len(x_coords)} inliers)")

        start_x, start_y = start_point
        end_x, end_y = end_point

        # Calculate trail length along the fitted line
        trail_length = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5

        # Validate that we have a reasonable arrow path
        min_trail_length = 200  # pixels - arrow trail should be at least this long
        if trail_length < min_trail_length:
            print(f"[QUEEN ARROW] Glow trail too short ({trail_length:.1f}px < {min_trail_length}px)")
            return None

        print(f"[QUEEN ARROW] Arrow trail detected: ({start_x},{start_y}) -> ({end_x},{end_y})")
        print(f"[QUEEN ARROW] Trail length: {trail_length:.1f}px")

        # Extrapolate path by 30% for better coverage
        dx = end_x - start_x
        dy = end_y - start_y
        extension_factor = 1.3
        extrapolated_end_x = int(start_x + dx * extension_factor)
        extrapolated_end_y = int(start_y + dy * extension_factor)

        print(f"[QUEEN ARROW] Extrapolated path end: ({extrapolated_end_x},{extrapolated_end_y})")
        send_discord_debug_log(f"Queen arrow: Glow trail detected ({len(all_glow_points)} points, {max_distance:.0f}px trail)")

        return [(start_x, start_y), (extrapolated_end_x, extrapolated_end_y)]

    except Exception as e:
        print(f"[QUEEN ARROW] Error in glow trail detection: {e}")
        send_discord_debug_log(f"Queen arrow glow detection failed: {e}", "WARNING")
        import traceback
        traceback.print_exc()
        return None


def detect_queen_arrow_path_and_cast_spells(queen_side, queen_ability_timing, spell_casting_flag):
    """
    Detect the Queen's Giant Arrow path and cast 11 Earthquakes along it.
    Uses glow trail detection (primary) with purple HP bar detection as fallback.

    Args:
        queen_side: 'up' or 'down' - which side Queen was deployed on
        queen_ability_timing: seconds to wait for Queen ability to activate (from settings)
        spell_casting_flag: shared flag dict to track spell casting phase (for hero ability re-selection)

    Returns True if successful, False otherwise.
    """
    try:
        print(f"[QUEEN ARROW] Waiting for Queen ability (deployed on {queen_side}, timing: {queen_ability_timing}s)...")

        # Wait for Queen ability to activate (already triggered by hero ability thread)
        time.sleep(queen_ability_timing)
        print(f"[QUEEN ARROW] Ability activated after {queen_ability_timing}s - starting detection...")

        # ===== PRIMARY METHOD: GLOW TRAIL DETECTION =====
        print(f"[QUEEN ARROW] Attempting glow trail detection...")
        arrow_path = detect_queen_arrow_projectile()

        if arrow_path is not None and len(arrow_path) == 2:
            # Successfully detected arrow glow trail - use these coordinates
            start, end = arrow_path
            print(f"[QUEEN ARROW] ✓ Glow trail detection successful: {start} -> {end}")
            send_discord_debug_log(f"SBarb Farm: Queen arrow glow trail detected")
            detection_method = "glow_trail"
        else:
            # ===== FALLBACK METHOD: PURPLE HP BAR DETECTION =====
            print(f"[QUEEN ARROW] Glow trail detection failed, using HP bar fallback...")
            time.sleep(0.5)  # Wait a bit more for damage to show

            # Capture screenshot
            screenshot = pyautogui.screenshot()
            img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Purple HP bar HSV range (magenta/purple color)
            lower_purple = np.array([140, 80, 80])   # Purple hue
            upper_purple = np.array([170, 255, 255])

            # Find purple HP bars
            mask = cv2.inRange(hsv, lower_purple, upper_purple)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Get centers of all HP bars with strict filtering
            hp_bar_centers = []
            for contour in contours:
                area = cv2.contourArea(contour)

                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by size: HP bars are small rectangles (50-500 pixels area typical)
                if area < 50 or area > 800:
                    continue

                # Filter by aspect ratio: HP bars are horizontal (wider than tall)
                if h == 0 or w / h < 1.5:  # Must be at least 1.5x wider than tall
                    continue

                # Filter by position: exclude UI areas (top/bottom edges, far left/right)
                # Game area is roughly (200, 200) to (2300, 1200)
                if x < 200 or x > 2300 or y < 200 or y > 1200:
                    continue

                # Calculate center
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    hp_bar_centers.append((cx, cy, area))
                    print(f"[QUEEN ARROW] HP bar detected: pos=({cx},{cy}), area={area}, size={w}x{h}, ratio={w/h:.2f}")

            print(f"[QUEEN ARROW] Detected {len(hp_bar_centers)} purple HP bars")

            # Exclude Queen's target based on deployment side
            if len(hp_bar_centers) >= 2:
                if queen_side == 'down':
                    # Queen at bottom - exclude bottom-most (highest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=True)  # Sort by Y (bottom to top)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed BOTTOM - excluded target at {queen_target[:2]}")
                elif queen_side == 'up':
                    # Queen at top - exclude top-most (lowest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=False)  # Sort by Y (top to bottom)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed TOP - excluded target at {queen_target[:2]}")

                print(f"[QUEEN ARROW] {len(hp_bar_centers)} damaged buildings remain after exclusion")

            # If we have at least 2 damaged buildings from arrow (early detection)
            if len(hp_bar_centers) >= 2:
                # Extract coordinates (without area)
                coords = [(p[0], p[1]) for p in hp_bar_centers]

                # Arrow flies in a straight line - use first and last detected building to extrapolate
                # Even with just 2-3 buildings detected, we can extrapolate the full path
                start = coords[0]
                end = coords[-1]

                # Calculate arrow direction vector
                dx = end[0] - start[0]
                dy = end[1] - start[1]

                # Extrapolate further along the arrow path for better coverage
                # Extend the line by 30% beyond the last detected building
                extension_factor = 1.3
                extended_end_x = int(start[0] + dx * extension_factor)
                extended_end_y = int(start[1] + dy * extension_factor)

                # Use extended end point for spell distribution
                end = (extended_end_x, extended_end_y)

                print(f"[QUEEN ARROW] ✓ HP bar fallback successful: {start} -> {end}")
                print(f"[QUEEN ARROW] Arrow path extrapolated from {len(coords)} buildings")
                send_discord_debug_log(f"SBarb Farm: Queen arrow HP bar fallback used ({len(coords)} buildings)")
                detection_method = "hp_bar"
            else:
                print(f"[QUEEN ARROW] ✗ Both detection methods failed ({len(hp_bar_centers)} HP bars)")
                send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed completely", "WARNING")
                return False

        # ===== SPELL CASTING (COMMON TO BOTH METHODS) =====
        print(f"[QUEEN ARROW] Casting 11 Earthquake spells along detected path ({detection_method})...")

        # Set flag to indicate spell casting is active (for hero ability re-selection)
        spell_casting_flag['value'] = True

        # Cast 11 Earthquake spells evenly distributed along the path - ULTRA FAST
        keyboard.send('a')  # Select Earthquake spell
        time.sleep(0.03)

        for i in range(11):
            # Calculate position along the line (0 to 1)
            t = i / 10  # 0%, 10%, 20%, ... 100%
            x = int(start[0] + t * (end[0] - start[0]))
            y = int(start[1] + t * (end[1] - start[1]))

            # Re-select spell every 4 casts to maintain selection
            if i % 4 == 0 and i > 0:
                keyboard.send('a')
                time.sleep(0.01)

            fast_click(x, y)
            time.sleep(0.02)  # Ultra-fast casting

        print(f"[QUEEN ARROW] Successfully cast 11 Earthquake spells on arrow path ({detection_method})")
        send_discord_debug_log(f"SBarb Farm: Cast 11 Earthquakes on Queen arrow path using {detection_method} detection")

        # Clear flag - spell casting complete
        spell_casting_flag['value'] = False

        # Wait for spells to finish casting animation
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"[QUEEN ARROW] Error detecting arrow path: {e}")
        send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed - {e}", "WARNING")
        return False
