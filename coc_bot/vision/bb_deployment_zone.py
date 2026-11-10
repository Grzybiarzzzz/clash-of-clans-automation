"""Builder Base deployment-zone detection: HSV masks, Hough lines and convex hulls."""

import cv2
import numpy as np
from PIL import ImageGrab

from coc_bot.discord_log import send_discord_debug_log

def filter_out_unit_bar(coordinates):
    """
    Filter out coordinates that fall within the unit bar area and surrender button area.
    Unit bar area: x=1, y=1209 to x=2553, y=1431 (non-clickable for unit placement)
    Surrender button area: x=4, y=1006 to x=301, y=1151 (expanded by 20px for mouse variance)
    """
    UNIT_BAR_X1 = 1
    UNIT_BAR_Y1 = 1209
    UNIT_BAR_X2 = 2553
    UNIT_BAR_Y2 = 1431

    # Surrender button with 20px padding for mouse movement variance
    SURRENDER_BTN_X1 = 4    # was 24
    SURRENDER_BTN_Y1 = 1006  # was 1026
    SURRENDER_BTN_X2 = 301   # was 281
    SURRENDER_BTN_Y2 = 1151  # was 1131

    filtered_coords = []
    excluded_count_unit_bar = 0
    excluded_count_surrender = 0

    for x, y in coordinates:
        # Check if coordinate is within unit bar bounds
        if UNIT_BAR_X1 <= x <= UNIT_BAR_X2 and UNIT_BAR_Y1 <= y <= UNIT_BAR_Y2:
            excluded_count_unit_bar += 1
            continue
        # Check if coordinate is within surrender button bounds
        if SURRENDER_BTN_X1 <= x <= SURRENDER_BTN_X2 and SURRENDER_BTN_Y1 <= y <= SURRENDER_BTN_Y2:
            excluded_count_surrender += 1
            continue
        filtered_coords.append((x, y))

    if excluded_count_unit_bar > 0:
        print(f"[BB] Filtered out {excluded_count_unit_bar} coordinates within unit bar area")
        send_discord_debug_log(f"BB: Excluded {excluded_count_unit_bar} coords in unit bar")
    if excluded_count_surrender > 0:
        print(f"[BB] Filtered out {excluded_count_surrender} coordinates within surrender button area")
        send_discord_debug_log(f"BB: Excluded {excluded_count_surrender} coords in surrender button area")

    return filtered_coords


