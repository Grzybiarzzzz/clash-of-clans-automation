import os
import threading
import time
import tkinter as tk

import keyboard
import pyautogui
import pytesseract
from PIL import ImageGrab

import config
from bot_gui import BotGUI
from bot_state import BotStateManager
from coc_bot import runtime
from coc_bot.attacks.achievement_farm import perform_achievement_farm_attack
from coc_bot.attacks.bb_elixir import handle_bb_elixir_mode
from coc_bot.attacks.bb_gold import handle_bb_gold_mode
from coc_bot.attacks.derank import handle_derank_mode
from coc_bot.attacks.normal import perform_normal_attack
from coc_bot.attacks.sbarb_farm import handle_sbarb_farm_mode
from coc_bot.attacks.sgoblin_farm import perform_sgoblin_farm_attack
from coc_bot.connection import start_connection_monitor
from coc_bot.controls import (
    check_discord_commands,
    exit_app,
    on_pause_from_web,
    stop_bot,
    toggle_pause,
    update_status,
)
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.input.camera import click_in_square
from coc_bot.overlay import clear_overlay_hotkey, overlay_clear, save_overlay_screenshot_hotkey
from coc_bot.session import check_auto_pause, schedule_next_break
from coc_bot.storages import read_bb_base_storages, read_own_base_storages
from coc_bot.village import switch_village
from coc_bot.vision.buildings import load_achievement_building_templates
from coc_bot.vision.ocr import check_bb_attacker_text, debug_save_ocr_regions
from coc_bot.vision.screens import (
    detect_return_home_button,
    detect_star_bonus_screen,
    is_base_search_ready,
    load_bb_gold_templates,
    wait_for_base_screen,
)
from humanized_input import fast_click, human_like_move_click, humanized_sleep
from web.server import start_web_server

# Ensure pytesseract knows its executable path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

# Enable PyAutoGUI failsafe - move mouse to corner to emergency stop
pyautogui.FAILSAFE = False
print("PyAutoGUI corner failsafe is disabled; use F2 to stop or ESC to exit")


# ============================================================
# WINDOWS API FAST-CLICK (for Turbo Deployment mode)
# ============================================================


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


# ============================================================================
# BB GOLD STATE MACHINE - HELPER FUNCTIONS
# ============================================================================


# ============================================================================
# STORAGE READING FUNCTIONS (for Queue System)
# ============================================================================


# ============================================================================
# ATTACK MODE HANDLERS
# ============================================================================


    # No delay - detection loop in main_loop() handles waiting for next base


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
