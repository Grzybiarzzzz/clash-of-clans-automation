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
from coc_bot.attacks.queen_arrow import detect_queen_arrow_path_and_cast_spells
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import (
    calculate_deployment_step,
    find_building_clusters,
    get_cluster_center,
    get_opposite_side,
)
from coc_bot.humanized_input import fast_click
from coc_bot.input.turbo import (
    TURBO_CLICK_DELAY_MS,
    turbo_deploy_along_path,
    turbo_deploy_heroes,
    turbo_deploy_siege,
    TURBO_SIDE_CORNERS,
)
from coc_bot.input.win32 import turbo_fast_click, turbo_move_cursor
from coc_bot.overlay import overlay_clear
from coc_bot.vision.buildings import (
    detect_all_achievement_buildings,
    scan_achievement_buildings_parallel_priority,
)
from coc_bot.vision.ocr import detect_destruction_percentage, ocr_remaining_troop_count
from coc_bot.vision.screens import (
    detect_return_home_button,
    detect_star_bonus_screen,
    detect_surrender_or_end_battle,
    wait_for_attack_screen_ready,
)


def _deploy_turbo(
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
):
    """Turbo deployment: both waves, heroes, siege and spells through rapid SendInput clicks."""
    print("[SBARB FARM] *** TURBO DEPLOYMENT MODE ENABLED ***")
    send_discord_debug_log("SBarb Farm: Turbo deployment mode active (~16 CPS)")

    # Get turbo corners for both sides
    first_corners = TURBO_SIDE_CORNERS[first_side].copy()
    second_corners = TURBO_SIDE_CORNERS[opposite_side].copy()

    # Randomly reverse direction sometimes
    if random.random() < 0.5:
        first_corners = list(reversed(first_corners))
        print(f"[TURBO DEPLOY] Reversed direction on {first_side}")
    if random.random() < 0.5:
        second_corners = list(reversed(second_corners))
        print(f"[TURBO DEPLOY] Reversed direction on {opposite_side}")

    # ===== PHASE 1: Deploy first half on first side =====
    print(f"[TURBO DEPLOY] Deploying {first_half} troops on {first_side}...")
    turbo_deploy_along_path(first_corners, first_half, TURBO_CLICK_DELAY_MS, sbarb_hotkey, destruction_reached)

    # ===== PHASE 2: Deploy heroes and siege on FIRST side (right after troops) =====
    if not destruction_reached["value"]:
        print(f"[TURBO DEPLOY] Deploying heroes and siege on {first_side}...")
        turbo_deploy_heroes(first_side, hero_timings, destruction_reached)
        turbo_deploy_siege(first_side, destruction_reached)
    else:
        print("[TURBO DEPLOY] 50% reached after first wave - skipping heroes/siege")

    # Get spell casting setting
    sbarb_cast_spells = settings.get("sbarb_cast_spells", False)

    # ===== PHASE 3-5: Camera, abilities, and second wave (skip if 50% reached) =====
    if not destruction_reached["value"]:
        # ===== PHASE 3: Camera to opposite side =====
        print(f"[TURBO DEPLOY] Moving camera to {opposite_side}...")

        # Click neutral area first to deselect
        pyautogui.click(1280, 400)
        time.sleep(0.1)

        # Extended drag for opposite side
        if opposite_side == "up":
            drag_start_opp, drag_end_opp = (1280, 200), (1280, 1100)
        else:  # down
            drag_start_opp, drag_end_opp = (1280, 1200), (1280, 400)

        pyautogui.moveTo(*drag_start_opp, duration=0.05)
        time.sleep(0.05)
        pyautogui.mouseDown()
        time.sleep(0.05)
        pyautogui.moveTo(*drag_end_opp, duration=0.15)
        time.sleep(0.05)
        pyautogui.mouseUp()

        # ===== PHASE 4: Activate ALL hero abilities immediately (during camera settle) =====
        if not destruction_reached["value"]:
            print("[TURBO DEPLOY] Activating all hero abilities...")
            for hero_key in ["queen", "king", "warden", "rc"]:
                timing = hero_timings.get(hero_key, -1)
                if timing >= 0:  # Only activate if not disabled (-1)
                    keyboard.send(KEYS[hero_key])
                    print(f"[TURBO DEPLOY] {hero_key.title()} ability activated")
                    time.sleep(0.08)  # Small delay between ability activations
            send_discord_debug_log("SBarb Farm: All hero abilities activated (turbo mode)")

        # ===== Start background achievement scan (after camera settled) =====
        if sbarb_cast_spells and not destruction_reached["value"]:
            scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
            scan_thread.start()
            print("[TURBO DEPLOY] Started background achievement building scan")

        # ===== PHASE 5: Deploy second half on opposite side =====
        if not destruction_reached["value"]:
            print(f"[TURBO DEPLOY] Deploying {first_half} troops on {opposite_side}...")
            turbo_deploy_along_path(second_corners, first_half, TURBO_CLICK_DELAY_MS, sbarb_hotkey, destruction_reached)
        else:
            print("[TURBO DEPLOY] 50% reached - skipping second wave")
    else:
        print("[TURBO DEPLOY] 50% reached - skipping phases 3-5")

    # ===== PHASE 6: Spell casting (only if 50% not reached) =====
    achievement_spells_deployed = False

    if not destruction_reached["value"] and sbarb_cast_spells:
        # Wait for background scan to complete (with timeout)
        scan_start = time.time()
        while not achievement_scan_result["completed"] and (time.time() - scan_start) < 6:
            if destruction_reached["value"]:
                break
            time.sleep(0.1)

        if achievement_scan_result["found"] and not destruction_reached["value"]:
            found_building = achievement_scan_result["building"]
            found_type = achievement_scan_result["type"]
            x, y, confidence = found_building

            print(f"[TURBO DEPLOY] CASTING SPELLS ON: {found_type.replace('_', ' ')} at ({x}, {y})")
            runtime.gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
            send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type} (turbo mode)")

            # Deploy 1 Earthquake + 10 Lightning using turbo clicks (~11 CPS)
            SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting
            spell_start = time.perf_counter()

            keyboard.send("a")
            time.sleep(0.05)
            turbo_move_cursor(x, y)
            turbo_fast_click()
            time.sleep(SPELL_CLICK_DELAY_MS / 1000)

            keyboard.send("s")
            time.sleep(0.05)
            spells_cast = 0
            for _ in range(10):
                if destruction_reached["value"]:
                    break
                spell_x = x + random.randint(-3, 3)
                spell_y = y + random.randint(-3, 3)
                turbo_move_cursor(spell_x, spell_y)
                turbo_fast_click()
                spells_cast += 1
                time.sleep(SPELL_CLICK_DELAY_MS / 1000)

            spell_elapsed = time.perf_counter() - spell_start
            print(
                f"[TURBO DEPLOY] Cast {spells_cast + 1} spells in {spell_elapsed * 1000:.0f}ms (~{(spells_cast + 1) / spell_elapsed:.0f} CPS)"
            )

            # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
            if found_type.startswith("cluster_") and "cluster_types" in achievement_scan_result:
                building_destroyed = achievement_scan_result["cluster_types"]
            else:
                building_destroyed = found_type
            spells_completed = True
            achievement_spells_deployed = True
            print(f"[TURBO DEPLOY] Spells deployed on {found_type}")

        # Fallback: random spells if no achievement building found
        if not achievement_spells_deployed and not destruction_reached["value"]:
            print("[TURBO DEPLOY] Deploying random spells...")
            spell_casting_active["value"] = True
            SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting

            keyboard.send("a")
            time.sleep(0.05)
            for _ in range(2):
                if destruction_reached["value"]:
                    break
                x, y = random.randint(700, 1800), random.randint(400, 1000)
                turbo_move_cursor(x, y)
                turbo_fast_click()
                time.sleep(SPELL_CLICK_DELAY_MS / 1000)

            keyboard.send("s")
            time.sleep(0.05)
            for _ in range(9):
                if destruction_reached["value"]:
                    break
                x, y = random.randint(700, 1800), random.randint(400, 1000)
                turbo_move_cursor(x, y)
                turbo_fast_click()
                time.sleep(SPELL_CLICK_DELAY_MS / 1000)

            spell_casting_active["value"] = False
            print("[TURBO DEPLOY] Random spells deployed")
    elif destruction_reached["value"]:
        print("[TURBO DEPLOY] 50% reached - skipping spell casting")

    # ===== Start background surrender button detection for fast surrender =====
    if not surrender_button_cache["detected"]:
        surrender_detect_thread = threading.Thread(target=detect_surrender_button_early, daemon=True)
        surrender_detect_thread.start()
        print("[TURBO DEPLOY] Started background surrender button detection")

    print("[TURBO DEPLOY] All deployment phases complete")
    print("[TURBO DEPLOY] *** TURBO MODE FINISHED - skipping standard deployment ***")
    send_discord_debug_log("SBarb Farm: Turbo deployment complete")
    return building_destroyed, spells_completed