def detect_bb_deployment_zone():
    """
    Detect Builder Base deployment zone by finding red boundary lines.
    Returns list of valid deployment coordinates outside the red lines.
    """
    try:
        # Capture the game screen area
        screen_region = (200, 100, 2360, 1200)  # Adjust based on your resolution
        screenshot = ImageGrab.grab(bbox=screen_region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Define red color range in HSV (for the red deployment boundary lines)
        # Red has two ranges in HSV
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        # Create masks for red color
        mask1 = cv2.inRange(screenshot_hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(screenshot_hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Find contours of red lines
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("[BB] No red deployment lines detected, using default coordinates")
            # Fallback to corners if detection fails
            return [
                (300, 300), (300, 1000), (2200, 300), (2200, 1000),
                (300, 650), (2200, 650), (1250, 300), (1250, 1000)
            ]

        # Find the bounding box of all red line contours
        all_points = np.concatenate(contours)
        x, y, w, h = cv2.boundingRect(all_points)

        # Convert back to screen coordinates
        x_offset, y_offset = screen_region[0], screen_region[1]
        boundary_left = x + x_offset
        boundary_top = y + y_offset
        boundary_right = x + w + x_offset
        boundary_bottom = y + h + y_offset

        print(f"[BB] Detected red boundary: left={boundary_left}, top={boundary_top}, right={boundary_right}, bottom={boundary_bottom}")
        send_discord_debug_log(f"BB deployment zone detected: {boundary_left}, {boundary_top}, {boundary_right}, {boundary_bottom}")

        # Generate valid deployment coordinates OUTSIDE the red boundary
        # Top, bottom, left, and right sides
        valid_coords = []

        # Top side (above red line)
        if boundary_top > 200:
            for x_pos in range(boundary_left, boundary_right, 100):
                valid_coords.append((x_pos, boundary_top - 50))

        # Bottom side (below red line)
        if boundary_bottom < 1200:
            for x_pos in range(boundary_left, boundary_right, 100):
                valid_coords.append((x_pos, boundary_bottom + 50))

        # Left side (left of red line)
        if boundary_left > 200:
            for y_pos in range(boundary_top, boundary_bottom, 100):
                valid_coords.append((boundary_left - 50, y_pos))

        # Right side (right of red line)
        if boundary_right < 2360:
            for y_pos in range(boundary_top, boundary_bottom, 100):
                valid_coords.append((boundary_right + 50, y_pos))

        if not valid_coords:
            print("[BB] No valid coordinates generated, using fallback")
            return [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

        print(f"[BB] Generated {len(valid_coords)} valid deployment coordinates")
        return valid_coords

    except Exception as e:
        print(f"[BB] Error detecting deployment zone: {e}")
        send_discord_debug_log(f"BB deployment zone detection error: {e}", "ERROR")
        # Fallback coordinates
        return [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]


# Baby Dragon deployment constants
BB_DRAGON_SCREEN_REGION = (200, 100, 2360, 1200)
BB_DRAGON_BOUNDARY_OFFSET = 25  # pixels from red line
BB_DRAGON_SAMPLE_INTERVAL = 50  # pixels between samples
BB_DRAGON_CIRCULARITY_THRESHOLD = 0.4  # max circularity for line-like contours (increased from 0.15)

# HSV red color ranges for deployment boundary detection
# Widened ranges to catch more red variations (lighting, shadows, base skins)
BB_DRAGON_LOWER_RED1 = np.array([0, 70, 80])
BB_DRAGON_UPPER_RED1 = np.array([12, 255, 255])
BB_DRAGON_LOWER_RED2 = np.array([158, 70, 80])
BB_DRAGON_UPPER_RED2 = np.array([180, 255, 255])

# Hough Line detection parameters
BB_DRAGON_HOUGH_MIN_LINE_LENGTH = 60   # Minimum line length in pixels
BB_DRAGON_HOUGH_MAX_LINE_GAP = 50      # Maximum gap to connect segments
BB_DRAGON_HOUGH_THRESHOLD = 40         # Votes threshold for Hough
BB_DRAGON_LINE_MERGE_ANGLE = 15        # Degrees - max angle diff for collinear
BB_DRAGON_LINE_MERGE_DIST = 40         # Pixels - max perpendicular distance
BB_DRAGON_LINE_MERGE_GAP = 100         # Pixels - max endpoint gap to merge


def detect_hough_lines(red_mask):
    """
    Detect straight line segments in the red mask using Hough Transform.

    Args:
        red_mask: Binary mask of detected red pixels

    Returns:
        List of line segments as (x1, y1, x2, y2) tuples
    """
    # Apply Canny edge detection for cleaner lines
    edges = cv2.Canny(red_mask, 50, 150, apertureSize=3)

    # Dilate edges slightly to ensure connectivity
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)

    # Detect lines using Probabilistic Hough Transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=BB_DRAGON_HOUGH_THRESHOLD,
        minLineLength=BB_DRAGON_HOUGH_MIN_LINE_LENGTH,
        maxLineGap=BB_DRAGON_HOUGH_MAX_LINE_GAP
    )

    if lines is None:
        return []

    return [tuple(line[0]) for line in lines]


def filter_lines_by_length(lines, min_length=50):
    """Filter lines to keep only those above minimum length."""
    filtered = []
    for line in lines:
        x1, y1, x2, y2 = line
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        if length >= min_length:
            filtered.append({
                'line': line,
                'length': length,
                'angle': np.arctan2(y2 - y1, x2 - x1)
            })
    return filtered


def are_lines_collinear(line1_data, line2_data):
    """
    Check if two line segments are approximately collinear.
    Uses angle similarity and perpendicular distance.
    """
    # Check angle similarity
    angle_diff = abs(line1_data['angle'] - line2_data['angle'])
    angle_diff = min(angle_diff, np.pi - angle_diff)  # Handle wraparound

    if np.degrees(angle_diff) > BB_DRAGON_LINE_MERGE_ANGLE:
        return False

    # Check perpendicular distance
    x1, y1, x2, y2 = line1_data['line']
    x3, y3, x4, y4 = line2_data['line']

    # Midpoint of line2
    mid_x = (x3 + x4) / 2
    mid_y = (y3 + y4) / 2

    # Distance from midpoint to line1 (extended)
    A = y2 - y1
    B = -(x2 - x1)
    C = (x2 - x1) * y1 - (y2 - y1) * x1

    denom = np.sqrt(A**2 + B**2)
    if denom < 1e-10:
        return False

    dist = abs(A * mid_x + B * mid_y + C) / denom
    return dist < BB_DRAGON_LINE_MERGE_DIST


def get_endpoint_distance(line1, line2):
    """Get minimum distance between any endpoints of two lines."""
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2

    endpoints1 = [(x1, y1), (x2, y2)]
    endpoints2 = [(x3, y3), (x4, y4)]

    min_dist = float('inf')
    for p1 in endpoints1:
        for p2 in endpoints2:
            dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
            min_dist = min(min_dist, dist)

    return min_dist


def merge_collinear_lines(line_data_list):
    """
    Merge line segments that are collinear and close together.
    Returns list of merged line segments.
    """
    if not line_data_list:
        return []

    merged = []
    used = set()

    for i, line1 in enumerate(line_data_list):
        if i in used:
            continue

        # Find all collinear lines close enough to merge
        group = [line1]
        used.add(i)

        for j, line2 in enumerate(line_data_list):
            if j in used:
                continue

            if are_lines_collinear(line1, line2):
                endpoint_dist = get_endpoint_distance(line1['line'], line2['line'])
                if endpoint_dist < BB_DRAGON_LINE_MERGE_GAP:
                    group.append(line2)
                    used.add(j)

        # Merge group into single line using extreme endpoints
        all_points = []
        for line_data in group:
            x1, y1, x2, y2 = line_data['line']
            all_points.extend([(x1, y1), (x2, y2)])

        # Find the two most distant points
        max_dist = 0
        best_pair = (all_points[0], all_points[-1])

        for k, p1 in enumerate(all_points):
            for p2 in all_points[k+1:]:
                dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                if dist > max_dist:
                    max_dist = dist
                    best_pair = (p1, p2)

        merged_line = (int(best_pair[0][0]), int(best_pair[0][1]),
                      int(best_pair[1][0]), int(best_pair[1][1]))
        merged.append(merged_line)

    return merged


def create_line_mask(lines, shape):
    """
    Create a mask image with the detected lines drawn on it.
    Used to filter the original red mask to only keep line regions.
    """
    line_mask = np.zeros(shape, dtype=np.uint8)
    for x1, y1, x2, y2 in lines:
        cv2.line(line_mask, (x1, y1), (x2, y2), 255, thickness=25)
    return line_mask


def sample_points_along_hull(hull_approx, base_center_x, base_center_y, red_mask):
    """
    Sample deployment coordinates evenly along a convex hull's edges.
    Applies radial offset and filters out invalid regions.

    Args:
        hull_approx: Approximated convex hull from cv2.approxPolyDP
        base_center_x: X coordinate of base center (in region coords)
        base_center_y: Y coordinate of base center (in region coords)
        red_mask: Original red mask for no-go zone filtering

    Returns:
        List of (screen_x, screen_y) deployment coordinates
    """
    # Extract hull vertices and close the loop
    hull_points = [hull_approx[i][0] for i in range(len(hull_approx))]
    hull_points.append(hull_points[0])  # Close the loop

    # Calculate cumulative distances along perimeter
    cumulative_distances = [0]
    for i in range(1, len(hull_points)):
        edge_dist = np.sqrt((hull_points[i][0] - hull_points[i-1][0])**2 +
                           (hull_points[i][1] - hull_points[i-1][1])**2)
        cumulative_distances.append(cumulative_distances[-1] + edge_dist)

    total_perimeter = cumulative_distances[-1]
    num_samples = max(int(total_perimeter / BB_DRAGON_SAMPLE_INTERVAL), 8)
    sample_spacing = total_perimeter / num_samples

    print(f"[BB DRAGONS] Perimeter: {total_perimeter:.0f}px, sampling {num_samples} points")

    # Sample at equal intervals along perimeter
    valid_coords = []
    for i in range(num_samples):
        target_dist = i * sample_spacing

        # Find which edge this distance falls on
        for j in range(1, len(cumulative_distances)):
            if cumulative_distances[j] >= target_dist:
                # Interpolate between vertices j-1 and j
                edge_start = cumulative_distances[j-1]
                edge_length = cumulative_distances[j] - edge_start
                t = (target_dist - edge_start) / edge_length if edge_length > 0 else 0

                # Interpolated point on hull edge
                point_x = hull_points[j-1][0] + t * (hull_points[j][0] - hull_points[j-1][0])
                point_y = hull_points[j-1][1] + t * (hull_points[j][1] - hull_points[j-1][1])

                # Vector from base center to interpolated point
                dx = point_x - base_center_x
                dy = point_y - base_center_y

                # Normalize and scale by offset distance
                length = np.sqrt(dx * dx + dy * dy)
                if length > 0:
                    offset_x = int(point_x + (dx / length) * BB_DRAGON_BOUNDARY_OFFSET)
                    offset_y = int(point_y + (dy / length) * BB_DRAGON_BOUNDARY_OFFSET)

                    # Convert to screen coordinates
                    screen_x = offset_x + BB_DRAGON_SCREEN_REGION[0]
                    screen_y = offset_y + BB_DRAGON_SCREEN_REGION[1]

                    valid_coords.append((screen_x, screen_y))
                break

    # Filter out coordinates inside the red boundary
    no_go_zone = cv2.dilate(red_mask, np.ones((15, 15), np.uint8), iterations=1)

    final_coords = []
    for screen_x, screen_y in valid_coords:
        region_x = screen_x - BB_DRAGON_SCREEN_REGION[0]
        region_y = screen_y - BB_DRAGON_SCREEN_REGION[1]

        if 0 <= region_x < no_go_zone.shape[1] and 0 <= region_y < no_go_zone.shape[0]:
            if no_go_zone[region_y, region_x] > 0:
                continue

        final_coords.append((screen_x, screen_y))

    # Filter out unit bar area
    final_coords = filter_out_unit_bar(final_coords)

    # Clamp all coordinates to valid screen bounds
    clamped_coords = []
    for x, y in final_coords:
        clamped_x = max(250, min(x, 2300))
        clamped_y = max(150, min(y, 1150))
        clamped_coords.append((clamped_x, clamped_y))
    final_coords = clamped_coords

    print(f"[BB DRAGONS] Final valid coordinates: {len(final_coords)}")

    if len(final_coords) < 6:
        print("[BB DRAGONS] Not enough coordinates, adding ring fallback")
        ring_coords = generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
        final_coords.extend(ring_coords)

    return final_coords


def generate_ring_fallback_coords(center_x=None, center_y=None, radius=400, num_points=8):
    """
    Generate deployment positions in a ring around base center.
    Used as intermediate fallback before corner positions.

    Args:
        center_x: X coordinate of ring center (in region coords, or None for default)
        center_y: Y coordinate of ring center (in region coords, or None for default)
        radius: Radius of the ring in pixels
        num_points: Number of points to generate around the ring

    Returns:
        List of (screen_x, screen_y) coordinates
    """
    # Default to center of screen region if no center provided
    region_width = BB_DRAGON_SCREEN_REGION[2] - BB_DRAGON_SCREEN_REGION[0]
    region_height = BB_DRAGON_SCREEN_REGION[3] - BB_DRAGON_SCREEN_REGION[1]

    if center_x is None:
        center_x = region_width // 2
    if center_y is None:
        center_y = region_height // 2

    coords = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        x = int(center_x + radius * np.cos(angle))
        y = int(center_y + radius * np.sin(angle))

        # Convert to screen coordinates
        screen_x = x + BB_DRAGON_SCREEN_REGION[0]
        screen_y = y + BB_DRAGON_SCREEN_REGION[1]

        # Clamp to valid screen area (with margin from edges)
        screen_x = max(250, min(screen_x, 2300))
        screen_y = max(150, min(screen_y, 1150))

        coords.append((screen_x, screen_y))

    return coords


def detect_bb_deployment_zone_advanced():
    """
    Detect BB deployment zone using Hough Line Transform + convex hull.
    Uses straight line detection to filter out building blobs, then creates
    a convex hull from the detected boundary lines.
    Returns list of valid deployment coordinates along the boundary.
    """
    try:
        # Capture the game screen area
        screenshot = ImageGrab.grab(bbox=BB_DRAGON_SCREEN_REGION)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Create masks for red color
        mask1 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED1, BB_DRAGON_UPPER_RED1)
        mask2 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED2, BB_DRAGON_UPPER_RED2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Calculate base center for reference
        height, width = screenshot_cv.shape[:2]
        base_center_x = width // 2
        base_center_y = height // 2

        # === HOUGH LINE DETECTION ===
        # Detect straight lines to filter out building blobs
        raw_lines = detect_hough_lines(red_mask)
        print(f"[BB DRAGONS] Hough detected {len(raw_lines)} raw lines")

        if len(raw_lines) >= 4:
            # Filter and merge collinear line segments
            filtered_lines = filter_lines_by_length(raw_lines, min_length=50)
            print(f"[BB DRAGONS] Filtered to {len(filtered_lines)} lines by length")

            if len(filtered_lines) >= 4:
                merged_lines = merge_collinear_lines(filtered_lines)
                print(f"[BB DRAGONS] Merged into {len(merged_lines)} line segments")

                if len(merged_lines) >= 4:
                    # Create a mask from detected lines to filter out building blobs
                    line_mask = create_line_mask(merged_lines, red_mask.shape)

                    # Dilate line mask to capture nearby red pixels
                    line_mask = cv2.dilate(line_mask, np.ones((10, 10), np.uint8), iterations=2)

                    # Keep only red pixels that are near detected straight lines
                    filtered_red_mask = cv2.bitwise_and(red_mask, line_mask)

                    # Dilate the filtered mask to connect fragments
                    kernel = np.ones((5, 5), np.uint8)
                    dilated_mask = cv2.dilate(filtered_red_mask, kernel, iterations=2)

                    # Find contours on the filtered mask
                    contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    if contours:
                        # Combine all line-filtered contours into one hull
                        all_points = np.vstack(contours)
                        print(f"[BB DRAGONS] HOUGH MODE: Using {len(contours)} line-filtered contours")

                        # Skip to hull creation with all_points as contour_to_use
                        contour_to_use = all_points

                        # Jump to hull creation (skip the old tier logic)
                        hull = cv2.convexHull(contour_to_use)
                        epsilon = 0.01 * cv2.arcLength(hull, True)
                        hull_approx = cv2.approxPolyDP(hull, epsilon, True)
                        print(f"[BB DRAGONS] Using convex hull with {len(hull_approx)} vertices")

                        # Sample points along hull edges
                        return sample_points_along_hull(hull_approx, base_center_x, base_center_y, red_mask)

        # === FALLBACK: Original contour-based detection ===
        print("[BB DRAGONS] Hough detection insufficient, falling back to contour method")

        # Dilate to connect fragmented contours
        kernel = np.ones((5, 5), np.uint8)
        dilated_mask = cv2.dilate(red_mask, kernel, iterations=2)

        # Find contours of red lines
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("[BB DRAGONS] No red deployment lines detected, using ring fallback")
            return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)

        print(f"[BB DRAGONS] Found {len(contours)} contours")

        # Sort contours by perimeter (largest first)
        contours_with_perimeter = [(cv2.arcLength(c, True), c) for c in contours]
        contours_with_perimeter.sort(reverse=True, key=lambda x: x[0])

        largest_perimeter, largest_contour = contours_with_perimeter[0]
        print(f"[BB DRAGONS] Largest contour perimeter: {largest_perimeter:.0f}px")

        # Minimum perimeter threshold - deployment boundary should be at least 1200px
        MIN_BOUNDARY_PERIMETER = 1200

        # TIER 1: Use largest contour if big enough
        if largest_perimeter >= MIN_BOUNDARY_PERIMETER:
            contour_to_use = largest_contour
            print("[BB DRAGONS] TIER 1: Using largest contour")
        else:
            # TIER 2: Try combining top contours if largest is too small
            print(f"[BB DRAGONS] Largest contour too small ({largest_perimeter:.0f}px), trying multi-contour combination...")

            # Combine top N contours with perimeter > 300px
            significant_contours = [c for perim, c in contours_with_perimeter if perim > 300]

            if len(significant_contours) >= 2:
                # Take up to 5 largest contours and combine their points
                contours_to_combine = significant_contours[:5]
                all_points = np.vstack(contours_to_combine)
                combined_perimeter = sum(cv2.arcLength(c, True) for c in contours_to_combine)
                print(f"[BB DRAGONS] TIER 2: Combining {len(contours_to_combine)} contours (total perimeter: {combined_perimeter:.0f}px)")

                if combined_perimeter >= MIN_BOUNDARY_PERIMETER:
                    contour_to_use = all_points
                else:
                    # TIER 3: Use ring fallback around red mask centroid
                    print("[BB DRAGONS] TIER 3: Combined perimeter still too small, using ring fallback around red centroid")
                    # Calculate centroid of red mask
                    red_points = cv2.findNonZero(red_mask)
                    if red_points is not None and len(red_points) > 0:
                        centroid = np.mean(red_points, axis=0)[0]
                        return generate_ring_fallback_coords(int(centroid[0]), int(centroid[1]), radius=350, num_points=8)
                    else:
                        return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
            else:
                # TIER 3: Not enough contours to combine, use ring fallback
                print("[BB DRAGONS] TIER 3: Not enough contours to combine, using ring fallback")
                red_points = cv2.findNonZero(red_mask)
                if red_points is not None and len(red_points) > 0:
                    centroid = np.mean(red_points, axis=0)[0]
                    return generate_ring_fallback_coords(int(centroid[0]), int(centroid[1]), radius=350, num_points=8)
                else:
                    return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)

        # Use CONVEX HULL on the selected contour(s)
        hull = cv2.convexHull(contour_to_use)

        # Approximate the hull to reduce points while maintaining shape
        epsilon = 0.01 * cv2.arcLength(hull, True)
        hull_approx = cv2.approxPolyDP(hull, epsilon, True)

        print(f"[BB DRAGONS] Using convex hull with {len(hull_approx)} vertices")

        # Sample points ALONG hull edges (not just at vertices)
        # This ensures even distribution around the perimeter
        valid_coords = []

        # Extract hull vertices and close the loop
        hull_points = [hull_approx[i][0] for i in range(len(hull_approx))]
        hull_points.append(hull_points[0])  # Close the loop

        # Calculate cumulative distances along perimeter
        cumulative_distances = [0]
        for i in range(1, len(hull_points)):
            edge_dist = np.sqrt((hull_points[i][0] - hull_points[i-1][0])**2 +
                               (hull_points[i][1] - hull_points[i-1][1])**2)
            cumulative_distances.append(cumulative_distances[-1] + edge_dist)

        total_perimeter = cumulative_distances[-1]
        num_samples = max(int(total_perimeter / BB_DRAGON_SAMPLE_INTERVAL), 8)
        sample_spacing = total_perimeter / num_samples

        print(f"[BB DRAGONS] Perimeter: {total_perimeter:.0f}px, sampling {num_samples} points at {sample_spacing:.0f}px intervals")

        # Sample at equal intervals along perimeter (interpolating between vertices)
        for i in range(num_samples):
            target_dist = i * sample_spacing

            # Find which edge this distance falls on
            for j in range(1, len(cumulative_distances)):
                if cumulative_distances[j] >= target_dist:
                    # Interpolate between vertices j-1 and j
                    edge_start = cumulative_distances[j-1]
                    edge_length = cumulative_distances[j] - edge_start
                    t = (target_dist - edge_start) / edge_length if edge_length > 0 else 0

                    # Interpolated point on hull edge
                    point_x = hull_points[j-1][0] + t * (hull_points[j][0] - hull_points[j-1][0])
                    point_y = hull_points[j-1][1] + t * (hull_points[j][1] - hull_points[j-1][1])

                    # Vector from base center to interpolated point
                    dx = point_x - base_center_x
                    dy = point_y - base_center_y

                    # Normalize and scale by offset distance
                    length = np.sqrt(dx * dx + dy * dy)
                    if length > 0:
                        offset_x = int(point_x + (dx / length) * BB_DRAGON_BOUNDARY_OFFSET)
                        offset_y = int(point_y + (dy / length) * BB_DRAGON_BOUNDARY_OFFSET)

                        # Convert to screen coordinates
                        screen_x = offset_x + BB_DRAGON_SCREEN_REGION[0]
                        screen_y = offset_y + BB_DRAGON_SCREEN_REGION[1]

                        valid_coords.append((screen_x, screen_y))
                    break

        print(f"[BB DRAGONS] Generated {len(valid_coords)} coordinates before filtering")

        # Final filter: remove coordinates inside the red boundary
        no_go_zone = cv2.dilate(red_mask, np.ones((15, 15), np.uint8), iterations=1)

        final_coords = []
        for screen_x, screen_y in valid_coords:
            region_x = screen_x - BB_DRAGON_SCREEN_REGION[0]
            region_y = screen_y - BB_DRAGON_SCREEN_REGION[1]

            if 0 <= region_x < no_go_zone.shape[1] and 0 <= region_y < no_go_zone.shape[0]:
                if no_go_zone[region_y, region_x] > 0:
                    continue

            final_coords.append((screen_x, screen_y))

        # Also filter out unit bar area
        final_coords = filter_out_unit_bar(final_coords)

        # Clamp all coordinates to valid screen bounds (with safety margins)
        clamped_coords = []
        for x, y in final_coords:
            clamped_x = max(250, min(x, 2300))
            clamped_y = max(150, min(y, 1150))
            clamped_coords.append((clamped_x, clamped_y))
        final_coords = clamped_coords

        print(f"[BB DRAGONS] Final valid coordinates: {len(final_coords)}")

        if len(final_coords) < 6:
            print("[BB DRAGONS] Not enough coordinates after filtering, adding ring fallback positions")
            # Use ring fallback around base center
            ring_coords = generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
            final_coords.extend(ring_coords)

        return final_coords

    except Exception as e:
        print(f"[BB DRAGONS] Error in advanced deployment zone detection: {e}")
        send_discord_debug_log(f"BB Dragons deployment zone error: {e}", "ERROR")
        # Use ring fallback around screen center on error
        return generate_ring_fallback_coords(radius=400, num_points=8)


