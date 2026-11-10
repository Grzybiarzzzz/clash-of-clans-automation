"""
Analyze Arrow Detection Mask Images

This tool analyzes mask images (black/white or black/yellow) to test arrow detection.
Useful for debugging detection issues using mask screenshots.

Usage:
1. Take a screenshot of a mask image (like the black/yellow one)
2. Save it as 'mask_sample.png' in the bot directory
3. Run this program to analyze which segments would be detected

python helperPrograms/debug_analyze_mask.py [path_to_mask.png]
"""

import sys
import os
import cv2
import numpy as np

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# Detection parameters (matching coc_bot/attacks/queen_arrow.py)
MIN_AREA = 100
MAX_AREA = 1000
MIN_THICKNESS = 8  # pixels - minimum width or height

def analyze_mask_image(mask_path):
    """
    Analyze a mask image to see which segments would be detected.
    """
    print("="*70)
    print("ARROW DETECTION MASK ANALYZER")
    print("="*70)
    print(f"\nLoading mask: {mask_path}")

    # Load the mask image
    mask_img = cv2.imread(mask_path)
    if mask_img is None:
        print(f"ERROR: Could not load image: {mask_path}")
        return

    # Convert to grayscale if needed
    if len(mask_img.shape) == 3:
        mask_gray = cv2.cvtColor(mask_img, cv2.COLOR_BGR2GRAY)
    else:
        mask_gray = mask_img

    # Threshold to binary (anything not black becomes white)
    _, mask_binary = cv2.threshold(mask_gray, 10, 255, cv2.THRESH_BINARY)

    print(f"Image size: {mask_binary.shape[1]}x{mask_binary.shape[0]}")
    print(f"White pixels: {np.sum(mask_binary == 255)}")

    # Find contours
    contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"\nTotal contours found: {len(contours)}")

    # Create annotated image
    annotated = cv2.cvtColor(mask_binary, cv2.COLOR_GRAY2BGR)

    # Analyze each contour
    valid_segments = []
    filtered_segments = {
        'too_small': 0,
        'too_large': 0,
        'too_thin': 0,
        'outside_area': 0
    }

    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)

        # Check filters
        is_valid = True
        filter_reason = None

        if area < MIN_AREA:
            is_valid = False
            filter_reason = 'too_small'
            filtered_segments['too_small'] += 1
        elif area > MAX_AREA:
            is_valid = False
            filter_reason = 'too_large'
            filtered_segments['too_large'] += 1
        elif w < MIN_THICKNESS and h < MIN_THICKNESS:
            is_valid = False
            filter_reason = 'too_thin'
            filtered_segments['too_thin'] += 1
        elif x < 200 or x > 2100 or y < 200 or y > 1000:
            is_valid = False
            filter_reason = 'outside_area'
            filtered_segments['outside_area'] += 1

        # Draw based on validity
        if is_valid:
            # Valid segment - draw GREEN
            cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # Calculate center
            M = cv2.moments(contour)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                cv2.circle(annotated, (cx, cy), 8, (255, 255, 0), 2)
                valid_segments.append((cx, cy, area, w, h))

                # Label
                label = f"#{len(valid_segments)}"
                cv2.putText(annotated, label, (x, y-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                print(f"\n  Valid #{len(valid_segments)}:")
                print(f"    Position: ({cx}, {cy})")
                print(f"    Size: {w}x{h} (area={area:.0f})")
        else:
            # Filtered segment - draw RED
            cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 255), 1)

            # Label with reason
            if filter_reason == 'too_thin':
                cv2.putText(annotated, f"thin:{w}x{h}", (x, y-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

    print(f"\n" + "="*70)
    print(f"DETECTION SUMMARY")
    print(f"="*70)
    print(f"Valid segments: {len(valid_segments)}")
    print(f"Filtered segments: {sum(filtered_segments.values())}")
    print(f"  - Too small (< {MIN_AREA}px): {filtered_segments['too_small']}")
    print(f"  - Too large (> {MAX_AREA}px): {filtered_segments['too_large']}")
    print(f"  - Too thin (< {MIN_THICKNESS}px): {filtered_segments['too_thin']}")
    print(f"  - Outside area: {filtered_segments['outside_area']}")

    # Path fitting if enough valid segments
    if len(valid_segments) >= 2:
        print(f"\n" + "="*70)
        print(f"ARROW PATH CALCULATION")
        print(f"="*70)

        # Extract coordinates
        x_coords = np.array([s[0] for s in valid_segments])
        y_coords = np.array([s[1] for s in valid_segments])

        # Connected component clustering - find densest region and include only connected points
        cluster_radius = 200

        # Count neighbors for each point
        neighbor_counts = []
        for i, (x1, y1) in enumerate(zip(x_coords, y_coords)):
            neighbor_count = 0
            for j, (x2, y2) in enumerate(zip(x_coords, y_coords)):
                if i != j:
                    dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if dist <= cluster_radius:
                        neighbor_count += 1
            neighbor_counts.append(neighbor_count)

        # Find ALL connected components, then choose the most LINEAR one
        if len(neighbor_counts) == 0 or max(neighbor_counts) == 0:
            print(f"No clustered points found, using all {len(valid_segments)} points")
            clustered_indices = list(range(len(valid_segments)))
        else:
            # Find all connected components
            visited = set()
            components = []

            for start_idx in range(len(x_coords)):
                if start_idx in visited:
                    continue

                # Build connected component from this point
                component = set([start_idx])
                queue = [start_idx]
                visited.add(start_idx)

                while queue:
                    current_idx = queue.pop(0)
                    x1, y1 = x_coords[current_idx], y_coords[current_idx]

                    for j, (x2, y2) in enumerate(zip(x_coords, y_coords)):
                        if j not in visited:
                            dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                            if dist <= cluster_radius:
                                component.add(j)
                                queue.append(j)
                                visited.add(j)

                if len(component) >= 3:
                    components.append(sorted(list(component)))

            print(f"Found {len(components)} connected components")

            # Score each component by linearity (arrow = straight line)
            best_component = None
            best_score = -1

            for comp_indices in components:
                comp_x = x_coords[comp_indices]
                comp_y = y_coords[comp_indices]

                # Fit line through component
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
                    continue

                # Linearity score: more points + lower deviation = better
                avg_distance = np.mean(distances)
                num_points = len(comp_indices)
                linearity_score = (num_points ** 2) / (avg_distance + 1)

                print(f"  Component {len(components)}: {num_points} points, avg dev={avg_distance:.1f}px, score={linearity_score:.1f}")

                if linearity_score > best_score:
                    best_score = linearity_score
                    best_component = comp_indices

            if best_component is None or len(best_component) < 2:
                print(f"No good linear component, using all {len(valid_segments)} points")
                clustered_indices = list(range(len(valid_segments)))
            else:
                clustered_indices = best_component
                print(f"Selected best linear component: {len(clustered_indices)} points (score={best_score:.1f})")

        print(f"Using component: {len(clustered_indices)}/{len(valid_segments)} points")

        # Mark clustered vs outliers
        for i in range(len(valid_segments)):
            cx, cy = valid_segments[i][0], valid_segments[i][1]
            if i in clustered_indices:
                cv2.circle(annotated, (cx, cy), 10, (255, 255, 0), 2)
            else:
                cv2.drawMarker(annotated, (cx, cy), (0, 0, 255),
                              cv2.MARKER_CROSS, 12, 2)

        # Fit line through clustered points with iterative outlier removal
        x_clustered = x_coords[clustered_indices]
        y_clustered = y_coords[clustered_indices]

        # Iterative outlier removal - remove points far from the line
        max_iterations = 3
        max_perpendicular_distance = 50

        for iteration in range(max_iterations):
            if len(x_clustered) < 3:
                break

            x_range = np.max(x_clustered) - np.min(x_clustered)
            y_range = np.max(y_clustered) - np.min(y_clustered)

            if x_range > y_range:
                coeffs = np.polyfit(x_clustered, y_clustered, 1)
                m, b = coeffs
                distances = np.abs(m * x_clustered - y_clustered + b) / np.sqrt(m**2 + 1)
            else:
                coeffs = np.polyfit(y_clustered, x_clustered, 1)
                m, b = coeffs
                distances = np.abs(m * y_clustered - x_clustered + b) / np.sqrt(m**2 + 1)

            inlier_mask = distances <= max_perpendicular_distance
            inliers_before = len(x_clustered)
            x_clustered = x_clustered[inlier_mask]
            y_clustered = y_clustered[inlier_mask]
            inliers_after = len(x_clustered)

            if inliers_before == inliers_after:
                break

            print(f"Iteration {iteration+1}: Removed {inliers_before - inliers_after} outliers (distance > {max_perpendicular_distance}px)")

        # Safety check: ensure we still have points after outlier removal
        if len(x_clustered) < 2:
            print(f"ERROR: All points removed as outliers! Only {len(x_clustered)} points remain.")
            print("This likely means no clear arrow glow was detected.")
            return  # Exit early

        # Final line fit
        x_range = np.max(x_clustered) - np.min(x_clustered)
        y_range = np.max(y_clustered) - np.min(y_clustered)

        if x_range > y_range:
            coeffs = np.polyfit(x_clustered, y_clustered, 1)
            m, b = coeffs
            x_min, x_max = np.min(x_clustered), np.max(x_clustered)
            start = (int(x_min), int(m * x_min + b))
            end = (int(x_max), int(m * x_max + b))
            print(f"Line orientation: horizontal-ish")
            print(f"Equation: y = {m:.3f}x + {b:.1f}")
        else:
            coeffs = np.polyfit(y_clustered, x_clustered, 1)
            m, b = coeffs
            y_min, y_max = np.min(y_clustered), np.max(y_clustered)
            start = (int(m * y_min + b), int(y_min))
            end = (int(m * y_max + b), int(y_max))
            print(f"Line orientation: vertical-ish")
            print(f"Equation: x = {m:.3f}y + {b:.1f}")

        print(f"Final inliers: {len(x_clustered)} points")

        trail_length = ((end[0] - start[0])**2 + (end[1] - start[1])**2)**0.5
        print(f"Arrow path: {start} -> {end}")
        print(f"Trail length: {trail_length:.1f}px")

        # Draw path
        cv2.line(annotated, start, end, (255, 0, 0), 3)
        cv2.circle(annotated, start, 10, (0, 255, 255), -1)
        cv2.circle(annotated, end, 10, (0, 255, 255), -1)

        # Extrapolate
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        ext_end = (int(start[0] + dx * 1.3), int(start[1] + dy * 1.3))

        # Draw extrapolation
        for t in np.linspace(0, 1, 10):
            pt = (int(end[0] + t * (ext_end[0] - end[0])),
                  int(end[1] + t * (ext_end[1] - end[1])))
            cv2.circle(annotated, pt, 3, (0, 0, 255), -1)

        # Draw spell positions
        for i in range(11):
            t = i / 10
            spell_pos = (int(start[0] + t * (ext_end[0] - start[0])),
                        int(start[1] + t * (ext_end[1] - start[1])))
            cv2.drawMarker(annotated, spell_pos, (255, 0, 255),
                          cv2.MARKER_TILTED_CROSS, 15, 2)

    # Add legend
    legend_y = 30
    cv2.putText(annotated, "MASK ANALYSIS", (10, legend_y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    legend_y += 35
    cv2.putText(annotated, f"Valid: {len(valid_segments)} | Filtered: {sum(filtered_segments.values())}",
               (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Save result
    output_path = mask_path.replace('.png', '_analyzed.png')
    cv2.imwrite(output_path, annotated)
    print(f"\n✓ Saved analysis: {output_path}")

    # Display
    cv2.imshow("Mask Analysis", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("="*70 + "\n")

def main():
    print("\nMask Analyzer - Analyze arrow detection from mask images")
    print("Usage: python debug_analyze_mask.py [path_to_mask.png]")
    print("="*70)

    if len(sys.argv) > 1:
        mask_path = sys.argv[1]
    else:
        mask_path = "mask_sample.png"
        print(f"\nNo image specified, using default: {mask_path}")

    if not os.path.exists(mask_path):
        print(f"\nERROR: Image not found: {mask_path}")
        print("\nPlease provide a mask image:")
        print("  python debug_analyze_mask.py path/to/mask.png")
        print("\nOr save a mask as 'mask_sample.png' in the bot directory")
        return

    analyze_mask_image(mask_path)

if __name__ == "__main__":
    main()
