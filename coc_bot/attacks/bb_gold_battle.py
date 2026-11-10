"""Builder Base gold battle steps: troop deployment, star monitoring, ending the battle and bookkeeping."""

import os
import random
import time
from datetime import datetime

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import fast_click, human_like_move_click
from coc_bot.input.win32 import turbo_fast_click, turbo_move_cursor
from coc_bot.village import collect_bb_loot
from coc_bot.vision.bb_deployment_zone import (
    detect_bb_deployment_zone,
    detect_bb_deployment_zone_advanced,
    filter_out_unit_bar,
    generate_ring_fallback_coords,
    save_bb_dragon_debug_visualization,
    select_equally_spaced_coords,
)
from coc_bot.vision.screens import (
    detect_end_battle_button,
    detect_return_home_button,
    detect_surrender_or_end_battle,
    detect_three_stars,
    detect_two_stars,
)

bb_gold_attack_count = 0  # Counter for BB Gold loot collection every 12 attacks


def deploy_bb_gold_baby_dragons(context):
    """
    Deploy 6 Baby Dragons equally spaced around the boundary + Battle Machine.
    Uses advanced deployment zone detection for close-to-boundary placement.

    Args:
        context (dict): State machine context

    Returns:
        bool: True if deployment successful, False otherwise
    """
    print("[BB DRAGONS] Starting Baby Dragons deployment...")
    send_discord_debug_log("BB Gold Baby Dragons: Starting deployment")

    # Zoom out before detecting deployment zone to see full base
    print("[BB DRAGONS] Zooming out for better detection...")
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.15)  # Brief wait for zoom animation

    # Detect valid deployment zone using advanced detection
    all_coords = detect_bb_deployment_zone_advanced()

    if not all_coords or len(all_coords) < 6:
        print("[BB DRAGONS] Not enough deployment coordinates, using ring fallback")
        send_discord_debug_log("BB Dragons: Using ring fallback coordinates", "WARNING")
        # Use ring fallback around screen center
        all_coords = generate_ring_fallback_coords(radius=400, num_points=8)

    # Select 6 equally-spaced coordinates for Baby Dragons
    dragon_coords = select_equally_spaced_coords(all_coords, num_points=6)
    print(f"[BB DRAGONS] Selected {len(dragon_coords)} equally-spaced positions")

    # Pre-calculate Battle Machine position for potential debug visualization
    remaining_coords = [c for c in all_coords if c not in dragon_coords]
    if remaining_coords:
        bm_coord = random.choice(remaining_coords)
    else:
        bm_coord = (1250, 650)  # Center fallback

    # Save debug visualization if enabled
    if runtime.gui.get_settings().get("bb_gold_dragon_debug_positions", False):
        print("[BB DRAGONS] Debug mode enabled - saving position visualization...")
        save_bb_dragon_debug_visualization(all_coords, dragon_coords, bm_coord)

    KEYS = config.KEYS
    surrender_pos = None

    # === DEPLOY BATTLE MACHINE FIRST ===
    print(f"[BB DRAGONS] Deploying Battle Machine first at {bm_coord}...")
    keyboard.send(KEYS["queen"])  # 'q' key
    time.sleep(0.02)
    turbo_move_cursor(bm_coord[0], bm_coord[1])
    turbo_fast_click()
    time.sleep(0.3)  # Brief wait to check for surrender button

    # Check if surrender button appeared (deployment successful)
    button_type, button_x, button_y = detect_surrender_or_end_battle()

    if button_type:
        surrender_pos = (button_x, button_y)
        context["surrender_button_cached"] = True
        context["surrender_button_pos"] = surrender_pos
        context["surrender_button_type"] = button_type
        print(f"[BB DRAGONS] Battle Machine deployed successfully - {button_type} button detected")
        runtime.gui.update_bb_gold_state("BATTLE_ACTIVE")
    else:
        # Try fallback position for BM
        print("[BB DRAGONS] BM position failed, trying fallback...")
        fallback_coord = (1250, 200)  # Top center
        keyboard.send(KEYS["queen"])
        time.sleep(0.02)
        turbo_move_cursor(fallback_coord[0], fallback_coord[1])
        turbo_fast_click()
        time.sleep(0.3)

        button_type, button_x, button_y = detect_surrender_or_end_battle()
        if button_type:
            surrender_pos = (button_x, button_y)
            context["surrender_button_cached"] = True
            context["surrender_button_pos"] = surrender_pos
            context["surrender_button_type"] = button_type
            bm_coord = fallback_coord
            print("[BB DRAGONS] BM fallback deployment successful")
            runtime.gui.update_bb_gold_state("BATTLE_ACTIVE")
        else:
            print("[BB DRAGONS] CRITICAL: Failed to deploy Battle Machine!")
            send_discord_debug_log("BB Dragons: CRITICAL - Failed to deploy BM", "ERROR")
            return False

    # Activate Battle Machine ability immediately
    print("[BB DRAGONS] Activating Battle Machine ability...")
    keyboard.send("q")
    context["battle_machine_ability_time"] = time.time()

    # === DEPLOY ALL 6 BABY DRAGONS AT ONCE ===
    print("[BB DRAGONS] Deploying all 6 Baby Dragons (turbo mode)...")
    for i in range(6):
        dragon_num = i + 1
        coord = dragon_coords[i] if i < len(dragon_coords) else random.choice(all_coords)

        keyboard.send(str(dragon_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay for key registration
        turbo_move_cursor(coord[0], coord[1])
        turbo_fast_click()
        time.sleep(0.02)  # Minimal delay between dragons

    print("[BB DRAGONS] All 6 Baby Dragons deployed")
    send_discord_debug_log("BB Dragons: All 6 dragons deployed")

    # Wait before casting abilities (dragons need time to spread out)
    print("[BB DRAGONS] Waiting before casting abilities...")
    time.sleep(4.3)

    # Cast all 6 Baby Dragon abilities (rapid fire)
    for ability_num in range(1, 7):
        keyboard.send(str(ability_num))
        time.sleep(0.02)

    print("[BB DRAGONS] All abilities cast")
    send_discord_debug_log("BB Dragons: All abilities cast")

    print("[BB DRAGONS] Deployment complete!")
    send_discord_debug_log("BB Dragons: Deployment complete - BM ability activated")

    return True


def deploy_bb_gold_troops(context):
    """
    Deploy troops for BB Gold mode based on selected troop mode.

    Args:
        context (dict): State machine context

    Returns:
        bool: True if deployment successful (surrender button appeared), False otherwise

    Supports three modes:
    - night_witches: Battle Machine + 6 Night Witches (default)
    - bomber_night_witches: Bomber + Battle Machine + Night Witches (22s ability recast)
    - baby_dragons: 6 Baby Dragons spread out + Battle Machine (14s ability recast)
    """
    # Check troop mode setting
    troop_mode = runtime.gui.get_settings().get("bb_gold_troop_mode", "night_witches")
    print(f"[BB GOLD DEPLOY] Troop mode: {troop_mode}")

    # Route to appropriate deployment function based on mode
    if troop_mode == "baby_dragons":
        return deploy_bb_gold_baby_dragons(context)

    # For night_witches and bomber_night_witches, use the standard deployment below
    # (bomber mode uses same deployment, just tracks bomber ability separately)

    # Detect valid deployment zone (outside red lines)
    valid_coords = detect_bb_deployment_zone()

    # Filter out unit bar area (x=1-2553, y=1209-1431)
    valid_coords = filter_out_unit_bar(valid_coords)

    # Safety check: if all coords were filtered out, use fallback
    if not valid_coords:
        print("[BB GOLD DEPLOY] WARNING: All coordinates filtered out, using fallback positions")
        send_discord_debug_log("BB Gold: All coords filtered - using fallback", "WARNING")
        valid_coords = [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

    # Randomly choose deployment position from valid coordinates
    if valid_coords:
        deployment_coord = random.choice(valid_coords)
        print(
            f"[BB GOLD DEPLOY] Using deployment position: {deployment_coord} (randomly selected from {len(valid_coords)} options)"
        )
        send_discord_debug_log(f"BB Gold: Deploying at randomly selected position {deployment_coord}")
    else:
        deployment_coord = (300, 300)  # Fallback to top-left corner
        print("[BB GOLD DEPLOY] WARNING: No valid coords detected, using fallback corner")
        send_discord_debug_log("BB Gold: Using fallback corner position", "WARNING")

    KEYS = config.KEYS

    # Try deploying at the chosen coordinate until surrender button appears
    surrender_pos = None
    deployment_attempt = 0

    print("[BB GOLD DEPLOY] Deploying Battle Machine...")
    send_discord_debug_log("BB Gold: Deploying Battle Machine")

    # Phase 1: Try valid coordinates first (up to 10 attempts)
    while not surrender_pos and deployment_attempt < 10:
        deployment_attempt += 1
        print(f"[BB GOLD DEPLOY] Deployment attempt {deployment_attempt}/10 at {deployment_coord}")

        # Deploy Battle Machine (q)
        keyboard.send(KEYS["queen"])  # 'q' key for Battle Machine
        time.sleep(0.2)
        human_like_move_click(deployment_coord[0], deployment_coord[1])
        time.sleep(0.5)

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)
            # CACHE surrender button position for fast clicking later (2-star path)
            context["surrender_button_cached"] = True
            context["surrender_button_pos"] = surrender_pos
            context["surrender_button_type"] = button_type
            print(
                f"[BB GOLD DEPLOY] Battle Machine deployed successfully at {deployment_coord} ({button_type} button detected)"
            )
            print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
            send_discord_debug_log(f"BB Gold: Battle Machine deployed - {button_type} button cached at {surrender_pos}")
            # Update GUI to show BATTLE_ACTIVE immediately
            runtime.gui.update_bb_gold_state("BATTLE_ACTIVE")
            break
        else:
            print("[BB GOLD DEPLOY] Surrender/end battle button not found - invalid placement, trying again...")
            # Try a different random valid coordinate for next attempt
            if valid_coords:
                deployment_coord = random.choice(valid_coords)

    # Phase 2: If still no success, try random coordinates across entire screen until success
    if not surrender_pos:
        print("[BB GOLD DEPLOY] Valid coords failed - trying random screen coordinates until success...")
        send_discord_debug_log("BB Gold: Switching to random coordinate mode", "WARNING")

        max_random_attempts = 20  # Safety limit
        while not surrender_pos and deployment_attempt < 30:  # 10 + 20 = 30 total max
            deployment_attempt += 1

            # Generate random coordinate (avoid edges and unit bar)
            random_x = random.randint(300, 2200)
            random_y = random.randint(200, 1100)  # Avoid unit bar at bottom

            print(
                f"[BB GOLD DEPLOY] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})"
            )

            # Deploy Battle Machine
            keyboard.send(KEYS["queen"])
            time.sleep(0.2)
            human_like_move_click(random_x, random_y)
            time.sleep(0.5)

            # Check if surrender or end battle button appeared
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                surrender_pos = (button_x, button_y)
                # CACHE surrender button position for fast clicking later (2-star path)
                context["surrender_button_cached"] = True
                context["surrender_button_pos"] = surrender_pos
                context["surrender_button_type"] = button_type
                print(
                    f"[BB GOLD DEPLOY] SUCCESS! Battle Machine deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected"
                )
                print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
                send_discord_debug_log(
                    f"BB Gold: Success with random coords - {button_type} button cached at {surrender_pos}"
                )
                # Update GUI to show BATTLE_ACTIVE immediately
                runtime.gui.update_bb_gold_state("BATTLE_ACTIVE")
                deployment_coord = (random_x, random_y)  # Update deployment coord for Night Witches
                break

    if not surrender_pos:
        print("[BB GOLD DEPLOY] CRITICAL: Failed to deploy Battle Machine after 30 attempts!")
        send_discord_debug_log("BB Gold: CRITICAL - Failed to deploy after 30 attempts", "ERROR")
        return False

    # Activate Battle Machine ability immediately after deployment
    print("[BB GOLD DEPLOY] Activating Battle Machine ability...")
    send_discord_debug_log("BB Gold: Activating Battle Machine ability")
    keyboard.send("q")  # Battle Machine ability key
    context["battle_machine_ability_time"] = time.time()  # Track when ability was used
    time.sleep(0.2)

    # Deploy all 6 Night Witches at the same position - FAST DEPLOYMENT
    print("[BB GOLD DEPLOY] Deploying 6 Night Witches...")
    send_discord_debug_log("BB Gold: Deploying 6 Night Witches")

    for witch_num in range(1, 7):
        keyboard.send(str(witch_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay
        fast_click(deployment_coord[0], deployment_coord[1])  # Ultra-fast click
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD DEPLOY] All Night Witches deployed")
    send_discord_debug_log("BB Gold: All 6 Night Witches deployed")

    # Wait 3 seconds before casting abilities
    print("[BB GOLD DEPLOY] Waiting 3 seconds before casting abilities...")
    time.sleep(3)

    # Cast abilities for all 6 Night Witches - FAST CASTING
    print("[BB GOLD DEPLOY] Casting Night Witch abilities...")
    send_discord_debug_log("BB Gold: Casting abilities")

    for ability_num in range(1, 7):
        keyboard.send(str(ability_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD DEPLOY] All abilities cast - troops deployed successfully")
    send_discord_debug_log("BB Gold: All abilities cast - deployment complete")

    # Set bomber ability timer after casting (bomber ability was cast when key '1' was pressed)
    if troop_mode == "bomber_night_witches":
        context["bomber_ability_time"] = time.time()
        print("[BB GOLD DEPLOY] Bomber ability timer started (22s recast)")

    return True


def monitor_bb_gold_battle(context):
    """
    Monitor BB Gold battle for 2/3 stars or Return Home button (battle ended).

    Args:
        context (dict): State machine context with attack_start_time, battle_machine_ability_time

    Returns:
        dict: {'stars': int, 'timeout_without_stars': bool, 'return_home_pos': tuple or None}

    Uses Return Home button detection instead of fixed timeout for immediate
    battle end detection. This is more responsive and works for all end scenarios.
    """
    max_wait_time = 180  # Maximum 3 minutes to get stars
    start_time = time.time()
    battle_machine_ability_time = context.get("battle_machine_ability_time")
    last_return_home_check = 0  # Track last Return Home check time
    return_home_check_interval = 2.0  # Check every 2 seconds to reduce overhead

    result = {"stars": 0, "timeout_without_stars": False, "return_home_pos": None}

    print("[BB GOLD MONITOR] Monitoring for 2/3 stars or battle end...")
    runtime.gui.log_message("BB Gold: Monitoring for 2/3 stars...")

    while (time.time() - start_time) < max_wait_time:
        current_time = time.time()

        # Check for Return Home button (battle ended without 2+ stars)
        # This replaces the fixed 80-second timeout with immediate detection
        if current_time - last_return_home_check >= return_home_check_interval:
            last_return_home_check = current_time
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                result["timeout_without_stars"] = True
                result["return_home_pos"] = return_home_pos
                print(
                    f"[BB GOLD MONITOR] Return Home button detected at {return_home_pos} - battle ended without stars"
                )
                runtime.gui.log_message("BB Gold: Battle ended - returning home")
                send_discord_debug_log("BB Gold: Return Home detected - battle ended without stars")
                break

        # Re-activate Battle Machine ability every 14 seconds if battle is still ongoing
        if battle_machine_ability_time is not None and current_time - battle_machine_ability_time >= 14:
            print("[BB GOLD MONITOR] 14 seconds elapsed - re-activating Battle Machine ability...")
            send_discord_debug_log("BB Gold: Re-activating Battle Machine ability after 14 seconds")
            keyboard.send("q")  # Re-activate Battle Machine ability
            battle_machine_ability_time = current_time  # Reset timer for next activation
            context["battle_machine_ability_time"] = current_time
            time.sleep(0.2)

        # Re-activate Bomber ability every 22 seconds if enabled and battle is still ongoing
        bomber_ability_time = context.get("bomber_ability_time")
        if bomber_ability_time is not None and current_time - bomber_ability_time >= 22:
            print("[BB GOLD MONITOR] 22 seconds elapsed - re-activating Bomber ability...")
            send_discord_debug_log("BB Gold: Re-activating Bomber ability after 22 seconds")
            keyboard.send("1")  # Re-activate Bomber ability (slot 1)
            context["bomber_ability_time"] = current_time
            time.sleep(0.2)

        # Check for 2 stars first (most common case) with double verification (optimized from 3x)
        two_star_verification = sum(1 for _ in range(2) if detect_two_stars())

        if two_star_verification >= 2:  # If both checks passed
            # Check if "try for 3 stars" is enabled for Baby Dragons
            try_3_stars = runtime.gui.get_settings().get("bb_gold_try_3_stars", False)
            troop_mode = runtime.gui.get_settings().get("bb_gold_troop_mode", "night_witches")

            if try_3_stars and troop_mode == "baby_dragons":
                # Skip 2-star exit, continue monitoring for 3 stars
                if result["stars"] < 2:  # Only log once when first reaching 2 stars
                    result["stars"] = 2
                    print("[BB GOLD MONITOR] 2 STARS DETECTED! Continuing for 3 stars...")
                    runtime.gui.log_message("BB Gold: 2 stars - trying for 3...")
                    send_discord_debug_log("BB Gold: 2 stars detected - continuing for 3 stars")
                # Don't break - continue monitoring for 3 stars or Return Home
            else:
                result["stars"] = 2
                print("[BB GOLD MONITOR] 2 STARS DETECTED! Surrendering immediately...")
                runtime.gui.log_message("BB Gold: 2 stars detected - surrendering")
                send_discord_debug_log("BB Gold: 2 stars detected - surrendering immediately")
                break

        # Check for 3 stars (rare edge case - Builder Hall destroyed last before 2nd star appears)
        three_star_verification = sum(1 for _ in range(2) if detect_three_stars())

        if three_star_verification >= 2:  # If both checks passed
            result["stars"] = 3
            print("[BB GOLD MONITOR] 3 STARS DETECTED! (Builder Hall was last building)")
            runtime.gui.log_message("BB Gold: 3 stars detected!")
            send_discord_debug_log("BB Gold: 3 stars detected - waiting 7 seconds before ending")

            # Wait 7 seconds as requested for 3 stars
            print("[BB GOLD MONITOR] Waiting 7 seconds...")
            time.sleep(7)
            break

        time.sleep(0.5)  # Check every ~0.5 seconds

    if result["stars"] == 0 and not result["timeout_without_stars"]:
        print("[BB GOLD MONITOR] WARNING: 2/3 stars not detected after 3 minutes, ending battle anyway")
        runtime.gui.log_message("BB Gold: Timeout - ending battle")
        send_discord_debug_log("BB Gold: Timeout waiting for stars - ending battle anyway", "WARNING")

    return result


def end_bb_gold_battle(stars_detected, context=None):
    """
    End BB Gold battle by clicking surrender (2 stars) or end battle (3 stars).

    Args:
        stars_detected (int): Number of stars detected (0, 1, 2, or 3)
        context (dict, optional): State machine context with cached surrender button position

    Returns:
        dict: {'success': bool, 'final_stars': int}

    Extracts end battle logic from original handle_bb_gold_mode()
    """
    result = {"success": False, "final_stars": stars_detected}

    # Check if we have a cached surrender button position (from deployment)
    cached_available = context and context.get("surrender_button_cached", False)
    if cached_available:
        cached_pos = context.get("surrender_button_pos")
        cached_type = context.get("surrender_button_type", "surrender")
        print(f"[BB GOLD END] ✓ Using cached {cached_type} button at {cached_pos}")
        send_discord_debug_log(f"BB Gold: Using cached {cached_type} button from deployment")

    if stars_detected == 3:
        # 3 STAR PATH - use end battle button (surrender not available with 3 stars)
        print("[BB GOLD END] 3 stars achieved - detecting end battle button...")
        send_discord_debug_log("BB Gold: 3 stars - using end battle button")

        end_battle_pos = detect_end_battle_button()

        if end_battle_pos:
            print(f"[BB GOLD END] Clicking end battle button at {end_battle_pos}")
            send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
            fast_click(*end_battle_pos)

            # Click confirm button
            print("[BB GOLD END] Clicking end battle confirmation...")
            send_discord_debug_log("BB Gold: Clicking end battle confirmation")
            fast_click(1483, 898)
            time.sleep(0.8)  # Optimized: reduced from 1.5s

            print("[BB GOLD END] 3-star battle ended successfully")
            send_discord_debug_log("BB Gold: 3-star battle ended")
            result["success"] = True
            return result
        else:
            # NO FALLBACK - Return failure so state machine can handle it
            print("[BB GOLD END] ERROR: End battle button not detected - cannot proceed")
            send_discord_debug_log("BB Gold: End battle button not found - returning failure", "ERROR")
            result["success"] = False
            return result

    elif stars_detected == 2:
        # 2 STAR PATH - use cached position if available, otherwise detect
        if cached_available:
            # Use cached position from deployment (INSTANT - no detection delay)
            button_type = cached_type
            button_x, button_y = cached_pos
            print(f"[BB GOLD END] 2 stars achieved - using CACHED {button_type} button")
            send_discord_debug_log(f"BB Gold: 2 stars - using cached {button_type} button (instant)")
        else:
            # No cache - detect button (slower)
            print("[BB GOLD END] 2 stars achieved - detecting surrender/end battle button...")
            send_discord_debug_log("BB Gold: 2 stars - detecting surrender/end battle button")
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            # Click surrender/end battle button - FAST CLICK for speed
            if not button_type:
                # NO FALLBACK - Return failure so state machine can handle it
                print("[BB GOLD END] ERROR: Surrender button not detected - cannot proceed")
                send_discord_debug_log("BB Gold: Surrender button not found - returning failure", "ERROR")
                result["success"] = False
                return result

        print(f"[BB GOLD END] Clicking {button_type} button at ({button_x}, {button_y})")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} at ({button_x}, {button_y})")
        fast_click(button_x, button_y)

        # Click confirm button
        print(f"[BB GOLD END] Clicking {button_type} confirmation...")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} confirmation")
        fast_click(1483, 898)
        time.sleep(0.8)  # Optimized: reduced from 1.5s

        # After surrender attempt, check if 3 stars appeared (Builder Hall destroyed during surrender)
        print("[BB GOLD END] Checking if 3 stars appeared after surrender attempt...")
        three_star_check = sum(1 for _ in range(3) if detect_three_stars())

        if three_star_check >= 2:
            # Edge case: Builder Hall was destroyed while clicking surrender
            # Surrender is NEGATED by 3 stars - must click end battle button instead
            result["final_stars"] = 3
            print("[BB GOLD END] 3 STARS DETECTED after surrender attempt! (Builder Hall destroyed during surrender)")
            runtime.gui.log_message("BB Gold: 3 stars appeared during surrender")
            send_discord_debug_log("BB Gold: 3 stars appeared after surrender - clicking end battle")

            # Must click end battle button since surrender was negated
            print("[BB GOLD END] Detecting end battle button (surrender negated by 3 stars)...")
            end_battle_pos = detect_end_battle_button()

            if not end_battle_pos:
                # NO FALLBACK - Return failure so state machine can handle it
                print("[BB GOLD END] ERROR: End battle button not detected (post-surrender 3 stars) - cannot proceed")
                send_discord_debug_log(
                    "BB Gold: End battle button not found (post-surrender) - returning failure", "ERROR"
                )
                result["success"] = False
                return result

            print(f"[BB GOLD END] Clicking end battle button at {end_battle_pos}")
            send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
            time.sleep(2.5)  # Wait for game to process 3-star state after surrender was negated
            fast_click(*end_battle_pos)

            # Click confirm button
            print("[BB GOLD END] Clicking end battle confirmation...")
            send_discord_debug_log("BB Gold: Clicking end battle confirmation")
            fast_click(1483, 898)
            time.sleep(0.8)  # Optimized: reduced from 1.5s

            print("[BB GOLD END] Post-surrender 3-star battle ended successfully")
            send_discord_debug_log("BB Gold: Post-surrender 3-star battle ended")
        else:
            print("[BB GOLD END] Surrender successful (2 stars)")
            send_discord_debug_log("BB Gold: surrendered successfully with 2 stars")

        result["success"] = True
        return result

    else:
        # 0/1 STAR PATH - use cached position if available, otherwise detect
        if cached_available:
            # Use cached position from deployment (INSTANT - no detection delay)
            button_type = cached_type
            button_x, button_y = cached_pos
            print(f"[BB GOLD END] {stars_detected} stars - using CACHED {button_type} button")
            send_discord_debug_log(f"BB Gold: {stars_detected} stars - using cached {button_type} button (instant)")
        else:
            # No cache - detect button (slower)
            print(f"[BB GOLD END] {stars_detected} stars - detecting surrender/end battle button...")
            send_discord_debug_log(f"BB Gold: {stars_detected} stars - detecting surrender/end battle button")
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if not button_type:
                # NO FALLBACK - Return failure so state machine can handle it
                print(f"[BB GOLD END] ERROR: No surrender/end battle button found ({stars_detected} stars)")
                send_discord_debug_log(
                    f"BB Gold: No button found ({stars_detected} stars) - returning failure", "ERROR"
                )
                result["success"] = False
                return result

        print(f"[BB GOLD END] Clicking {button_type} button at ({button_x}, {button_y})")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} at ({button_x}, {button_y})")
        fast_click(button_x, button_y)

        # Click confirm button
        print(f"[BB GOLD END] Clicking {button_type} confirmation...")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} confirmation")
        fast_click(1483, 898)
        time.sleep(0.8)

        print(f"[BB GOLD END] Battle ended successfully ({stars_detected} stars)")
        send_discord_debug_log(f"BB Gold: Battle ended with {stars_detected} stars")
        result["success"] = True
        return result


