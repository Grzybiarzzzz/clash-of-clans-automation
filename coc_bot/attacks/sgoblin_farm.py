"""Super Goblin farming routine."""

import random
import threading
import time

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.attacks.common import (
    deploy_wall_breaker,
    handle_post_battle,
    skip_base,
    wait_for_battle_end,
)
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import calculate_deployment_step, get_opposite_side
from coc_bot.humanized_input import fast_click, human_like_move_click
from coc_bot.input.camera import move_camera_to_opposite_side, move_camera_to_side
from coc_bot.vision.buildings import scan_achievement_buildings_parallel_priority
from coc_bot.vision.ocr import evaluate_base_resources
from coc_bot.vision.screens import (
    detect_return_home_button,
    detect_surrender_or_end_battle,
    wait_for_attack_screen_ready,
)

def _deploy_first_side(KEYS, chosen_side, settings, side_coords, troop_counts):
    """Passes 1 and 2: wall breakers (optional) and the first half of the troops on the chosen side. Returns whether wall breakers are in use."""
    print("Deploying first wave of troops...")
    send_discord_debug_log("Deploying first wave of troops")

    # Check if wall breakers should be deployed
    use_wallbreakers = settings.get('sgoblin_use_wallbreakers', False)

    if use_wallbreakers:
        # NEW MODE: Deploy with wall breakers interspersed
        print("Using wall breaker deployment mode")
        send_discord_debug_log("Using wall breaker deployment mode")
        wb_positions = config.WALL_BREAKER_POSITIONS[chosen_side]

    # NEW DEPLOYMENT STRATEGY: 4 fast passes (2 per side) through entire coordinate path
    # Each pass deploys ~1/4 of troops by moving quickly through all coordinates
    print("[SGOBLIN FARM] Using 4-pass deployment strategy (2 per side)")
    send_discord_debug_log("SGoblin Farm: 4-pass deployment - 2 per side")

    # Deploy wall breakers FIRST on first side if enabled (before goblins)
    if use_wallbreakers:
        print(f"[SGOBLIN FARM] Deploying 2 Super Wall Breakers on {chosen_side}...")
        send_discord_debug_log(f"SGoblin Farm: Deploying wall breakers on {chosen_side}")
        deploy_wall_breaker(wb_positions[0])
        deploy_wall_breaker(wb_positions[1])
        print(f"[SGOBLIN FARM] Wall breakers deployed on {chosen_side}")
        send_discord_debug_log(f"2 Wall Breakers deployed on {chosen_side}")
        time.sleep(0.5)  # Wait for walls to start breaking

    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'
            # Get all available coordinates for this side
            available_coords = side_coords['units']

            # Calculate deployment step for even distribution (4 passes total, 2 per side)
            troops_per_pass = troop_count // 4  # Divided across 4 total passes
            deployment_step = calculate_deployment_step(troops_per_pass, len(available_coords))

            print(f"[SGOBLIN FARM] Deploying {troop_count} {troop_key} troops (2 passes on {chosen_side})")
            print(f"[SGOBLIN FARM] Step size: {deployment_step} (~{troops_per_pass} troops per pass)")

            # PASS 1 & 2: Deploy on first side (chosen_side)
            for pass_num in range(1, 3):
                print(f"  Pass {pass_num}/2 on {chosen_side}...")
                keyboard.send(KEYS[troop_key])
                time.sleep(0.05)

                # Start at first coordinate
                first_coord = available_coords[0]
                pyautogui.moveTo(*first_coord, duration=0.02)
                pyautogui.mouseDown()
                time.sleep(0.3)  # Short hold to start deployment

                # Fast drag through coordinates - dynamic step based on troop count
                for i in range(1, len(available_coords), deployment_step):
                    coord = available_coords[i]
                    pyautogui.moveTo(*coord, duration=0.003)  # VERY FAST movement
                    time.sleep(0.001)

                pyautogui.mouseUp()
                time.sleep(0.1)
                print(f"  Pass {pass_num} complete")

            # First side complete - 2 passes done
            send_discord_debug_log(f"First side ({chosen_side}) complete: 2 passes with {troop_count//2} troops")
            print(f"[SGOBLIN FARM] First side complete: ~{troop_count//2} {troop_key} deployed on {chosen_side}")
    return use_wallbreakers



