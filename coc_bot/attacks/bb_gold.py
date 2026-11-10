"""Builder Base gold farming routine, driven by an explicit state machine."""

import os
import random
import time
from datetime import datetime
from enum import auto, Enum

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import fast_click, human_like_move_click
from coc_bot.input.camera import click_in_square
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
from coc_bot.vision.ocr import check_bb_attacker_text
from coc_bot.vision.screens import (
    detect_current_game_state,
    detect_end_battle_button,
    detect_end_screen_state,
    detect_ghost_attack,
    detect_in_base_state,
    detect_return_home_button,
    detect_surrender_or_end_battle,
    detect_three_stars,
    detect_two_stars,
)

bb_gold_attack_count = 0  # Counter for BB Gold loot collection every 12 attacks


# BB Gold State Machine Enum
class BBGoldState(Enum):
    """BB Gold mode states - explicit lifecycle tracking"""
    IN_BASE = auto()              # At home base, army_button.png visible
    SEARCHING = auto()            # Search button clicked, waiting for match
    ATTACK_READY = auto()         # "Attacker" text confirmed, ready to deploy
    TROOPS_DEPLOYING = auto()     # Battle Machine/Night Witches being placed
    BATTLE_ACTIVE = auto()        # All troops deployed, monitoring stars
    BATTLE_ENDING = auto()        # 2/3 stars detected or timeout, clicking surrender/end
    END_SCREEN = auto()           # Battle finished, on victory/defeat screen
    RETURNING_HOME = auto()       # Return button clicked, transitioning to base
    ERROR_RECOVERY = auto()       # Ghost attack or error state, recovering


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
    if runtime.gui.get_settings().get('bb_gold_dragon_debug_positions', False):
        print("[BB DRAGONS] Debug mode enabled - saving position visualization...")
        save_bb_dragon_debug_visualization(all_coords, dragon_coords, bm_coord)

    KEYS = config.KEYS
    surrender_pos = None

    # === DEPLOY BATTLE MACHINE FIRST ===
    print(f"[BB DRAGONS] Deploying Battle Machine first at {bm_coord}...")
    keyboard.send(KEYS['queen'])  # 'q' key
    time.sleep(0.02)
    turbo_move_cursor(bm_coord[0], bm_coord[1])
    turbo_fast_click()
    time.sleep(0.3)  # Brief wait to check for surrender button

    # Check if surrender button appeared (deployment successful)
    button_type, button_x, button_y = detect_surrender_or_end_battle()

    if button_type:
        surrender_pos = (button_x, button_y)
        context['surrender_button_cached'] = True
        context['surrender_button_pos'] = surrender_pos
        context['surrender_button_type'] = button_type
        print(f"[BB DRAGONS] Battle Machine deployed successfully - {button_type} button detected")
        runtime.gui.update_bb_gold_state('BATTLE_ACTIVE')
    else:
        # Try fallback position for BM
        print("[BB DRAGONS] BM position failed, trying fallback...")
        fallback_coord = (1250, 200)  # Top center
        keyboard.send(KEYS['queen'])
        time.sleep(0.02)
        turbo_move_cursor(fallback_coord[0], fallback_coord[1])
        turbo_fast_click()
        time.sleep(0.3)

        button_type, button_x, button_y = detect_surrender_or_end_battle()
        if button_type:
            surrender_pos = (button_x, button_y)
            context['surrender_button_cached'] = True
            context['surrender_button_pos'] = surrender_pos
            context['surrender_button_type'] = button_type
            bm_coord = fallback_coord
            print(f"[BB DRAGONS] BM fallback deployment successful")
            runtime.gui.update_bb_gold_state('BATTLE_ACTIVE')
        else:
            print("[BB DRAGONS] CRITICAL: Failed to deploy Battle Machine!")
            send_discord_debug_log("BB Dragons: CRITICAL - Failed to deploy BM", "ERROR")
            return False

    # Activate Battle Machine ability immediately
    print("[BB DRAGONS] Activating Battle Machine ability...")
    keyboard.send('q')
    context['battle_machine_ability_time'] = time.time()

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
    troop_mode = runtime.gui.get_settings().get('bb_gold_troop_mode', 'night_witches')
    print(f"[BB GOLD DEPLOY] Troop mode: {troop_mode}")

    # Route to appropriate deployment function based on mode
    if troop_mode == 'baby_dragons':
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
        print(f"[BB GOLD DEPLOY] Using deployment position: {deployment_coord} (randomly selected from {len(valid_coords)} options)")
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
        keyboard.send(KEYS['queen'])  # 'q' key for Battle Machine
        time.sleep(0.2)
        human_like_move_click(deployment_coord[0], deployment_coord[1])
        time.sleep(0.5)

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)
            # CACHE surrender button position for fast clicking later (2-star path)
            context['surrender_button_cached'] = True
            context['surrender_button_pos'] = surrender_pos
            context['surrender_button_type'] = button_type
            print(f"[BB GOLD DEPLOY] Battle Machine deployed successfully at {deployment_coord} ({button_type} button detected)")
            print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
            send_discord_debug_log(f"BB Gold: Battle Machine deployed - {button_type} button cached at {surrender_pos}")
            # Update GUI to show BATTLE_ACTIVE immediately
            runtime.gui.update_bb_gold_state('BATTLE_ACTIVE')
            break
        else:
            print(f"[BB GOLD DEPLOY] Surrender/end battle button not found - invalid placement, trying again...")
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

            print(f"[BB GOLD DEPLOY] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})")

            # Deploy Battle Machine
            keyboard.send(KEYS['queen'])
            time.sleep(0.2)
            human_like_move_click(random_x, random_y)
            time.sleep(0.5)

            # Check if surrender or end battle button appeared
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                surrender_pos = (button_x, button_y)
                # CACHE surrender button position for fast clicking later (2-star path)
                context['surrender_button_cached'] = True
                context['surrender_button_pos'] = surrender_pos
                context['surrender_button_type'] = button_type
                print(f"[BB GOLD DEPLOY] SUCCESS! Battle Machine deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected")
                print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
                send_discord_debug_log(f"BB Gold: Success with random coords - {button_type} button cached at {surrender_pos}")
                # Update GUI to show BATTLE_ACTIVE immediately
                runtime.gui.update_bb_gold_state('BATTLE_ACTIVE')
                deployment_coord = (random_x, random_y)  # Update deployment coord for Night Witches
                break

    if not surrender_pos:
        print("[BB GOLD DEPLOY] CRITICAL: Failed to deploy Battle Machine after 30 attempts!")
        send_discord_debug_log("BB Gold: CRITICAL - Failed to deploy after 30 attempts", "ERROR")
        return False

    # Activate Battle Machine ability immediately after deployment
    print("[BB GOLD DEPLOY] Activating Battle Machine ability...")
    send_discord_debug_log("BB Gold: Activating Battle Machine ability")
    keyboard.send('q')  # Battle Machine ability key
    context['battle_machine_ability_time'] = time.time()  # Track when ability was used
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
    if troop_mode == 'bomber_night_witches':
        context['bomber_ability_time'] = time.time()
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
    battle_machine_ability_time = context.get('battle_machine_ability_time')
    last_return_home_check = 0  # Track last Return Home check time
    return_home_check_interval = 2.0  # Check every 2 seconds to reduce overhead

    result = {
        'stars': 0,
        'timeout_without_stars': False,
        'return_home_pos': None
    }

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
                result['timeout_without_stars'] = True
                result['return_home_pos'] = return_home_pos
                print(f"[BB GOLD MONITOR] Return Home button detected at {return_home_pos} - battle ended without stars")
                runtime.gui.log_message("BB Gold: Battle ended - returning home")
                send_discord_debug_log("BB Gold: Return Home detected - battle ended without stars")
                break

        # Re-activate Battle Machine ability every 14 seconds if battle is still ongoing
        if (battle_machine_ability_time is not None and
            current_time - battle_machine_ability_time >= 14):
            print("[BB GOLD MONITOR] 14 seconds elapsed - re-activating Battle Machine ability...")
            send_discord_debug_log("BB Gold: Re-activating Battle Machine ability after 14 seconds")
            keyboard.send('q')  # Re-activate Battle Machine ability
            battle_machine_ability_time = current_time  # Reset timer for next activation
            context['battle_machine_ability_time'] = current_time
            time.sleep(0.2)

        # Re-activate Bomber ability every 22 seconds if enabled and battle is still ongoing
        bomber_ability_time = context.get('bomber_ability_time')
        if (bomber_ability_time is not None and
            current_time - bomber_ability_time >= 22):
            print("[BB GOLD MONITOR] 22 seconds elapsed - re-activating Bomber ability...")
            send_discord_debug_log("BB Gold: Re-activating Bomber ability after 22 seconds")
            keyboard.send('1')  # Re-activate Bomber ability (slot 1)
            context['bomber_ability_time'] = current_time
            time.sleep(0.2)

        # Check for 2 stars first (most common case) with double verification (optimized from 3x)
        two_star_verification = sum(1 for _ in range(2) if detect_two_stars())

        if two_star_verification >= 2:  # If both checks passed
            # Check if "try for 3 stars" is enabled for Baby Dragons
            try_3_stars = runtime.gui.get_settings().get('bb_gold_try_3_stars', False)
            troop_mode = runtime.gui.get_settings().get('bb_gold_troop_mode', 'night_witches')

            if try_3_stars and troop_mode == 'baby_dragons':
                # Skip 2-star exit, continue monitoring for 3 stars
                if result['stars'] < 2:  # Only log once when first reaching 2 stars
                    result['stars'] = 2
                    print("[BB GOLD MONITOR] 2 STARS DETECTED! Continuing for 3 stars...")
                    runtime.gui.log_message("BB Gold: 2 stars - trying for 3...")
                    send_discord_debug_log("BB Gold: 2 stars detected - continuing for 3 stars")
                # Don't break - continue monitoring for 3 stars or Return Home
            else:
                result['stars'] = 2
                print("[BB GOLD MONITOR] 2 STARS DETECTED! Surrendering immediately...")
                runtime.gui.log_message("BB Gold: 2 stars detected - surrendering")
                send_discord_debug_log("BB Gold: 2 stars detected - surrendering immediately")
                break

        # Check for 3 stars (rare edge case - Builder Hall destroyed last before 2nd star appears)
        three_star_verification = sum(1 for _ in range(2) if detect_three_stars())

        if three_star_verification >= 2:  # If both checks passed
            result['stars'] = 3
            print("[BB GOLD MONITOR] 3 STARS DETECTED! (Builder Hall was last building)")
            runtime.gui.log_message("BB Gold: 3 stars detected!")
            send_discord_debug_log("BB Gold: 3 stars detected - waiting 7 seconds before ending")

            # Wait 7 seconds as requested for 3 stars
            print("[BB GOLD MONITOR] Waiting 7 seconds...")
            time.sleep(7)
            break

        time.sleep(0.5)  # Check every ~0.5 seconds

    if result['stars'] == 0 and not result['timeout_without_stars']:
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
    result = {'success': False, 'final_stars': stars_detected}

    # Check if we have a cached surrender button position (from deployment)
    cached_available = context and context.get('surrender_button_cached', False)
    if cached_available:
        cached_pos = context.get('surrender_button_pos')
        cached_type = context.get('surrender_button_type', 'surrender')
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
            result['success'] = True
            return result
        else:
            # NO FALLBACK - Return failure so state machine can handle it
            print("[BB GOLD END] ERROR: End battle button not detected - cannot proceed")
            send_discord_debug_log("BB Gold: End battle button not found - returning failure", "ERROR")
            result['success'] = False
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
                result['success'] = False
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
            result['final_stars'] = 3
            print("[BB GOLD END] 3 STARS DETECTED after surrender attempt! (Builder Hall destroyed during surrender)")
            runtime.gui.log_message("BB Gold: 3 stars appeared during surrender")
            send_discord_debug_log("BB Gold: 3 stars appeared after surrender - clicking end battle")

            # Must click end battle button since surrender was negated
            print("[BB GOLD END] Detecting end battle button (surrender negated by 3 stars)...")
            end_battle_pos = detect_end_battle_button()

            if not end_battle_pos:
                # NO FALLBACK - Return failure so state machine can handle it
                print("[BB GOLD END] ERROR: End battle button not detected (post-surrender 3 stars) - cannot proceed")
                send_discord_debug_log("BB Gold: End battle button not found (post-surrender) - returning failure", "ERROR")
                result['success'] = False
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

        result['success'] = True
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
                send_discord_debug_log(f"BB Gold: No button found ({stars_detected} stars) - returning failure", "ERROR")
                result['success'] = False
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
        result['success'] = True
        return result


