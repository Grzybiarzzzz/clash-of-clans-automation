"""Template-matching detectors for buildings on the enemy base."""

import glob
import os
import time
from concurrent.futures import as_completed, ThreadPoolExecutor

import cv2
import numpy as np
from PIL import ImageGrab

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.overlay import overlay_draw_detection
from coc_bot.vision.matching import gpu_match_template

# Template cache for achievement buildings (speeds up detection by 0.5-1s per scan)
achievement_building_templates = {}


def detect_air_defenses():
    """
    Detect air defense positions in the enemy base using template matching.
    Returns list of (x, y, level, confidence) tuples sorted by priority.
    """
    air_defenses = []
    
    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    
    # Check if templates directory exists
    if not os.path.exists(config.AIR_DEFENSE_TEMPLATES_DIR):
        print(f"Air defense templates directory not found: {config.AIR_DEFENSE_TEMPLATES_DIR}")
        send_discord_debug_log(f"Air defense templates directory not found: {config.AIR_DEFENSE_TEMPLATES_DIR}", "WARNING")
        return air_defenses
    
    print(f"Testing {len([f for f in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])} templates...")
    send_discord_debug_log(f"Testing {len([f for f in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])} air defense templates")
    
    # Load and match each template
    for template_file in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(config.AIR_DEFENSE_TEMPLATES_DIR, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                print(f"Failed to load template: {template_file}")
                send_discord_debug_log(f"Failed to load air defense template: {template_file}", "WARNING")
                continue
                
            # Perform template matching
            result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= config.AIR_DEFENSE_DETECTION_THRESHOLD)
            
            # Extract level from filename (e.g., "air_defense_level_5.png" -> 5)
            level = 1  # default
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Add detected positions
            matches_found = 0
            for pt in zip(*locations[::-1]):  # Switch columns and rows
                x, y = pt
                # Convert to global coordinates
                global_x = x + config.BASE_VIEW_REGION[0]
                global_y = y + config.BASE_VIEW_REGION[1]
                
                # Get confidence score
                confidence = result[y, x]
                
                air_defenses.append((global_x, global_y, level, confidence))
                matches_found += 1
            
            if matches_found > 0:
                print(f"  {template_file}: {matches_found} matches (max conf: {np.max(result):.3f})")
                send_discord_debug_log(f"Air defense {template_file}: {matches_found} matches (max conf: {np.max(result):.3f})")
            else:
                max_conf = np.max(result)
                print(f"  {template_file}: No matches (max conf: {max_conf:.3f})")
    
    # Remove duplicates (positions too close to each other)
    filtered_defenses = []
    for defense in air_defenses:
        x, y, level, conf = defense
        is_duplicate = False
        for existing in filtered_defenses:
            ex, ey, _, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates (increased from 50)
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_defenses.append(defense)

    # Sort by priority (higher level = higher priority, then by confidence)
    filtered_defenses.sort(key=lambda x: (config.AIR_DEFENSE_PRIORITY.get(f'level_{x[2]}', 1), x[3]), reverse=True)

    # If more than max count detected, prioritize by confidence score
    if len(filtered_defenses) > config.AIR_DEFENSE_MAX_COUNT:
        print(f"Detected {len(filtered_defenses)} air defenses, targeting top {config.AIR_DEFENSE_MAX_COUNT} by confidence")
        send_discord_debug_log(f"Detected {len(filtered_defenses)} air defenses, targeting top {config.AIR_DEFENSE_MAX_COUNT} by confidence")
        # Re-sort by confidence score (highest first)
        filtered_defenses.sort(key=lambda x: x[3], reverse=True)

    send_discord_debug_log(f"Air defense detection completed: {len(filtered_defenses)} defenses found")

    # Draw air defense detections on overlay
    result = filtered_defenses[:config.AIR_DEFENSE_MAX_COUNT]
    for x, y, level, conf in result:
        overlay_draw_detection(x, y, 60, 60, "Air Defense", level, conf,
                               config.OVERLAY_COLORS.get('air_defense', '#FF4444'))

    return result


