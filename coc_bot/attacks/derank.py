"""Trophy-dropping routine."""

import random
import time

import keyboard

import config
from coc_bot import runtime
from coc_bot.attacks.common import choose_attack_side, prepare_hotkeys
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import human_like_move_click
from coc_bot.input.camera import move_camera_to_side
from coc_bot.vision.screens import detect_alt_hotkeys, is_attack_screen_ready

def handle_derank_mode():
    """Handle derank mode attack - place one unit using normal deployment strategy and surrender immediately"""
    send_discord_debug_log("Derank mode: attacking any base")
    runtime.gui.log_message("Derank mode: attacking any base")
    # Wait for attack screen to be ready (alt hotkey region visible)
    for _ in range(30):  # Wait up to ~6 seconds
        if is_attack_screen_ready():
            print("[DERANK] Attack screen ready (hotkey region visible)")
            break
        time.sleep(0.2)
    else:
        print("[DERANK] Timeout waiting for attack screen, proceeding anyway")
    # Use normal deployment strategy: pick a random side and a valid coordinate
    settings = runtime.gui.get_settings()
    chosen_side, side_coords = choose_attack_side(settings)
    print(f"[DERANK] Chosen side: {chosen_side}")
    send_discord_debug_log(f"Derank: chosen side {chosen_side}")
    # Detect alternate hotkeys and prepare KEYS
    alt_hotkeys = detect_alt_hotkeys()
    KEYS = prepare_hotkeys(alt_hotkeys)
    # Move camera to the chosen side
    move_camera_to_side(chosen_side)
    # Pick a random valid deployment coordinate from side_coords['units']
    if side_coords['units']:
        chosen_coord = random.choice(side_coords['units'])
    else:
        # Fallback to a corner if for some reason units list is empty
        chosen_coord = (400, 400)
    troop_key = getattr(config, 'KEYS', {}).get('eDragon', '1') if hasattr(config, 'KEYS') else '1'
    keyboard.send(troop_key)
    time.sleep(0.3)
    human_like_move_click(chosen_coord[0], chosen_coord[1])
    print(f"[DERANK] Clicked at {chosen_coord}")
    send_discord_debug_log(f"Derank: placed unit at {chosen_coord} (side {chosen_side})")
    # Wait 1 second before surrendering
    time.sleep(1)
    # Click surrender button (x=145, y=1132)
    human_like_move_click(145, 1132)
    time.sleep(1)
    # Click confirm surrender button (x=1507, y=901)
    human_like_move_click(1507, 901)
    time.sleep(2)
    send_discord_debug_log("Derank: surrendered attack")
    runtime.gui.log_message("Derank: surrendered attack")
    # Return home
    human_like_move_click(*config.RETURN_BUTTON)
    time.sleep(config.RETURN_DELAY)
    return True