def _deploy_heroes_first_wave(
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
):
    """Standard deployment, heroes-first order: heroes and siege, optional Queen-arrow spells, then the first wave."""
    print("[SBARB FARM] Using STANDARD deployment mode (hold-and-drag)")

    # CONDITIONAL DEPLOYMENT ORDER BASED ON SETTING
    if heroes_first:
        # ===== HEROES FIRST ORDER =====
        print(f"[SBARB FARM] Deploying heroes first on {first_side}...")
        hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]["hero"]

        # Deploy each hero and start their ability timer immediately
        for hero_key in ["queen", "king", "warden", "rc"]:
            # Deploy hero
            keyboard.send(KEYS[hero_key])
            time.sleep(0.01)
            pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
            pyautogui.click()
            time.sleep(0.01)

            # Start ability timer RIGHT AFTER deploying this hero
            timing = hero_timings[hero_key]
            if timing != -1:
                ability_thread = threading.Thread(
                    target=activate_sbarb_hero_ability, args=(hero_key, timing), daemon=True
                )
                ability_thread.start()
                print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

        print("[SBARB FARM] All heroes deployed, ability timers started")

        # Deploy siege machine
        keyboard.send(KEYS["siege"])
    time.sleep(0.01)
    pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
    pyautogui.click()
    time.sleep(0.3)

    # Check if Queen arrow spell targeting is enabled
    queen_arrow_spells = settings.get("sbarb_queen_arrow_spells", False)

    if queen_arrow_spells:
        # ===== QUEEN ARROW PATH DETECTION (BEFORE TROOPS) =====
        print("[SBARB FARM] Using Queen arrow path detection (before troop deployment)...")
        send_discord_debug_log("SBarb Farm: Detecting Queen arrow path before troops")

        # Wait for Queen ability to activate and arrow to hit
        success = detect_queen_arrow_path_and_cast_spells(first_side, queen_timing, spell_casting_active)

        if success:
            print("[SBARB FARM] Queen arrow spells deployed successfully")
            # Spells have been cast, skip normal spell deployment later
            # Extra delay to ensure all spell animations complete
            time.sleep(0.3)
        else:
            # Detection failed - will use fallback spells later
            print("[SBARB FARM] Queen arrow detection failed, will use fallback spells later")
            queen_arrow_spells = False

    # Click neutral area to ensure we're not in drag mode (after spells)
    pyautogui.click(1280, 400)  # Click top-center (safe area)
    # time.sleep(0.3)  # Increased delay to ensure spell mode is fully exited - COMMENTED OUT FOR SPEED

    # Now deploy first half of troops
    print(f"[SBARB FARM] Deploying first half ({first_half} troops) on {first_side}...")
    keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
    # time.sleep(0.4)  # Increased delay for troop selection to register after spells - COMMENTED OUT FOR SPEED

    # Hold-and-drag deployment - much faster and better spread
    if first_half > 0:
        first_coord = first_side_coords[0]
        pyautogui.moveTo(*first_coord, duration=0)
        pyautogui.mouseDown()
        time.sleep(0.5)  # Hold at first position to activate deployment mode

        # Drag through coordinates quickly - dynamic step based on troop count
        for i in range(1, len(first_side_coords), first_side_step):
            coord = first_side_coords[i]
            pyautogui.moveTo(coord[0], coord[1], duration=0.01)
            time.sleep(0.003)  # Brief pause at each position

        pyautogui.mouseUp()
        time.sleep(0.05)

    # Check if 50% reached during first wave deployment
    if destruction_reached["value"]:
        print("[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
        pass  # Will check again before next phase
    return queen_arrow_spells


def _deploy_army_first_wave(
    KEYS,
    activate_sbarb_hero_ability,
    destruction_reached,
    first_half,
    first_side,
    first_side_coords,
    first_side_step,
    hero_timings,
    sbarb_hotkey,
):
    """Standard deployment, army-first order: the first wave, then heroes and siege."""
    print(f"[SBARB FARM] Deploying first half ({first_half} troops) on {first_side}...")
    keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
    time.sleep(0.05)

    # Hold-and-drag deployment - much faster and better spread
    if first_half > 0:
        first_coord = first_side_coords[0]
        pyautogui.moveTo(*first_coord, duration=0)
        pyautogui.mouseDown()
        time.sleep(0.5)  # Hold at first position to activate deployment mode

        # Drag through coordinates quickly - dynamic step based on troop count
        for i in range(1, len(first_side_coords), first_side_step):
            coord = first_side_coords[i]
            pyautogui.moveTo(coord[0], coord[1], duration=0.01)
            time.sleep(0.003)  # Brief pause at each position

        pyautogui.mouseUp()
        time.sleep(0.05)

    # Deploy heroes at first side position - ULTRA FAST
    print("[SBARB FARM] Deploying heroes on first side...")
    hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]["hero"]

    # Deploy each hero and start their ability timer immediately
    for hero_key in ["queen", "king", "warden", "rc"]:
        # Deploy hero
        keyboard.send(KEYS[hero_key])
        time.sleep(0.01)
        pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
        pyautogui.click()
        time.sleep(0.01)

        # Start ability timer RIGHT AFTER deploying this hero
        timing = hero_timings[hero_key]
        if timing != -1:
            ability_thread = threading.Thread(target=activate_sbarb_hero_ability, args=(hero_key, timing), daemon=True)
            ability_thread.start()
            print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

    print("[SBARB FARM] All heroes deployed, ability timers started")

    # Deploy siege machine - ULTRA FAST
    keyboard.send(KEYS["siege"])
    time.sleep(0.01)
    pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
    pyautogui.click()
    time.sleep(0.2)  # Brief pause after siege

    # Check if 50% reached during first wave deployment
    if destruction_reached["value"]:
        print("[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
        pass  # Will check again before next phase


def _deploy_second_wave(
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
):
    """Standard deployment: move the camera, deploy the second wave on the opposite side and clean up leftover troops."""
    print(f"[SBARB FARM] Moving camera to opposite side ({opposite_side})...")
    send_discord_debug_log(f"SBarb Farm: Moving camera to {opposite_side}")
    # Instant drag to opposite side - INCREASED DRAG DISTANCE
    drag_start_opposite, drag_end_opposite = drag_map[opposite_side]
    # Double the drag distance for better camera movement
    if opposite_side == "up":
        drag_end_opposite = (1280, 1100)  # Increased from 900 to 1100
    elif opposite_side == "down":
        drag_end_opposite = (1280, 500)  # Increased from 700 to 500

    pyautogui.moveTo(*drag_start_opposite, duration=0)
    pyautogui.mouseDown()
    pyautogui.moveTo(*drag_end_opposite, duration=0.15)  # Slightly slower for longer drag
    pyautogui.mouseUp()
    time.sleep(0.1)  # Reduced delay to exit camera drag mode (optimized for speed)

    # Start background achievement building scan if spell casting is enabled
    if settings.get("sbarb_cast_spells", False) and not achievement_scan_result["scanning"]:
        scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
        scan_thread.start()
        print("[SBARB FARM] Started background achievement building scan during deployment")
        send_discord_debug_log("SBarb Farm: Background scan started during 2nd wave deployment")

    # Start background surrender button detection
    if not surrender_button_cache["detected"]:
        surrender_detect_thread = threading.Thread(target=detect_surrender_button_early, daemon=True)
        surrender_detect_thread.start()

    # Deploy second half on opposite side - HOLD-AND-DRAG for maximum spread
    print(f"[SBARB FARM] Deploying second half on {opposite_side}...")

    # Click somewhere neutral to ensure we're not in drag mode
    pyautogui.click(1280, 400)  # Click top-center (safe area)
    time.sleep(0.1)

    keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
    time.sleep(0.1)  # Reduced delay for troop selection (optimized for speed)

    # Calculate how many troops remain
    remaining_troops = first_half  # Should be roughly the same or slightly more

    # Hold-and-drag deployment
    if remaining_troops > 0 and len(second_side_coords) > 0:
        first_coord = second_side_coords[0]
        pyautogui.moveTo(*first_coord, duration=0)
        pyautogui.mouseDown()
        time.sleep(0.5)  # Hold at first position to activate deployment mode

        # Drag through coordinates quickly - dynamic step based on troop count
        for i in range(1, len(second_side_coords), second_side_step):
            coord = second_side_coords[i]
            pyautogui.moveTo(coord[0], coord[1], duration=0.01)
            time.sleep(0.003)  # Brief pause at each position

        pyautogui.mouseUp()
        time.sleep(0.05)

    print("[SBARB FARM] All troops deployed")
    send_discord_debug_log("SBarb Farm: All troops deployed")

    # SMART CLEANUP: OCR remaining troops and deploy with individual clicks
    if not destruction_reached["value"]:
        print("[SBARB FARM] Checking remaining troop count via OCR...")
        send_discord_debug_log("SBarb Farm: OCR cleanup check started")

        # OCR the remaining troop count
        remaining_count = ocr_remaining_troop_count()

        if remaining_count == 0:
            # No troops left - skip cleanup entirely (avoids "no units" message)
            print("[SBARB FARM] No troops remaining - skipping cleanup")
            send_discord_debug_log("SBarb Farm: 0 troops remaining, cleanup skipped")
        elif remaining_count > 0:
            # Deploy remaining troops with individual clicks
            print(f"[SBARB FARM] {remaining_count} troops remaining - deploying with clicks")
            send_discord_debug_log(f"SBarb Farm: {remaining_count} troops remaining, starting click deployment")

            keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
            time.sleep(0.05)

            # Choose 6 evenly spaced positions from last deployed side
            cleanup_coords = second_side_coords
            num_coords = len(cleanup_coords)
            num_clicks = min(8, num_coords)  # Up to 8 clicks

            # Calculate indices for even spacing
            if num_coords > 0:
                step = max(1, num_coords // num_clicks)
                click_positions = [cleanup_coords[i * step] for i in range(num_clicks)]

                # Deploy with individual clicks
                for i, pos in enumerate(click_positions):
                    if destruction_reached["value"]:
                        print("[SBARB FARM] 50% reached during cleanup - stopping")
                        break

                    fast_click(*pos)
                    time.sleep(0.08)  # Brief delay between clicks
                    print(f"  Cleanup click {i + 1}/{num_clicks}")

                print(f"[SBARB FARM] Cleanup complete - {num_clicks} clicks deployed")
                send_discord_debug_log(f"SBarb Farm: Cleanup complete ({num_clicks} clicks)")
        else:
            # OCR failed - fallback to 3 safety clicks
            print("[SBARB FARM] OCR failed - fallback to 3 safety clicks")
            send_discord_debug_log("SBarb Farm: OCR failed, using fallback clicks")

            keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
            time.sleep(0.05)

            cleanup_coords = second_side_coords
            if len(cleanup_coords) >= 3:
                # Click at start, middle, end
                for pos in [cleanup_coords[0], cleanup_coords[len(cleanup_coords) // 2], cleanup_coords[-1]]:
                    if destruction_reached["value"]:
                        break
                    fast_click(*pos)
                    time.sleep(0.08)

            print("[SBARB FARM] Fallback cleanup complete")
            send_discord_debug_log("SBarb Farm: Fallback cleanup complete")


def _cast_spells_after_deployment(
    achievement_scan_result,
    building_destroyed,
    destruction_reached,
    heroes_first,
    queen_arrow_spells,
    settings,
    spell_casting_active,
    spells_completed,
):
    """Standard deployment: cast spells on achievement buildings, or the fallback spells, unless the Queen-arrow spells already ran."""
    queen_arrow_setting = settings.get("sbarb_queen_arrow_spells", False)

    # In heroes-first mode, queen_arrow_spells variable indicates if spells were deployed successfully
    # In army-first mode, we always need to deploy spells here
    if heroes_first and queen_arrow_setting and queen_arrow_spells:
        # Spells already deployed before troops via Queen arrow detection
        print("[SBARB FARM] Spells already deployed via Queen arrow detection, skipping")
    elif not heroes_first and queen_arrow_setting:
        # Army-first mode with queen arrow enabled - not supported
        print("[SBARB FARM] WARNING: Queen arrow spells require heroes-first mode, using random spells")
        send_discord_debug_log("SBarb Farm: Queen arrow requires heroes-first mode", "WARNING")
        # Deploy random spells as fallback
    # Otherwise spells still need to be deployed: army-first mode, heroes-first without
    # the Queen arrow, or arrow detection failed

    # Deploy spells if needed
    if not (heroes_first and queen_arrow_setting and queen_arrow_spells):
        # Check if achievement building spell casting is enabled
        cast_spells_on_achievement = settings.get("sbarb_cast_spells", False)
        achievement_spells_deployed = False

        if cast_spells_on_achievement:
            # Use cached scan results from background thread
            print("[SBARB FARM] Checking background scan results...")

            # Wait for background scan to complete (max 2 seconds)
            scan_wait_start = time.time()
            while achievement_scan_result["scanning"] and (time.time() - scan_wait_start) < 2.0:
                if destruction_reached["value"]:
                    print("[SBARB FARM] 50% reached while waiting for scan - skipping")
                    break
                time.sleep(0.1)

            if achievement_scan_result["found"]:
                # Background scan found a building - use cached result!
                found_building = achievement_scan_result["building"]
                found_type = achievement_scan_result["type"]
                print(f"[SBARB FARM] ✓ Using cached scan result: {found_type.replace('_', ' ')}")
                send_discord_debug_log(f"SBarb Farm: Using cached building ({found_type})")
            elif achievement_scan_result["completed"]:
                # Scan completed but found nothing
                print("[SBARB FARM] Background scan completed - no buildings found")
                send_discord_debug_log("SBarb Farm: Background scan found no buildings")
                found_building = None
                found_type = None
            else:
                # Scan timed out or 50% reached - no result available
                print("[SBARB FARM] Background scan incomplete - no result available")
                send_discord_debug_log("SBarb Farm: Background scan incomplete")
                found_building = None
                found_type = None

            if found_building:
                # Set flag to indicate spell casting is active
                spell_casting_active["value"] = True

                x, y, confidence = found_building
                print(
                    f"[SBARB FARM] CASTING SPELLS ON: {found_type.replace('_', ' ').title()} at ({x}, {y}) - Confidence: {confidence:.3f}"
                )
                runtime.gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
                send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type.replace('_', ' ')} at ({x}, {y})")

                # Deploy 1 Earthquake spell
                print("Deploying Earthquake spell...")
                keyboard.send("a")  # Earthquake hotkey
                time.sleep(0.02)
                fast_click(x, y)
                time.sleep(0.05)

                # Deploy 10 Lightning spells
                print("Deploying Lightning spells...")
                lightning_spells_cast = 0
                for i in range(10):
                    if destruction_reached["value"]:
                        print("[SBARB FARM] 50% reached during spell deployment - stopping")
                        break
                    keyboard.send("s")  # Lightning hotkey
                    time.sleep(0.01)
                    # Add slight variation to position (±3px like Achievement Farm)
                    spell_x = x + random.randint(-3, 3)
                    spell_y = y + random.randint(-3, 3)
                    fast_click(spell_x, spell_y)
                    time.sleep(0.03)
                    lightning_spells_cast += 1
                    print(f"  Lightning {i + 1}/10 deployed")

                # Check if all 10 lightning spells were successfully cast
                if lightning_spells_cast == 10:
                    print("[SBARB FARM] All spells deployed (1 Earthquake + 10 Lightning)!")
                    runtime.gui.log_message("Spells deployed successfully")
                    send_discord_debug_log("SBarb Farm: All spells deployed (1 Earthquake + 10 Lightning)")

                    # Track building destruction for CSV
                    # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
                    if found_type.startswith("cluster_") and "cluster_types" in achievement_scan_result:
                        building_destroyed = achievement_scan_result["cluster_types"]
                    else:
                        building_destroyed = found_type
                    spells_completed = True
                    print(f"[SBARB FARM] ✓ Achievement building destroyed: {found_type.replace('_', ' ').title()}")
                    send_discord_debug_log(f"SBarb Farm: {found_type.replace('_', ' ').title()} destroyed")
                else:
                    print(
                        f"[SBARB FARM] Spell deployment interrupted ({lightning_spells_cast}/10 lightning spells cast)"
                    )
                    send_discord_debug_log(f"SBarb Farm: Spell deployment interrupted ({lightning_spells_cast}/10)")

                achievement_spells_deployed = True

                # Clear flag - spell casting complete
                spell_casting_active["value"] = False
            else:
                print("[SBARB FARM] No achievement buildings found - falling back to random spells")
                runtime.gui.log_message("No achievement buildings found")
                send_discord_debug_log("SBarb Farm: No achievement buildings found, using random spells")

        # If achievement spells not enabled or no buildings found, deploy random spells
        if not achievement_spells_deployed:
            # Deploy 2 Earthquake + 9 Lightning spells at random base locations - FAST (ORIGINAL METHOD)
            print("[SBARB FARM] Deploying 2 Earthquake + 9 Lightning spells randomly...")
            send_discord_debug_log("SBarb Farm: Deploying 2 Earthquake + 9 Lightning spells")

            # Set flag to indicate spell casting is active (for hero ability re-selection)
            spell_casting_active["value"] = True

            # Spell region (center of base for maximum damage)
            spell_region = (982, 554, 1548, 871)

            # Deploy 2 Earthquake spells first
            keyboard.send("a")  # Select Earthquake spell
            time.sleep(0.05)

            for spell_num in range(2):
                # Check during spell deployment
                if destruction_reached["value"]:
                    print("[SBARB FARM] 50% reached during spell deployment - stopping")
                    break
                # Random location within spell region
                random_x = random.randint(spell_region[0], spell_region[2])
                random_y = random.randint(spell_region[1], spell_region[3])
                fast_click(random_x, random_y)
                time.sleep(0.05)

            if not destruction_reached["value"]:
                print("[SBARB FARM] 2 Earthquake spells deployed")

                # Deploy 9 Lightning spells
                keyboard.send("s")  # Select Lightning spell
                time.sleep(0.05)

                for spell_num in range(9):
                    # Check during spell deployment
                    if destruction_reached["value"]:
                        print("[SBARB FARM] 50% reached during spell deployment - stopping")
                        break

                    # Random location within spell region
                    random_x = random.randint(spell_region[0], spell_region[2])
                    random_y = random.randint(spell_region[1], spell_region[3])

                    if spell_num % 4 == 0 and spell_num > 0:  # Re-select spell every 4 casts
                        keyboard.send("s")
                        time.sleep(0.02)

                    fast_click(random_x, random_y)
                    time.sleep(0.05)  # Very fast spell casting

                if not destruction_reached["value"]:
                    print("[SBARB FARM] All spells deployed (2 Earthquake + 9 Lightning)")
                    send_discord_debug_log("SBarb Farm: All spells deployed (2 Earthquake + 9 Lightning)")

            # Clear flag - spell casting complete
            spell_casting_active["value"] = False
    return building_destroyed, spells_completed


def _end_battle(attack_failed_early, destruction_reached, surrender_button_cache):
    """Leave the battle: skip if Return Home was already detected, otherwise surrender or end the battle."""
    if attack_failed_early and destruction_reached.get("return_home_pos"):
        print("[SBARB FARM] Skipping surrender - Return Home already detected (battle ended)")
        send_discord_debug_log("SBarb Farm: Skipping surrender - already at end screen")
    # OPTIMIZED surrender sequence - use cached position for instant surrender
    elif surrender_button_cache["detected"]:
        # Use cached surrender button position (FAST - no template matching delay)
        surrender_pos = surrender_button_cache["position"]
        print(f"[SBARB FARM] Using cached surrender button at {surrender_pos}")
        send_discord_debug_log(f"SBarb Farm: Using cached surrender position at {surrender_pos}")
        fast_click(*surrender_pos)
        time.sleep(0.1)  # Minimal delay (reduced from 0.3s)

        # Click confirm surrender button - FAST
        print("[SBARB FARM] Clicking surrender confirmation...")
        send_discord_debug_log("SBarb Farm: Clicking surrender confirmation")
        fast_click(1483, 898)
        time.sleep(0.1)  # Minimal delay
    else:
        # Detect surrender OR end battle button (both end the battle)
        print("[SBARB FARM] Detecting surrender/end battle button...")
        button_type, x, y = detect_surrender_or_end_battle()

        if button_type:
            print(f"[SBARB FARM] Clicking {button_type} button at ({x}, {y})")
            send_discord_debug_log(f"SBarb Farm: Clicking {button_type} at ({x}, {y})")
            fast_click(x, y)
            time.sleep(0.1)

            # Click confirm button - FAST
            print(f"[SBARB FARM] Clicking {button_type} confirmation...")
            send_discord_debug_log(f"SBarb Farm: Clicking {button_type} confirmation")
            fast_click(1483, 898)
            time.sleep(0.1)  # Minimal delay (reduced from 0.3s)
        else:
            # NO FALLBACK - Detect actual state and handle appropriately
            print("[SBARB FARM] WARNING: Surrender button not detected - detecting state...")
            send_discord_debug_log("SBarb Farm: Surrender not found - detecting state", "WARNING")

            # Check if battle already ended or we're already at base
            button_type, x, y = detect_surrender_or_end_battle()
            if button_type == "end_battle":
                print("[SBARB FARM] Battle already ended - clicking end battle button")
                send_discord_debug_log("SBarb Farm: Battle ended - clicking end battle")
                fast_click(x, y)
                time.sleep(0.1)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.1)
            elif detect_return_home_button():
                print("[SBARB FARM] Already at end screen - surrender not needed")
                send_discord_debug_log("SBarb Farm: Already at end screen")
            else:
                # Still in battle but can't find surrender - try deploying troop to enable it
                print("[SBARB FARM] Deploying troop to enable surrender...")
                send_discord_debug_log("SBarb Farm: Deploying troop to enable surrender", "WARNING")
                fast_click(1282, 720)  # Deploy one troop
                time.sleep(2.0)

                # Try finding surrender again
                for retry in range(2):
                    button_type, x, y = detect_surrender_or_end_battle()
                    if button_type == "surrender":
                        print(f"[SBARB FARM] Surrender now available at {x}, {y}")
                        fast_click(x, y)
                        time.sleep(0.1)
                        fast_click(1483, 898)
                        time.sleep(0.1)
                        break
                    elif button_type == "end_battle":
                        print("[SBARB FARM] Battle ended - clicking end battle")
                        fast_click(x, y)
                        time.sleep(0.1)
                        fast_click(1483, 898)
                        time.sleep(0.1)
                        break
                    time.sleep(1.0)
                else:
                    # Still can't find - log error but continue
                    print("[SBARB FARM] ERROR: Could not find surrender/end battle - continuing anyway")
                    send_discord_debug_log("SBarb Farm: Failed to surrender - button not found", "ERROR")
                    time.sleep(3)  # Wait for potential auto-end


def _return_home(destruction_reached):
    """Click Return Home (cached position when available) and close the star bonus screen if it appears."""
    if destruction_reached.get("return_home_pos"):
        print(f"[SBARB FARM] Using cached Return Home position: {destruction_reached['return_home_pos']}")
        fast_click(*destruction_reached["return_home_pos"])
    else:
        fast_click(*config.RETURN_BUTTON)
    time.sleep(1.5)

    # Additional delay before star bonus check
    time.sleep(0.5)

    # Check for star bonus screen
    print("[SBARB FARM] Checking for star bonus screen...")
    if detect_star_bonus_screen():
        print("[SBARB FARM] Star bonus detected! Clicking close button...")
        runtime.gui.log_message("SBarb Farm: Star bonus collected")
        send_discord_debug_log("SBarb Farm: Star bonus screen detected and closed")

        # Click the close button (X button)
        fast_click(102, 824)
        time.sleep(0.5)

        # Click return button again to go home
        fast_click(*config.RETURN_BUTTON)
        time.sleep(1.5)
    else:
        print("[SBARB FARM] No star bonus screen detected, continuing...")


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
        building_destroyed, spells_completed = _deploy_turbo(
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
        queen_arrow_spells = _deploy_heroes_first_wave(
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
        _deploy_army_first_wave(
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
        _deploy_second_wave(
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
        building_destroyed, spells_completed = _cast_spells_after_deployment(
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
    _end_battle(attack_failed_early, destruction_reached, surrender_button_cache)

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
    _return_home(destruction_reached)

    return True  # Attack completed