def select_equally_spaced_coords(coords, num_points=6, min_distance=150):
    """
    Select N points equally spaced around the boundary with minimum distance enforcement.
    Sorts coordinates by angle from center and picks points ensuring minimum pixel distance.

    Args:
        coords: List of (x, y) coordinates
        num_points: Number of points to select (default 6)
        min_distance: Minimum pixel distance between selected points (default 250)
    """
    import math

    if len(coords) <= num_points:
        return coords

    # Calculate center of all coordinates
    center_x = sum(c[0] for c in coords) / len(coords)
    center_y = sum(c[1] for c in coords) / len(coords)

    # Sort by angle from center (clockwise)
    def angle_from_center(coord):
        return math.atan2(coord[1] - center_y, coord[0] - center_x)

    sorted_coords = sorted(coords, key=angle_from_center)

    def distance(p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def is_far_enough(candidate, selected_points, min_dist):
        """Check if candidate is at least min_dist away from all selected points."""
        for p in selected_points:
            if distance(candidate, p) < min_dist:
                return False
        return True

    # Pick points with minimum distance enforcement
    selected = []
    step = len(sorted_coords) // num_points

    # Start with evenly spaced candidates, but enforce minimum distance
    for i in range(len(sorted_coords)):
        if len(selected) >= num_points:
            break

        # Prefer evenly spaced starting points
        idx = (i * step) % len(sorted_coords)
        candidate = sorted_coords[idx]

        if is_far_enough(candidate, selected, min_distance):
            selected.append(candidate)

    # If we didn't get enough points with strict distance, relax and try again
    if len(selected) < num_points:
        print(f"[BB DRAGONS] Only found {len(selected)} points with {min_distance}px spacing, relaxing constraint...")
        selected = []
        relaxed_distance = 90  # Relaxed minimum distance

        for i in range(len(sorted_coords)):
            if len(selected) >= num_points:
                break
            idx = (i * step) % len(sorted_coords)
            candidate = sorted_coords[idx]

            if is_far_enough(candidate, selected, relaxed_distance):
                selected.append(candidate)

    # Final fallback: just take evenly spaced points regardless of distance
    if len(selected) < num_points:
        print(f"[BB DRAGONS] Still only {len(selected)} points, using basic spacing")
        selected = [sorted_coords[i * step] for i in range(num_points)]

    return selected


def save_bb_dragon_debug_visualization(all_coords, dragon_coords, bm_coord):
    """
    Save debug visualization of BB Gold Baby Dragons deployment detection.
    Creates a 3-panel image: Raw Mask | Mask Overlay | Deployment Positions

    Args:
        all_coords: List of all valid deployment coordinates
        dragon_coords: List of 6 dragon deployment positions
        bm_coord: Battle Machine deployment position (x, y)
    """
    try:
        from datetime import datetime
        import os

        # Ensure output directory exists
        output_dir = "screenshots/debug/bb_deployment_zone"
        os.makedirs(output_dir, exist_ok=True)

        # Capture current screen
        screenshot = ImageGrab.grab(bbox=BB_DRAGON_SCREEN_REGION)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Detect red boundary (same logic as detect_bb_deployment_zone_advanced)
        mask1 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED1, BB_DRAGON_UPPER_RED1)
        mask2 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED2, BB_DRAGON_UPPER_RED2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((5, 5), np.uint8)
        dilated_mask = cv2.dilate(red_mask, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # === PANEL 1: Raw Mask (white on black) ===
        panel1 = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)

        # === PANEL 2: Hough Lines Detection ===
        panel2 = screenshot_cv.copy()

        # Detect and draw Hough lines
        raw_lines = detect_hough_lines(red_mask)
        filtered_lines = filter_lines_by_length(raw_lines, min_length=50) if raw_lines else []
        merged_lines = merge_collinear_lines(filtered_lines) if len(filtered_lines) >= 4 else []

        # Draw raw detected lines in blue (thin)
        for line in raw_lines:
            x1, y1, x2, y2 = line
            cv2.line(panel2, (x1, y1), (x2, y2), (255, 100, 100), 1)

        # Draw merged lines in green (thick)
        for line in merged_lines:
            x1, y1, x2, y2 = line
            cv2.line(panel2, (x1, y1), (x2, y2), (0, 255, 0), 3)

        # === PANEL 3: Deployment positions with hull ===
        panel3 = screenshot_cv.copy()

        # Draw hull if contours found
        hull = None
        largest_perimeter = 0
        if contours:
            contours_with_perimeter = [(cv2.arcLength(c, True), c) for c in contours]
            contours_with_perimeter.sort(reverse=True, key=lambda x: x[0])
            largest_perimeter, largest_contour = contours_with_perimeter[0]

            MIN_BOUNDARY_PERIMETER = 1200
            if largest_perimeter >= MIN_BOUNDARY_PERIMETER:
                hull = cv2.convexHull(largest_contour)
                epsilon = 0.01 * cv2.arcLength(hull, True)
                hull = cv2.approxPolyDP(hull, epsilon, True)
                cv2.drawContours(panel3, [hull], -1, (255, 255, 0), 3)

        # Draw all valid coordinates as small gray circles
        for x, y in all_coords:
            region_x = x - BB_DRAGON_SCREEN_REGION[0]
            region_y = y - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (region_x, region_y), 5, (128, 128, 128), -1)

        # Draw dragon positions as numbered green circles
        for i, (x, y) in enumerate(dragon_coords):
            region_x = x - BB_DRAGON_SCREEN_REGION[0]
            region_y = y - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (region_x, region_y), 15, (0, 255, 0), -1)
            cv2.circle(panel3, (region_x, region_y), 17, (255, 255, 255), 2)
            text = str(i + 1)
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(panel3, text, (region_x - text_w // 2, region_y + text_h // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # Draw Battle Machine position
        if bm_coord:
            bm_region_x = bm_coord[0] - BB_DRAGON_SCREEN_REGION[0]
            bm_region_y = bm_coord[1] - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (bm_region_x, bm_region_y), 15, (0, 165, 255), -1)
            cv2.circle(panel3, (bm_region_x, bm_region_y), 17, (255, 255, 255), 2)
            (text_w, text_h), _ = cv2.getTextSize("BM", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.putText(panel3, "BM", (bm_region_x - text_w // 2, bm_region_y + text_h // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # === Add labels to each panel ===
        label_y = 30
        cv2.putText(panel1, "1. Raw Mask", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(panel2, "2. Hough Lines", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(panel3, "3. Positions", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Add stats to panel 2 (Hough lines info)
        hough_stats = [
            f"Raw lines: {len(raw_lines)}",
            f"Filtered: {len(filtered_lines)}",
            f"Merged: {len(merged_lines)}",
        ]
        for i, stat in enumerate(hough_stats):
            y_pos = 60 + i * 25
            (text_w, text_h), _ = cv2.getTextSize(stat, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(panel2, (8, y_pos - text_h - 2), (12 + text_w, y_pos + 2), (0, 0, 0), -1)
            cv2.putText(panel2, stat, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Add stats to panel 3
        stats = [
            f"Contours: {len(contours)}",
            f"Largest: {largest_perimeter:.0f}px",
            f"Coords: {len(all_coords)}",
        ]
        for i, stat in enumerate(stats):
            y_pos = 60 + i * 25
            (text_w, text_h), _ = cv2.getTextSize(stat, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(panel3, (8, y_pos - text_h - 2), (12 + text_w, y_pos + 2), (0, 0, 0), -1)
            cv2.putText(panel3, stat, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # === Combine all 3 panels side by side ===
        combined = np.hstack([panel1, panel2, panel3])

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bb_debug_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, combined)

        print(f"[BB DRAGONS DEBUG] Visualization saved to: {filepath}")
        send_discord_debug_log(f"BB Dragons debug visualization saved: {filename}")

    except Exception as e:
        print(f"[BB DRAGONS DEBUG] Error saving visualization: {e}")
        send_discord_debug_log(f"BB Dragons debug visualization error: {e}", "ERROR")