def load_achievement_building_templates():
    """
    Pre-load all achievement building templates into memory for faster detection.
    Called once at bot startup to avoid repeated disk I/O during attacks.

    Returns:
        dict: Template cache with structure {building_type: [(template_cv, filename), ...]}
    """
    global achievement_building_templates

    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot', 'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
    templates_loaded = 0

    print("[TEMPLATE CACHE] Loading achievement building templates...")

    for building_type in building_types:
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"[TEMPLATE CACHE] Warning: {building_type} templates directory not found")
            achievement_building_templates[building_type] = []
            continue

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"[TEMPLATE CACHE] No {building_type} templates found")
            achievement_building_templates[building_type] = []
            continue

        # Load all templates for this building type
        templates = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)

            if template is not None:
                templates.append((template, template_file))
                templates_loaded += 1

        achievement_building_templates[building_type] = templates
        print(f"[TEMPLATE CACHE] Loaded {len(templates)} {building_type.replace('_', ' ')} templates")

    print(f"[TEMPLATE CACHE] ✓ Template cache ready: {templates_loaded} total templates loaded")
    print(f"[TEMPLATE CACHE] Cache size: {sum(len(t) for t in achievement_building_templates.values())} templates")

    return achievement_building_templates


def detect_achievement_building(building_type):
    """
    Detect ALL achievement buildings (Eagle, Monolith, X-Bow, Inferno, Scattershot) using template matching.
    OPTIMIZED: Uses pre-loaded template cache instead of disk I/O (saves ~0.5-1s per scan).

    Args:
        building_type: Type of building ('eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot')

    Returns:
        List of (x, y, confidence) tuples for all detected buildings, or empty list if none found
    """
    global achievement_building_templates

    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # Use cached templates (or fall back to loading from disk if cache empty)
    if building_type in achievement_building_templates and achievement_building_templates[building_type]:
        templates_list = achievement_building_templates[building_type]
        print(f"Testing {len(templates_list)} {building_type.replace('_', ' ')} templates (cached)...")
        send_discord_debug_log(f"Testing {len(templates_list)} {building_type.replace('_', ' ')} templates (cached)")
    else:
        # Fallback: load from disk if cache not available
        print(f"[WARNING] Template cache miss for {building_type}, loading from disk...")
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"{building_type.replace('_', ' ').title()} templates directory not found: {templates_dir}")
            send_discord_debug_log(f"{building_type.replace('_', ' ').title()} templates directory not found: {templates_dir}", "WARNING")
            return []

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"No {building_type.replace('_', ' ')} templates found")
            return []

        # Load templates on-the-fly
        templates_list = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            if template is not None:
                templates_list.append((template, template_file))

    all_buildings = []

    # Match each template (now using cached templates)
    for template, template_name in templates_list:

        # Perform template matching (GPU if available, else CPU)
        result = gpu_match_template(base_cv, template)

        # Detection threshold lowered to 0.6 for visualization (0.7+ used for attacks)
        threshold = 0.6
        locations = np.where(result >= threshold)

        # Add all detected positions
        for pt in zip(*locations[::-1]):  # Switch columns and rows
            x, y = pt
            # Convert to global coordinates
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]

            # Get confidence score
            confidence = result[y, x]

            all_buildings.append((global_x, global_y, confidence))

    # Sort by confidence FIRST (so higher confidence detections get priority in duplicate filtering)
    all_buildings.sort(key=lambda x: x[2], reverse=True)

    # Remove duplicates (positions too close to each other) - higher confidence kept
    filtered_buildings = []
    for building in all_buildings:
        x, y, conf = building
        is_duplicate = False
        for existing in filtered_buildings:
            ex, ey, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_buildings.append(building)

    # Get actual template size for this building type
    box_w, box_h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))

    # Get building-specific threshold (default 0.7)
    high_threshold = config.ACHIEVEMENT_BUILDING_THRESHOLDS.get(building_type, 0.7)

    # Separate high confidence and low confidence buildings
    high_conf_buildings = [b for b in filtered_buildings if b[2] >= high_threshold]
    low_conf_buildings = [b for b in filtered_buildings if 0.6 <= b[2] < high_threshold]

    # Draw LOW confidence buildings in RED (for debugging threshold tuning)
    # Check if user wants to hide low confidence detections
    hide_low_conf = runtime.gui.get_settings().get('overlay_hide_low_conf', False) if runtime.gui else False
    if not hide_low_conf:
        for x, y, conf in low_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, f"{building_type.replace('_', ' ').title()} (LOW)", None, conf,
                                   config.OVERLAY_COLORS.get('achievement_low', '#FF0000'))

    # Draw HIGH confidence buildings in CYAN (these are used for attacks)
    if high_conf_buildings:
        print(f"{building_type.replace('_', ' ').title()}: {len(high_conf_buildings)} building(s) detected")
        for i, (x, y, conf) in enumerate(high_conf_buildings):
            print(f"  {i+1}. Position ({x}, {y}) - Confidence: {conf:.3f}")
            overlay_draw_detection(x, y, box_w, box_h, building_type.replace('_', ' ').title(), None, conf,
                                   config.OVERLAY_COLORS.get('achievement', '#00FFFF'))
        if low_conf_buildings:
            print(f"  + {len(low_conf_buildings)} low-confidence detections (0.6-{high_threshold}) shown in red")
        send_discord_debug_log(f"{building_type.replace('_', ' ').title()}: {len(high_conf_buildings)} detected")
    else:
        print(f"{building_type.replace('_', ' ').title()}: No buildings detected (>= {high_threshold})")
        if low_conf_buildings:
            print(f"  Note: {len(low_conf_buildings)} low-confidence detections (0.6-{high_threshold}) shown in red")
        send_discord_debug_log(f"{building_type.replace('_', ' ').title()}: No buildings detected")

    # Only return high confidence buildings for attack logic
    return high_conf_buildings


