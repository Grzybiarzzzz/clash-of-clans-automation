"""Super Barbarian farming routine."""

import os
import random
import threading
import time
from datetime import datetime

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.attacks.common import skip_base
from coc_bot.attacks.sbarb_stages import (
    cast_spells_after_deployment,
    deploy_army_first_wave,
    deploy_heroes_first_wave,
    deploy_second_wave,
    deploy_turbo,
    end_battle,
    return_home,
)
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import (
    calculate_deployment_step,
    find_building_clusters,
    get_cluster_center,
    get_opposite_side,
)
from coc_bot.overlay import overlay_clear
from coc_bot.vision.buildings import (
    detect_all_achievement_buildings,
    scan_achievement_buildings_parallel_priority,
)
from coc_bot.vision.ocr import detect_destruction_percentage
from coc_bot.vision.screens import (
    detect_return_home_button,
    detect_surrender_or_end_battle,
    wait_for_attack_screen_ready,
)


def handle_sbarb_farm_mode():
    """
    Handle SBarb Farm mode - deploy Super Barbarians on two sides, throw 11 earthquake spells randomly,
    surrender when 50% destruction reached (or 60s timeout).
    Optimized for speed and efficiency - no base evaluation, no defense/TH detection, attacks first base immediately.
    """
    send_discord_debug_log("SBarb Farm mode: starting attack")
    runtime.gui.log_message("SBarb Farm: starting attack")

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[SBARB FARM] Attack screen not ready - skipping base")
        send_discord_debug_log("SBarb Farm: Attack screen timeout - skipping", "WARNING")
        runtime.gui.log_message("SBarb Farm: Attack screen timeout - skipping")
        skip_base()
        return False

    # Zoom out NOW that we're in attack screen (BEFORE any camera movement)
    print("[SBARB FARM] Zooming out...")
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    # Zoom out aggressively - 5 scrolls of -300
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.1)  # Reduced wait for zoom animation (optimized for speed)
    print("[SBARB FARM] Zoom complete")

    # Get settings for deployment
    settings = runtime.gui.get_settings()
    KEYS = config.KEYS
    heroes_first = settings.get("sbarb_heroes_first", False)
    turbo_deployment = settings.get("sbarb_turbo_deployment", False)

    # Achievement building destruction tracking for CSV
    building_destroyed = "None"  # Type of building destroyed (or "None")
    spells_completed = False  # True if all 10 lightning spells were cast

    # Choose two opposite sides for split deployment (only vertical - up/down)
    # Left/right has coordinate issues, restrict to top-bottom or bottom-top only
    sides = ["up", "down"]
    first_side = random.choice(sides)
    opposite_side = get_opposite_side(first_side)

    deployment_order = "Heroes First" if heroes_first else "Army First"
    print(f"[SBARB FARM] Deploying on {first_side} and {opposite_side} ({deployment_order})")
    send_discord_debug_log(f"SBarb Farm: Deploying on {first_side} and {opposite_side} ({deployment_order})")

    # Draw overlay for SBarb Farm attack (no side arrow - too cluttered)
    overlay_clear()
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        runtime.gui.overlay.draw_text(
            100, 80, f"SBarb Farm: {first_side.upper()} then {opposite_side.upper()}", "#FFFF00"
        )
        runtime.gui.overlay.draw_text(100, 110, f"Mode: {deployment_order}", "#FFFF00")
        runtime.gui.overlay.update()

    # Move camera to first side - ULTRA FAST for SBarb Farm (skip camera movement delays)
    # Ensure zoom is complete before dragging (don't drag during zoom - it blocks zoom)
    time.sleep(0.1)  # Extra buffer to ensure zoom fully complete before camera drag
    drag_map = {
        "left": ((600, 700), (1500, 700)),
        "right": ((2000, 700), (1000, 700)),
        "up": ((1280, 300), (1280, 900)),
        "down": ((1280, 1100), (1280, 700)),
    }
    drag_start, drag_end = drag_map[first_side]
    pyautogui.moveTo(*drag_start, duration=0)
    pyautogui.mouseDown()
    pyautogui.moveTo(*drag_end, duration=0.1)  # Fast drag
    pyautogui.mouseUp()
    time.sleep(0.1)  # Minimal delay

    # Get deployment coordinates
    first_side_coords = config.SIDE_DEPLOYMENT_COORDS[first_side]["units"]
    second_side_coords = config.SIDE_DEPLOYMENT_COORDS[opposite_side]["units"]

    # Randomize deployment direction (sometimes reverse coordinates for variety)
    if random.random() < 0.5:
        first_side_coords = list(reversed(first_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {first_side}")
    if random.random() < 0.5:
        second_side_coords = list(reversed(second_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {opposite_side}")

    # Get actual troop count from settings
    troop_counts = settings.get("troop_counts", [64, 0, 0, 0, 0, 0, 0])

    # Find which slot has Super Barbarians (first non-zero count)
    sbarb_slot_index = None
    total_troops = 0
    for i, count in enumerate(troop_counts):
        if count > 0:
            sbarb_slot_index = i
            total_troops = count
            break

    # If no troops found, default to slot 0
    if sbarb_slot_index is None:
        sbarb_slot_index = 0
        total_troops = troop_counts[0]

    # Get the hotkey for this slot
    sbarb_hotkey = KEYS[f"troop{sbarb_slot_index + 1}"]

    print(
        f"[SBARB FARM] Detected Super Barbarians in slot {sbarb_slot_index + 1}, using hotkey '{sbarb_hotkey}', count: {total_troops}"
    )

    first_half = total_troops // 2

    # Calculate deployment step for even distribution across coordinates
    first_side_step = calculate_deployment_step(first_half, len(first_side_coords))
    second_side_step = calculate_deployment_step(first_half, len(second_side_coords))

    print(f"[SBARB FARM] Deploying {total_troops} troops ({first_half} per side)")
    print(f"[SBARB FARM] Step size: {first_side_step} (first), {second_side_step} (second)")

    # Start timer for attack duration tracking (before any deployments)
    attack_start_time = time.time()

    # Get hero ability timings from GUI settings
    queen_timing = settings.get("queen_ability_timing", 1)
    king_timing = settings.get("king_ability_timing", 1)
    warden_timing = settings.get("warden_ability_timing", 1)
    rc_timing = settings.get("rc_ability_timing", 1)

    hero_timings = {"queen": queen_timing, "king": king_timing, "warden": warden_timing, "rc": rc_timing}

    # Shared flag for 50% destruction monitoring
    target_destruction = 50
    destruction_reached = {"value": False, "percentage": 0}
    max_wait_time = 60
    attack_failed_early = False  # True if Return Home detected before 50% (troops died)

    # Reset destruction percentage tracking for new attack
    detect_destruction_percentage.last_valid = None

    # Shared flag for spell casting phase (to handle hero ability re-selection)
    spell_casting_active = {"value": False}

    # Shared dict for achievement building scan results
    achievement_scan_result = {"found": False, "building": None, "type": None, "scanning": False, "completed": False}

    # Shared dict for cached surrender button position
    surrender_button_cache = {"position": None, "detected": False}

    def scan_achievement_buildings_background():
        """Background thread to scan for achievement buildings in parallel with deployment"""
        achievement_scan_result["scanning"] = True
        print("[SBARB FARM] Background achievement building scan started...")
        send_discord_debug_log("SBarb Farm: Background achievement building scan started")

        # Get settings from GUI
        settings = runtime.gui.get_settings()

        # Check if 50% already reached before scanning
        if destruction_reached["value"]:
            print("[SBARB FARM] 50% reached before scan - skipping")
            achievement_scan_result["completed"] = True
            achievement_scan_result["scanning"] = False
            return

        # Get targeting mode from settings (default: clumps for backward compatibility)
        target_mode = settings.get("sbarb_cast_spells_target_mode", "clumps")
        print(f"[SBARB FARM] Targeting mode: {target_mode.replace('_', ' ').title()}")

        if target_mode == "clumps":
            # CLUMPS MODE: Scan all enabled buildings and look for clusters
            print("[SBARB FARM] Scanning all buildings for clusters...")

            # Build list of enabled buildings from checkboxes
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
                print("[SBARB FARM] No buildings enabled for scanning")
                achievement_scan_result["completed"] = True
                achievement_scan_result["scanning"] = False
                return

            # Detect all enabled buildings
            all_buildings = detect_all_achievement_buildings(enabled_buildings)

            if not all_buildings:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log("SBarb Farm: No buildings found (clumps mode)")
                achievement_scan_result["completed"] = True
                achievement_scan_result["scanning"] = False
                return

            # Combine all buildings into single list with type labels
            combined_buildings = []
            for building_type, buildings in all_buildings.items():
                for bx, by, conf in buildings:
                    combined_buildings.append((bx, by, conf, building_type))

            print(f"[SBARB FARM] Found {len(combined_buildings)} total building(s)")

            # Look for clusters (2+ buildings within 125px)
            clusters = find_building_clusters(combined_buildings, max_distance=125)

            if len(clusters) > 0 and len(clusters[0]) >= 2:
                # Attack the biggest cluster center
                biggest_cluster = clusters[0]
                x, y = get_cluster_center(biggest_cluster)
                # Count building types in cluster for detailed logging
                cluster_type_counts = {}
                for cx, cy, cconf, ctype in biggest_cluster:
                    cluster_type_counts[ctype] = cluster_type_counts.get(ctype, 0) + 1
                cluster_types_summary = ", ".join(
                    [f"{count} {btype.replace('_', ' ')}" for btype, count in cluster_type_counts.items()]
                )
                print(f"  [BACKGROUND SCAN] ✓ CLUSTER of {len(biggest_cluster)} buildings at ({x}, {y})")
                print(f"    Types: {cluster_types_summary}")
                achievement_scan_result["found"] = True
                achievement_scan_result["building"] = (x, y, 1.0)
                achievement_scan_result["type"] = f"cluster_{len(biggest_cluster)}"
                achievement_scan_result["cluster_types"] = cluster_types_summary  # Store for CSV logging
                send_discord_debug_log(
                    f"SBarb Farm: Cluster of {len(biggest_cluster)} buildings ({cluster_types_summary}) at ({x}, {y})"
                )
            else:
                # No cluster found, use priority building
                priority_list = settings.get("achievement_priority_list", building_types)
                priority_enabled = [b for b in priority_list if b in enabled_buildings]

                for building_type in priority_enabled:
                    if building_type in all_buildings and all_buildings[building_type]:
                        bx, by, conf = all_buildings[building_type][0]
                        # Calculate center
                        bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                        x = bx + bw // 2
                        y = by + bh // 2
                        print(
                            f"  [BACKGROUND SCAN] ✓ No cluster - using priority {building_type.replace('_', ' ')} at ({x}, {y})"
                        )
                        achievement_scan_result["found"] = True
                        achievement_scan_result["building"] = (x, y, conf)
                        achievement_scan_result["type"] = building_type
                        send_discord_debug_log(f"SBarb Farm: {building_type} at ({x}, {y}) (no cluster)")
                        break
                else:
                    print("[BACKGROUND SCAN] No priority buildings found")
                    send_discord_debug_log("SBarb Farm: No priority buildings found")

        else:  # target_mode in ['target', 'first_detected']
            # TARGET/FIRST_DETECTED MODE: Scan in priority order, return first match
            result = scan_achievement_buildings_parallel_priority(settings)

            if result is not None:
                x, y, confidence, building_type = result
                # Convert top-left to center coordinates
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                achievement_scan_result["found"] = True
                achievement_scan_result["building"] = (center_x, center_y, confidence)
                achievement_scan_result["type"] = building_type
                print(
                    f"  [BACKGROUND SCAN] ✓ {building_type.replace('_', ' ')} FOUND at center ({center_x}, {center_y})! ({target_mode.replace('_', ' ')} mode)"
                )
                send_discord_debug_log(
                    f"SBarb Farm: {building_type} found at ({center_x}, {center_y}) ({target_mode} mode)"
                )
            else:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log(f"SBarb Farm: No buildings found ({target_mode} mode)")

        achievement_scan_result["completed"] = True
        achievement_scan_result["scanning"] = False

    def detect_surrender_button_early():
        """Detect and cache surrender or end battle button position early during attack"""
        if not surrender_button_cache["detected"]:
            print("[SBARB FARM] Pre-detecting surrender/end battle button position...")
            button_type, button_x, button_y = detect_surrender_or_end_battle()
            if button_type:
                surrender_button_cache["position"] = (button_x, button_y)
                surrender_button_cache["detected"] = True
                print(f"[SBARB FARM] {button_type.replace('_', ' ').title()} button cached at ({button_x}, {button_y})")
                send_discord_debug_log(f"SBarb Farm: {button_type} button pre-cached at ({button_x}, {button_y})")
            else:
                print("[SBARB FARM] Surrender/end battle button not detected yet")

    def monitor_destruction_continuous():
        """Background thread to continuously monitor destruction percentage and Return Home button"""
        nonlocal attack_failed_early

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached["value"]:
                break

            # Check for Return Home button (battle ended early - troops died before 50%)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                elapsed = time.time() - attack_start_time
                current_pct = destruction_reached.get("percentage", 0)
                print(
                    f"[SBARB FARM] Return Home detected after {elapsed:.1f}s - attack failed (troops died at {current_pct}%, before {target_destruction}%)"
                )
                runtime.gui.log_message(f"SBarb Farm: Attack failed - troops died at {current_pct}%")
                send_discord_debug_log(
                    f"SBarb Farm: Attack failed after {elapsed:.1f}s - Return Home detected at {current_pct}%",
                    "WARNING",
                )
                destruction_reached["value"] = True  # Signal main loop to stop waiting
                destruction_reached["return_home_pos"] = return_home_pos  # Cache position for faster click
                attack_failed_early = True
                break

            current_destruction = detect_destruction_percentage(save_debug_screenshots=False)
            if current_destruction is not None:
                destruction_reached["percentage"] = current_destruction
                if current_destruction >= target_destruction:
                    elapsed = time.time() - attack_start_time
                    destruction_reached["value"] = True
                    print(f"[SBARB FARM] {target_destruction}% REACHED! ({current_destruction}% after {elapsed:.1f}s)")
                    runtime.gui.log_message(f"SBarb Farm: {current_destruction}% reached - stopping deployment!")
                    send_discord_debug_log(
                        f"SBarb Farm: {current_destruction}% destruction reached after {elapsed:.1f}s"
                    )
                    break

            time.sleep(0.2)  # Check every 0.2 seconds (faster polling for quicker detection)

    # Start destruction monitoring thread
    monitor_thread = threading.Thread(target=monitor_destruction_continuous, daemon=True)
    monitor_thread.start()
    print(f"[SBARB FARM] Started background monitoring for {target_destruction}% destruction")

    # ============================================================
    # TURBO DEPLOYMENT MODE (Windows API fast-click)
    # ============================================================
    if turbo_deployment:
        building_destroyed, spells_completed = deploy_turbo(
            KEYS,
            achievement_scan_result,
            building_destroyed,
            destruction_reached,
            detect_surrender_button_early,
            first_half,
            first_side,
            hero_timings,
            opposite_side,
            sbarb_hotkey,
            scan_achievement_buildings_background,
            settings,
            spell_casting_active,
            spells_completed,
            surrender_button_cache,
        )

    # Helper function for hero ability activation (used by both turbo and standard modes)
    def activate_sbarb_hero_ability(hero_role, timing):
        """Activate hero ability after specified timing, then re-select spell or troops"""
        if timing >= 0:
            if timing > 0:
                time.sleep(timing)
            keyboard.send(KEYS[hero_role])
            print(f"[SBARB FARM] {hero_role.title()} ability activated at {timing}s")
            send_discord_debug_log(f"SBarb Farm: {hero_role.title()} ability activated at {timing}s")
            # Re-select spells or troops depending on current phase
            time.sleep(0.05)
            if spell_casting_active["value"]:
                keyboard.send("a")  # Re-select Earthquake spell
                print(f"[SBARB FARM] Re-selected Earthquake spell after {hero_role.title()} ability")
            else:
                keyboard.send(sbarb_hotkey)  # Re-select troops (dynamic slot)
                print(f"[SBARB FARM] Re-selected troops after {hero_role.title()} ability")

    # ============================================================
    # STANDARD DEPLOYMENT MODE (hold-and-drag)
    # Skip this entire section if turbo deployment was used
    # ============================================================
    # Only the heroes-first sequence can cast spells along the Queen's arrow
    queen_arrow_spells = False

    if not turbo_deployment and heroes_first:
        queen_arrow_spells = deploy_heroes_first_wave(
            KEYS,
            activate_sbarb_hero_ability,
            destruction_reached,
            first_half,
            first_side,
            first_side_coords,
            first_side_step,
            hero_timings,
            heroes_first,
            queen_timing,
            sbarb_hotkey,
            settings,
            spell_casting_active,
        )

    elif not turbo_deployment:
        # Army-first order: only when turbo deployment is disabled and heroes_first is off
        deploy_army_first_wave(
            KEYS,
            activate_sbarb_hero_ability,
            destruction_reached,
            first_half,
            first_side,
            first_side_coords,
            first_side_step,
            hero_timings,
            sbarb_hotkey,
        )

    # Check if 50% reached before moving camera for second wave
    # Skip if turbo deployment was used (already handled above)
    if not destruction_reached["value"] and not turbo_deployment:
        deploy_second_wave(
            achievement_scan_result,
            destruction_reached,
            detect_surrender_button_early,
            drag_map,
            first_half,
            opposite_side,
            sbarb_hotkey,
            scan_achievement_buildings_background,
            second_side_coords,
            second_side_step,
            settings,
            surrender_button_cache,
        )
    else:
        print("[SBARB FARM] 50% reached - skipping second wave deployment")

    # Check if 50% reached before deploying spells
    # Note: In heroes-first mode with queen arrow spells, spells are already deployed before troops
    # Skip if turbo deployment was used (spells already handled in turbo mode)
    if not destruction_reached["value"] and not turbo_deployment:
        building_destroyed, spells_completed = cast_spells_after_deployment(
            achievement_scan_result,
            building_destroyed,
            destruction_reached,
            heroes_first,
            queen_arrow_spells,
            settings,
            spell_casting_active,
            spells_completed,
        )
    else:
        print("[SBARB FARM] 50% reached - skipping spell deployment")

    # Wait for 50% if not reached yet (background thread still monitoring)
    if not destruction_reached["value"]:
        print(f"[SBARB FARM] Waiting for {target_destruction}% destruction (60s timeout)...")
        runtime.gui.log_message(f"SBarb Farm: Waiting for {target_destruction}%...")

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached["value"]:
                break
            time.sleep(0.2)  # Check every 0.2 seconds (faster polling)

        if not destruction_reached["value"]:
            elapsed = time.time() - attack_start_time
            print(f"[SBARB FARM] 60s timeout reached (failsafe triggered after {elapsed:.1f}s)")
            runtime.gui.log_message("SBarb Farm: 60s timeout - surrendering")
            send_discord_debug_log("SBarb Farm: 60s timeout failsafe triggered", "WARNING")

    # Leave the battle (surrender, end battle, or nothing if it already ended)
    end_battle(attack_failed_early, destruction_reached, surrender_button_cache)

    # End timer and save attack duration to CSV
    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time

    # Save to data/sbarb_time.csv with achievement building destruction tracking
    csv_file = "data/sbarb_time.csv"
    file_exists = os.path.exists(csv_file)

    # Format building name for CSV (only if all spells completed, otherwise blank)
    building_name_display = building_destroyed.replace("_", " ").title() if spells_completed else ""

    # Determine attack outcome
    if destruction_reached.get("percentage", 0) >= target_destruction:
        attack_outcome = "Success"
    elif attack_failed_early:
        attack_outcome = "Failed (early end)"
    else:
        attack_outcome = "Failed (timeout)"

    try:
        import csv

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Loop #", "Duration (seconds)", "Timestamp", "Building Destroyed", "Outcome"])
            writer.writerow(
                [
                    runtime.loop_count + 1,
                    f"{attack_duration:.2f}",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    building_name_display,
                    attack_outcome,
                ]
            )
    except Exception as e:
        print(f"[SBARB FARM] Error saving timing to CSV: {e}")
        send_discord_debug_log(f"SBarb Farm: Error saving timing - {e}", "WARNING")

    destruction_info = f", {building_name_display} destroyed" if spells_completed else ""
    print(f"[SBARB FARM] Attack duration: {attack_duration:.2f}s{destruction_info} (saved to {csv_file})")
    send_discord_debug_log(f"SBarb Farm: Attack completed in {attack_duration:.2f}s{destruction_info}")

    if attack_failed_early:
        send_discord_debug_log(f"SBarb Farm: attack failed ({attack_outcome})")
        runtime.gui.log_message(f"SBarb Farm: attack failed ({attack_outcome})")
    else:
        send_discord_debug_log("SBarb Farm: surrendered attack")
        runtime.gui.log_message("SBarb Farm: surrendered attack")

    # Return home - use cached position if available (faster when detected during battle)
    return_home(destruction_reached)

    return True  # Attack completed
