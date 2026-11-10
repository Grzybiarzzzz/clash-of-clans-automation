import os
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from enum import auto, Enum

import cv2
import keyboard
import numpy as np
import pyautogui
import pytesseract
from PIL import ImageGrab

import config
from bot_gui import BotGUI
from bot_state import BotStateManager
from coc_bot import runtime
from coc_bot.connection import start_connection_monitor
from coc_bot.controls import (
    check_discord_commands,
    exit_app,
    on_pause_from_web,
    stop_bot,
    toggle_pause,
    update_status,
)
from coc_bot.discord_log import send_discord_debug_log, send_discord_notification
from coc_bot.geometry import (
    calculate_deployment_step,
    calculate_lightning_spells_needed,
    find_building_clusters,
    get_air_defense_proximity_sorter,
    get_cluster_center,
    get_lightning_spell_targets,
    get_opposite_side,
)
from coc_bot.input.camera import click_in_square, move_camera_to_opposite_side, move_camera_to_side
from coc_bot.input.turbo import (
    TURBO_CLICK_DELAY_MS,
    turbo_deploy_along_path,
    turbo_deploy_heroes,
    turbo_deploy_siege,
    TURBO_SIDE_CORNERS,
)
from coc_bot.input.win32 import turbo_fast_click, turbo_move_cursor
from coc_bot.overlay import (
    clear_overlay_hotkey,
    overlay_clear,
    overlay_draw_side,
    overlay_draw_spell_target,
    overlay_update,
    save_overlay_screenshot_hotkey,
)
from coc_bot.profiles import get_global_reinforcements_enabled, get_global_skip_on_th_fail
from coc_bot.session import check_auto_pause, save_loot_data, schedule_next_break
from coc_bot.storages import (
    check_and_pause_if_storages_full,
    read_bb_base_storages,
    read_own_base_storages,
    track_resources,
)
from coc_bot.village import collect_bb_loot, switch_village
from coc_bot.vision.bb_deployment_zone import (
    detect_bb_deployment_zone,
    detect_bb_deployment_zone_advanced,
    filter_out_unit_bar,
    generate_ring_fallback_coords,
    save_bb_dragon_debug_visualization,
    select_equally_spaced_coords,
)
from coc_bot.vision.buildings import (
    detect_achievement_building,
    detect_air_defenses,
    detect_air_sweepers,
    detect_all_achievement_buildings,
    detect_town_hall,
    load_achievement_building_templates,
    scan_achievement_buildings_parallel_priority,
)
from coc_bot.vision.ocr import (
    check_bb_attacker_text,
    debug_save_ocr_regions,
    detect_destruction_percentage,
    evaluate_base_resources,
    ocr_attack_resource_template_digits,
    ocr_loot,
    ocr_remaining_troop_count,
)
from coc_bot.vision.screens import (
    detect_alt_hotkeys,
    detect_army_button,
    detect_current_game_state,
    detect_end_battle_button,
    detect_end_screen_state,
    detect_ghost_attack,
    detect_in_base_state,
    detect_return_home_button,
    detect_star_bonus_screen,
    detect_surrender_or_end_battle,
    detect_three_stars,
    detect_two_stars,
    is_attack_screen_ready,
    is_base_search_ready,
    load_bb_gold_templates,
    wait_for_attack_screen_ready,
    wait_for_base_screen,
)
from humanized_input import (
    fast_click,
    human_like_move_click,
    humanized_sleep,
    mouse_drift_idle,
    random_sleep,
    reading_pause,
    thinking_pause,
)
from web.server import start_web_server

# Ensure pytesseract knows its executable path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

# Enable PyAutoGUI failsafe - move mouse to corner to emergency stop
pyautogui.FAILSAFE = False
print("PyAutoGUI corner failsafe is disabled; use F2 to stop or ESC to exit")


# ============================================================
# WINDOWS API FAST-CLICK (for Turbo Deployment mode)
# ============================================================


# Session counters
bb_elixir_attack_count = 0  # Counter for BB Elixir loot collection every 12 attacks
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


# Create GUI
runtime.root = tk.Tk()
runtime.gui = BotGUI(runtime.root)

# Initialize shared state manager for web GUI
runtime.state_manager = BotStateManager()

# Load existing state from JSON if it exists
WEB_STATE_FILE = os.path.join("data", "web_state.json")
if os.path.exists(WEB_STATE_FILE):
    try:
        runtime.state_manager.load_from_json(WEB_STATE_FILE)
        print("[MAIN] Loaded web state from JSON")
    except Exception as e:
        print(f"[MAIN] Failed to load web state: {e}")

# Initialize default state values
runtime.state_manager.update({
    "running": False,
    "paused": True,
    "status": "PAUSED",
    "current_profile": runtime.gui.current_profile,
    "loop_count": 0,
    "bases_attacked": 0,
    "bases_skipped": 0
})

# Connect GUI to state manager for web GUI integration
runtime.gui.state_manager = runtime.state_manager
runtime.gui._sync_state_to_manager()
runtime.state_manager.subscribe(runtime.gui._on_state_change)


runtime.gui.set_control_callback('pause', on_pause_from_web)
print("[MAIN] GUI connected to state manager for web sync")

# ============================================================
# VISUALIZATION OVERLAY HELPERS
# ============================================================


# Initialize Queue Manager (callbacks will be set later after functions are defined)
try:
    from queue_manager import QueueManager
    runtime.queue_manager = QueueManager(runtime.gui)
    print("[MAIN] Queue Manager initialized (callbacks pending)")

    # Start queue if enabled in settings
    settings = runtime.gui.get_settings()
    if settings.get('queue_enabled', False):
        runtime.queue_manager.start_queue()
except ImportError:
    runtime.queue_manager = None
    print("[MAIN] Queue Manager not available")
except Exception as e:
    runtime.queue_manager = None
    print(f"[MAIN] Failed to initialize Queue Manager: {e}")


# human_like_move_click is now imported from humanized_input module
# This provides enhanced movement with overshoots, tremor, and variable acceleration


# random_sleep is now imported from humanized_input module
# This provides realistic timing distributions (lognormal/gamma) instead of uniform


# ============================================================================
# BB GOLD TEMPLATE CACHING
# ============================================================================


# ============================================================================
# BB GOLD STATE MACHINE - STATE DETECTION FUNCTIONS
# ============================================================================


# ============================================================================
# CONNECTION LOST DETECTION AND RECOVERY
# ============================================================================


# Control callbacks


# Bind hotkeys
keyboard.add_hotkey('f1', toggle_pause)
keyboard.add_hotkey('f2', stop_bot)
keyboard.add_hotkey('esc', exit_app)
keyboard.add_hotkey('f6', debug_save_ocr_regions)


keyboard.add_hotkey('f7', clear_overlay_hotkey)


keyboard.add_hotkey('f8', save_overlay_screenshot_hotkey)


runtime.break_time = schedule_next_break()


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
        keyboard.send(KEYS['troop1'])
        time.sleep(0.1)
        human_like_move_click(chosen_coord[0], chosen_coord[1])
        time.sleep(0.3)  # Wait briefly for troop to deploy

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)  # Store for later use
            print(f"[BB ELIXIR] {button_type.replace('_', ' ').title()} button detected! Troop successfully deployed at {chosen_coord}")
            send_discord_debug_log(f"BB Elixir: Success - {button_type} button found at ({button_x}, {button_y})")
            break
        else:
            print(f"[BB ELIXIR] Surrender/end battle button not found - invalid placement, trying different location...")

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

            print(f"[BB ELIXIR] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})")

            # Select troop and try to deploy
            keyboard.send(KEYS['troop1'])
            time.sleep(0.1)
            human_like_move_click(random_x, random_y)
            time.sleep(0.3)

            # Check if surrender or end battle button appeared (deployment successful)
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                print(f"[BB ELIXIR] SUCCESS! Troop deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected")
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

        if detected_state == 'in_base':
            print("[BB ELIXIR] Already at base - no surrender needed")
            send_discord_debug_log("BB Elixir: Already at base")
        elif detected_state == 'battle_ending' or detected_state == 'end_screen':
            print(f"[BB ELIXIR] Battle already ending ({detected_state}) - no surrender needed")
            send_discord_debug_log(f"BB Elixir: Battle ending - {detected_state}")
        else:
            # Still in battle but can't find surrender - try deploying troop to enable it
            print("[BB ELIXIR] Deploying troop to enable surrender...")
            fast_click(1282, 720)
            time.sleep(2.0)

            # Try finding surrender again
            button_type, x, y = detect_surrender_or_end_battle()
            if button_type == 'surrender':
                print(f"[BB ELIXIR] Surrender now available at {x}, {y}")
                fast_click(x, y)
                time.sleep(0.3)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.3)
            elif button_type == 'end_battle':
                print(f"[BB ELIXIR] Battle ended - clicking end battle")
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
    collect_interval = settings.get('bb_collect_interval', 12)
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


# ============================================================================
# BB GOLD STATE MACHINE - HELPER FUNCTIONS
# ============================================================================

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
            print("[BB GOLD STATE] IN_BASE: Initiating search")
            runtime.gui.log_message("BB Gold: Starting search")

            # NEW: If queue is active, wait for storage UI to stabilize before checking
            try:
                if 'queue_manager' in globals() and runtime.queue_manager and runtime.queue_manager.queue_active:
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

            # Sleep removed - state transitions are now instant
            continue

        # STATE 2: SEARCHING -> ATTACK_READY
        if current_state == BBGoldState.SEARCHING:
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
            continue

        # STATE 3: ATTACK_READY -> BATTLE_ACTIVE
        if current_state == BBGoldState.ATTACK_READY:
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
            continue

        # STATE 4: BATTLE_ACTIVE -> BATTLE_ENDING
        if current_state == BBGoldState.BATTLE_ACTIVE:
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
            continue

        # STATE 5: BATTLE_ENDING -> END_SCREEN
        if current_state == BBGoldState.BATTLE_ENDING:
            print("[BB GOLD STATE] BATTLE_ENDING: Clicking surrender/end battle")

            # Skip if battle ended (Return Home button detected without stars)
            if not context.get('battle_lost', False):
                end_result = end_bb_gold_battle(context['stars_detected'], context)

                if not end_result['success']:
                    print("[BB GOLD STATE] BATTLE_ENDING: End button click failed, retrying")
                    time.sleep(1)
                    continue

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