def detect_achievement_building_from_image(building_type, base_cv):
    """
    Detect achievement buildings from a pre-captured screenshot (for parallel processing).

    Args:
        building_type: Type of building to detect
        base_cv: Pre-captured base screenshot in OpenCV format

    Returns:
        List of (x, y, confidence) tuples for all detected buildings, or empty list if none found
    """
    global achievement_building_templates

    # Use cached templates (or fall back to loading from disk if cache empty)
    if building_type in achievement_building_templates and achievement_building_templates[building_type]:
        templates_list = achievement_building_templates[building_type]
        print(f"  [{building_type}] Testing {len(templates_list)} templates (cached)...")
    else:
        # Fallback: load from disk if cache not available
        print(f"  [{building_type}] WARNING: Template cache miss, loading from disk...")
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"  [{building_type}] Templates directory not found: {templates_dir}")
            return []

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"  [{building_type}] No templates found")
            return []

        # Load templates on-the-fly
        templates_list = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            if template is not None:
                templates_list.append((template, template_file))

    all_buildings = []

    # Match each template
    for template, template_name in templates_list:
        # Perform template matching (GPU if available, else CPU)
        result = gpu_match_template(base_cv, template)

        # Detection threshold lowered to 0.6 for visualization (0.7+ used for attacks)
        threshold = 0.6
        locations = np.where(result >= threshold)

        # Add all detected positions
        for pt in zip(*locations[::-1]):
            x, y = pt
            # Convert to global coordinates
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]

            # Get confidence score
            confidence = result[y, x]

            all_buildings.append((global_x, global_y, confidence))

    # Sort by confidence FIRST (so higher confidence detections get priority in duplicate filtering)
    all_buildings.sort(key=lambda x: x[2], reverse=True)

    # Remove duplicates (positions too close to each other) - higher confidence kept
    filtered_buildings = []
    for building in all_buildings:
        x, y, conf = building
        is_duplicate = False
        for existing in filtered_buildings:
            ex, ey, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_buildings.append(building)

    # Get actual template size for this building type
    box_w, box_h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))

    # Get building-specific threshold (default 0.7)
    high_threshold = config.ACHIEVEMENT_BUILDING_THRESHOLDS.get(building_type, 0.7)

    # Separate high confidence and low confidence buildings
    high_conf_buildings = [b for b in filtered_buildings if b[2] >= high_threshold]
    low_conf_buildings = [b for b in filtered_buildings if 0.6 <= b[2] < high_threshold]

    # Draw LOW confidence buildings in RED (for debugging threshold tuning)
    # Check if user wants to hide low confidence detections
    hide_low_conf = runtime.gui.get_settings().get('overlay_hide_low_conf', False) if runtime.gui else False
    if not hide_low_conf:
        for x, y, conf in low_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, f"{building_type.replace('_', ' ').title()} (LOW)", None, conf,
                                   config.OVERLAY_COLORS.get('achievement_low', '#FF0000'))

    # Draw HIGH confidence buildings in CYAN (these are used for attacks)
    if high_conf_buildings:
        print(f"  [{building_type}] {len(high_conf_buildings)} building(s) detected")
        for x, y, conf in high_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, building_type.replace('_', ' ').title(), None, conf,
                                   config.OVERLAY_COLORS.get('achievement', '#00FFFF'))
        if low_conf_buildings:
            print(f"  [{building_type}] + {len(low_conf_buildings)} low-confidence (0.6-{high_threshold}) shown in red")
    else:
        print(f"  [{building_type}] No buildings detected (>= {high_threshold})")
        if low_conf_buildings:
            print(f"  [{building_type}] Note: {len(low_conf_buildings)} low-confidence (0.6-{high_threshold}) shown in red")

    # Only return high confidence buildings for attack logic
    return high_conf_buildings