def _deploy_heroes_and_siege(KEYS, settings, side_coords):
    """Deploy the four heroes with their ability timers, then the siege machine."""

    def activate_hero_ability_sgoblin(hero_role):
        """Activate hero ability after 1 second for SGoblin Farm"""
        time.sleep(1)
        keyboard.send(KEYS[hero_role])
        print(f"[SGOBLIN FARM] {hero_role.title()} ability activated at 1s")
        send_discord_debug_log(f"{hero_role.title()} ability activated after 1 second")
        # No troop reselection needed - first wave already deployed, second wave hasn't started yet

    print("Deploying heroes...")
    send_discord_debug_log("Deploying heroes")
    hero_pos = side_coords['hero']

    # Get hero ability timings from settings
    queen_timing = settings.get('queen_ability_timing', -1)
    king_timing = settings.get('king_ability_timing', -1)
    warden_timing = settings.get('warden_ability_timing', -1)
    rc_timing = settings.get('rc_ability_timing', -1)

    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }

    for role in ['queen', 'king', 'warden', 'rc']:
        # Deploy the hero
        keyboard.send(KEYS[role])
        time.sleep(0.05)
        pyautogui.moveTo(*hero_pos, duration=0.02)
        pyautogui.click()
        time.sleep(0.02)

        # Start ability timer only if not disabled (-1)
        timing = hero_timings[role]
        if timing != -1:
            ability_thread = threading.Thread(
                target=activate_hero_ability_sgoblin,
                args=(role,),
                daemon=True
            )
            ability_thread.start()
            send_discord_debug_log(f"{role.title()} ability timer started ({timing}s)")
        else:
            send_discord_debug_log(f"{role.title()} ability disabled")
        print(f"Deployed {role.title()}")

    print("All 4 heroes deployed")
    send_discord_debug_log("All 4 heroes deployed")

    # Deploy siege machine IMMEDIATELY after heroes (before abilities trigger at 1s)
    print("Deploying siege machine...")
    send_discord_debug_log("Deploying siege machine")
    keyboard.send('z')  # Siege machine hotkey
    time.sleep(0.05)
    pyautogui.moveTo(*hero_pos, duration=0.02)  # Same position as heroes
    pyautogui.click()
    time.sleep(0.02)
    print("Siege machine deployed")
    send_discord_debug_log("Siege machine deployed (before abilities trigger)")



def _deploy_opposite_side(KEYS, opposite_coords, opposite_side, troop_counts, use_wallbreakers):
    """Passes 3 and 4: wall breakers (optional) and the second half of the troops on the opposite side."""
    print(f"[SGOBLIN FARM] Deploying second half on opposite side ({opposite_side})...")
    send_discord_debug_log(f"SGoblin Farm: Deploying on {opposite_side}")

    # Deploy wall breakers FIRST on opposite side if enabled (before goblins)
    if use_wallbreakers:
        wb_positions_opposite = config.WALL_BREAKER_POSITIONS[opposite_side]
        print(f"[SGOBLIN FARM] Deploying 2 Super Wall Breakers on {opposite_side}...")
        send_discord_debug_log(f"SGoblin Farm: Deploying wall breakers on {opposite_side}")
        deploy_wall_breaker(wb_positions_opposite[0])
        deploy_wall_breaker(wb_positions_opposite[1])
        print(f"[SGOBLIN FARM] Wall breakers deployed on {opposite_side}")
        send_discord_debug_log(f"2 Wall Breakers deployed on {opposite_side}")
        time.sleep(0.5)  # Wait for walls to start breaking

    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'
            # Get all available coordinates for opposite side
            available_coords = opposite_coords['units']

            # Calculate deployment step for even distribution (same as first side)
            troops_per_pass = troop_count // 4  # Divided across 4 total passes
            deployment_step = calculate_deployment_step(troops_per_pass, len(available_coords))

            print(f"[SGOBLIN FARM] Deploying {troop_count} {troop_key} troops (2 passes on {opposite_side})")
            print(f"[SGOBLIN FARM] Step size: {deployment_step} (~{troops_per_pass} troops per pass)")

            # PASS 3 & 4: Deploy on opposite side
            for pass_num in range(3, 5):
                print(f"  Pass {pass_num}/4 on {opposite_side}...")
                keyboard.send(KEYS[troop_key])
                time.sleep(0.05)

                # Start at first coordinate
                first_coord = available_coords[0]
                pyautogui.moveTo(*first_coord, duration=0.02)
                pyautogui.mouseDown()
                time.sleep(0.3)  # Short hold to start deployment

                # Fast drag through coordinates - dynamic step based on troop count
                for i in range(1, len(available_coords), deployment_step):
                    coord = available_coords[i]
                    pyautogui.moveTo(*coord, duration=0.003)  # VERY FAST movement
                    time.sleep(0.001)

                pyautogui.mouseUp()
                time.sleep(0.1)
                print(f"  Pass {pass_num} complete")

            # Second side complete - 4 passes total done
            send_discord_debug_log(f"Second side ({opposite_side}) complete: 2 passes with {troop_count//2} troops")
            print(f"[SGOBLIN FARM] Second side complete: ~{troop_count//2} {troop_key} deployed on {opposite_side}")

    print("[SGOBLIN FARM] All 4 passes complete - all troops deployed!")
    send_discord_debug_log("SGoblin Farm: All 4 passes complete")