def detect_queen_arrow_projectile():
    """
    Detect the Queen's Giant Arrow by tracking its bright cyan/green glow trail.
    Uses color-based detection (HSV) to find the distinctive arrow trail across multiple frames.

    Returns:
        List of (x, y) coordinates along arrow path for spell casting, or None if detection failed
    """
    try:
        print(f"[QUEEN ARROW] Starting glow trail detection...")

        # Arrow glow trail color range (bright cyan/green beam)
        # CALIBRATED VALUES - tuned to reduce false positives
        lower_cyan = np.array([77, 0, 194])     # H=77-95 (cyan), S=0+ (any saturation), V=194+ (very bright only)
        upper_cyan = np.array([95, 255, 255])   # High brightness threshold filters out dark objects

        # Capture multiple frames to track arrow movement
        frame_count = config.QUEEN_ARROW_FRAME_COUNT
        frame_interval = config.QUEEN_ARROW_FRAME_INTERVAL
        glow_detections = []  # List of (frame_num, points_along_trail)

        print(f"[QUEEN ARROW] Capturing {frame_count} frames at {frame_interval}s intervals...")

        for frame_num in range(frame_count):
            # Capture screenshot of base region only
            base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
            img = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Find cyan/green glow pixels
            mask = cv2.inRange(hsv, lower_cyan, upper_cyan)

            # Find contours of glow trail
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            frame_glow_points = []

            for contour in contours:
                area = cv2.contourArea(contour)

                # Filter by size: glow trail segments should be reasonably sized
                # Not tiny noise pixels, but also not huge water/terrain reflections
                if area < 100:  # Minimum 100 pixels for glow trail segment
                    continue
                if area > 1000:  # Maximum 1000 pixels - filters out large false positives (water, terrain)
                    continue

                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by width/height: arrow glow is THICK, not thin lines
                # Thin wall lines are 2-5px wide, arrow glow is 10-30px wide
                min_thickness = 8  # pixels - minimum width or height
                if w < min_thickness and h < min_thickness:
                    # Both dimensions too thin - it's a line, not arrow glow
                    continue

                # Filter by position: exclude UI areas
                if x < 200 or x > 2100 or y < 200 or y > 1000:
                    continue

                # Calculate center of this glow segment
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert to global screen coordinates
                    global_x = cx + config.BASE_VIEW_REGION[0]
                    global_y = cy + config.BASE_VIEW_REGION[1]

                    frame_glow_points.append((global_x, global_y, area))

            if frame_glow_points:
                glow_detections.append((frame_num, frame_glow_points))
                print(f"[QUEEN ARROW] Frame {frame_num}: Detected {len(frame_glow_points)} glow segments")

            # Wait before next frame
            if frame_num < frame_count - 1:
                time.sleep(frame_interval)

        print(f"[QUEEN ARROW] Glow detected in {len(glow_detections)} frames")

        # Need glow in at least 2 frames to determine path
        if len(glow_detections) < 2:
            print(f"[QUEEN ARROW] Insufficient glow detections ({len(glow_detections)} frames) - need at least 2")
            return None

        # Collect all glow points from all frames
        all_glow_points = []
        for frame_num, points in glow_detections:
            all_glow_points.extend([(p[0], p[1]) for p in points])  # (x, y) only

        if len(all_glow_points) < 2:
            print(f"[QUEEN ARROW] Not enough glow points detected ({len(all_glow_points)})")
            return None

        print(f"[QUEEN ARROW] Total glow points across all frames: {len(all_glow_points)}")

        # IMPROVED: Find the densest cluster of points (main arrow trail)
        # Strategy: Use pairwise distances to find the largest group of nearby points
        x_coords_all = np.array([p[0] for p in all_glow_points])
        y_coords_all = np.array([p[1] for p in all_glow_points])

        if len(x_coords_all) < 3:
            print(f"[QUEEN ARROW] Not enough points for clustering")
            return None

        # IMPROVED: Find the densest LINE segment by starting from the densest point
        # and including only connected neighbors - prevents scattered points from skewing the line
        cluster_radius = 200  # pixels - connection radius
        min_neighbors = 2  # Reduced - we'll filter more later

        # Step 1: Count neighbors for each point
        neighbor_counts = []
        for i, (x1, y1) in enumerate(zip(x_coords_all, y_coords_all)):
            neighbor_count = 0
            for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                if i != j:
                    dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if dist <= cluster_radius:
                        neighbor_count += 1
            neighbor_counts.append(neighbor_count)

        # Step 2: Find ALL connected components, then choose the most LINEAR one
        # (Arrow paths are straight lines, not scattered clusters)
        if len(neighbor_counts) == 0 or max(neighbor_counts) == 0:
            print(f"[QUEEN ARROW] No clustered points found")
            clustered_indices = list(range(len(all_glow_points)))
        else:
            # Find all connected components
            visited = set()
            components = []

            for start_idx in range(len(x_coords_all)):
                if start_idx in visited:
                    continue

                # Build connected component from this point
                component = set([start_idx])
                queue = [start_idx]
                visited.add(start_idx)

                while queue:
                    current_idx = queue.pop(0)
                    x1, y1 = x_coords_all[current_idx], y_coords_all[current_idx]

                    for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                        if j not in visited:
                            dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                            if dist <= cluster_radius:
                                component.add(j)
                                queue.append(j)
                                visited.add(j)

                if len(component) >= 3:  # Only keep components with 3+ points
                    components.append(sorted(list(component)))

            print(f"[QUEEN ARROW] Found {len(components)} connected components")

            # Score each component by linearity (how well points form a straight line)
            best_component = None
            best_score = -1

            for comp_indices in components:
                comp_x = x_coords_all[comp_indices]
                comp_y = y_coords_all[comp_indices]

                # Fit a line through this component
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
                    continue  # Skip degenerate components

                # Calculate linearity score: favor more points with lower deviation from line
                avg_distance = np.mean(distances)
                num_points = len(comp_indices)
                linearity_score = (num_points ** 2) / (avg_distance + 1)  # +1 to avoid division by zero

                print(f"[QUEEN ARROW] Component with {num_points} points: avg deviation={avg_distance:.1f}px, score={linearity_score:.1f}")

                if linearity_score > best_score:
                    best_score = linearity_score
                    best_component = comp_indices

            if best_component is None or len(best_component) < 3:
                print(f"[QUEEN ARROW] No good linear component found, using all points")
                clustered_indices = list(range(len(all_glow_points)))
            else:
                clustered_indices = best_component
                print(f"[QUEEN ARROW] Selected best linear component: {len(clustered_indices)} points")

        # Use only the connected component points for line fitting
        x_coords = x_coords_all[clustered_indices]
        y_coords = y_coords_all[clustered_indices]

        print(f"[QUEEN ARROW] Using {len(x_coords)} connected points (filtered {len(all_glow_points) - len(x_coords)} scattered points)")

        # IMPROVED: Iterative outlier removal based on perpendicular distance from line
        # Fit initial line, remove points far from it, refit - focuses on the main straight line
        max_iterations = 3
        max_perpendicular_distance = 50  # pixels - max distance from line

        for iteration in range(max_iterations):
            if len(x_coords) < 3:
                break

            # Check if line is more vertical than horizontal
            x_range = np.max(x_coords) - np.min(x_coords)
            y_range = np.max(y_coords) - np.min(y_coords)

            if x_range > y_range:
                # Horizontal-ish line: fit y = mx + b
                coeffs = np.polyfit(x_coords, y_coords, 1)
                m, b = coeffs

                # Calculate perpendicular distance for each point
                # For line y = mx + b, perpendicular distance = |mx - y + b| / sqrt(m^2 + 1)
                distances = np.abs(m * x_coords - y_coords + b) / np.sqrt(m**2 + 1)

            else:
                # Vertical-ish line: fit x = my + b
                coeffs = np.polyfit(y_coords, x_coords, 1)
                m, b = coeffs

                # For line x = my + b, perpendicular distance = |my - x + b| / sqrt(m^2 + 1)
                distances = np.abs(m * y_coords - x_coords + b) / np.sqrt(m**2 + 1)

            # Keep only points within max distance
            inlier_mask = distances <= max_perpendicular_distance
            inliers_before = len(x_coords)
            x_coords = x_coords[inlier_mask]
            y_coords = y_coords[inlier_mask]
            inliers_after = len(x_coords)

            if inliers_before == inliers_after:
                # No points removed, we're done
                break

            print(f"[QUEEN ARROW] Iteration {iteration+1}: Removed {inliers_before - inliers_after} points far from line")

        # Safety check: ensure we still have enough points after outlier removal
        if len(x_coords) < 2:
            print(f"[QUEEN ARROW] All points removed as outliers! Only {len(x_coords)} points remain.")
            print(f"[QUEEN ARROW] No clear arrow glow detected - detection failed")
            return None

        # Final line fit with refined points
        x_range = np.max(x_coords) - np.min(x_coords)
        y_range = np.max(y_coords) - np.min(y_coords)

        if x_range > y_range:
            # Horizontal-ish line: fit y = mx + b
            coeffs = np.polyfit(x_coords, y_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            x_min, x_max = np.min(x_coords), np.max(x_coords)
            start_point = (int(x_min), int(m * x_min + b))
            end_point = (int(x_max), int(m * x_max + b))

            print(f"[QUEEN ARROW] Final line: y = {m:.3f}x + {b:.1f} ({len(x_coords)} inliers)")
        else:
            # Vertical-ish line: fit x = my + b
            coeffs = np.polyfit(y_coords, x_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            y_min, y_max = np.min(y_coords), np.max(y_coords)
            start_point = (int(m * y_min + b), int(y_min))
            end_point = (int(m * y_max + b), int(y_max))

            print(f"[QUEEN ARROW] Final line: x = {m:.3f}y + {b:.1f} ({len(x_coords)} inliers)")

        start_x, start_y = start_point
        end_x, end_y = end_point

        # Calculate trail length along the fitted line
        trail_length = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5

        # Validate that we have a reasonable arrow path
        min_trail_length = 200  # pixels - arrow trail should be at least this long
        if trail_length < min_trail_length:
            print(f"[QUEEN ARROW] Glow trail too short ({trail_length:.1f}px < {min_trail_length}px)")
            return None

        print(f"[QUEEN ARROW] Arrow trail detected: ({start_x},{start_y}) -> ({end_x},{end_y})")
        print(f"[QUEEN ARROW] Trail length: {trail_length:.1f}px")

        # Extrapolate path by 30% for better coverage
        dx = end_x - start_x
        dy = end_y - start_y
        extension_factor = 1.3
        extrapolated_end_x = int(start_x + dx * extension_factor)
        extrapolated_end_y = int(start_y + dy * extension_factor)

        print(f"[QUEEN ARROW] Extrapolated path end: ({extrapolated_end_x},{extrapolated_end_y})")
        send_discord_debug_log(f"Queen arrow: Glow trail detected ({len(all_glow_points)} points, {max_distance:.0f}px trail)")

        return [(start_x, start_y), (extrapolated_end_x, extrapolated_end_y)]

    except Exception as e:
        print(f"[QUEEN ARROW] Error in glow trail detection: {e}")
        send_discord_debug_log(f"Queen arrow glow detection failed: {e}", "WARNING")
        import traceback
        traceback.print_exc()
        return None

def detect_queen_arrow_path_and_cast_spells(queen_side, queen_ability_timing, spell_casting_flag):
    """
    Detect the Queen's Giant Arrow path and cast 11 Earthquakes along it.
    Uses glow trail detection (primary) with purple HP bar detection as fallback.

    Args:
        queen_side: 'up' or 'down' - which side Queen was deployed on
        queen_ability_timing: seconds to wait for Queen ability to activate (from settings)
        spell_casting_flag: shared flag dict to track spell casting phase (for hero ability re-selection)

    Returns True if successful, False otherwise.
    """
    try:
        print(f"[QUEEN ARROW] Waiting for Queen ability (deployed on {queen_side}, timing: {queen_ability_timing}s)...")

        # Wait for Queen ability to activate (already triggered by hero ability thread)
        time.sleep(queen_ability_timing)
        print(f"[QUEEN ARROW] Ability activated after {queen_ability_timing}s - starting detection...")

        # ===== PRIMARY METHOD: GLOW TRAIL DETECTION =====
        print(f"[QUEEN ARROW] Attempting glow trail detection...")
        arrow_path = detect_queen_arrow_projectile()

        if arrow_path is not None and len(arrow_path) == 2:
            # Successfully detected arrow glow trail - use these coordinates
            start, end = arrow_path
            print(f"[QUEEN ARROW] ✓ Glow trail detection successful: {start} -> {end}")
            send_discord_debug_log(f"SBarb Farm: Queen arrow glow trail detected")
            detection_method = "glow_trail"
        else:
            # ===== FALLBACK METHOD: PURPLE HP BAR DETECTION =====
            print(f"[QUEEN ARROW] Glow trail detection failed, using HP bar fallback...")
            time.sleep(0.5)  # Wait a bit more for damage to show

            # Capture screenshot
            screenshot = pyautogui.screenshot()
            img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Purple HP bar HSV range (magenta/purple color)
            lower_purple = np.array([140, 80, 80])   # Purple hue
            upper_purple = np.array([170, 255, 255])

            # Find purple HP bars
            mask = cv2.inRange(hsv, lower_purple, upper_purple)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Get centers of all HP bars with strict filtering
            hp_bar_centers = []
            for contour in contours:
                area = cv2.contourArea(contour)

                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by size: HP bars are small rectangles (50-500 pixels area typical)
                if area < 50 or area > 800:
                    continue

                # Filter by aspect ratio: HP bars are horizontal (wider than tall)
                if h == 0 or w / h < 1.5:  # Must be at least 1.5x wider than tall
                    continue

                # Filter by position: exclude UI areas (top/bottom edges, far left/right)
                # Game area is roughly (200, 200) to (2300, 1200)
                if x < 200 or x > 2300 or y < 200 or y > 1200:
                    continue

                # Calculate center
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    hp_bar_centers.append((cx, cy, area))
                    print(f"[QUEEN ARROW] HP bar detected: pos=({cx},{cy}), area={area}, size={w}x{h}, ratio={w/h:.2f}")

            print(f"[QUEEN ARROW] Detected {len(hp_bar_centers)} purple HP bars")

            # Exclude Queen's target based on deployment side
            if len(hp_bar_centers) >= 2:
                if queen_side == 'down':
                    # Queen at bottom - exclude bottom-most (highest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=True)  # Sort by Y (bottom to top)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed BOTTOM - excluded target at {queen_target[:2]}")
                elif queen_side == 'up':
                    # Queen at top - exclude top-most (lowest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=False)  # Sort by Y (top to bottom)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed TOP - excluded target at {queen_target[:2]}")

                print(f"[QUEEN ARROW] {len(hp_bar_centers)} damaged buildings remain after exclusion")

            # If we have at least 2 damaged buildings from arrow (early detection)
            if len(hp_bar_centers) >= 2:
                # Extract coordinates (without area)
                coords = [(p[0], p[1]) for p in hp_bar_centers]

                # Arrow flies in a straight line - use first and last detected building to extrapolate
                # Even with just 2-3 buildings detected, we can extrapolate the full path
                start = coords[0]
                end = coords[-1]

                # Calculate arrow direction vector
                dx = end[0] - start[0]
                dy = end[1] - start[1]

                # Extrapolate further along the arrow path for better coverage
                # Extend the line by 30% beyond the last detected building
                extension_factor = 1.3
                extended_end_x = int(start[0] + dx * extension_factor)
                extended_end_y = int(start[1] + dy * extension_factor)

                # Use extended end point for spell distribution
                end = (extended_end_x, extended_end_y)

                print(f"[QUEEN ARROW] ✓ HP bar fallback successful: {start} -> {end}")
                print(f"[QUEEN ARROW] Arrow path extrapolated from {len(coords)} buildings")
                send_discord_debug_log(f"SBarb Farm: Queen arrow HP bar fallback used ({len(coords)} buildings)")
                detection_method = "hp_bar"
            else:
                print(f"[QUEEN ARROW] ✗ Both detection methods failed ({len(hp_bar_centers)} HP bars)")
                send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed completely", "WARNING")
                return False

        # ===== SPELL CASTING (COMMON TO BOTH METHODS) =====
        print(f"[QUEEN ARROW] Casting 11 Earthquake spells along detected path ({detection_method})...")

        # Set flag to indicate spell casting is active (for hero ability re-selection)
        spell_casting_flag['value'] = True

        # Cast 11 Earthquake spells evenly distributed along the path - ULTRA FAST
        keyboard.send('a')  # Select Earthquake spell
        time.sleep(0.03)

        for i in range(11):
            # Calculate position along the line (0 to 1)
            t = i / 10  # 0%, 10%, 20%, ... 100%
            x = int(start[0] + t * (end[0] - start[0]))
            y = int(start[1] + t * (end[1] - start[1]))

            # Re-select spell every 4 casts to maintain selection
            if i % 4 == 0 and i > 0:
                keyboard.send('a')
                time.sleep(0.01)

            fast_click(x, y)
            time.sleep(0.02)  # Ultra-fast casting

        print(f"[QUEEN ARROW] Successfully cast 11 Earthquake spells on arrow path ({detection_method})")
        send_discord_debug_log(f"SBarb Farm: Cast 11 Earthquakes on Queen arrow path using {detection_method} detection")

        # Clear flag - spell casting complete
        spell_casting_flag['value'] = False

        # Wait for spells to finish casting animation
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"[QUEEN ARROW] Error detecting arrow path: {e}")
        send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed - {e}", "WARNING")
        return False

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
    heroes_first = settings.get('sbarb_heroes_first', False)
    turbo_deployment = settings.get('sbarb_turbo_deployment', False)

    # Achievement building destruction tracking for CSV
    building_destroyed = "None"  # Type of building destroyed (or "None")
    spells_completed = False  # True if all 10 lightning spells were cast

    # Choose two opposite sides for split deployment (only vertical - up/down)
    # Left/right has coordinate issues, restrict to top-bottom or bottom-top only
    sides = ['up', 'down']
    first_side = random.choice(sides)
    opposite_side = get_opposite_side(first_side)

    deployment_order = "Heroes First" if heroes_first else "Army First"
    print(f"[SBARB FARM] Deploying on {first_side} and {opposite_side} ({deployment_order})")
    send_discord_debug_log(f"SBarb Farm: Deploying on {first_side} and {opposite_side} ({deployment_order})")

    # Draw overlay for SBarb Farm attack (no side arrow - too cluttered)
    overlay_clear()
    if runtime.gui.overlay and runtime.gui.overlay_enabled:
        runtime.gui.overlay.draw_text(100, 80, f"SBarb Farm: {first_side.upper()} then {opposite_side.upper()}", '#FFFF00')
        runtime.gui.overlay.draw_text(100, 110, f"Mode: {deployment_order}", '#FFFF00')
        runtime.gui.overlay.update()

    # Move camera to first side - ULTRA FAST for SBarb Farm (skip camera movement delays)
    # Ensure zoom is complete before dragging (don't drag during zoom - it blocks zoom)
    time.sleep(0.1)  # Extra buffer to ensure zoom fully complete before camera drag
    drag_map = {
        'left': ((600, 700), (1500, 700)),
        'right': ((2000, 700), (1000, 700)),
        'up': ((1280, 300), (1280, 900)),
        'down': ((1280, 1100), (1280, 700)),
    }
    drag_start, drag_end = drag_map[first_side]
    pyautogui.moveTo(*drag_start, duration=0)
    pyautogui.mouseDown()
    pyautogui.moveTo(*drag_end, duration=0.1)  # Fast drag
    pyautogui.mouseUp()
    time.sleep(0.1)  # Minimal delay

    # Get deployment coordinates
    first_side_coords = config.SIDE_DEPLOYMENT_COORDS[first_side]['units']
    second_side_coords = config.SIDE_DEPLOYMENT_COORDS[opposite_side]['units']

    # Randomize deployment direction (sometimes reverse coordinates for variety)
    if random.random() < 0.5:
        first_side_coords = list(reversed(first_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {first_side}")
    if random.random() < 0.5:
        second_side_coords = list(reversed(second_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {opposite_side}")

    # Get actual troop count from settings
    troop_counts = settings.get('troop_counts', [64, 0, 0, 0, 0, 0, 0])

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
    sbarb_hotkey = KEYS[f'troop{sbarb_slot_index + 1}']

    print(f"[SBARB FARM] Detected Super Barbarians in slot {sbarb_slot_index + 1}, using hotkey '{sbarb_hotkey}', count: {total_troops}")

    first_half = total_troops // 2

    # Calculate deployment step for even distribution across coordinates
    first_side_step = calculate_deployment_step(first_half, len(first_side_coords))
    second_side_step = calculate_deployment_step(first_half, len(second_side_coords))

    print(f"[SBARB FARM] Deploying {total_troops} troops ({first_half} per side)")
    print(f"[SBARB FARM] Step size: {first_side_step} (first), {second_side_step} (second)")

    # Start timer for attack duration tracking (before any deployments)
    attack_start_time = time.time()

    # Get hero ability timings from GUI settings
    queen_timing = settings.get('queen_ability_timing', 1)
    king_timing = settings.get('king_ability_timing', 1)
    warden_timing = settings.get('warden_ability_timing', 1)
    rc_timing = settings.get('rc_ability_timing', 1)

    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }

    import threading

    # Shared flag for 50% destruction monitoring
    target_destruction = 50
    destruction_reached = {'value': False, 'percentage': 0}
    max_wait_time = 60
    attack_failed_early = False  # True if Return Home detected before 50% (troops died)

    # Reset destruction percentage tracking for new attack
    detect_destruction_percentage.last_valid = None

    # Shared flag for spell casting phase (to handle hero ability re-selection)
    spell_casting_active = {'value': False}

    # Shared dict for achievement building scan results
    achievement_scan_result = {'found': False, 'building': None, 'type': None, 'scanning': False, 'completed': False}

    # Shared dict for cached surrender button position
    surrender_button_cache = {'position': None, 'detected': False}

    def scan_achievement_buildings_background():
        """Background thread to scan for achievement buildings in parallel with deployment"""
        achievement_scan_result['scanning'] = True
        print("[SBARB FARM] Background achievement building scan started...")
        send_discord_debug_log("SBarb Farm: Background achievement building scan started")

        # Get settings from GUI
        settings = runtime.gui.get_settings()

        # Check if 50% already reached before scanning
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached before scan - skipping")
            achievement_scan_result['completed'] = True
            achievement_scan_result['scanning'] = False
            return

        # Get targeting mode from settings (default: clumps for backward compatibility)
        target_mode = settings.get('sbarb_cast_spells_target_mode', 'clumps')
        print(f"[SBARB FARM] Targeting mode: {target_mode.replace('_', ' ').title()}")

        if target_mode == 'clumps':
            # CLUMPS MODE: Scan all enabled buildings and look for clusters
            print("[SBARB FARM] Scanning all buildings for clusters...")

            # Build list of enabled buildings from checkboxes
            enabled_buildings = []
            building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                              'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
            for bt in building_types:
                if settings.get(f'achievement_scan_{bt}', True):
                    enabled_buildings.append(bt)

            if not enabled_buildings:
                print("[SBARB FARM] No buildings enabled for scanning")
                achievement_scan_result['completed'] = True
                achievement_scan_result['scanning'] = False
                return

            # Detect all enabled buildings
            all_buildings = detect_all_achievement_buildings(enabled_buildings)

            if not all_buildings:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log("SBarb Farm: No buildings found (clumps mode)")
                achievement_scan_result['completed'] = True
                achievement_scan_result['scanning'] = False
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
                cluster_types_summary = ", ".join([f"{count} {btype.replace('_', ' ')}" for btype, count in cluster_type_counts.items()])
                print(f"  [BACKGROUND SCAN] ✓ CLUSTER of {len(biggest_cluster)} buildings at ({x}, {y})")
                print(f"    Types: {cluster_types_summary}")
                achievement_scan_result['found'] = True
                achievement_scan_result['building'] = (x, y, 1.0)
                achievement_scan_result['type'] = f"cluster_{len(biggest_cluster)}"
                achievement_scan_result['cluster_types'] = cluster_types_summary  # Store for CSV logging
                send_discord_debug_log(f"SBarb Farm: Cluster of {len(biggest_cluster)} buildings ({cluster_types_summary}) at ({x}, {y})")
            else:
                # No cluster found, use priority building
                priority_list = settings.get('achievement_priority_list', building_types)
                priority_enabled = [b for b in priority_list if b in enabled_buildings]

                for building_type in priority_enabled:
                    if building_type in all_buildings and all_buildings[building_type]:
                        bx, by, conf = all_buildings[building_type][0]
                        # Calculate center
                        bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                        x = bx + bw // 2
                        y = by + bh // 2
                        print(f"  [BACKGROUND SCAN] ✓ No cluster - using priority {building_type.replace('_', ' ')} at ({x}, {y})")
                        achievement_scan_result['found'] = True
                        achievement_scan_result['building'] = (x, y, conf)
                        achievement_scan_result['type'] = building_type
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
                achievement_scan_result['found'] = True
                achievement_scan_result['building'] = (center_x, center_y, confidence)
                achievement_scan_result['type'] = building_type
                print(f"  [BACKGROUND SCAN] ✓ {building_type.replace('_', ' ')} FOUND at center ({center_x}, {center_y})! ({target_mode.replace('_', ' ')} mode)")
                send_discord_debug_log(f"SBarb Farm: {building_type} found at ({center_x}, {center_y}) ({target_mode} mode)")
            else:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log(f"SBarb Farm: No buildings found ({target_mode} mode)")

        achievement_scan_result['completed'] = True
        achievement_scan_result['scanning'] = False

    def detect_surrender_button_early():
        """Detect and cache surrender or end battle button position early during attack"""
        if not surrender_button_cache['detected']:
            print("[SBARB FARM] Pre-detecting surrender/end battle button position...")
            button_type, button_x, button_y = detect_surrender_or_end_battle()
            if button_type:
                surrender_button_cache['position'] = (button_x, button_y)
                surrender_button_cache['detected'] = True
                print(f"[SBARB FARM] {button_type.replace('_', ' ').title()} button cached at ({button_x}, {button_y})")
                send_discord_debug_log(f"SBarb Farm: {button_type} button pre-cached at ({button_x}, {button_y})")
            else:
                print("[SBARB FARM] Surrender/end battle button not detected yet")

    def monitor_destruction_continuous():
        """Background thread to continuously monitor destruction percentage and Return Home button"""
        nonlocal attack_failed_early

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached['value']:
                break

            # Check for Return Home button (battle ended early - troops died before 50%)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                elapsed = time.time() - attack_start_time
                current_pct = destruction_reached.get('percentage', 0)
                print(f"[SBARB FARM] Return Home detected after {elapsed:.1f}s - attack failed (troops died at {current_pct}%, before {target_destruction}%)")
                runtime.gui.log_message(f"SBarb Farm: Attack failed - troops died at {current_pct}%")
                send_discord_debug_log(f"SBarb Farm: Attack failed after {elapsed:.1f}s - Return Home detected at {current_pct}%", "WARNING")
                destruction_reached['value'] = True  # Signal main loop to stop waiting
                destruction_reached['return_home_pos'] = return_home_pos  # Cache position for faster click
                attack_failed_early = True
                break

            current_destruction = detect_destruction_percentage(save_debug_screenshots=False)
            if current_destruction is not None:
                destruction_reached['percentage'] = current_destruction
                if current_destruction >= target_destruction:
                    elapsed = time.time() - attack_start_time
                    destruction_reached['value'] = True
                    print(f"[SBARB FARM] {target_destruction}% REACHED! ({current_destruction}% after {elapsed:.1f}s)")
                    runtime.gui.log_message(f"SBarb Farm: {current_destruction}% reached - stopping deployment!")
                    send_discord_debug_log(f"SBarb Farm: {current_destruction}% destruction reached after {elapsed:.1f}s")
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
        print(f"[SBARB FARM] *** TURBO DEPLOYMENT MODE ENABLED ***")
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
        if not destruction_reached['value']:
            print(f"[TURBO DEPLOY] Deploying heroes and siege on {first_side}...")
            turbo_deploy_heroes(first_side, hero_timings, destruction_reached)
            turbo_deploy_siege(first_side, destruction_reached)
        else:
            print(f"[TURBO DEPLOY] 50% reached after first wave - skipping heroes/siege")

        # Get spell casting setting
        sbarb_cast_spells = settings.get('sbarb_cast_spells', False)

        # ===== PHASE 3-5: Camera, abilities, and second wave (skip if 50% reached) =====
        if not destruction_reached['value']:
            # ===== PHASE 3: Camera to opposite side =====
            print(f"[TURBO DEPLOY] Moving camera to {opposite_side}...")

            # Click neutral area first to deselect
            pyautogui.click(1280, 400)
            time.sleep(0.1)

            # Extended drag for opposite side
            if opposite_side == 'up':
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
            if not destruction_reached['value']:
                print(f"[TURBO DEPLOY] Activating all hero abilities...")
                for hero_key in ['queen', 'king', 'warden', 'rc']:
                    timing = hero_timings.get(hero_key, -1)
                    if timing >= 0:  # Only activate if not disabled (-1)
                        keyboard.send(KEYS[hero_key])
                        print(f"[TURBO DEPLOY] {hero_key.title()} ability activated")
                        time.sleep(0.08)  # Small delay between ability activations
                send_discord_debug_log("SBarb Farm: All hero abilities activated (turbo mode)")

            # ===== Start background achievement scan (after camera settled) =====
            if sbarb_cast_spells and not destruction_reached['value']:
                scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
                scan_thread.start()
                print("[TURBO DEPLOY] Started background achievement building scan")

            # ===== PHASE 5: Deploy second half on opposite side =====
            if not destruction_reached['value']:
                print(f"[TURBO DEPLOY] Deploying {first_half} troops on {opposite_side}...")
                turbo_deploy_along_path(second_corners, first_half, TURBO_CLICK_DELAY_MS, sbarb_hotkey, destruction_reached)
            else:
                print(f"[TURBO DEPLOY] 50% reached - skipping second wave")
        else:
            print(f"[TURBO DEPLOY] 50% reached - skipping phases 3-5")

        # ===== PHASE 6: Spell casting (only if 50% not reached) =====
        achievement_spells_deployed = False

        if not destruction_reached['value'] and sbarb_cast_spells:
            # Wait for background scan to complete (with timeout)
            scan_start = time.time()
            while not achievement_scan_result['completed'] and (time.time() - scan_start) < 6:
                if destruction_reached['value']:
                    break
                time.sleep(0.1)

            if achievement_scan_result['found'] and not destruction_reached['value']:
                found_building = achievement_scan_result['building']
                found_type = achievement_scan_result['type']
                x, y, confidence = found_building

                print(f"[TURBO DEPLOY] CASTING SPELLS ON: {found_type.replace('_', ' ')} at ({x}, {y})")
                runtime.gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
                send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type} (turbo mode)")

                # Deploy 1 Earthquake + 10 Lightning using turbo clicks (~11 CPS)
                SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting
                spell_start = time.perf_counter()

                keyboard.send('a')
                time.sleep(0.05)
                turbo_move_cursor(x, y)
                turbo_fast_click()
                time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                keyboard.send('s')
                time.sleep(0.05)
                spells_cast = 0
                for _ in range(10):
                    if destruction_reached['value']:
                        break
                    spell_x = x + random.randint(-3, 3)
                    spell_y = y + random.randint(-3, 3)
                    turbo_move_cursor(spell_x, spell_y)
                    turbo_fast_click()
                    spells_cast += 1
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                spell_elapsed = time.perf_counter() - spell_start
                print(f"[TURBO DEPLOY] Cast {spells_cast + 1} spells in {spell_elapsed*1000:.0f}ms (~{(spells_cast + 1)/spell_elapsed:.0f} CPS)")

                # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
                if found_type.startswith('cluster_') and 'cluster_types' in achievement_scan_result:
                    building_destroyed = achievement_scan_result['cluster_types']
                else:
                    building_destroyed = found_type
                spells_completed = True
                achievement_spells_deployed = True
                print(f"[TURBO DEPLOY] Spells deployed on {found_type}")

            # Fallback: random spells if no achievement building found
            if not achievement_spells_deployed and not destruction_reached['value']:
                print("[TURBO DEPLOY] Deploying random spells...")
                spell_casting_active['value'] = True
                SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting

                keyboard.send('a')
                time.sleep(0.05)
                for _ in range(2):
                    if destruction_reached['value']:
                        break
                    x, y = random.randint(700, 1800), random.randint(400, 1000)
                    turbo_move_cursor(x, y)
                    turbo_fast_click()
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                keyboard.send('s')
                time.sleep(0.05)
                for _ in range(9):
                    if destruction_reached['value']:
                        break
                    x, y = random.randint(700, 1800), random.randint(400, 1000)
                    turbo_move_cursor(x, y)
                    turbo_fast_click()
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                spell_casting_active['value'] = False
                print("[TURBO DEPLOY] Random spells deployed")
        elif destruction_reached['value']:
            print(f"[TURBO DEPLOY] 50% reached - skipping spell casting")

        # ===== Start background surrender button detection for fast surrender =====
        if not surrender_button_cache['detected']:
            surrender_detect_thread = threading.Thread(target=detect_surrender_button_early, daemon=True)
            surrender_detect_thread.start()
            print("[TURBO DEPLOY] Started background surrender button detection")

        print(f"[TURBO DEPLOY] All deployment phases complete")
        print(f"[TURBO DEPLOY] *** TURBO MODE FINISHED - skipping standard deployment ***")
        send_discord_debug_log("SBarb Farm: Turbo deployment complete")

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
            if spell_casting_active['value']:
                keyboard.send('a')  # Re-select Earthquake spell
                print(f"[SBARB FARM] Re-selected Earthquake spell after {hero_role.title()} ability")
            else:
                keyboard.send(sbarb_hotkey)  # Re-select troops (dynamic slot)
                print(f"[SBARB FARM] Re-selected troops after {hero_role.title()} ability")

    # ============================================================
    # STANDARD DEPLOYMENT MODE (hold-and-drag)
    # Skip this entire section if turbo deployment was used
    # ============================================================
    if not turbo_deployment:
        print(f"[SBARB FARM] Using STANDARD deployment mode (hold-and-drag)")

        # CONDITIONAL DEPLOYMENT ORDER BASED ON SETTING
        if heroes_first:
            # ===== HEROES FIRST ORDER =====
            print(f"[SBARB FARM] Deploying heroes first on {first_side}...")
            hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]['hero']

            # Deploy each hero and start their ability timer immediately
            for hero_key in ['queen', 'king', 'warden', 'rc']:
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
                        target=activate_sbarb_hero_ability,
                        args=(hero_key, timing),
                        daemon=True
                    )
                    ability_thread.start()
                    print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

            print("[SBARB FARM] All heroes deployed, ability timers started")

            # Deploy siege machine
            keyboard.send(KEYS['siege'])
        time.sleep(0.01)
        pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
        pyautogui.click()
        time.sleep(0.3)

        # Check if Queen arrow spell targeting is enabled
        queen_arrow_spells = settings.get('sbarb_queen_arrow_spells', False)

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
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
            pass  # Will check again before next phase

    elif not turbo_deployment:
        # ===== ARMY FIRST ORDER (ORIGINAL) =====
        # (Only runs when turbo deployment is disabled AND heroes_first is False)
        # Deploy first half - HOLD-AND-DRAG for maximum spread
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
        hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]['hero']

        # Deploy each hero and start their ability timer immediately
        for hero_key in ['queen', 'king', 'warden', 'rc']:
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
                    target=activate_sbarb_hero_ability,
                    args=(hero_key, timing),
                    daemon=True
                )
                ability_thread.start()
                print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

        print("[SBARB FARM] All heroes deployed, ability timers started")

        # Deploy siege machine - ULTRA FAST
        keyboard.send(KEYS['siege'])
        time.sleep(0.01)
        pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
        pyautogui.click()
        time.sleep(0.2)  # Brief pause after siege

        # Check if 50% reached during first wave deployment
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
            pass  # Will check again before next phase

    # Check if 50% reached before moving camera for second wave
    # Skip if turbo deployment was used (already handled above)
    if not destruction_reached['value'] and not turbo_deployment:
        # Move camera to opposite side - ULTRA FAST (skip camera movement delays)
        print(f"[SBARB FARM] Moving camera to opposite side ({opposite_side})...")
        send_discord_debug_log(f"SBarb Farm: Moving camera to {opposite_side}")
        # Instant drag to opposite side - INCREASED DRAG DISTANCE
        drag_start_opposite, drag_end_opposite = drag_map[opposite_side]
        # Double the drag distance for better camera movement
        if opposite_side == 'up':
            drag_end_opposite = (1280, 1100)  # Increased from 900 to 1100
        elif opposite_side == 'down':
            drag_end_opposite = (1280, 500)  # Increased from 700 to 500

        pyautogui.moveTo(*drag_start_opposite, duration=0)
        pyautogui.mouseDown()
        pyautogui.moveTo(*drag_end_opposite, duration=0.15)  # Slightly slower for longer drag
        pyautogui.mouseUp()
        time.sleep(0.1)  # Reduced delay to exit camera drag mode (optimized for speed)

        # Start background achievement building scan if spell casting is enabled
        if settings.get('sbarb_cast_spells', False) and not achievement_scan_result['scanning']:
            scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
            scan_thread.start()
            print("[SBARB FARM] Started background achievement building scan during deployment")
            send_discord_debug_log("SBarb Farm: Background scan started during 2nd wave deployment")

        # Start background surrender button detection
        if not surrender_button_cache['detected']:
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
        if not destruction_reached['value']:
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
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during cleanup - stopping")
                            break

                        fast_click(*pos)
                        time.sleep(0.08)  # Brief delay between clicks
                        print(f"  Cleanup click {i+1}/{num_clicks}")

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
                    for pos in [cleanup_coords[0], cleanup_coords[len(cleanup_coords)//2], cleanup_coords[-1]]:
                        if destruction_reached['value']:
                            break
                        fast_click(*pos)
                        time.sleep(0.08)

                print("[SBARB FARM] Fallback cleanup complete")
                send_discord_debug_log("SBarb Farm: Fallback cleanup complete")
    else:
        print("[SBARB FARM] 50% reached - skipping second wave deployment")

    # Check if 50% reached before deploying spells
    # Note: In heroes-first mode with queen arrow spells, spells are already deployed before troops
    # Skip if turbo deployment was used (spells already handled in turbo mode)
    if not destruction_reached['value'] and not turbo_deployment:
        # Check if Queen arrow spells were enabled and if they've been deployed already
        queen_arrow_setting = settings.get('sbarb_queen_arrow_spells', False)

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
            queen_arrow_use_fallback = True
        else:
            # Need to deploy spells: either army-first mode, or heroes-first with no queen arrow, or detection failed
            queen_arrow_use_fallback = True

        # Deploy spells if needed
        if not (heroes_first and queen_arrow_setting and queen_arrow_spells):
            # Check if achievement building spell casting is enabled
            cast_spells_on_achievement = settings.get('sbarb_cast_spells', False)
            achievement_spells_deployed = False

            if cast_spells_on_achievement:
                # Use cached scan results from background thread
                print("[SBARB FARM] Checking background scan results...")

                # Wait for background scan to complete (max 2 seconds)
                scan_wait_start = time.time()
                while achievement_scan_result['scanning'] and (time.time() - scan_wait_start) < 2.0:
                    if destruction_reached['value']:
                        print("[SBARB FARM] 50% reached while waiting for scan - skipping")
                        break
                    time.sleep(0.1)

                if achievement_scan_result['found']:
                    # Background scan found a building - use cached result!
                    found_building = achievement_scan_result['building']
                    found_type = achievement_scan_result['type']
                    print(f"[SBARB FARM] ✓ Using cached scan result: {found_type.replace('_', ' ')}")
                    send_discord_debug_log(f"SBarb Farm: Using cached building ({found_type})")
                elif achievement_scan_result['completed']:
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
                    spell_casting_active['value'] = True

                    x, y, confidence = found_building
                    print(f"[SBARB FARM] CASTING SPELLS ON: {found_type.replace('_', ' ').title()} at ({x}, {y}) - Confidence: {confidence:.3f}")
                    runtime.gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
                    send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type.replace('_', ' ')} at ({x}, {y})")

                    # Deploy 1 Earthquake spell
                    print("Deploying Earthquake spell...")
                    keyboard.send('a')  # Earthquake hotkey
                    time.sleep(0.02)
                    fast_click(x, y)
                    time.sleep(0.05)

                    # Deploy 10 Lightning spells
                    print("Deploying Lightning spells...")
                    lightning_spells_cast = 0
                    for i in range(10):
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during spell deployment - stopping")
                            break
                        keyboard.send('s')  # Lightning hotkey
                        time.sleep(0.01)
                        # Add slight variation to position (±3px like Achievement Farm)
                        spell_x = x + random.randint(-3, 3)
                        spell_y = y + random.randint(-3, 3)
                        fast_click(spell_x, spell_y)
                        time.sleep(0.03)
                        lightning_spells_cast += 1
                        print(f"  Lightning {i+1}/10 deployed")

                    # Check if all 10 lightning spells were successfully cast
                    if lightning_spells_cast == 10:
                        print("[SBARB FARM] All spells deployed (1 Earthquake + 10 Lightning)!")
                        runtime.gui.log_message("Spells deployed successfully")
                        send_discord_debug_log("SBarb Farm: All spells deployed (1 Earthquake + 10 Lightning)")

                        # Track building destruction for CSV
                        # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
                        if found_type.startswith('cluster_') and 'cluster_types' in achievement_scan_result:
                            building_destroyed = achievement_scan_result['cluster_types']
                        else:
                            building_destroyed = found_type
                        spells_completed = True
                        print(f"[SBARB FARM] ✓ Achievement building destroyed: {found_type.replace('_', ' ').title()}")
                        send_discord_debug_log(f"SBarb Farm: {found_type.replace('_', ' ').title()} destroyed")
                    else:
                        print(f"[SBARB FARM] Spell deployment interrupted ({lightning_spells_cast}/10 lightning spells cast)")
                        send_discord_debug_log(f"SBarb Farm: Spell deployment interrupted ({lightning_spells_cast}/10)")

                    achievement_spells_deployed = True

                    # Clear flag - spell casting complete
                    spell_casting_active['value'] = False
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
                spell_casting_active['value'] = True

                # Spell region (center of base for maximum damage)
                spell_region = (982, 554, 1548, 871)

                # Deploy 2 Earthquake spells first
                keyboard.send('a')  # Select Earthquake spell
                time.sleep(0.05)

                for spell_num in range(2):
                    # Check during spell deployment
                    if destruction_reached['value']:
                        print("[SBARB FARM] 50% reached during spell deployment - stopping")
                        break
                    # Random location within spell region
                    random_x = random.randint(spell_region[0], spell_region[2])
                    random_y = random.randint(spell_region[1], spell_region[3])
                    fast_click(random_x, random_y)
                    time.sleep(0.05)

                if not destruction_reached['value']:
                    print("[SBARB FARM] 2 Earthquake spells deployed")

                    # Deploy 9 Lightning spells
                    keyboard.send('s')  # Select Lightning spell
                    time.sleep(0.05)

                    for spell_num in range(9):
                        # Check during spell deployment
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during spell deployment - stopping")
                            break

                        # Random location within spell region
                        random_x = random.randint(spell_region[0], spell_region[2])
                        random_y = random.randint(spell_region[1], spell_region[3])

                        if spell_num % 4 == 0 and spell_num > 0:  # Re-select spell every 4 casts
                            keyboard.send('s')
                            time.sleep(0.02)

                        fast_click(random_x, random_y)
                        time.sleep(0.05)  # Very fast spell casting

                    if not destruction_reached['value']:
                        print("[SBARB FARM] All spells deployed (2 Earthquake + 9 Lightning)")
                        send_discord_debug_log("SBarb Farm: All spells deployed (2 Earthquake + 9 Lightning)")

                # Clear flag - spell casting complete
                spell_casting_active['value'] = False
    else:
        print("[SBARB FARM] 50% reached - skipping spell deployment")

    # Wait for 50% if not reached yet (background thread still monitoring)
    if not destruction_reached['value']:
        print(f"[SBARB FARM] Waiting for {target_destruction}% destruction (60s timeout)...")
        runtime.gui.log_message(f"SBarb Farm: Waiting for {target_destruction}%...")

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached['value']:
                break
            time.sleep(0.2)  # Check every 0.2 seconds (faster polling)

        if not destruction_reached['value']:
            elapsed = time.time() - attack_start_time
            print(f"[SBARB FARM] 60s timeout reached (failsafe triggered after {elapsed:.1f}s)")
            runtime.gui.log_message("SBarb Farm: 60s timeout - surrendering")
            send_discord_debug_log("SBarb Farm: 60s timeout failsafe triggered", "WARNING")

    # Skip surrender if Return Home was already detected (battle ended early - troops died)
    if attack_failed_early and destruction_reached.get('return_home_pos'):
        print("[SBARB FARM] Skipping surrender - Return Home already detected (battle ended)")
        send_discord_debug_log("SBarb Farm: Skipping surrender - already at end screen")
    # OPTIMIZED surrender sequence - use cached position for instant surrender
    elif surrender_button_cache['detected']:
        # Use cached surrender button position (FAST - no template matching delay)
        surrender_pos = surrender_button_cache['position']
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
            if button_type == 'end_battle':
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
                    if button_type == 'surrender':
                        print(f"[SBARB FARM] Surrender now available at {x}, {y}")
                        fast_click(x, y)
                        time.sleep(0.1)
                        fast_click(1483, 898)
                        time.sleep(0.1)
                        break
                    elif button_type == 'end_battle':
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

    # End timer and save attack duration to CSV
    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time

    # Save to data/sbarb_time.csv with achievement building destruction tracking
    csv_file = "data/sbarb_time.csv"
    file_exists = os.path.exists(csv_file)

    # Format building name for CSV (only if all spells completed, otherwise blank)
    building_name_display = building_destroyed.replace('_', ' ').title() if spells_completed else ""

    # Determine attack outcome
    if destruction_reached.get('percentage', 0) >= target_destruction:
        attack_outcome = "Success"
    elif attack_failed_early:
        attack_outcome = "Failed (early end)"
    else:
        attack_outcome = "Failed (timeout)"

    try:
        import csv
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Loop #', 'Duration (seconds)', 'Timestamp', 'Building Destroyed', 'Outcome'])
            writer.writerow([
                runtime.loop_count + 1,
                f'{attack_duration:.2f}',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                building_name_display,
                attack_outcome
            ])
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
    if destruction_reached.get('return_home_pos'):
        print(f"[SBARB FARM] Using cached Return Home position: {destruction_reached['return_home_pos']}")
        fast_click(*destruction_reached['return_home_pos'])
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

    return True  # Attack completed


# ============================================================================
# STORAGE READING FUNCTIONS (for Queue System)
# ============================================================================


# ============================================================================
# ATTACK MODE HANDLERS
# ============================================================================

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


def should_skip_base(gold, elixir, air_defenses, settings):
    """Determine if base should be skipped based on resources and air defenses"""
    min_amount = settings.get('min_resources', config.MIN_AMOUNT)
    reinforcements_enabled = get_global_reinforcements_enabled()
    
    # Check resources
    if gold + elixir < min_amount:
        send_discord_debug_log(f"Insufficient resources: {gold + elixir:,} < {min_amount:,}, skipping base")
        return True, "insufficient_resources"
    
    # Check air defenses
    if reinforcements_enabled and len(air_defenses) < 4:
        print(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base.")
        runtime.gui.log_message(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base.")
        send_discord_debug_log(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base", "WARNING")
        return True, "insufficient_air_defenses"
    
    if not reinforcements_enabled and len(air_defenses) < 3:
        print(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        runtime.gui.log_message(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        send_discord_debug_log(f"Only {len(air_defenses)} air defenses detected, skipping base", "WARNING")
        return True, "insufficient_air_defenses"
    
    return False, None

def skip_base():
    """Skip the current base"""
    x, y = config.SKIP_BUTTON
    jitter = 24
    click_in_square((x - jitter, y - jitter, x + jitter, y + jitter))
    # No delay - detection loop in main_loop() handles waiting for next base

def choose_attack_side(settings, town_hall=None):
    """Choose attack side based on settings and town hall position"""
    attack_side_mode = settings.get('attack_side_mode', 'random')
    sides = list(config.SIDE_DEPLOYMENT_COORDS.keys())
    
    if attack_side_mode == 'th_side' and town_hall:
        # Base center point for side detection
        BASE_CENTER_X = 1298
        BASE_CENTER_Y = 697
        
        # Adjust Town Hall position to its center for side detection
        th_center = (town_hall[0] + 60, town_hall[1] + 75)
        
        # Determine which side of the base center the town hall is located
        th_x, th_y = th_center
        
        # Calculate relative position from base center
        x_diff = th_x - BASE_CENTER_X
        y_diff = th_y - BASE_CENTER_Y
        
        # Determine side based on which quadrant the town hall is in
        if abs(x_diff) > abs(y_diff):
            # Town hall is more horizontally offset
            if x_diff > 0:
                chosen_side = 'right'
            else:
                chosen_side = 'left'
        else:
            # Town hall is more vertically offset
            if y_diff > 0:
                chosen_side = 'down'
            else:
                chosen_side = 'up'
        
        # Debug information
        debug_info = f"TH at ({th_x}, {th_y}), center at ({BASE_CENTER_X}, {BASE_CENTER_Y})"
        debug_info += f", x_diff={x_diff:.1f}, y_diff={y_diff:.1f}"
        runtime.gui.debug_message(debug_info)
        
        side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
        runtime.gui.log_message(f"Chosen attack side: {chosen_side} (TH on {chosen_side} side of base center)")
        print(f"Chosen attack side: {chosen_side} (TH on {chosen_side} side of base center)")
        send_discord_debug_log(f"Attack side chosen: {chosen_side} (TH-based)")
        # Draw attack side indicator on overlay
        overlay_draw_side(chosen_side)
        overlay_update()
        return chosen_side, side_coords
    else:
        # Fallback to random
        chosen_side = random.choice(sides)
        side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
        runtime.gui.log_message(f"Chosen attack side: {chosen_side} (random)")
        print(f"Chosen attack side: {chosen_side} (random)")
        send_discord_debug_log(f"Attack side chosen: {chosen_side} (random)")
        # Draw attack side indicator on overlay
        overlay_draw_side(chosen_side)
        overlay_update()
        return chosen_side, side_coords


def prepare_hotkeys(alt_hotkeys):
    """Prepare hotkeys based on whether alternate hotkeys are detected"""
    KEYS = dict(config.KEYS)
    if alt_hotkeys:
        # Swap troop1 and troop2 if alternate hotkeys detected
        KEYS['troop1'], KEYS['troop2'] = KEYS['troop2'], KEYS['troop1']
        KEYS['queen'], KEYS['warden'] = KEYS['warden'], KEYS['queen']
    return KEYS

def check_town_hall_level(town_hall, settings):
    """Check if town hall level is acceptable, return True if should skip"""
    if town_hall:
        x, y, level, conf = town_hall
        print(f"Detected Town Hall Level {level} at ({x}, {y}) - Confidence: {conf:.2f}")
        runtime.gui.log_message(f"Town Hall Level {level} detected")
        
        # Check max Town Hall level from settings
        max_th_level = settings.get('max_th_level', 15)
        if level > max_th_level:
            print(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            runtime.gui.log_message(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            send_discord_debug_log(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base", "WARNING")
            return True
    else:
        print("Town Hall not detected")
        runtime.gui.log_message("Town Hall not detected")
        
        # Check if we should skip when town hall detection fails
        skip_on_th_fail = get_global_skip_on_th_fail()
        if skip_on_th_fail:
            print("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base.")
            runtime.gui.log_message("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base.")
            send_discord_debug_log("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base", "WARNING")
            return True
    
    return False

def deploy_lightning_spells(air_defenses, lightning_targets, chosen_side, settings, KEYS):
    """Deploy lightning spells on air defenses"""
    if not lightning_targets:
        print("No air defenses detected - skipping lightning spells")
        runtime.gui.log_message("No air defenses detected - skipping lightning spells")
        send_discord_debug_log("No air defenses detected - skipping lightning spells", "WARNING")
        return
    
    reinforcements_enabled = get_global_reinforcements_enabled()
    
    if reinforcements_enabled:
        print(f"Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        runtime.gui.log_message(f"Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        send_discord_debug_log("Deploying 13 lightning spells (Reinforcements mode)")
        
        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level
        
        spells_used = 0
        lightning_damage = settings.get('lightning_damage', 300)
        
        # Use 12 spells (3 per AD) on 4 air defenses
        for idx, (x, y, level, _) in enumerate(air_defenses[:4]):
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            for i in range(spell_count):
                if spells_used < 11:
                    keyboard.send(KEYS['lightning'])
                else:
                    keyboard.send('s')  # Use 'S' for the last 2 spells
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/13 at ({x}, {y}) (AD {idx+1})")
                spells_used += 1
        
        # 13th spell at random location
        random_x = random.randint(1003, 1495)
        random_y = random.randint(471, 853)
        keyboard.send('s')
        time.sleep(0.02)
        jitter = random.randint(-5, 5)
        pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
        pyautogui.click()
        print(f"    13th Lightning spell at random location ({random_x}, {random_y})")
        spells_used += 1
        
        runtime.gui.log_message("Lightning spell deployment completed (Reinforcements mode)")
        send_discord_debug_log("Lightning spell deployment completed (Reinforcements mode)")
    else:
        print(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        runtime.gui.log_message(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        send_discord_debug_log(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        
        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level
        
        spells_used = 0
        lightning_damage = settings.get('lightning_damage', 300)
        
        # Target exactly 3 air defenses (9 spells total)
        for idx, (x, y) in enumerate(lightning_targets[:3]):  # Only first 3 air defenses
            level = position_to_level.get((x, y), 1)
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            hp = config.AIR_DEFENSE_HP.get(level, 1000)
            print(f"  Air Defense {idx+1} (Level {level}) has {hp} HP, using {spell_count} lightning spells ({lightning_damage} damage each)")
            
            for i in range(spell_count):
                keyboard.send(KEYS['lightning'])
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/9 at ({x}, {y}) (AD {idx+1})")
                spells_used += 1
        
        print(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining for air sweepers")
        runtime.gui.log_message(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")
        send_discord_debug_log(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")
        
        # Handle remaining spells (should be 2 for air sweepers)
        handle_remaining_lightning_spells(spells_used, chosen_side, KEYS)
        
        runtime.gui.log_message("Lightning spell deployment completed (non-reinforcements mode)")
        send_discord_debug_log("Lightning spell deployment completed (non-reinforcements mode)")

def handle_remaining_lightning_spells(spells_used, chosen_side, KEYS):
    """Handle remaining lightning spells (air sweepers or random)"""
    if spells_used < 11:
        remaining_spells = 11 - spells_used
        print(f"Handling {remaining_spells} remaining lightning spells...")
        
        if remaining_spells == 2:
            # Perfect scenario: 2 spells for air sweepers
            sweepers = detect_air_sweepers()
            print(f"Detected {len(sweepers)} air sweepers for lightning targeting.")
            runtime.gui.log_message(f"Detected {len(sweepers)} air sweepers for lightning targeting.")
            send_discord_debug_log(f"Detected {len(sweepers)} air sweepers for lightning targeting")
            
            # Map attack side to directions
            side_to_dirs = {
                'left': ['left', 'up_left', 'down_left'],
                'right': ['right', 'up_right', 'down_right'],
                'up': ['up', 'up_left', 'up_right'],
                'down': ['down', 'down_left', 'down_right']
            }
            preferred_dirs = side_to_dirs.get(chosen_side, [])
            
            # Find sweeper facing the attack side
            target_sweeper = None
            for sw in sweepers:
                if sw[2] in preferred_dirs:
                    target_sweeper = sw
                    break
            if not target_sweeper and sweepers:
                target_sweeper = random.choice(sweepers)
            
            if target_sweeper:
                x, y, direction, conf = target_sweeper
                print(f"Targeting air sweeper at ({x}, {y}) facing {direction} (confidence: {conf:.3f})")
                for i in range(2):
                    keyboard.send(KEYS['lightning'])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Lightning spell {spells_used + i + 1}/11 at Air Sweeper ({x}, {y}) facing {direction}")
                print("Air sweeper lightning spells deployed successfully")
                runtime.gui.log_message("Air sweeper lightning spells deployed successfully")
                send_discord_debug_log("Air sweeper lightning spells deployed successfully")
            else:
                print("No air sweeper found for remaining lightning spells.")
                runtime.gui.log_message("No air sweeper found for remaining lightning spells.")
                send_discord_debug_log("No air sweeper found for remaining lightning spells", "WARNING")
                # Use the 2 spells at random coordinates as fallback
                random_coords = [
                    (1003, 471),  # Point 1
                    (1495, 853)   # Point 2
                ]
                for i in range(2):
                    x1, y1 = random_coords[0]
                    x2, y2 = random_coords[1]
                    random_x = random.randint(min(x1, x2), max(x1, x2))
                    random_y = random.randint(min(y1, y2), max(y1, y2))
                    keyboard.send(KEYS['lightning'])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")
        else:
            # Failsafe: Use remaining lightning spells at random coordinates
            print(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            runtime.gui.log_message(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            send_discord_debug_log(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            
            random_coords = [
                (1003, 471),  # Point 1
                (1495, 853)   # Point 2
            ]
            for i in range(remaining_spells):
                x1, y1 = random_coords[0]
                x2, y2 = random_coords[1]
                random_x = random.randint(min(x1, x2), max(x1, x2))
                random_y = random.randint(min(y1, y2), max(y1, y2))
                keyboard.send(KEYS['lightning'])
                time.sleep(0.02)
                jitter = random.randint(-5, 5)
                pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")


def deploy_troops(side_coords, settings, KEYS):
    """Deploy all troops (generic troop slots 1-7, Siege, Heroes)"""
    # Get troop counts from settings
    troop_counts = settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])

    # Deploy each troop type that has count > 0
    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'

            # Get deployment coordinates
            troop_coords = random.sample(side_coords['units'], min(troop_count, len(side_coords['units'])))

            # Select troop
            keyboard.send(KEYS[troop_key])
            time.sleep(0.1)

            # Deploy troops
            for x, y in troop_coords:
                random_sleep(config.SLEEP_MIN, config.SLEEP_MAX)
                pyautogui.moveTo(x, y, duration=random.uniform(0.03, 0.07))
                pyautogui.click()

            send_discord_debug_log(f"Deployed {troop_count} troops from slot {i+1}")
            print(f"Deployed {troop_count} troops from slot {i+1}")
    
    # Deploy Siege Machine and Heroes
    print("Deploying siege machine and heroes...")
    send_discord_debug_log("Deploying siege machine and heroes")
    hero_pos = side_coords['hero']
    
    # Get individual hero ability timing from settings
    settings = runtime.gui.get_settings()
    queen_timing = settings.get('queen_ability_timing', 15)
    king_timing = settings.get('king_ability_timing', 15)
    warden_timing = settings.get('warden_ability_timing', 15)
    rc_timing = settings.get('rc_ability_timing', 15)
    
    # Deploy siege machine
    keyboard.send(KEYS['siege'])
    time.sleep(config.HERO_DELAY)
    human_like_move_click(*hero_pos)
    time.sleep(config.POST_DEPLOY_DELAY)
    
    # Deploy heroes and start their ability timers individually
    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }
    
    import threading
    
    def activate_hero_ability(hero_role, timing):
        """Activate a specific hero's ability after the specified timing"""
        if timing >= 0:
            if timing > 0:
                time.sleep(timing)
            keyboard.send(KEYS[hero_role])
            send_discord_debug_log(f"{hero_role.title()} ability activated after {timing} seconds")
        elif timing == -1:
            send_discord_debug_log(f"{hero_role.title()} ability disabled")
    
    # Deploy each hero and start their individual ability timer
    for role in ['queen', 'king', 'warden', 'rc']:
        # Deploy the hero
        keyboard.send(KEYS[role])
        time.sleep(config.HERO_DELAY)
        human_like_move_click(*hero_pos)
        time.sleep(config.POST_DEPLOY_DELAY)
        
        # Start ability timer for this specific hero
        timing = hero_timings[role]
        if timing != -1:  # Only start thread if ability is not disabled
            ability_thread = threading.Thread(
                target=activate_hero_ability, 
                args=(role, timing), 
                daemon=True
            )
            ability_thread.start()
            send_discord_debug_log(f"Started {role.title()} ability timer ({timing} seconds)")

def wait_for_battle_end():
    """Wait until battle ends by detecting black bar region"""
    send_discord_debug_log("Waiting for battle to end...")
    check_count = 0
    while runtime.running:
        img = ImageGrab.grab(bbox=config.BLACK_BAR_REGION)
        if all(pixel == config.BLACK_BAR_COLOR for pixel in img.getdata()):
            break

        # Occasional mouse drift during wait (every ~5 checks = ~5 seconds)
        if check_count % 5 == 0:
            mouse_drift_idle(max_drift=10)

        time.sleep(1)
        check_count += 1

def handle_post_battle():
    """Handle post-battle activities (loot capture, return home, reinforcements)"""
    # Capture loot after battle ends
    print("Battle ended, capturing loot...")
    runtime.gui.log_message("Battle ended, capturing loot...")
    send_discord_debug_log("Battle ended, capturing loot")
    time.sleep(config.LOOT_CAPTURE_DELAY)
    
    loot_data = ocr_loot()
    save_loot_data(loot_data, runtime.loop_count + 1)
    
    # Update GUI loot statistics
    runtime.root.after(0, lambda: runtime.gui.update_loot_stats(loot_data))
    
    # Return home
    human_like_move_click(*config.RETURN_BUTTON)

    # Wait for base screen to load (template matching army button)
    if not wait_for_base_screen(timeout=15):
        print("[WARNING] Base screen not detected after return - OCR may be inaccurate")
        send_discord_debug_log("Base screen not detected after return - OCR may fail", "WARNING")

    # Wait for resources to stabilize before reading
    time.sleep(0.3)

    # Check base resources after returning home (template matching OCR with retry)
    max_retries = 3

    # Read Gold with retry
    base_gold = 0
    for attempt in range(max_retries):
        base_gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
        base_gold = ocr_attack_resource_template_digits(base_gold_img, context='base_screen', debug=False, resource_type='gold')
        if base_gold > 0:
            break
        if attempt < max_retries - 1:
            print(f"[STORAGE] Gold OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
            time.sleep(0.2)

    # Read Elixir with retry
    base_elixir = 0
    for attempt in range(max_retries):
        base_elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
        base_elixir = ocr_attack_resource_template_digits(base_elixir_img, context='base_screen', debug=False, resource_type='elixir')
        if base_elixir > 0:
            break
        if attempt < max_retries - 1:
            print(f"[STORAGE] Elixir OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
            time.sleep(0.2)

    # Read Dark Elixir with retry
    base_dark_elixir = 0
    if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
        for attempt in range(max_retries):
            base_dark_elixir_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
            base_dark_elixir = ocr_attack_resource_template_digits(base_dark_elixir_img, context='base_dark_elixir', debug=False)
            if base_dark_elixir > 0:
                break
            if attempt < max_retries - 1:
                print(f"[STORAGE] DE OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(0.2)
    print(f"Base resources after attack: Gold={base_gold}, Elixir={base_elixir}, Dark Elixir={base_dark_elixir}")
    send_discord_debug_log(f"Base resources after attack: Gold={base_gold:,}, Elixir={base_elixir:,}, Dark Elixir={base_dark_elixir:,}")

    # Track resources and check for full storages (no loot gained over 3 attacks)
    track_resources(base_gold, base_elixir, base_dark_elixir, base_type='main_base')
    check_and_pause_if_storages_full(base_type='main_base')

    # Check if storages are full (Farming profile, at least 2 of 3 full)
    settings = runtime.gui.get_settings()
    current_profile = settings.get('current_profile', '')
    if current_profile == 'Farming':
        # Get max values from settings (fall back to defaults if missing)
        try:
            import json
            with open('bot_settings.json', 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            max_gold = int(file_data.get('max_gold_storage', 14000000))
            max_elixir = int(file_data.get('max_elixir_storage', 14000000))
            max_dark = int(file_data.get('max_dark_elixir_storage', 240000))
        except Exception:
            max_gold = 14000000
            max_elixir = 14000000
            max_dark = 240000
        full_count = 0
        if base_gold == max_gold:
            full_count += 1
        if base_elixir == max_elixir:
            full_count += 1
        if base_dark_elixir == max_dark:
            full_count += 1
        if full_count >= 2:
            msg = f"<@everyone> Storages are full! Gold: {base_gold:,}/{max_gold:,}, Elixir: {base_elixir:,}/{max_elixir:,}, Dark Elixir: {base_dark_elixir:,}/{max_dark:,}. Bot paused."
            send_discord_notification(msg)
            runtime.gui.log_message("At least 2 storages are full. Bot paused.")
            return True  # Signal to pause bot
    
    # Check if storages are full (legacy logic)
    if base_gold == 11_000_000 or base_elixir == 14_000_000:
        msg = f"<@everyone> Storages are full! Gold: {base_gold:,}, Elixir: {base_elixir:,}. Bot paused."
        send_discord_notification(msg)
        return True  # Signal to pause bot
    
    # Handle reinforcements
    reinforcements_enabled = get_global_reinforcements_enabled()
    if reinforcements_enabled:
        print("Requesting reinforcements...")
        runtime.gui.log_message("Requesting reinforcements...")
        send_discord_debug_log("Requesting reinforcements")

        # Detect and click army button
        army_button_pos = detect_army_button()
        if army_button_pos:
            human_like_move_click(*army_button_pos)
            time.sleep(0.5)

            # Click reinforce request button
            human_like_move_click(*config.REINFORCE_REQUEST_COORDS)
            time.sleep(0.5)

            # Click confirm button
            human_like_move_click(*config.Confirm_Coords)
            time.sleep(1.0)

            print("Reinforcements requested successfully")
            runtime.gui.log_message("Reinforcements requested successfully")
            send_discord_debug_log("Reinforcements requested successfully")
        else:
            print("Failed to detect army button - skipping reinforcements")
            runtime.gui.log_message("Failed to detect army button - skipping reinforcements")
            send_discord_debug_log("Failed to detect army button - skipping reinforcements", "WARNING")

    return False  # No need to pause


def perform_achievement_farm_attack():
    """Perform Achievement Farm attack with 3 targeting modes: Target, Clumps, First Detected"""
    print("=== ENTERING ACHIEVEMENT FARM MODE ===")
    send_discord_debug_log("=== ENTERING ACHIEVEMENT FARM MODE ===")
    runtime.gui.log_message("Achievement Farm mode activated")

    # Get current settings from GUI
    settings = runtime.gui.get_settings()

    # Get priority building type, targeting mode, and priority list from settings
    priority_building = settings.get('achievement_target_building', 'eagle_artillery')
    target_mode = settings.get('achievement_farm_target_mode', 'clumps')
    priority_list = settings.get('achievement_priority_list', [
        'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
        'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
    ])

    # Build list of enabled buildings from checkboxes
    # Uses full key names: achievement_scan_eagle_artillery, achievement_scan_inferno_tower, etc.
    enabled_buildings = []
    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                      'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
    for bt in building_types:
        if settings.get(f'achievement_scan_{bt}', True):
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
    send_discord_debug_log(f"Achievement Farm: Mode={target_mode}, Target={priority_building.replace('_', ' ')}, Enabled={len(enabled_buildings)}")

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

    if target_mode == 'target':
        # MODE 1: Target - Try buildings in priority order until one is found
        print(f"[TARGET MODE] Trying buildings in priority order...")

        # Filter priority list to only include enabled buildings
        priority_enabled = [b for b in priority_list if b in enabled_buildings]

        if not priority_enabled:
            print(f"[TARGET MODE] No enabled buildings in priority list!")
            runtime.gui.log_message(f"No enabled buildings - surrendering")
            send_discord_debug_log(f"Achievement Farm [TARGET]: No enabled buildings", "WARNING")
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
            print(f"[TARGET MODE] No buildings detected in priority list - skipping base")
            runtime.gui.log_message(f"No targets found - skipping base")
            send_discord_debug_log(f"Achievement Farm [TARGET]: No buildings found - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            runtime.skipped_bases += 1
            return False  # Continue to next base

    elif target_mode == 'first_detected':
        # MODE 3: First Detected - FAST MODE: Stop scanning as soon as ANY building is found (PRIORITY ORDER)
        print(f"[FIRST DETECTED MODE] Scanning in priority order for first match...")
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
            print(f"FIRST DETECTED: {found_type.replace('_', ' ').title()} at center ({x}, {y}) - Confidence: {confidence:.3f}")
            runtime.gui.log_message(f"First detected: {found_type.replace('_', ' ')} - attacking!")
            send_discord_debug_log(f"Achievement Farm [FIRST]: {found_type.replace('_', ' ')} at ({x}, {y})")
            # Draw spell target on overlay at building center
            overlay_draw_spell_target(x, y, f"FIRST: {found_type.replace('_', ' ')}")
        else:
            print(f"No buildings detected after scanning priority list - skipping base")
            runtime.gui.log_message(f"No buildings detected - skipping base")
            send_discord_debug_log(f"Achievement Farm [FIRST]: No buildings detected - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            runtime.skipped_bases += 1
            return False

    else:  # target_mode == 'clumps'
        # MODE 2: Clumps - Look for clusters, prefer priority building if no cluster
        print(f"[CLUMPS MODE] Scanning enabled building types for clusters...")
        overlay_clear()  # Clear overlay before scanning
        if runtime.gui.overlay and runtime.gui.overlay_enabled:
            runtime.gui.overlay.draw_text(100, 50, "CLUMPS MODE: Scanning all building types...", '#FFFF00')
            runtime.gui.overlay.update()
        all_buildings = detect_all_achievement_buildings(enabled_buildings)

        if not all_buildings:
            print(f"No achievement buildings found - skipping base")
            runtime.gui.log_message(f"No achievement buildings found - skipping base")
            send_discord_debug_log(f"Achievement Farm [CLUMPS]: No buildings found - skipping base")
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
            print(f"No cluster found, selecting highest priority building...")

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
                print(f"PRIORITY TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
                runtime.gui.log_message(f"Single {target_type.replace('_', ' ')} (priority #{priority_list.index(target_type)+1}) - attacking")
                send_discord_debug_log(f"Achievement Farm [CLUMPS-PRIORITY]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})")
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
                print(f"FALLBACK TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
                runtime.gui.log_message(f"Single {target_type.replace('_', ' ')} (fallback) - attacking")
                send_discord_debug_log(f"Achievement Farm [CLUMPS-FALLBACK]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})")
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
    keyboard.send('a')
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)
    turbo_move_cursor(x, y)
    turbo_fast_click()
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    # Lightning spells - Windows API fast clicks (tight spread)
    for i in range(10):
        keyboard.send('s')
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)
        spell_x = x + random.randint(-3, 3)
        spell_y = y + random.randint(-3, 3)
        turbo_move_cursor(spell_x, spell_y)
        turbo_fast_click()
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    spell_elapsed = time.time() - spell_start
    print(f"[ACH FARM] Cast 11 spells in {spell_elapsed*1000:.0f}ms (~{11/spell_elapsed:.0f} CPS)")

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


def perform_normal_attack():
    """Perform a normal attack (non-derank mode)"""
    # SANITY CHECK: Verify we should be here
    settings = runtime.gui.get_settings()
    current_profile = settings.get('current_profile', 'Unknown')
    sbarb_mode_check = settings.get('sbarb_farm_mode', False)

    if sbarb_mode_check:
        print(f"\n{'!'*70}")
        print(f"[ERROR] ❌ CRITICAL: perform_normal_attack() called with sbarb_farm_mode=True!")
        print(f"[ERROR] Profile: {current_profile}")
        print(f"[ERROR] This should NEVER happen - SBarb Farm should skip evaluation!")
        print(f"[ERROR] Check that bot was restarted after code changes!")
        print(f"{'!'*70}\n")
        send_discord_debug_log(f"ERROR: perform_normal_attack() called with sbarb_farm_mode=True! Profile: {current_profile}", "ERROR")

    # Get current settings from GUI
    settings = runtime.gui.get_settings()

    # OCR resources
    gold, elixir = evaluate_base_resources()

    # Human-like pause to "read" the loot values
    reading_pause(0.4)  # Quick glance at loot

    # Detect air defenses
    air_defenses = detect_air_defenses()
    print(f"Air defenses detected (count): {len(air_defenses)}")
    for i, ad in enumerate(air_defenses):
        x, y, level, conf = ad
        print(f"  AD {i+1}: ({x}, {y}), Level: {level}, Confidence: {conf:.2f}")

    # Human-like pause to "analyze" the base and make decision
    thinking_pause(0.3, 0.8)  # Quick analysis

    # Check if should skip base
    should_skip, skip_reason = should_skip_base(gold, elixir, air_defenses, settings)
    if should_skip:
        skip_base()
        return False  # Attack not completed
    
    send_discord_debug_log(f"Base selected for attack: {len(air_defenses)} air defenses, {gold + elixir:,} resources")
    
    # Choose attack side
    town_hall = detect_town_hall()
    if check_town_hall_level(town_hall, settings):
        skip_base()
        return False  # Attack not completed
    
    chosen_side, side_coords = choose_attack_side(settings, town_hall)

    # Brief pause before committing to attack (simulates final decision)
    thinking_pause(0.2, 0.5)  # Quick final check

    # Detect alternate hotkeys
    alt_hotkeys = detect_alt_hotkeys()
    KEYS = prepare_hotkeys(alt_hotkeys)

    # Get lightning spell targets
    ad_target_mode = settings.get('ad_target_mode', 'level')
    if ad_target_mode == 'proximity':
        sorter = get_air_defense_proximity_sorter(chosen_side)
        sorted_air_defenses = sorted(air_defenses, key=sorter)
        lightning_targets = [(x, y) for x, y, _, _ in sorted_air_defenses]
    else:
        lightning_targets = get_lightning_spell_targets(air_defenses)

    # Attack screen already loaded by main_loop - proceed with spell deployment
    print("[NORMAL ATTACK] Deploying lightning spells...")

    # Deploy lightning spells with smart targeting:
    # - Reinforcements mode: 13 spells on 4 air defenses (3 per AD + 1 random)
    # - Non-reinforcements mode: 9 spells on 3 air defenses + 2 spells on air sweepers
    deploy_lightning_spells(air_defenses, lightning_targets, chosen_side, settings, KEYS)
    
    # Move camera to chosen side
    move_camera_to_side(chosen_side)
    
    # Deploy troops
    deploy_troops(side_coords, settings, KEYS)
    
    # Wait for battle to end
    wait_for_battle_end()
    
    # Handle post-battle activities
    should_pause = handle_post_battle()
    if should_pause:
        return True  # Signal to pause bot
    
    return False  # Attack completed successfully

def deploy_wall_breaker(position):
    """Deploy a single Super Wall Breaker at the specified position"""
    keyboard.send('2')  # Wall Breaker hotkey
    time.sleep(0.05)
    pyautogui.moveTo(*position, duration=0.02)
    pyautogui.click()
    time.sleep(0.05)

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

    # Deploy heroes AFTER first wave
    import threading

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

    # Move camera to opposite side (fast mode for SGoblin Farm)
    print(f"Moving camera to opposite side ({opposite_side})...")
    send_discord_debug_log(f"Moving camera to opposite side ({opposite_side})")
    move_camera_to_opposite_side(chosen_side, fast_mode=True)

    # PASS 3 & 4: Deploy second half on opposite side
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

    # CLEANUP PHASE: Deploy any remaining units by dragging backwards for 3 seconds (REMOVED - no longer needed with 4-pass strategy)
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

    # All troops deployed - START 10 second timer before surrender
    print("All troops deployed, starting 10 second timer...")
    send_discord_debug_log("SGoblin: All troops deployed, 10 second timer started")
    timer_start = time.time()

    # Check if spell casting on achievement buildings is enabled
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


def main_loop():
    
    # Each iteration covers one full attack cycle
    while runtime.running:
        # Check for Discord commands
        check_discord_commands()
        
        # Check if GUI wants to stop
        if not runtime.gui.bot_running:
            runtime.running = False
            send_discord_debug_log("Bot stopped by GUI", "INFO")
            break
            
        # Check if GUI wants to pause
        runtime.paused = runtime.gui.bot_paused
        
        # Automatic break check
        if runtime.break_time is not None and time.time() >= runtime.break_time:
            print("Taking scheduled break.")
            runtime.paused = True
            runtime.gui.bot_paused = True
            runtime.gui.log_message("Taking scheduled break")
            send_discord_debug_log("Taking scheduled break", "INFO")
            runtime.root.after(0, update_status)
            
            # Get break duration from settings and schedule auto-resume
            settings = runtime.gui.get_settings()
            break_duration = settings.get('break_duration', 5)  # minutes
            runtime.root.after(0, lambda: runtime.gui.schedule_auto_resume(break_duration))
            
            # schedule next break after auto-resume
            runtime.break_time = schedule_next_break()
        
        time.sleep(0.1)
        if runtime.paused:
            continue
        time.sleep(0.2)
        if runtime.paused:
            continue

        # ===== UNIVERSAL: Return Home Recovery for Main Base Modes =====
        # If stuck on end screen (Return Home button visible), click it and recover
        # BB modes are excluded - they have their own state machine recovery
        settings_check = runtime.gui.get_settings()
        bb_mode_active = settings_check.get('bb_elixir_mode', False) or settings_check.get('bb_gold_mode', False)

        if not bb_mode_active:
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                print(f"[MAIN LOOP] !! Return Home detected at loop start - recovering from stuck end screen")
                runtime.gui.log_message("Recovery: Clicking Return Home (stuck on end screen)")
                send_discord_debug_log("Main Loop: Return Home recovery triggered", "WARNING")

                # Click Return Home button
                fast_click(*return_home_pos)
                time.sleep(1.5)  # Wait for transition

                # Handle potential star bonus screen
                if detect_star_bonus_screen():
                    print("[MAIN LOOP] Star bonus detected during recovery - closing")
                    fast_click(102, 824)  # Close star bonus
                    time.sleep(0.5)

                # Wait for base screen to load
                wait_for_base_screen(timeout=10)

                print("[MAIN LOOP] Recovery complete - restarting loop iteration")
                continue  # Restart this loop iteration cleanly

        try:
            # Start of attack cycle
            send_discord_debug_log(f"Starting attack cycle {runtime.loop_count + 1}")

            # Get current settings from GUI
            settings = runtime.gui.get_settings()

            # DEBUG: Check overlay status at start of each cycle
            if runtime.gui.overlay_enabled:
                print(f"[OVERLAY] Cycle {runtime.loop_count + 1}: Overlay is ENABLED, drawing test marker...")
                overlay_clear()
                # Draw a test marker so we know the overlay is working
                if runtime.gui.overlay:
                    runtime.gui.overlay.draw_text(100, 50, f"Bot Cycle: {runtime.loop_count + 1}", '#00FF00')
                    runtime.gui.overlay.update()
            else:
                if runtime.loop_count == 0:  # Only print once
                    print("[OVERLAY] Overlay is disabled (checkbox not checked)")

            # Check if queue system is active
            queue_enabled = settings.get('queue_enabled', False)

            if queue_enabled and 'queue_manager' in globals() and runtime.queue_manager:
                # Ensure queue is started (handles race condition from web GUI)
                if not runtime.queue_manager.queue_active:
                    runtime.queue_manager.start_queue()

                # Get next mode from queue system
                next_mode = runtime.queue_manager.get_next_mode()

                if next_mode is None:
                    # Queue complete - stop bot
                    print("[QUEUE] Queue execution complete")
                    runtime.running = False
                    break

                # Set mode flags based on queue's selected mode
                print(f"[QUEUE] Executing mode: {next_mode}")
                derank_mode = (next_mode == 'Derank')
                sgoblin_farm_mode = (next_mode == 'SGoblin Farm')
                sbarb_farm_mode = (next_mode == 'SBarb Farm')
                bb_elixir_mode = (next_mode == 'BB Elixir')
                bb_gold_mode = (next_mode == 'BB Gold')
                achievement_farm_mode = (next_mode == 'Achievement Farm')

                # Update GUI profile to match queue mode
                if runtime.gui.current_profile != next_mode:
                    print(f"[QUEUE] Switching profile to: {next_mode}")
                    runtime.gui.current_profile = next_mode
                    runtime.gui.profile_var.set(next_mode)
                    runtime.gui.apply_current_profile(silent=True)  # Silent mode for queue auto-switching
            else:
                # Normal mode - use profile settings
                derank_mode = settings.get('derank_mode', False)
                sgoblin_farm_mode = settings.get('sgoblin_farm_mode', False)
                sbarb_farm_mode = settings.get('sbarb_farm_mode', False)
                bb_elixir_mode = settings.get('bb_elixir_mode', False)
                bb_gold_mode = settings.get('bb_gold_mode', False)
                achievement_farm_mode = settings.get('achievement_farm_mode', False)

            # CRITICAL DEBUG: Print ALL settings to verify
            current_profile = settings.get('current_profile', 'Unknown')

            send_discord_debug_log(f"Cycle {runtime.loop_count+1} | Profile: {current_profile}")

            # Handle potential star bonus screen and other popups (blind click - no detection)
            # This handles star bonus for BB Gold mode after returning to base
            # Harmless if no popup is present - click location chosen to avoid interfering with UI
            fast_click(73, 820)
            time.sleep(0.1)

            # 1. Open attack GUI (randomized click)
            x1,y1,x2,y2 = config.OPEN_GUI_BUTTON
            click_in_square((x1,y1,x2,y2))
            # Human-like delay with natural variance (0.4-0.7s range)
            humanized_sleep(0.55, variance=0.273)

            # Skip-based fast modes (no evaluation): derank, sgoblin, sbarb, bb modes, achievement
            # Use BB-specific search button for BB Elixir mode (BB Gold uses state machine)
            if bb_elixir_mode or bb_gold_mode:
                # Builder Base modes - skip main base search/attack buttons
                if bb_elixir_mode:
                    mode_name = "BB ELIXIR"

                    # Retry loop for base loading
                    retry_count = 0
                    base_loaded = False

                    while retry_count < config.BB_LOAD_MAX_RETRIES and not base_loaded:
                        # Click BB search button
                        click_in_square(config.BB_SEARCH_BUTTON)
                        print(f"[{mode_name}] Using Builder Base search button")
                        runtime.gui.log_message(f"{mode_name}: Searching for base...")
                        send_discord_debug_log(f"{mode_name}: Using Builder Base search button")

                        # Poll for "Attacker" text with timeout
                        print(f"[{mode_name}] Checking for Attacker text...")
                        runtime.gui.log_message(f"{mode_name}: Checking for Attacker text...")
                        send_discord_debug_log(f"{mode_name}: Checking for Attacker text")

                        start_time = time.time()
                        found = False

                        while not found and (time.time() - start_time) < config.BB_LOAD_TIMEOUT:
                            if check_bb_attacker_text():
                                found = True
                                base_loaded = True
                                print(f"[{mode_name}] ✓ Attacker text detected - base loaded!")
                                runtime.gui.log_message(f"{mode_name}: Base loaded!")
                                send_discord_debug_log(f"{mode_name}: Attacker text detected - base loaded")
                                time.sleep(0.5)
                                break
                            time.sleep(config.BB_LOAD_CHECK_INTERVAL)

                        # If timeout, click return and retry
                        if not found:
                            print(f"[{mode_name}] ⚠️ Base load timeout - no Attacker text found")
                            runtime.gui.log_message(f"{mode_name}: Base load timeout")
                            send_discord_debug_log(f"{mode_name}: Base load timeout - no Attacker text found", "WARNING")

                            print(f"[{mode_name}] Clicking return button to recover from ghost attack")
                            runtime.gui.log_message(f"{mode_name}: Returning to base...")
                            send_discord_debug_log(f"{mode_name}: Clicking return button to recover from ghost attack")
                            click_in_square(config.BB_RETURN_BUTTON_GHOST)
                            time.sleep(config.BB_RETRY_WAIT_TIME)

                            retry_count += 1

                            if retry_count < config.BB_LOAD_MAX_RETRIES:
                                print(f"[{mode_name}] Retrying search... (attempt {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES})")
                                runtime.gui.log_message(f"{mode_name}: Retry {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES}")
                                send_discord_debug_log(f"{mode_name}: Retrying search (attempt {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES})")
                            else:
                                print(f"[{mode_name}] ❌ Base load failed after {config.BB_LOAD_MAX_RETRIES} retries - skipping to next search")
                                runtime.gui.log_message(f"{mode_name}: Max retries exceeded - skipping")
                                send_discord_debug_log(f"{mode_name}: Base load failed after {config.BB_LOAD_MAX_RETRIES} retries - skipping", "ERROR")
                                # Skip to next search iteration - don't proceed with attack
                                continue
                # BB Gold mode doesn't need any clicks here - state machine handles everything internally
            else:
                # Main base modes only - click main base search and attack buttons
                click_in_square(config.SEARCH_BUTTON)

                # Wait for army selection screen to appear
                print("Waiting for army selection screen...")
                runtime.gui.log_message("Waiting for army screen...")
                send_discord_debug_log("Waiting for army selection screen")

                # Simple fixed delay for army selection screen to load
                time.sleep(0.2)  # Fast delay for army selection screen

                print("Army selection screen should be ready")
                runtime.gui.log_message("Army screen ready")
                send_discord_debug_log("Army selection screen ready")

                # Click START_ATTACK_BUTTON (green "Attack!" button) for all home base modes
                print(f"Clicking START_ATTACK_BUTTON at {config.START_ATTACK_BUTTON}")
                send_discord_debug_log(f"Clicking START_ATTACK_BUTTON at {config.START_ATTACK_BUTTON}")
                print(f"Current mouse position: {pyautogui.position()}")

                x_coord, y_coord = config.START_ATTACK_BUTTON
                print(f"Target coordinates: x={x_coord}, y={y_coord}")
                human_like_move_click(x_coord, y_coord)

                print(f"After click, mouse position: {pyautogui.position()}")
                # No fixed delay needed - OCR and base detection will handle timing

            # 2. Fast attack modes (no evaluation) - handle immediately and skip evaluation loop
            # These modes attack every base without checking resources/defenses
            print(f"[DEBUG] Checking fast attack modes...")
            if derank_mode:
                print(f"[DEBUG] ✓ derank_mode matched - using handle_derank_mode()")
                # Derank: attack every base with one troop
                if handle_derank_mode():
                    runtime.loop_count += 1
                    runtime.gui.update_loop_count(runtime.loop_count)
                    runtime.state_manager.set("loop_count", runtime.loop_count)
                    runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                    runtime.gui.log_message(f"Derank attack {runtime.loop_count} completed")
                    runtime.attacked_bases += 1
                    send_discord_debug_log(f"Derank attack {runtime.loop_count} completed")
                continue  # Skip to next attack cycle immediately

            elif sbarb_farm_mode:
                print(f"[DEBUG] ✓ ✓ ✓ sbarb_farm_mode matched - using handle_sbarb_farm_mode()")
                print(f"[DEBUG] NO EVALUATION - NO SKIPPING - Attacking base immediately!")
                send_discord_debug_log("SBarb Farm: Mode ACTIVE - NO evaluation, attacking immediately")
                # SBarb Farm: NO EVALUATION, NO SKIPPING - Attack every base immediately
                if handle_sbarb_farm_mode():
                    runtime.loop_count += 1
                    runtime.gui.update_loop_count(runtime.loop_count)
                    runtime.state_manager.set("loop_count", runtime.loop_count)
                    runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                    runtime.gui.log_message(f"SBarb Farm attack {runtime.loop_count} completed")
                    runtime.attacked_bases += 1
                    send_discord_debug_log(f"SBarb Farm attack {runtime.loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif bb_elixir_mode:
                # BB Elixir: attack every BB base with one troop
                if handle_bb_elixir_mode():
                    runtime.loop_count += 1
                    runtime.gui.update_loop_count(runtime.loop_count)
                    runtime.state_manager.set("loop_count", runtime.loop_count)
                    runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                    runtime.gui.log_message(f"BB Elixir attack {runtime.loop_count} completed")
                    runtime.attacked_bases += 1
                    send_discord_debug_log(f"BB Elixir attack {runtime.loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif bb_gold_mode:
                # BB Gold: deploy troops, wait for 2 stars, surrender
                if handle_bb_gold_mode():
                    runtime.loop_count += 1
                    runtime.gui.update_loop_count(runtime.loop_count)
                    runtime.state_manager.set("loop_count", runtime.loop_count)
                    runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                    runtime.gui.log_message(f"BB Gold attack {runtime.loop_count} completed")
                    runtime.attacked_bases += 1
                    send_discord_debug_log(f"BB Gold attack {runtime.loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif achievement_farm_mode:
                # Achievement Farm: search for specific building and attack
                should_pause = perform_achievement_farm_attack()
                if should_pause:
                    runtime.paused = True
                    runtime.gui.bot_paused = True
                    runtime.gui.log_message("Bot paused due to full storages. Discord notification sent.")
                    send_discord_debug_log("Bot paused due to full storages", "WARNING")
                    runtime.root.after(0, update_status)
                    break  # Exit main loop

                runtime.loop_count += 1
                runtime.gui.update_loop_count(runtime.loop_count)
                runtime.state_manager.set("loop_count", runtime.loop_count)
                runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                runtime.gui.log_message(f"Achievement Farm attack {runtime.loop_count} completed")
                runtime.attacked_bases += 1
                send_discord_debug_log(f"Achievement Farm attack {runtime.loop_count} completed successfully")
                runtime.root.after(0, lambda: runtime.gui.update_skipped_stats(runtime.skipped_bases, runtime.attacked_bases))

                # Check auto-pause condition
                if check_auto_pause():
                    continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            # 3. Evaluation-based attack modes (may skip bases)
            # These modes check resources/defenses and may skip bases
            print(f"[DEBUG] ❌ No fast modes matched - entering evaluation loop")
            print(f"[DEBUG] Will check: SGoblin Farm or Normal Attack")
            while runtime.running:
                if sgoblin_farm_mode:
                    print(f"[DEBUG] ✓ sgoblin_farm_mode matched - using perform_sgoblin_farm_attack()")
                    # Handle SGoblin Farm mode (no TH/AD detection, resource-based only)
                    result = perform_sgoblin_farm_attack()
                    if result == True:
                        # Pause bot due to full storages
                        runtime.paused = True
                        runtime.gui.bot_paused = True
                        runtime.gui.log_message("Bot paused due to full storages. Discord notification sent.")
                        send_discord_debug_log("Bot paused due to full storages", "WARNING")
                        runtime.root.after(0, update_status)
                        break  # Exit inner while loop
                    elif result == "skipped":
                        # Base was skipped, increment skipped counter and wait for next base
                        runtime.skipped_bases += 1
                        runtime.gui.log_message(f"Base skipped (total: {runtime.skipped_bases})")
                        send_discord_debug_log(f"SGoblin Farm: Base skipped (total: {runtime.skipped_bases})")
                        runtime.root.after(0, lambda: runtime.gui.update_skipped_stats(runtime.skipped_bases, runtime.attacked_bases))

                        # Wait for next base to load automatically (skip initiates auto-search)
                        print("Waiting for next base after skip...")
                        base_found = False
                        max_wait_time = 30  # Maximum 30 seconds to find next base
                        start_time = time.time()

                        while not base_found and (time.time() - start_time) < max_wait_time:
                            if is_base_search_ready():
                                base_found = True
                                print("Next base loaded after skip!")
                                runtime.gui.log_message("Next base loaded")
                                time.sleep(0.1)  # Small delay to ensure screen is stable
                                break
                            time.sleep(0.2)  # Check every 200ms

                        if not base_found:
                            print("WARNING: Base search timed out after skip")
                            runtime.gui.log_message("Base search timeout after skip")
                            send_discord_debug_log("Base search timeout after skip", "WARNING")
                            time.sleep(1)

                        # Continue loop to evaluate next base (don't break - stay in evaluation loop)
                        continue
                    else:
                        # Attack completed successfully
                        runtime.loop_count += 1
                        runtime.gui.update_loop_count(runtime.loop_count)
                        runtime.state_manager.set("loop_count", runtime.loop_count)
                        runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                        runtime.gui.log_message(f"SGoblin Farm attack {runtime.loop_count} completed")
                        runtime.attacked_bases += 1
                        send_discord_debug_log(f"SGoblin Farm attack {runtime.loop_count} completed successfully")
                        runtime.root.after(0, lambda: runtime.gui.update_skipped_stats(runtime.skipped_bases, runtime.attacked_bases))
                        break  # Exit inner while loop to start a new attack cycle
                else:
                    print(f"[DEBUG] Using NORMAL ATTACK mode (will evaluate and may skip)")
                    # Handle normal attack mode
                    should_pause = perform_normal_attack()
                    if should_pause:
                        runtime.paused = True
                        runtime.gui.bot_paused = True
                        runtime.gui.log_message("Bot paused due to full storages. Discord notification sent.")
                        send_discord_debug_log("Bot paused due to full storages", "WARNING")
                        runtime.root.after(0, update_status)
                        break  # Exit inner while loop

                    # Update loop count and continue
                    runtime.loop_count += 1
                    runtime.gui.update_loop_count(runtime.loop_count)
                    runtime.state_manager.set("loop_count", runtime.loop_count)
                    runtime.state_manager.set("bases_attacked", runtime.attacked_bases + 1)
                    runtime.gui.log_message(f"Attack {runtime.loop_count} completed")
                    runtime.attacked_bases += 1
                    send_discord_debug_log(f"Attack {runtime.loop_count} completed successfully")

                    # Update skipped/ratio statistics in GUI
                    runtime.root.after(0, lambda: runtime.gui.update_skipped_stats(runtime.skipped_bases, runtime.attacked_bases))
                    break  # Exit inner while loop to start a new attack cycle

        except pytesseract.pytesseract.TesseractNotFoundError:
            print("OCR engine missing. Pausing.")
            runtime.paused = True
            runtime.gui.bot_paused = True
            runtime.gui.log_message("ERROR: OCR engine missing")
            send_discord_debug_log("OCR engine missing - bot paused", "ERROR")
            runtime.root.after(0, update_status)
            time.sleep(5)
        except Exception as e:
            print(f"Error during loop: {e}")
            import traceback
            traceback.print_exc()  # Print full stack trace
            runtime.paused = True
            runtime.gui.bot_paused = True
            try:
                runtime.gui.log_message(f"ERROR: {str(e)}")
            except:
                print("[ERROR] Failed to log message to GUI")
            send_discord_debug_log(f"Error during attack loop: {str(e)}", "ERROR")
            try:
                runtime.root.after(0, update_status)
            except:
                print("[ERROR] Failed to update status")
            # --- Error screenshot saving ---
            try:
                error_dir = "errors"
                os.makedirs(error_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(error_dir, f"error_{timestamp}.png")
                img = ImageGrab.grab()
                img.save(screenshot_path)
                print(f"Error screenshot saved: {screenshot_path}")
                runtime.gui.log_message(f"Error screenshot saved: {screenshot_path}")
                send_discord_debug_log(f"Error screenshot saved: {screenshot_path}", "WARNING")
            except Exception as err:
                print(f"Failed to save error screenshot: {err}")
                runtime.gui.log_message(f"Failed to save error screenshot: {err}")
                send_discord_debug_log(f"Failed to save error screenshot: {err}", "ERROR")

    if runtime.attacked_bases > 0:
        skip_ratio = runtime.skipped_bases / runtime.attacked_bases
    else:
        skip_ratio = 0
    print(f"Bases skipped: {runtime.skipped_bases}, Attacks: {runtime.attacked_bases}, Skip/Attack ratio: {skip_ratio:.2f}")
    runtime.gui.log_message(f"Bases skipped: {runtime.skipped_bases}, Attacks: {runtime.attacked_bases}, Skip/Attack ratio: {skip_ratio:.2f}")
    send_discord_debug_log(f"Session summary: {runtime.skipped_bases} skipped, {runtime.attacked_bases} attacked, ratio: {skip_ratio:.2f}")

# Override GUI's run_bot method with our main loop
def gui_run_bot():
    runtime.running = True
    runtime.paused = False
    runtime.gui.bot_running = True
    runtime.gui.bot_paused = False
    runtime.gui.log_message("Bot thread started")
    # Update web state
    runtime.state_manager.set("running", True)
    runtime.state_manager.set("paused", False)
    runtime.state_manager.set("status", "RUNNING")
    main_loop()

runtime.gui.run_bot = gui_run_bot

# Set Queue Manager callbacks now that all functions are defined
if runtime.queue_manager:
    runtime.queue_manager.set_callbacks(read_own_base_storages, read_bb_base_storages, switch_village)

# Add window close handler to ensure cleanup
runtime.root.protocol("WM_DELETE_WINDOW", exit_app)

# Pre-load achievement building templates for faster detection (SBarb Farm optimization)
print("\n" + "="*70)
print("INITIALIZING TEMPLATE CACHE FOR SBARB FARM OPTIMIZATIONS")
print("="*70)
load_achievement_building_templates()
print("="*70 + "\n")

# Pre-load BB Gold templates for faster BB Gold attacks
print("="*70)
print("INITIALIZING BB GOLD TEMPLATE CACHE")
print("="*70)
load_bb_gold_templates()
print("="*70 + "\n")

# Start connection monitor (checks for connection lost every 5 seconds)
print("="*70)
print("STARTING CONNECTION MONITOR")
print("="*70)
start_connection_monitor()
print("="*70 + "\n")

# Start web server in background thread
print("="*70)
print("STARTING WEB GUI SERVER")
print("="*70)
web_thread = threading.Thread(
    target=start_web_server,
    args=(runtime.state_manager, "127.0.0.1", 8000),
    daemon=True
)
web_thread.start()
print("[MAIN] Web GUI available at http://localhost:8000")
print("="*70 + "\n")

# Start the GUI
runtime.root.mainloop()