def detect_town_hall():
    """
    Detect Town Hall level in the enemy base using template matching.
    Returns (x, y, level, confidence) tuple or None if not found.
    """
    # Capture the Town Hall region
    th_img = ImageGrab.grab(bbox=config.TOWN_HALL_REGION)
    th_cv = cv2.cvtColor(np.array(th_img), cv2.COLOR_RGB2BGR)
    
    # Check if templates directory exists
    if not os.path.exists(config.TOWN_HALL_TEMPLATES_DIR):
        print(f"Town Hall templates directory not found: {config.TOWN_HALL_TEMPLATES_DIR}")
        send_discord_debug_log(f"Town Hall templates directory not found: {config.TOWN_HALL_TEMPLATES_DIR}", "WARNING")
        return None
    
    best_match = None
    best_confidence = 0
    
    # Load and match each template
    for template_file in os.listdir(config.TOWN_HALL_TEMPLATES_DIR):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(config.TOWN_HALL_TEMPLATES_DIR, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                continue
                
            # Perform template matching
            result = cv2.matchTemplate(th_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # Extract level from filename (e.g., "town_hall_level_12.png" -> 12)
            level = 1  # default
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Check if this is the best match so far
            if max_val >= config.TOWN_HALL_DETECTION_THRESHOLD and max_val > best_confidence:
                x, y = max_loc
                # Convert to global coordinates
                global_x = x + config.TOWN_HALL_REGION[0]
                global_y = y + config.TOWN_HALL_REGION[1]
                
                best_match = (global_x, global_y, level, max_val)
                best_confidence = max_val
    
    if best_match:
        x, y, level, conf = best_match
        send_discord_debug_log(f"Town Hall Level {level} detected at ({x}, {y}) with confidence {conf:.3f}")
        # Draw town hall detection on overlay (100x100 bounding box for TH)
        overlay_draw_detection(x, y, 100, 100, "Town Hall", level, conf,
                               config.OVERLAY_COLORS.get('town_hall', '#AA00FF'))
    else:
        send_discord_debug_log("No Town Hall detected", "WARNING")

    return best_match


def detect_air_sweepers():
    """
    Detect air sweepers in the base using template matching for all 8 directions.
    Returns a list of (x, y, direction, confidence) tuples.
    """
    sweepers = []
    templates_dir = "screenshots/reference/air_sweepers"
    if not os.path.exists(templates_dir):
        print(f"Air sweeper templates directory not found: {templates_dir}")
        return sweepers
    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    # For each template (direction)
    for template_path in glob.glob(os.path.join(templates_dir, "air_sweeper_*.png")):
        direction = os.path.splitext(os.path.basename(template_path))[0].replace("air_sweeper_", "")
        template = cv2.imread(template_path)
        if template is None:
            continue
        result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= 0.7)  # Threshold can be adjusted
        for pt in zip(*locations[::-1]):
            x, y = pt
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]
            confidence = result[y, x]
            sweepers.append((global_x, global_y, direction, confidence))
    # Remove duplicates (positions too close)
    filtered = []
    for sw in sweepers:
        x, y, direction, conf = sw
        is_dup = False
        for ex in filtered:
            ex_x, ex_y, _, _ = ex
            if ((x - ex_x) ** 2 + (y - ex_y) ** 2) ** 0.5 < 50:
                is_dup = True
                break
        if not is_dup:
            filtered.append(sw)
    # Sort by confidence
    filtered.sort(key=lambda x: x[3], reverse=True)
    # Return up to 2 sweepers
    return filtered[:2]


