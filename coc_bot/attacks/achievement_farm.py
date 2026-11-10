"""Achievement farming: target specific defensive buildings with spells."""

import random
import time

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.attacks.common import skip_base
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import find_building_clusters, get_cluster_center
from coc_bot.humanized_input import fast_click
from coc_bot.input.win32 import turbo_fast_click, turbo_move_cursor
from coc_bot.overlay import overlay_clear, overlay_draw_spell_target, overlay_update
from coc_bot.vision.buildings import detect_achievement_building, detect_all_achievement_buildings
from coc_bot.vision.screens import wait_for_attack_screen_ready


def perform_achievement_farm_attack():
    """Perform Achievement Farm attack with 3 targeting modes: Target, Clumps, First Detected"""
    print("=== ENTERING ACHIEVEMENT FARM MODE ===")
    send_discord_debug_log("=== ENTERING ACHIEVEMENT FARM MODE ===")
    runtime.gui.log_message("Achievement Farm mode activated")

    # Get current settings from GUI
    settings = runtime.gui.get_settings()

    # Get priority building type, targeting mode, and priority list from settings
    priority_building = settings.get("achievement_target_building", "eagle_artillery")
    target_mode = settings.get("achievement_farm_target_mode", "clumps")
    priority_list = settings.get(
        "achievement_priority_list",
        [
            "eagle_artillery",
            "monolith",
            "xbow",
            "inferno_tower",
            "scattershot",
            "spell_tower",
            "multi_archer_tower",
            "ricochet_cannon",
            "firespitter",
            "multi_gear_tower",
        ],
    )

    # Build list of enabled buildings from checkboxes
    # Uses full key names: achievement_scan_eagle_artillery, achievement_scan_inferno_tower, etc.
    enabled_buildings = []
    building_types = [
        "eagle_artillery",
        "monolith",
        "xbow",
        "inferno_tower",
        "scattershot",
        "spell_tower",
        "multi_archer_tower",
        "ricochet_cannon",
        "firespitter",
        "multi_gear_tower",
    ]
    for bt in building_types:
        if settings.get(f"achievement_scan_{bt}", True):
            enabled_buildings.append(bt)

    if not enabled_buildings:
        print("[ACH FARM] ERROR: No buildings enabled for scanning! Please enable at least one building type.")
        runtime.gui.log_message("No buildings enabled - aborting")
        send_discord_debug_log("Achievement Farm: No buildings enabled for scanning", "ERROR")
        return False

    print(f"Targeting Mode: {target_mode.replace('_', ' ').title()}")
    print(f"Priority target: {priority_building.replace('_', ' ').title()}")
    print(f"Enabled buildings: {', '.join([b.replace('_', ' ').title() for b in enabled_buildings])}")
    runtime.gui.log_message(f"Mode: {target_mode.replace('_', ' ').title()}")
    send_discord_debug_log(
        f"Achievement Farm: Mode={target_mode}, Target={priority_building.replace('_', ' ')}, Enabled={len(enabled_buildings)}"
    )

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[ACH FARM] Attack screen not ready - skipping base")
        send_discord_debug_log("Achievement Farm: Attack screen timeout - skipping", "WARNING")
        runtime.gui.log_message("Achievement Farm: Attack screen timeout - skipping")
        skip_base()
        return False

    # Attack screen verified ready, preparing to scan...
    print("[ACH FARM] Attack screen ready, preparing to scan...")
    time.sleep(0.1)  # Short delay before zoom

    # Zoom out BEFORE template matching for better detection and speed
    print("[ACH FARM] Zooming out before template matching...")
    pyautogui.moveTo(1280, 700, duration=0)
    time.sleep(0.1)
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.2)
    print("[ACH FARM] Zoom complete, starting template matching...")

    # Determine attack target based on targeting mode
    x, y = None, None

    if target_mode == "target":
        # MODE 1: Target - Try buildings in priority order until one is found
        print("[TARGET MODE] Trying buildings in priority order...")

        # Filter priority list to only include enabled buildings
        priority_enabled = [b for b in priority_list if b in enabled_buildings]

        if not priority_enabled:
            print("[TARGET MODE] No enabled buildings in priority list!")
            runtime.gui.log_message("No enabled buildings - surrendering")
            send_discord_debug_log("Achievement Farm [TARGET]: No enabled buildings", "WARNING")
            # Surrender immediately
            fast_click(152, 1136)
            time.sleep(0.3)
            fast_click(1483, 898)
            time.sleep(0.3)
            fast_click(*config.RETURN_BUTTON)
            time.sleep(1.5)
            runtime.skipped_bases += 1
            return False

        # Try each building in priority order
        overlay_clear()  # Clear overlay before scanning
        found = False
        for building_type in priority_enabled:
            print(f"  Trying: {building_type.replace('_', ' ').title()}...", end=" ")
            buildings = detect_achievement_building(building_type)
            if buildings:
                x, y, confidence = buildings[0]
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                x = x + bw // 2
                y = y + bh // 2
                print(f"FOUND at center ({x}, {y})")
                runtime.gui.log_message(f"Target {building_type.replace('_', ' ')} found - attacking!")
                send_discord_debug_log(f"Achievement Farm [TARGET]: {building_type.replace('_', ' ')} at ({x}, {y})")
                # Draw spell target on overlay at building center
                overlay_draw_spell_target(x, y, f"TARGET: {building_type.replace('_', ' ')}")
                found = True
                break
            else:
                print("not found")

        if not found:
            print("[TARGET MODE] No buildings detected in priority list - skipping base")
            runtime.gui.log_message("No targets found - skipping base")
            send_discord_debug_log("Achievement Farm [TARGET]: No buildings found - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            runtime.skipped_bases += 1
            return False  # Continue to next base

    elif target_mode == "first_detected":
        # MODE 3: First Detected - FAST MODE: Stop scanning as soon as ANY building is found (PRIORITY ORDER)
        print("[FIRST DETECTED MODE] Scanning in priority order for first match...")
        overlay_clear()  # Clear overlay before scanning

        # Filter priority list to only include enabled buildings
        priority_enabled = [b for b in priority_list if b in enabled_buildings]

        # Scan in PRIORITY ORDER and stop at first match
        found_building = None
        found_type = None

        for building_type in priority_enabled:
            buildings = detect_achievement_building(building_type)
            if buildings:
                # FOUND! Stop scanning immediately
                found_building = buildings[0]
                found_type = building_type
                break

        if found_building:
            x, y, confidence = found_building
            # Calculate building center using actual template size
            bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(found_type, (70, 70))
            x = x + bw // 2
            y = y + bh // 2
            print(
                f"FIRST DETECTED: {found_type.replace('_', ' ').title()} at center ({x}, {y}) - Confidence: {confidence:.3f}"
            )
            runtime.gui.log_message(f"First detected: {found_type.replace('_', ' ')} - attacking!")
            send_discord_debug_log(f"Achievement Farm [FIRST]: {found_type.replace('_', ' ')} at ({x}, {y})")
            # Draw spell target on overlay at building center
            overlay_draw_spell_target(x, y, f"FIRST: {found_type.replace('_', ' ')}")
        else:
            print("No buildings detected after scanning priority list - skipping base")
            runtime.gui.log_message("No buildings detected - skipping base")
            send_discord_debug_log("Achievement Farm [FIRST]: No buildings detected - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            runtime.skipped_bases += 1
            return False

    else:  # target_mode == 'clumps'
        # MODE 2: Clumps - Look for clusters, prefer priority building if no cluster
        print("[CLUMPS MODE] Scanning enabled building types for clusters...")
        overlay_clear()  # Clear overlay before scanning
        if runtime.gui.overlay and runtime.gui.overlay_enabled:
            runtime.gui.overlay.draw_text(100, 50, "CLUMPS MODE: Scanning all building types...", "#FFFF00")
            runtime.gui.overlay.update()
        all_buildings = detect_all_achievement_buildings(enabled_buildings)

        if not all_buildings:
            print("No achievement buildings found - skipping base")
            runtime.gui.log_message("No achievement buildings found - skipping base")
            send_discord_debug_log("Achievement Farm [CLUMPS]: No buildings found - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            runtime.skipped_bases += 1
            return False  # Continue to next base

        # Combine all buildings into single list with type labels
        combined_buildings = []
        for building_type, buildings in all_buildings.items():
            for bx, by, conf in buildings:
                combined_buildings.append((bx, by, conf, building_type))

        print(f"Found {len(combined_buildings)} total building(s)")

        # Look for clusters (pass buildings with types for accurate center-to-center distance)
        clusters = find_building_clusters(combined_buildings, max_distance=125)

        if len(clusters) > 0 and len(clusters[0]) >= 2:
            # Attack the biggest cluster
            biggest_cluster = clusters[0]
            x, y = get_cluster_center(biggest_cluster)

            # Identify building types in cluster (now directly available in cluster data)
            cluster_types = {}
            for cx, cy, cconf, ctype in biggest_cluster:
                cluster_types[ctype] = cluster_types.get(ctype, 0) + 1

            type_summary = ", ".join([f"{count} {btype.replace('_', ' ')}" for btype, count in cluster_types.items()])

            print(f"CLUSTER FOUND: {len(biggest_cluster)} buildings clustered together!")
            print(f"  Cluster contains: {type_summary}")
            print(f"  Attack center: ({x}, {y})")
            runtime.gui.log_message(f"Cluster: {type_summary} - attacking all!")
            send_discord_debug_log(f"Achievement Farm [CLUMPS]: {type_summary} at ({x}, {y})")
            # Draw cluster center on overlay
            overlay_draw_spell_target(x, y, f"CLUSTER ({len(biggest_cluster)})")
        else:
            # No cluster - select building based on priority list order
            print("No cluster found, selecting highest priority building...")

            # Filter priority list to only buildings that were actually found
            found_building_types = list(all_buildings.keys())
            priority_enabled = [b for b in priority_list if b in found_building_types]

            # Attack the highest priority building that was found
            target_building = None
            target_type = None

            if priority_enabled:
                target_type = priority_enabled[0]  # Highest priority
                target_building = all_buildings[target_type][0]  # Highest confidence of that type
                x, y, confidence = target_building
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(target_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                print(
                    f"PRIORITY TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}"
                )
                runtime.gui.log_message(
                    f"Single {target_type.replace('_', ' ')} (priority #{priority_list.index(target_type) + 1}) - attacking"
                )
                send_discord_debug_log(
                    f"Achievement Farm [CLUMPS-PRIORITY]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})"
                )
                # Draw priority target on overlay at building center
                overlay_draw_spell_target(center_x, center_y, f"PRIORITY: {target_type.replace('_', ' ')}")
                # Update x, y to center for spell casting
                x, y = center_x, center_y
            else:
                # Fallback: attack any found building (shouldn't happen)
                target_type = list(all_buildings.keys())[0]
                x, y, confidence = all_buildings[target_type][0]
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(target_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                print(
                    f"FALLBACK TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}"
                )
                runtime.gui.log_message(f"Single {target_type.replace('_', ' ')} (fallback) - attacking")
                send_discord_debug_log(
                    f"Achievement Farm [CLUMPS-FALLBACK]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})"
                )
                # Draw fallback target on overlay at building center
                overlay_draw_spell_target(center_x, center_y, f"FALLBACK: {target_type.replace('_', ' ')}")
                # Update x, y to center for spell casting
                x, y = center_x, center_y

    # Update overlay to show all detections and target before attacking
    overlay_update()

    # Deploy spells on target - ULTRA FAST using Windows API (~12 CPS)
    # 1 Earthquake spell (hotkey A) + 10 Lightning spells (hotkey S)
    SPELL_CLICK_DELAY_MS = 83  # ~12 CPS for spell casting

    print(f"[ACH FARM] Deploying 1 Earthquake + 10 Lightning spells at ({x}, {y}) using Windows API (~12 CPS)...")
    spell_start = time.time()

    # Earthquake spell
    keyboard.send("a")
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)
    turbo_move_cursor(x, y)
    turbo_fast_click()
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    # Lightning spells - Windows API fast clicks (tight spread)
    for i in range(10):
        keyboard.send("s")
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)
        spell_x = x + random.randint(-3, 3)
        spell_y = y + random.randint(-3, 3)
        turbo_move_cursor(spell_x, spell_y)
        turbo_fast_click()
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    spell_elapsed = time.time() - spell_start
    print(f"[ACH FARM] Cast 11 spells in {spell_elapsed * 1000:.0f}ms (~{11 / spell_elapsed:.0f} CPS)")

    print("[ACH FARM] All spells deployed - surrendering...")
    runtime.gui.log_message("Spells deployed - surrendering")
    send_discord_debug_log("Achievement Farm: All spells deployed - surrendering")

    time.sleep(0.3)  # Reduced wait time

    # Surrender - ULTRA FAST
    fast_click(152, 1136)
    time.sleep(0.2)
    fast_click(1483, 898)
    time.sleep(0.2)

    send_discord_debug_log("Achievement Farm: Surrendered attack")
    runtime.gui.log_message("Achievement Farm: Attack surrendered")

    # Return home
    fast_click(*config.RETURN_BUTTON)
    time.sleep(1.5)

    return False  # Attack completed successfully