def increment_bb_gold_counter():
    """
    Increment BB Gold attack counter and collect loot if interval reached.
    Extracts counter logic from original handle_bb_gold_mode().
    """
    global bb_gold_attack_count
    settings = runtime.gui.get_settings()
    collect_interval = settings.get('bb_collect_interval', 12)
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
    attack_start_time = context.get('attack_start_time')
    if attack_start_time is None:
        print("[BB GOLD] No attack start time recorded - skipping duration logging")
        return

    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time
    stars = context.get('final_stars', context.get('stars_detected', 0))

    # Get the troop mode used for this attack
    troop_mode = runtime.gui.get_settings().get('bb_gold_troop_mode', 'night_witches')
    # Map internal names to display names
    troop_mode_display = {
        'night_witches': 'Night Witches',
        'bomber_night_witches': 'Bomber + Night Witches',
        'baby_dragons': 'Baby Dragons'
    }.get(troop_mode, troop_mode)

    csv_file = "data/bb_gold_time.csv"
    file_exists = os.path.exists(csv_file)

    try:
        import csv
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Loop #', 'Duration (seconds)', 'Stars', 'Troop Mode', 'Timestamp'])
            writer.writerow([
                bb_gold_attack_count + 1,
                f'{attack_duration:.2f}',
                stars,
                troop_mode_display,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        print(f"[BB GOLD] Attack duration: {attack_duration:.2f}s, {stars} stars, mode: {troop_mode_display} (saved to {csv_file})")
        send_discord_debug_log(f"BB Gold: Attack completed in {attack_duration:.2f}s with {stars} stars ({troop_mode_display})")
    except Exception as e:
        print(f"[BB GOLD] Error saving timing to CSV: {e}")
        send_discord_debug_log(f"BB Gold: Error saving timing - {e}", "WARNING")


def _state_in_base(context):
    """IN_BASE: click the search button. Returns the next state."""
    print("[BB GOLD STATE] IN_BASE: Initiating search")
    runtime.gui.log_message("BB Gold: Starting search")

    # NEW: If queue is active, wait for storage UI to stabilize before checking
    try:
        if runtime.queue_manager and runtime.queue_manager.queue_active:
            print("[BB GOLD STATE] Queue active - waiting for storage UI to stabilize")
            time.sleep(1.5)  # Allow storage bars to fully render
    except NameError:
        pass  # queue_manager not initialized yet

    # NOTE: Star bonus handling is done by main loop's blind click at (73, 820)
    # No detection needed here - blind click handles all popups efficiently

    # Click search button - use fast click for instant response
    fast_click(*config.BB_SEARCH_BUTTON[:2])  # Extract (x, y) from (x1, y1, x2, y2)

    # Update state immediately after clicking
    current_state = BBGoldState.SEARCHING
    context['search_start_time'] = time.time()
    runtime.gui.update_bb_gold_state(current_state.name)
    return current_state



def _state_searching(current_state, state_timeout):
    """SEARCHING: wait for an opponent, or detect a ghost attack. Returns the next state."""
    print("[BB GOLD STATE] SEARCHING: Waiting for match...")

    # Wait for either attack ready or timeout
    timeout_start = time.time()
    while time.time() - timeout_start < state_timeout:

        # Check if attack ready
        if check_bb_attacker_text():
            print("[BB GOLD STATE] SEARCHING -> ATTACK_READY: Attacker text detected")
            current_state = BBGoldState.ATTACK_READY
            runtime.gui.update_bb_gold_state(current_state.name)
            break

        # Check for ghost attack after 10 seconds
        if time.time() - timeout_start > 10:
            if detect_ghost_attack():
                print("[BB GOLD STATE] SEARCHING -> ERROR_RECOVERY: Ghost attack")
                current_state = BBGoldState.ERROR_RECOVERY
                runtime.gui.update_bb_gold_state(current_state.name)
                break

        time.sleep(config.BB_LOAD_CHECK_INTERVAL)

    # Timeout handling
    if current_state == BBGoldState.SEARCHING:
        print("[BB GOLD STATE] SEARCHING timeout - assuming ghost attack")
        current_state = BBGoldState.ERROR_RECOVERY
        runtime.gui.update_bb_gold_state(current_state.name)
    return current_state



def _state_attack_ready(context):
    """ATTACK_READY: deploy the troops. Returns the next state."""
    print("[BB GOLD STATE] ATTACK_READY: Deploying troops")
    runtime.gui.log_message("BB Gold: Deploying troops")

    # Set attack start time
    context['attack_start_time'] = time.time()

    # Deploy troops using helper function
    deployment_success = deploy_bb_gold_troops(context)

    if deployment_success:
        context['troops_deployed'] = True
        current_state = BBGoldState.BATTLE_ACTIVE
        runtime.gui.update_bb_gold_state(current_state.name)
        print("[BB GOLD STATE] ATTACK_READY -> BATTLE_ACTIVE: Troops deployed")
    else:
        print("[BB GOLD STATE] ATTACK_READY -> ERROR_RECOVERY: Deployment failed")
        current_state = BBGoldState.ERROR_RECOVERY
        runtime.gui.update_bb_gold_state(current_state.name)
    return current_state



def _state_battle_active(context):
    """BATTLE_ACTIVE: monitor the battle until stars are earned or it ends. Returns the next state."""
    print("[BB GOLD STATE] BATTLE_ACTIVE: Monitoring for stars")
    runtime.gui.log_message("BB Gold: Monitoring battle...")

    # Monitor for stars or Return Home button (battle ended)
    battle_result = monitor_bb_gold_battle(context)

    context['stars_detected'] = battle_result['stars']
    context['battle_lost'] = battle_result['timeout_without_stars']

    # Cache Return Home button position if detected (for faster END_SCREEN handling)
    if battle_result.get('return_home_pos'):
        context['return_home_button_pos'] = battle_result['return_home_pos']

    current_state = BBGoldState.BATTLE_ENDING
    runtime.gui.update_bb_gold_state(current_state.name)
    print(f"[BB GOLD STATE] BATTLE_ACTIVE -> BATTLE_ENDING: {battle_result['stars']} stars, lost={battle_result['timeout_without_stars']}")
    return current_state



def _state_battle_ending(context, current_state):
    """BATTLE_ENDING: surrender or end the battle and find the end screen. Returns the next state."""
    print("[BB GOLD STATE] BATTLE_ENDING: Clicking surrender/end battle")

    # Skip if battle ended (Return Home button detected without stars)
    if not context.get('battle_lost', False):
        end_result = end_bb_gold_battle(context['stars_detected'], context)

        if not end_result['success']:
            print("[BB GOLD STATE] BATTLE_ENDING: End button click failed, retrying")
            time.sleep(1)
            return current_state

        # Update final stars from end result
        context['final_stars'] = end_result['final_stars']
    else:
        print("[BB GOLD STATE] BATTLE_ENDING: Battle ended (Return Home detected), skipping surrender")
        context['final_stars'] = 0
        # Return Home button position already cached from monitor_bb_gold_battle()

    # Special handling for 3 stars - FORCE return home button detection
    if context.get('final_stars', 0) == 3:
        print("[BB GOLD STATE] BATTLE_ENDING: 3 stars - forcing return home button detection (no fallback)")
        send_discord_debug_log("BB Gold: 3 stars - waiting for return home button confirmation")

        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            print(f"[BB GOLD STATE] BATTLE_ENDING: Checking for return home button (attempt {attempt}/{max_attempts})...")

            # Wait up to 5 seconds for return home button to appear
            timeout_start = time.time()
            return_home_found = False

            while time.time() - timeout_start < 5:
                return_home_pos = detect_return_home_button()
                if return_home_pos:
                    print(f"[BB GOLD STATE] BATTLE_ENDING: ✓ Return home button confirmed at {return_home_pos}")
                    send_discord_debug_log(f"BB Gold: Return home button confirmed (3 stars)")
                    # Cache position for END_SCREEN state
                    context['return_home_button_pos'] = return_home_pos
                    return_home_found = True
                    break
                time.sleep(0.3)  # Optimized: reduced from 0.5s

            if return_home_found:
                # Success - transition to END_SCREEN
                print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed (return home visible)")
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                break
            else:
                # Return home button not visible - end battle/surrender didn't work
                print(f"[BB GOLD STATE] BATTLE_ENDING: ✗ Return home button not visible (attempt {attempt}/{max_attempts})")
                send_discord_debug_log(f"BB Gold: Return home not visible - clicking end battle again (attempt {attempt})", "WARNING")

                # Click end battle button again
                end_battle_pos = detect_end_battle_button()
                if end_battle_pos:
                    print(f"[BB GOLD STATE] BATTLE_ENDING: Clicking end battle button at {end_battle_pos}")
                    fast_click(*end_battle_pos)
                else:
                    print("[BB GOLD STATE] BATTLE_ENDING: End battle button not detected, using fallback")
                    fast_click(144, 1080)

                time.sleep(1.0)

                # Click confirm
                print("[BB GOLD STATE] BATTLE_ENDING: Clicking confirmation")
                fast_click(1483, 898)
                time.sleep(1.0)  # Optimized: reduced from 2.0s

        if current_state != BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] BATTLE_ENDING: ERROR - Failed to confirm return home button after 5 attempts")
            send_discord_debug_log("BB Gold: CRITICAL - Failed to confirm end screen after 5 attempts", "ERROR")
            # Assume end screen present to avoid getting stuck
            current_state = BBGoldState.END_SCREEN
            runtime.gui.update_bb_gold_state(current_state.name)

    else:
        # 0/1/2 stars - use standard end screen detection with fallback
        print("[BB GOLD STATE] BATTLE_ENDING: 0/1/2 stars - standard end screen detection")
        end_screen_timeout = getattr(config, 'BB_END_SCREEN_TIMEOUT', 10)
        timeout_start = time.time()
        while time.time() - timeout_start < end_screen_timeout:
            end_screen = detect_end_screen_state()
            if end_screen['detected']:
                print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed")
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                context['star_bonus'] = end_screen['star_bonus']
                # Cache return home button position if detected
                if end_screen.get('return_button_pos'):
                    context['return_home_button_pos'] = end_screen['return_button_pos']
                break
            time.sleep(0.3)  # Optimized: reduced from 0.5s

        if current_state != BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] BATTLE_ENDING: End screen not detected, assuming present")
            current_state = BBGoldState.END_SCREEN
            runtime.gui.update_bb_gold_state(current_state.name)
    return current_state