def detect_all_achievement_buildings(enabled_buildings=None):
    """
    Detect achievement building types on the base using PARALLEL template matching.
    All building types are scanned simultaneously for maximum speed.

    Args:
        enabled_buildings: List of building types to scan. If None, scans all types.

    Returns:
        Dictionary with building type as key and list of (x, y, confidence) tuples as value
    """
    if enabled_buildings is None:
        enabled_buildings = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot', 'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    print(f"[PARALLEL SCAN] Scanning {len(enabled_buildings)} building types simultaneously...")
    start_time = time.time()

    # Capture base screenshot ONCE (shared by all threads)
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    results = {}
    total_found = 0

    # Use ThreadPoolExecutor to scan all building types in parallel (max 5 workers to reduce CPU usage)
    with ThreadPoolExecutor(max_workers=min(5, len(enabled_buildings))) as executor:
        # Submit all detection tasks
        future_to_building = {
            executor.submit(detect_achievement_building_from_image, building_type, base_cv): building_type
            for building_type in enabled_buildings
        }

        # Collect results as they complete
        for future in as_completed(future_to_building):
            building_type = future_to_building[future]
            try:
                buildings = future.result()
                if buildings:
                    results[building_type] = buildings
                    total_found += len(buildings)
                    print(f"  ✓ {building_type.replace('_', ' ')}: {len(buildings)} found")
                else:
                    print(f"  - {building_type.replace('_', ' ')}: none found")
            except Exception as e:
                print(f"  ✗ {building_type.replace('_', ' ')}: ERROR - {str(e)}")
                send_discord_debug_log(f"Error detecting {building_type}: {str(e)}", "ERROR")

    elapsed_time = time.time() - start_time
    print(f"[PARALLEL SCAN] Complete in {elapsed_time:.2f}s - Total found: {total_found}")
    send_discord_debug_log(f"Parallel scan complete: {total_found} buildings in {elapsed_time:.2f}s")

    return results


def _scan_achievement_buildings_parallel_internal(settings):
    """
    INTERNAL: Scan achievement buildings in parallel and return highest-priority match.

    This is the internal parallel implementation used when user enables parallel scanning.
    Scans all enabled achievement building types simultaneously using ThreadPoolExecutor.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for highest-priority building found,
        or None if no buildings detected
    """
    # 1. Extract enabled buildings from checkboxes
    enabled_buildings = []
    all_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower',
                 'scattershot', 'spell_tower', 'multi_archer_tower',
                 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    for building_type in all_types:
        checkbox_key = f'achievement_scan_{building_type}'
        if settings.get(checkbox_key, True):  # Default enabled if not found
            enabled_buildings.append(building_type)

    if not enabled_buildings:
        print("[PARALLEL SCAN] No achievement buildings enabled in settings")
        return None

    print(f"[PARALLEL SCAN] Scanning {len(enabled_buildings)} enabled building types in parallel...")

    # 2. Get priority list from settings
    priority_list = settings.get('achievement_priority_list', all_types)

    # 3. Filter to only enabled buildings in priority order
    priority_enabled = [b for b in priority_list if b in enabled_buildings]

    # 4. Parallel scan using existing function (scans all types simultaneously)
    all_buildings = detect_all_achievement_buildings(enabled_buildings)

    if not all_buildings:
        print("[PARALLEL SCAN] No achievement buildings detected on base")
        return None

    # 5. Select highest-priority building from results
    for building_type in priority_enabled:
        if building_type in all_buildings and all_buildings[building_type]:
            # Get highest confidence match of this type
            best_match = max(all_buildings[building_type], key=lambda x: x[2])
            x, y, confidence = best_match
            print(f"[PARALLEL SCAN] Selected: {building_type.replace('_', ' ').title()} (Priority #{priority_enabled.index(building_type)+1}, Confidence: {confidence:.3f})")
            return (x, y, confidence, building_type)

    # Fallback: return highest confidence overall (shouldn't happen if priority list is complete)
    best_overall = None
    best_conf = 0
    best_type = None
    for btype, matches in all_buildings.items():
        for match in matches:
            if match[2] > best_conf:
                best_overall = match
                best_conf = match[2]
                best_type = btype

    if best_overall:
        print(f"[PARALLEL SCAN] Fallback: Selected {best_type.replace('_', ' ').title()} (highest confidence: {best_conf:.3f})")
        return (best_overall[0], best_overall[1], best_overall[2], best_type)

    return None


