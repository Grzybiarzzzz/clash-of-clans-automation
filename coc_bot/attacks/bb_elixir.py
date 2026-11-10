"""Builder Base elixir farming routine."""

import random
import time

import keyboard

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import fast_click, human_like_move_click
from coc_bot.village import collect_bb_loot
from coc_bot.vision.bb_deployment_zone import detect_bb_deployment_zone, filter_out_unit_bar
from coc_bot.vision.screens import detect_current_game_state, detect_surrender_or_end_battle

# Session counters
bb_elixir_attack_count = 0  # Counter for BB Elixir loot collection every 12 attacks


def handle_bb_elixir_mode():
    """Handle BB Elixir mode - detect deployment zone, place one unit, and surrender immediately"""
    send_discord_debug_log("BB Elixir mode: attacking any base")
    runtime.gui.log_message("BB Elixir mode: attacking any base")

    # Detect valid deployment zone (outside red lines)
    valid_coords = detect_bb_deployment_zone()

    # Filter out unit bar area (x=1-2553, y=1209-1431)
    valid_coords = filter_out_unit_bar(valid_coords)

    # Safety check: if all coords were filtered out, use fallback
    if not valid_coords:
        print("[BB ELIXIR] WARNING: All coordinates filtered out, using fallback positions")
        send_discord_debug_log("BB Elixir: All coords filtered - using fallback", "WARNING")
        valid_coords = [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

    # Use first troop slot (Builder Base troops)
    KEYS = config.KEYS

    # Try deploying at different coordinates until surrender button appears
    surrender_pos = None
    deployment_attempt = 0

    print("[BB ELIXIR] Starting deployment with surrender button validation...")
    send_discord_debug_log("BB Elixir: Starting deployment loop")

    # Phase 1: Try valid coordinates first (up to 10 attempts)
    while not surrender_pos and deployment_attempt < 10:
        deployment_attempt += 1

        # Choose a random coordinate from valid coordinates
        chosen_coord = random.choice(valid_coords)

        print(f"[BB ELIXIR] Deployment attempt {deployment_attempt}/10 at {chosen_coord}")
        send_discord_debug_log(f"BB Elixir: Attempt {deployment_attempt} at {chosen_coord}")

        # Select troop and try to deploy
        keyboard.send(KEYS["troop1"])
        time.sleep(0.1)
        human_like_move_click(chosen_coord[0], chosen_coord[1])
        time.sleep(0.3)  # Wait briefly for troop to deploy

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)  # Store for later use
            print(
                f"[BB ELIXIR] {button_type.replace('_', ' ').title()} button detected! Troop successfully deployed at {chosen_coord}"
            )
            send_discord_debug_log(f"BB Elixir: Success - {button_type} button found at ({button_x}, {button_y})")
            break
        else:
            print("[BB ELIXIR] Surrender/end battle button not found - invalid placement, trying different location...")

    # Phase 2: If still no success, try random coordinates across entire screen until success
    if not surrender_pos:
        print("[BB ELIXIR] Valid coords failed - trying random screen coordinates until success...")
        send_discord_debug_log("BB Elixir: Switching to random coordinate mode", "WARNING")

        max_random_attempts = 50  # Safety limit
        while not surrender_pos and deployment_attempt < 60:  # 10 + 50 = 60 total max
            deployment_attempt += 1

            # Generate random coordinate (avoid edges and unit bar)
            random_x = random.randint(300, 2200)
            random_y = random.randint(200, 1100)  # Avoid unit bar at bottom

            print(
                f"[BB ELIXIR] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})"
            )

            # Select troop and try to deploy
            keyboard.send(KEYS["troop1"])
            time.sleep(0.1)
            human_like_move_click(random_x, random_y)
            time.sleep(0.3)

            # Check if surrender or end battle button appeared (deployment successful)
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                print(
                    f"[BB ELIXIR] SUCCESS! Troop deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected"
                )
                send_discord_debug_log(f"BB Elixir: Success with random coords - {button_type} button found")
                surrender_pos = (button_x, button_y)  # Store position for use below
                break

    # Click surrender/end battle button - FAST CLICK for speed
    if surrender_pos:
        print(f"[BB ELIXIR] Clicking battle end button at {surrender_pos}")
        send_discord_debug_log(f"BB Elixir: Clicking battle end button at {surrender_pos}")
        fast_click(*surrender_pos)  # Ultra-fast click
        time.sleep(0.3)  # Reduced from 1s to 0.3s

        # Click confirm button (fixed coordinate) - FAST CLICK for speed
        print("[BB ELIXIR] Clicking confirmation...")
        send_discord_debug_log("BB Elixir: Clicking confirmation")
        fast_click(1483, 898)  # Ultra-fast click
        time.sleep(0.3)  # Reduced from 2s to 0.3s
    else:
        # NO FALLBACK - Detect actual state and handle appropriately
        print("[BB ELIXIR] CRITICAL: Surrender button not found - detecting state...")
        send_discord_debug_log("BB Elixir: Surrender not found - detecting state", "ERROR")

        detected_state = detect_current_game_state()

        if detected_state == "in_base":
            print("[BB ELIXIR] Already at base - no surrender needed")
            send_discord_debug_log("BB Elixir: Already at base")
        elif detected_state == "battle_ending" or detected_state == "end_screen":
            print(f"[BB ELIXIR] Battle already ending ({detected_state}) - no surrender needed")
            send_discord_debug_log(f"BB Elixir: Battle ending - {detected_state}")
        else:
            # Still in battle but can't find surrender - try deploying troop to enable it
            print("[BB ELIXIR] Deploying troop to enable surrender...")
            fast_click(1282, 720)
            time.sleep(2.0)

            # Try finding surrender again
            button_type, x, y = detect_surrender_or_end_battle()
            if button_type == "surrender":
                print(f"[BB ELIXIR] Surrender now available at {x}, {y}")
                fast_click(x, y)
                time.sleep(0.3)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.3)
            elif button_type == "end_battle":
                print("[BB ELIXIR] Battle ended - clicking end battle")
                fast_click(x, y)
                time.sleep(0.3)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.3)
            else:
                print("[BB ELIXIR] ERROR: Could not find surrender/end battle - waiting for timeout")
                send_discord_debug_log("BB Elixir: No surrender/end battle found - waiting", "ERROR")
                time.sleep(5)  # Wait for potential auto-end

    send_discord_debug_log("BB Elixir: surrendered attack")
    runtime.gui.log_message("BB Elixir: surrendered attack")

    # Return home - FAST CLICK for speed
    fast_click(*config.RETURN_BUTTON)  # Ultra-fast click
    time.sleep(1.5)  # Reduced delay (was config.RETURN_DELAY which is 7s)

    # Note: Skip full storage check for BB Elixir - quick surrenders gain minimal loot,
    # so same readings are normal behavior, not an indication of full storages

    # Increment BB Elixir attack counter
    global bb_elixir_attack_count
    settings = runtime.gui.get_settings()
    collect_interval = settings.get("bb_collect_interval", 12)
    bb_elixir_attack_count += 1
    print(f"[BB ELIXIR] Attack count: {bb_elixir_attack_count}/{collect_interval}")
    send_discord_debug_log(f"BB Elixir: Attack {bb_elixir_attack_count}/{collect_interval} completed")

    # Collect loot every N attacks (configurable)
    if bb_elixir_attack_count >= collect_interval:
        print(f"[BB ELIXIR] {collect_interval} attacks completed - collecting loot!")
        runtime.gui.log_message(f"BB Elixir: {collect_interval} attacks done - collecting loot")
        send_discord_debug_log(f"BB Elixir: {collect_interval} attacks completed - starting loot collection")

        collect_bb_loot()

        # Reset counter
        bb_elixir_attack_count = 0
        print("[BB ELIXIR] Counter reset - starting new cycle")
        send_discord_debug_log("BB Elixir: Loot collected, counter reset to 0")

    return True  # Attack completed