def handle_bb_gold_mode_stateful():
    """
    Handle BB Gold mode using explicit state machine.

    States:
    1. IN_BASE -> SEARCHING: Click search button
    2. SEARCHING -> ATTACK_READY: "Attacker" text detected
    3. ATTACK_READY -> BATTLE_ACTIVE: Deploy Battle Machine + Night Witches
    4. BATTLE_ACTIVE -> BATTLE_ENDING: 2/3 stars or Return Home detected (battle ended)
    5. BATTLE_ENDING -> END_SCREEN: Surrender/end clicked, confirm end screen
    6. END_SCREEN -> RETURNING_HOME: Click return button
    7. RETURNING_HOME -> IN_BASE: Verify back at base
    8. ERROR_RECOVERY -> IN_BASE: Click return button, verify arrival

    Returns:
        bool: True if attack completed successfully, False if error
    """
    current_state = BBGoldState.IN_BASE
    context = {
        'retry_count': 0,
        'troops_deployed': False,
        'stars_detected': 0,
        'attack_start_time': None,
        'battle_machine_ability_time': None,
        'battle_lost': False
    }

    state_timeout = getattr(config, 'BB_STATE_DETECTION_TIMEOUT', 30)
    max_retries = getattr(config, 'BB_LOAD_MAX_RETRIES', 3)

    print("[BB GOLD STATE] Starting stateful attack")
    send_discord_debug_log("BB Gold: Starting state machine attack")

    # Main state machine loop
    iteration_count = 0
    max_iterations = 100  # Safety limit to prevent infinite loops

    while iteration_count < max_iterations:
        iteration_count += 1

        # UNIVERSAL: Return Home detection - if found in any state, we're on end screen
        # This provides reliable error recovery since Return Home ONLY appears on end screen
        if current_state not in [BBGoldState.END_SCREEN, BBGoldState.RETURNING_HOME]:
            # Throttle checks to every 0.5 seconds to minimize performance impact
            last_universal_check = context.get('last_return_home_universal_check', 0)
            current_time = time.time()
            if current_time - last_universal_check >= 0.5:
                context['last_return_home_universal_check'] = current_time
                return_home_pos = detect_return_home_button(quiet=True)
                if return_home_pos:
                    print(f"[BB GOLD STATE] !! Return Home detected in {current_state.name} - transitioning to END_SCREEN")
                    context['return_home_button_pos'] = return_home_pos
                    current_state = BBGoldState.END_SCREEN
                    runtime.gui.update_bb_gold_state(current_state.name)
                    continue  # Skip to END_SCREEN handling

        # STATE 1: IN_BASE -> SEARCHING
        if current_state == BBGoldState.IN_BASE and context['retry_count'] == 0:
            current_state = _state_in_base(context)
            continue

        # STATE 2: SEARCHING -> ATTACK_READY
        if current_state == BBGoldState.SEARCHING:
            current_state = _state_searching(current_state, state_timeout)
            continue

        # STATE 3: ATTACK_READY -> BATTLE_ACTIVE
        if current_state == BBGoldState.ATTACK_READY:
            current_state = _state_attack_ready(context)
            continue

        # STATE 4: BATTLE_ACTIVE -> BATTLE_ENDING
        if current_state == BBGoldState.BATTLE_ACTIVE:
            current_state = _state_battle_active(context)
            continue

        # STATE 5: BATTLE_ENDING -> END_SCREEN
        if current_state == BBGoldState.BATTLE_ENDING:
            current_state = _state_battle_ending(context, current_state)

            continue

        # STATE 6: END_SCREEN -> RETURNING_HOME
        if current_state == BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] END_SCREEN: Detecting and clicking return button")
            runtime.gui.log_message("BB Gold: Returning home")

            # Use cached position if available (from BATTLE_ENDING state for 3 stars)
            cached_pos = context.get('return_home_button_pos')
            clicked = False  # Initialize clicked variable

            if cached_pos:
                # Use cached position - no need to detect again
                print(f"[BB GOLD STATE] END_SCREEN: Using cached return home position {cached_pos} - clicking instantly")
                send_discord_debug_log(f"BB Gold: Clicking cached return home at {cached_pos}")
                fast_click(*cached_pos)
                clicked = True  # Mark as clicked
            else:
                # No cached position - actively detect
                print("[BB GOLD STATE] END_SCREEN: Scanning for return home button...")
                max_wait = 10  # Maximum 10 seconds to find button
                start_time = time.time()

                # Exponential backoff - fast checks early, slower later
                import itertools
                check_intervals = [0.05, 0.05, 0.1, 0.1, 0.2, 0.2, 0.3]
                for interval in itertools.cycle(check_intervals):
                    if time.time() - start_time >= max_wait:
                        break
                    return_home_pos = detect_return_home_button()
                    if return_home_pos:
                        print(f"[BB GOLD STATE] END_SCREEN: ✓ Return home button detected at {return_home_pos} - clicking instantly")
                        send_discord_debug_log(f"BB Gold: Clicking return home at {return_home_pos}")
                        fast_click(*return_home_pos)
                        clicked = True
                        break
                    time.sleep(interval)  # Exponential backoff

                if not clicked:
                    # NO FALLBACK - Detect actual state and handle appropriately
                    print("[BB GOLD STATE] END_SCREEN: Return home button not detected after 10s - detecting actual state")
                    send_discord_debug_log("BB Gold: Return home button not found - detecting state", "WARNING")

                    detected_state = detect_current_game_state()

                    if detected_state == 'in_base':
                        # Already at base - skip to IN_BASE state
                        print("[BB GOLD STATE] END_SCREEN: Already at base - transitioning to IN_BASE")
                        send_discord_debug_log("BB Gold: Already at base (return button not needed)")
                        current_state = BBGoldState.IN_BASE
                        runtime.gui.update_bb_gold_state(current_state.name)
                        save_bb_gold_attack_duration(context)
                        increment_bb_gold_counter()
                        return True

                    elif detected_state == 'battle_active':
                        # Still in battle - need to surrender
                        print("[BB GOLD STATE] END_SCREEN: Still in active battle - attempting surrender")
                        send_discord_debug_log("BB Gold: Stuck in battle - surrendering", "WARNING")
                        button_type, x, y = detect_surrender_or_end_battle()
                        if button_type == 'surrender':
                            fast_click(x, y)
                            time.sleep(0.5)
                            # Click confirmation
                            fast_click(1483, 898)
                            time.sleep(2.0)
                        current_state = BBGoldState.BATTLE_ENDING
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == 'battle_ending':
                        # Battle ending - transition to BATTLE_ENDING state
                        print("[BB GOLD STATE] END_SCREEN: Battle still ending - transitioning to BATTLE_ENDING")
                        current_state = BBGoldState.BATTLE_ENDING
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == 'end_screen':
                        # This shouldn't happen (we just failed to detect return button)
                        # But detection succeeded now - retry click
                        print("[BB GOLD STATE] END_SCREEN: Return button now detected - retrying click")
                        return_home_pos = detect_return_home_button()
                        if return_home_pos:
                            fast_click(*return_home_pos)
                            clicked = True
                        else:
                            # Still can't find it - enter error recovery
                            print("[BB GOLD STATE] END_SCREEN: Return button still not found - entering ERROR_RECOVERY")
                            send_discord_debug_log("BB Gold: Return button inconsistent - error recovery", "ERROR")
                            current_state = BBGoldState.ERROR_RECOVERY
                            runtime.gui.update_bb_gold_state(current_state.name)
                            continue

                    else:  # 'unknown'
                        # Unknown state - enter error recovery
                        print("[BB GOLD STATE] END_SCREEN: Unknown state detected - entering ERROR_RECOVERY")
                        send_discord_debug_log("BB Gold: Unknown state - entering error recovery", "ERROR")
                        current_state = BBGoldState.ERROR_RECOVERY
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

            # Only proceed to RETURNING_HOME if return button was actually clicked
            if clicked:
                time.sleep(1.0)  # Brief wait for transition
                current_state = BBGoldState.RETURNING_HOME
                runtime.gui.update_bb_gold_state(current_state.name)
                print("[BB GOLD STATE] END_SCREEN -> RETURNING_HOME: Return clicked")
            continue

        # STATE 7: RETURNING_HOME -> IN_BASE
        if current_state == BBGoldState.RETURNING_HOME:
            print("[BB GOLD STATE] RETURNING_HOME: Waiting for base arrival")

            # Wait for IN_BASE confirmation
            return_timeout = getattr(config, 'BB_RETURN_HOME_TIMEOUT', 15)
            timeout_start = time.time()
            while time.time() - timeout_start < return_timeout:
                if detect_in_base_state():
                    print("[BB GOLD STATE] RETURNING_HOME -> IN_BASE: Army button detected")
                    runtime.gui.update_bb_gold_state("IN_BASE")

                    # Save attack duration to CSV
                    save_bb_gold_attack_duration(context)

                    # Update attack counter
                    increment_bb_gold_counter()

                    return True  # Success!
                time.sleep(0.3)  # Optimized: reduced from 0.5s

            # Timeout - assume we're back anyway
            print("[BB GOLD STATE] RETURNING_HOME: Base detection timeout, assuming success")
            save_bb_gold_attack_duration(context)
            increment_bb_gold_counter()
            return True

        # STATE 8: ERROR_RECOVERY -> IN_BASE
        if current_state == BBGoldState.ERROR_RECOVERY:
            print("[BB GOLD STATE] ERROR_RECOVERY: Attempting recovery")
            runtime.gui.log_message("BB Gold: Error recovery")
            send_discord_debug_log("BB Gold: Entering error recovery", "WARNING")

            # Quick check: Return Home button means we're on end screen (cache position for fast click)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                print("[BB GOLD STATE] ERROR_RECOVERY: Return Home detected - on end screen")
                context['return_home_button_pos'] = return_home_pos
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                continue

            # If not on end screen, detect what state we're actually in
            detected_state = detect_current_game_state()

            if detected_state == 'in_base':
                # Already recovered - return to IN_BASE
                print("[BB GOLD STATE] ERROR_RECOVERY: Already at base - recovery successful")
                send_discord_debug_log("BB Gold: Error recovery successful (already at base)")
                context['retry_count'] += 1
                if context['retry_count'] < max_retries:
                    print(f"[BB GOLD STATE] ERROR_RECOVERY -> IN_BASE: Retry {context['retry_count']}/{max_retries}")
                    current_state = BBGoldState.IN_BASE
                    runtime.gui.update_bb_gold_state(current_state.name)
                else:
                    print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                    send_discord_debug_log("BB Gold: Max retries exceeded, aborting", "ERROR")
                    return False

            elif detected_state == 'battle_active':
                # Stuck in battle - surrender to exit
                print("[BB GOLD STATE] ERROR_RECOVERY: In active battle - surrendering")
                send_discord_debug_log("BB Gold: Error recovery - surrendering from battle", "WARNING")
                button_type, x, y = detect_surrender_or_end_battle()
                if button_type == 'surrender':
                    fast_click(x, y)
                    time.sleep(0.5)
                    # Click confirmation
                    fast_click(1483, 898)
                    time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    runtime.gui.update_bb_gold_state(current_state.name)
                else:
                    # Can't find surrender - try minimal troop deployment to enable it
                    print("[BB GOLD STATE] ERROR_RECOVERY: Surrender not found - deploying troop")
                    fast_click(1282, 720)  # Deploy one troop
                    time.sleep(3.0)
                    # Try surrender again
                    button_type, x, y = detect_surrender_or_end_battle()
                    if button_type == 'surrender':
                        fast_click(x, y)
                        time.sleep(0.5)
                        fast_click(1483, 898)
                        time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    runtime.gui.update_bb_gold_state(current_state.name)

            elif detected_state == 'battle_ending' or detected_state == 'end_screen':
                # Battle ending or end screen - transition appropriately
                print(f"[BB GOLD STATE] ERROR_RECOVERY: Detected {detected_state} - transitioning")
                if detected_state == 'battle_ending':
                    current_state = BBGoldState.BATTLE_ENDING
                else:
                    current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)

            else:  # 'unknown'
                # Unknown state - try clicking return button and retry
                print("[BB GOLD STATE] ERROR_RECOVERY: Unknown state - clicking return button")
                send_discord_debug_log("BB Gold: Unknown state in error recovery - clicking return", "WARNING")
                click_in_square(config.BB_RETURN_BUTTON_GHOST)
                time.sleep(config.BB_RETRY_WAIT_TIME)

                # Check again if we're at base now
                if detect_in_base_state():
                    print("[BB GOLD STATE] ERROR_RECOVERY: Return click worked - at base now")
                    context['retry_count'] += 1
                    if context['retry_count'] < max_retries:
                        current_state = BBGoldState.IN_BASE
                        runtime.gui.update_bb_gold_state(current_state.name)
                    else:
                        print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                        return False
                else:
                    # Still stuck - increment retry and continue looping
                    context['retry_count'] += 1
                    if context['retry_count'] >= max_retries:
                        print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded - aborting")
                        send_discord_debug_log("BB Gold: Max error recovery retries exceeded", "ERROR")
                        return False
                    print(f"[BB GOLD STATE] ERROR_RECOVERY: Still stuck - retry {context['retry_count']}/{max_retries}")
                    time.sleep(2)

            continue

        # Safety: break infinite loops
        print(f"[BB GOLD STATE] WARNING: Unexpected state {current_state}, breaking")
        break

    # If we exit the loop without returning, something went wrong
    print("[BB GOLD STATE] ERROR: State machine exceeded max iterations or entered invalid state")
    send_discord_debug_log("BB Gold: State machine error - max iterations exceeded", "ERROR")
    return False


# Alias the new stateful function as the main function
def handle_bb_gold_mode():
    """
    Handle BB Gold mode using state machine.
    This is an alias for handle_bb_gold_mode_stateful().
    """
    return handle_bb_gold_mode_stateful()