def increment_bb_gold_counter():
    """
    Increment BB Gold attack counter and collect loot if interval reached.
    Extracts counter logic from original handle_bb_gold_mode().
    """
    global bb_gold_attack_count
    settings = runtime.gui.get_settings()
    collect_interval = settings.get("bb_collect_interval", 12)
    bb_gold_attack_count += 1

    print(f"[BB GOLD] Attack count: {bb_gold_attack_count}/{collect_interval}")
    send_discord_debug_log(f"BB Gold: Attack {bb_gold_attack_count}/{collect_interval} completed")

    # Collect loot every N attacks (configurable)
    if bb_gold_attack_count >= collect_interval:
        print(f"[BB GOLD] {collect_interval} attacks completed - collecting loot!")
        runtime.gui.log_message(f"BB Gold: {collect_interval} attacks done - collecting loot")
        send_discord_debug_log(f"BB Gold: {collect_interval} attacks completed - starting loot collection")

        collect_bb_loot()

        # Reset counter
        bb_gold_attack_count = 0
        print("[BB GOLD] Counter reset - starting new cycle")
        send_discord_debug_log("BB Gold: Loot collected, counter reset to 0")


def save_bb_gold_attack_duration(context):
    """
    Save BB Gold attack duration to CSV file.

    Args:
        context: Attack context dict containing 'attack_start_time' and 'stars_detected'
    """
    attack_start_time = context.get("attack_start_time")
    if attack_start_time is None:
        print("[BB GOLD] No attack start time recorded - skipping duration logging")
        return

    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time
    stars = context.get("final_stars", context.get("stars_detected", 0))

    # Get the troop mode used for this attack
    troop_mode = runtime.gui.get_settings().get("bb_gold_troop_mode", "night_witches")
    # Map internal names to display names
    troop_mode_display = {
        "night_witches": "Night Witches",
        "bomber_night_witches": "Bomber + Night Witches",
        "baby_dragons": "Baby Dragons",
    }.get(troop_mode, troop_mode)

    csv_file = "data/bb_gold_time.csv"
    file_exists = os.path.exists(csv_file)

    try:
        import csv

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Loop #", "Duration (seconds)", "Stars", "Troop Mode", "Timestamp"])
            writer.writerow(
                [
                    bb_gold_attack_count + 1,
                    f"{attack_duration:.2f}",
                    stars,
                    troop_mode_display,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
        print(
            f"[BB GOLD] Attack duration: {attack_duration:.2f}s, {stars} stars, mode: {troop_mode_display} (saved to {csv_file})"
        )
        send_discord_debug_log(
            f"BB Gold: Attack completed in {attack_duration:.2f}s with {stars} stars ({troop_mode_display})"
        )
    except Exception as e:
        print(f"[BB GOLD] Error saving timing to CSV: {e}")
        send_discord_debug_log(f"BB Gold: Error saving timing - {e}", "WARNING")