def _deploy_leftover_troops(KEYS, opposite_coords, troop_counts):
    """Cleanup: drag the first non-empty troop slot along the deployment line to place leftovers."""
    print("Starting cleanup deployment phase (3 seconds)...")
    send_discord_debug_log("SGoblin: Cleanup phase - deploying remaining units")

    # Find first troop slot that has units
    cleanup_troop_key = None
    for i in range(7):
        if troop_counts[i] > 0:
            cleanup_troop_key = f'troop{i+1}'
            break

    if cleanup_troop_key:
        # Select the troop
        keyboard.send(KEYS[cleanup_troop_key])
        time.sleep(0.05)

        # Get coordinates from the opposite side (last deployed side)
        cleanup_coords = opposite_coords['units']
        num_cleanup_coords = len(cleanup_coords)

        # Start dragging backwards through coordinates for 3 seconds
        cleanup_start = time.time()
        cleanup_duration = 3.0  # 3 seconds

        # Start at first position
        pyautogui.moveTo(*cleanup_coords[0], duration=0.02)
        pyautogui.mouseDown()
        time.sleep(0.5)  # Hold in place to activate deployment mode (not camera drag)

        coord_idx = 0
        direction = 1  # 1 for forward, -1 for backward

        while (time.time() - cleanup_start) < cleanup_duration:
            coord_idx += direction

            # Reverse direction at boundaries
            if coord_idx >= num_cleanup_coords:
                coord_idx = num_cleanup_coords - 2
                direction = -1
            elif coord_idx < 0:
                coord_idx = 1
                direction = 1

            x, y = cleanup_coords[coord_idx]
            pyautogui.moveTo(x, y, duration=0.05)
            time.sleep(0.05)

        pyautogui.mouseUp()
        print("Cleanup deployment phase complete")
        send_discord_debug_log("SGoblin: Cleanup phase complete")