def scan_achievement_buildings_parallel_priority(settings):
    """
    Scan achievement buildings using user's preferred method (parallel or sequential).

    Checks GUI setting 'achievement_parallel_scan' to decide:
    - True: Use parallel scanning (faster, higher CPU usage, may cause spikes/crashes)
    - False: Use sequential scanning (slower, minimal CPU usage, stable) [DEFAULT]

    This function acts as a dispatcher based on user preference.

    Used by: SBarb Farm, SGoblin Farm modes.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_parallel_scan: Boolean (default False)
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for highest-priority building found,
        or None if no buildings detected
    """
    # Check if user enabled parallel scanning (default: False for stability)
    use_parallel = settings.get('achievement_parallel_scan', False)

    if use_parallel:
        print("[SCAN MODE] Using parallel scanning (fast, higher CPU)")
        send_discord_debug_log("Achievement scan: Parallel mode (fast, higher CPU)")
        return _scan_achievement_buildings_parallel_internal(settings)
    else:
        print("[SCAN MODE] Using sequential scanning (slower, low CPU)")
        send_discord_debug_log("Achievement scan: Sequential mode (slower, low CPU)")
        return scan_achievement_buildings_sequential(settings)


def scan_achievement_buildings_sequential(settings):
    """
    Scan achievement buildings sequentially (one at a time) in priority order.

    This is slower than parallel scanning but uses minimal CPU and won't cause spikes.
    Stops at FIRST priority match found for efficiency.

    Used by: SBarb Farm, SGoblin Farm when parallel scanning is disabled.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for first priority building found,
        or None if no buildings detected
    """
    # 1. Extract enabled buildings from checkboxes
    enabled_buildings = []
    all_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower',
                 'scattershot', 'spell_tower', 'multi_archer_tower',
                 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    for building_type in all_types:
        checkbox_key = f'achievement_scan_{building_type}'
        if settings.get(checkbox_key, True):
            enabled_buildings.append(building_type)

    if not enabled_buildings:
        print("[SEQUENTIAL SCAN] No achievement buildings enabled in settings")
        return None

    # 2. Get priority list from settings
    priority_list = settings.get('achievement_priority_list', all_types)

    # 3. Filter to only enabled buildings in priority order
    priority_enabled = [b for b in priority_list if b in enabled_buildings]

    print(f"[SEQUENTIAL SCAN] Scanning {len(priority_enabled)} enabled buildings in priority order...")
    send_discord_debug_log(f"Sequential scan: checking {len(priority_enabled)} building types")

    # 4. Capture screenshot ONCE (shared for all detections)
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # 5. Scan each building type sequentially (one at a time)
    for i, building_type in enumerate(priority_enabled):
        print(f"  [{i+1}/{len(priority_enabled)}] Checking {building_type.replace('_', ' ')}...")

        # Call detection function with shared screenshot
        buildings = detect_achievement_building_from_image(building_type, base_cv)

        if buildings:
            # FOUND! Return first match immediately (early exit)
            best_match = max(buildings, key=lambda x: x[2])  # Highest confidence
            x, y, confidence = best_match
            print(f"  ✓ FOUND! {building_type.replace('_', ' ').title()} (Priority #{i+1}, Confidence: {confidence:.3f})")
            send_discord_debug_log(f"Sequential scan found: {building_type} (priority #{i+1})")
            return (x, y, confidence, building_type)
        else:
            print(f"  ✗ Not found, continuing...")

    print("[SEQUENTIAL SCAN] No achievement buildings detected")
    send_discord_debug_log("Sequential scan: no buildings found")
    return None