def _cast_spells_on_achievement_buildings(settings):
    """Cast spells on a detected achievement building when the setting is enabled."""
    cast_spells_enabled = settings.get('sgoblin_cast_spells', False)

    if cast_spells_enabled:
        # Scan for achievement buildings using parallel priority scan
        print("[PRIORITY SCAN] Scanning for achievement buildings...")
        send_discord_debug_log("SGoblin: Scanning achievement buildings")
        runtime.gui.log_message("Scanning for achievement buildings...")

        # PARALLEL SCAN using GUI priority list (3-5x faster than sequential)
        result = scan_achievement_buildings_parallel_priority(settings)

        if result is not None:
            x, y, confidence, building_type = result
            # Convert top-left to center coordinates
            bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
            center_x = x + bw // 2
            center_y = y + bh // 2
            print(f"CASTING SPELLS ON: {building_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
            runtime.gui.log_message(f"Casting spells on {building_type.replace('_', ' ')}")
            send_discord_debug_log(f"SGoblin: Casting on {building_type} at ({center_x}, {center_y})")

            # Deploy 1 Earthquake spell
            print("Deploying Earthquake spell...")
            keyboard.send('a')  # Earthquake hotkey
            time.sleep(0.02)
            fast_click(center_x, center_y)
            time.sleep(0.05)

            # Deploy 10 Lightning spells
            print("Deploying Lightning spells...")
            for i in range(10):
                keyboard.send('s')  # Lightning hotkey
                time.sleep(0.01)
                # Add slight variation to position (±3px like Achievement Farm)
                spell_x = center_x + random.randint(-3, 3)
                spell_y = center_y + random.randint(-3, 3)
                fast_click(spell_x, spell_y)
                time.sleep(0.03)
                print(f"  Lightning {i+1}/10 deployed")

            print(f"Spell casting complete on {building_type.replace('_', ' ')}")
            runtime.gui.log_message("Spells deployed successfully")
            send_discord_debug_log(f"SGoblin: 1 EQ + 10 Lightning on {building_type}")
        else:
            print("[PRIORITY SCAN] No achievement buildings found")
            runtime.gui.log_message("No achievement buildings detected")
            send_discord_debug_log("SGoblin: No buildings found")



def _surrender_or_end_battle():
    """Find the surrender or end-battle button (three attempts) and confirm leaving the battle."""
    print("Looking for surrender/end battle button...")
    send_discord_debug_log("Looking for surrender/end battle button")
    button_type = None
    button_x = None
    button_y = None

    for attempt in range(3):
        button_type, button_x, button_y = detect_surrender_or_end_battle()
        if button_type:
            break
        else:
            print(f"Surrender/end battle button not found, retry {attempt + 1}/3...")
            time.sleep(0.5)

    if button_type:
        print(f"{button_type.replace('_', ' ').title()} button found at ({button_x}, {button_y}), clicking...")
        send_discord_debug_log(f"SGoblin: {button_type} button found at ({button_x}, {button_y})")
        human_like_move_click(button_x, button_y)
        time.sleep(0.5)

        # Click confirmation
        print(f"Clicking {button_type} confirmation...")
        send_discord_debug_log(f"SGoblin: Clicking {button_type} confirmation")
        human_like_move_click(1483, 898)
        time.sleep(2)
    else:
        # NO FALLBACK - Detect actual state and handle appropriately
        print("Warning: Surrender button not found after 3 attempts! Detecting actual state...")
        send_discord_debug_log("SGoblin: Surrender button not found - detecting state", "WARNING")

        # Check if battle already ended (end battle button or return home button visible)
        button_type, x, y = detect_surrender_or_end_battle()
        if button_type == 'end_battle':
            print("Battle already ended - clicking end battle button")
            send_discord_debug_log("SGoblin: Battle ended before surrender - clicking end battle")
            human_like_move_click(x, y)
            time.sleep(1.5)
        elif detect_return_home_button():
            print("Already at end screen - surrender not needed")
            send_discord_debug_log("SGoblin: Already at end screen - skipping surrender")
        else:
            # Still in battle but can't find surrender - try deploying a troop to enable it
            print("Surrender not available - attempting troop deployment to enable surrender")
            send_discord_debug_log("SGoblin: Deploying troop to enable surrender", "WARNING")
            human_like_move_click(1282, 720)  # Deploy one troop
            time.sleep(2.0)

            # Try finding surrender again
            for retry in range(2):
                button_type, x, y = detect_surrender_or_end_battle()
                if button_type == 'surrender':
                    print(f"Surrender button now available at {x}, {y} - clicking")
                    human_like_move_click(x, y)
                    time.sleep(0.5)
                    human_like_move_click(1483, 898)
                    time.sleep(2)
                    break
                elif button_type == 'end_battle':
                    print("Battle ended - clicking end battle button")
                    human_like_move_click(x, y)
                    time.sleep(1.5)
                    break
                time.sleep(1.0)
            else:
                # Still can't find surrender after troop deployment - log error but continue
                print("ERROR: Could not find surrender or end battle button - continuing anyway")
                send_discord_debug_log("SGoblin: Failed to surrender - button not found after retries", "ERROR")
                time.sleep(3)  # Wait a bit for battle to potentially end on its own



def perform_sgoblin_farm_attack():
    """Perform SGoblin Farm attack - split army on opposite sides and surrender after 10s"""
    print("=== ENTERING SGOBLIN FARM MODE ===")
    send_discord_debug_log("=== ENTERING SGOBLIN FARM MODE ===")
    runtime.gui.log_message("SGoblin Farm mode activated")

    # Get current settings from GUI
    settings = runtime.gui.get_settings()

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[SGOBLIN] Attack screen not ready - skipping base")
        send_discord_debug_log("SGoblin Farm: Attack screen timeout - skipping", "WARNING")
        runtime.gui.log_message("SGoblin Farm: Attack screen timeout - skipping")
        skip_base()
        return "skipped"

    # OCR resources with retry if 0 detected - keep retrying until both values > 0
    retry_attempt = 0
    while True:
        gold, elixir = evaluate_base_resources()

        # If either value is 0, retry after 0.2 seconds (give more time for screen to load)
        if gold == 0 or elixir == 0:
            retry_attempt += 1
            print(f"[SGOBLIN] OCR returned 0 (gold={gold}, elixir={elixir}), retrying in 0.2s... (attempt {retry_attempt})")
            send_discord_debug_log(f"SGoblin Farm: OCR retry {retry_attempt} - gold={gold}, elixir={elixir}")
            time.sleep(0.2)
            continue

        # Success - both values are non-zero
        print(f"[SGOBLIN] OCR successful: gold={gold:,}, elixir={elixir:,}")
        break

    # Check if resources meet minimum threshold (no TH or AD check for SGoblin Farm)
    min_resources = settings.get('min_resources', 800000)
    total_resources = gold + elixir

    if total_resources < min_resources:
        print(f"Resources too low: {total_resources:,} < {min_resources:,}, skipping base")
        skip_base()
        return "skipped"  # Base was skipped, not attacked

    send_discord_debug_log(f"Base selected for SGoblin Farm: {total_resources:,} resources")

    # Attack screen already loaded by main_loop - proceed with deployment
    print("[SGOBLIN FARM] Starting SGoblin Farm attack...")

    # Get troop counts from settings
    troop_counts = settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])

    # Choose initial attack side randomly (only up/down for SGoblin Farm)
    sides = ['up', 'down']
    chosen_side = random.choice(sides)
    side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
    opposite_side = get_opposite_side(chosen_side)
    opposite_coords = config.SIDE_DEPLOYMENT_COORDS[opposite_side]

    print(f"SGoblin Farm: Deploying on {chosen_side} and {opposite_side}")
    send_discord_debug_log(f"SGoblin Farm: Deploying on {chosen_side} and {opposite_side}")
    runtime.gui.log_message(f"SGoblin Farm: Attacking from {chosen_side} and {opposite_side}")

    # Use standard hotkeys (no alternate hotkey detection for SGoblin Farm speed)
    KEYS = config.KEYS

    # Move camera to first side (fast mode for SGoblin Farm)
    move_camera_to_side(chosen_side, fast_mode=True)

    # Zoom out before deploying troops (ensure camera movement has finished)
    time.sleep(0.1)  # Wait for camera drag to complete
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    # Zoom out aggressively - 5 scrolls of -300
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.1)
    # time.sleep(0.5)  # Wait for zoom animation to complete
    print("Zoomed out for SGoblin Farm deployment")
    send_discord_debug_log("Zoomed out for SGoblin Farm deployment")

    # Deploy first half of troops FIRST
    use_wallbreakers = _deploy_first_side(KEYS, chosen_side, settings, side_coords, troop_counts)

    # Deploy heroes AFTER first wave
    _deploy_heroes_and_siege(KEYS, settings, side_coords)

    # Move camera to opposite side (fast mode for SGoblin Farm)
    print(f"Moving camera to opposite side ({opposite_side})...")
    send_discord_debug_log(f"Moving camera to opposite side ({opposite_side})")
    move_camera_to_opposite_side(chosen_side, fast_mode=True)

    # PASS 3 & 4: Deploy second half on opposite side
    _deploy_opposite_side(KEYS, opposite_coords, opposite_side, troop_counts, use_wallbreakers)

    # CLEANUP PHASE: Deploy any remaining units by dragging backwards for 3 seconds (REMOVED - no longer needed with 4-pass strategy)
    _deploy_leftover_troops(KEYS, opposite_coords, troop_counts)

    # All troops deployed - START 10 second timer before surrender
    print("All troops deployed, starting 10 second timer...")
    send_discord_debug_log("SGoblin: All troops deployed, 10 second timer started")
    timer_start = time.time()

    # Check if spell casting on achievement buildings is enabled
    _cast_spells_on_achievement_buildings(settings)

    # Calculate remaining time to reach 10 seconds total
    elapsed = time.time() - timer_start
    remaining = max(0, 10 - elapsed)

    if remaining > 0:
        print(f"Waiting {remaining:.1f} more seconds (total 10s from deployment)...")
        send_discord_debug_log(f"SGoblin: Waiting {remaining:.1f}s more (scan/cast took {elapsed:.1f}s)")
        time.sleep(remaining)
    else:
        print("10 seconds already elapsed during scanning/casting")
        send_discord_debug_log("SGoblin: 10 seconds already elapsed")

    # Detect and click surrender OR end battle button (retry up to 3 times)
    _surrender_or_end_battle()

    # Wait for battle to end
    wait_for_battle_end()

    # Check if fast return (skip loot logging) is enabled
    skip_logging = settings.get('sgoblin_skip_logging', False)

    if skip_logging:
        # Fast return - skip loot capture and logging
        print("Fast return enabled - skipping loot logging")
        send_discord_debug_log("SGoblin: Fast return - skipping loot logging")
        fast_click(*config.RETURN_BUTTON)
        time.sleep(1.5)  # Reduced return delay
        return False  # Attack completed successfully
    else:
        # Normal post-battle handling with loot tracking
        should_pause = handle_post_battle()
        if should_pause:
            return True  # Signal to pause bot
        return False  # Attack completed successfully
