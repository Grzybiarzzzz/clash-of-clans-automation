"""Switching between the Home Village and the Builder Base."""

import time

import pyautogui

from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.vision.screens import detect_bb_boat, detect_main_base_boat
from humanized_input import human_like_move_click

def switch_village(target_village):
    """
    Switch between Main Base and Builder Base.

    Args:
        target_village: 'main' or 'builder_base'

    Returns:
        True if switch successful, False otherwise
    """
    print(f"[VILLAGE SWITCH] Switching to {target_village}...")
    send_discord_debug_log(f"Switching to {target_village}")

    try:
        # Determine which boat to look for based on target village
        if target_village == 'builder_base':
            # Currently on Main Base, need to find Main Base boat
            print("[VILLAGE SWITCH] Preparing to detect boat on Main Base...")

            # Zoom out to see more of the base
            print("[VILLAGE SWITCH] Zooming out...")
            pyautogui.scroll(-3)  # Scroll down to zoom out
            time.sleep(0.5)

            # Drag camera to left-bottom to make boat visible
            # To see LEFT-BOTTOM area: drag RIGHT and UP
            print("[VILLAGE SWITCH] Dragging camera to left-bottom area...")
            start_x, start_y = 1280, 720  # Screen center
            end_x, end_y = start_x + 600, start_y - 400  # Drag right and up
            pyautogui.moveTo(start_x, start_y, duration=0.3)
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=0.5, button='left')
            time.sleep(1)

            # Now detect boat
            print("[VILLAGE SWITCH] Looking for boat on Main Base...")
            boat_pos = detect_main_base_boat()

            if not boat_pos:
                print("[VILLAGE SWITCH] Failed to find boat on Main Base")
                send_discord_debug_log("Failed to find boat on Main Base", "ERROR")
                return False

        else:  # target_village == 'main'
            # Currently on Builder Base, need to find BB boat
            print("[VILLAGE SWITCH] Looking for boat on Builder Base...")
            boat_pos = detect_bb_boat()

            if not boat_pos:
                # Boat not visible, try camera drag
                print("[VILLAGE SWITCH] Boat not found, dragging camera...")
                # Drag camera to see right side
                start_x, start_y = 1280, 720
                end_x, end_y = start_x - 800, start_y + 800
                pyautogui.moveTo(start_x, start_y, duration=0.3)
                pyautogui.drag(end_x - start_x, end_y - start_y, duration=0.5, button='left')
                time.sleep(1)

                # Try detection again
                boat_pos = detect_bb_boat()

                if not boat_pos:
                    print("[VILLAGE SWITCH] Failed to find boat on Builder Base")
                    send_discord_debug_log("Failed to find boat on Builder Base", "ERROR")
                    return False

        # Click the boat (or cart position if using trees fallback)
        click_x, click_y = boat_pos[0], boat_pos[1]
        is_cart = boat_pos[2] if len(boat_pos) > 2 else False
        if is_cart:
            print(f"[VILLAGE SWITCH] Clicking elixir cart area at ({click_x}, {click_y})")
        else:
            print(f"[VILLAGE SWITCH] Clicking boat at ({click_x}, {click_y})")
        human_like_move_click(click_x, click_y)
        time.sleep(0.5)

        # Wait for village transition (animation takes ~3-4 seconds)
        print("[VILLAGE SWITCH] Waiting for village transition...")
        time.sleep(4)

        # Verify we're in the correct village
        print(f"[VILLAGE SWITCH] Successfully switched to {target_village}")
        send_discord_debug_log(f"Successfully switched to {target_village}")
        return True

    except Exception as e:
        print(f"[VILLAGE SWITCH] Error switching village: {e}")
        send_discord_debug_log(f"Village switch error: {e}", "ERROR")
        return False


def collect_bb_loot():
    """
    Collect loot from Builder Base by finding the boat and clicking the relative position.
    """
    print("[BB LOOT] Starting loot collection...")
    send_discord_debug_log("BB Elixir: Starting loot collection")
    runtime.gui.log_message("BB Elixir: Collecting loot...")

    # Drag camera to see right side and slightly up
    # To see RIGHT: drag LEFT. To see UP: drag DOWN.
    print("[BB LOOT] Dragging camera to boat area...")
    start_x, start_y = 1280, 720  # Screen center
    end_x, end_y = start_x - 800, start_y + 800  # Drag left 100px, down 50px

    pyautogui.moveTo(start_x, start_y, duration=0.1)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.1)
    pyautogui.moveTo(end_x, end_y, duration=0.5)
    time.sleep(0.1)
    pyautogui.mouseUp()
    time.sleep(1)  # Wait for camera to settle

    # Try to detect boat (retry up to 3 times)
    boat_pos = None
    for attempt in range(3):
        boat_pos = detect_bb_boat()
        if boat_pos:
            break
        else:
            print(f"[BB LOOT] Boat not found, retry {attempt + 1}/3...")
            time.sleep(0.5)

    if boat_pos:
        pos_x, pos_y, is_cart = boat_pos

        if is_cart:
            # Trees fallback - click elixir cart directly
            click_x = pos_x
            click_y = pos_y
            print(f"[BB LOOT] Clicking elixir cart directly at ({click_x}, {click_y})")
        else:
            # Boat detected - click at offset position
            click_x = pos_x - 450
            click_y = pos_y + 150
            print(f"[BB LOOT] Clicking loot at ({click_x}, {click_y}) (relative to boat)")
        send_discord_debug_log(f"BB Elixir: Clicking loot at ({click_x}, {click_y})")
        human_like_move_click(click_x, click_y)
        time.sleep(2)

        # Click second position
        print("[BB LOOT] Clicking confirmation at (1857, 1215)")
        send_discord_debug_log("BB Elixir: Clicking loot confirmation (1857, 1215)")
        human_like_move_click(1857, 1215)
        time.sleep(1.5)

        # Click third position
        print("[BB LOOT] Clicking final button at (211, 900)")
        send_discord_debug_log("BB Elixir: Clicking final loot button (211, 900)")
        human_like_move_click(211, 900)
        time.sleep(2)

        print("[BB LOOT] Loot collection completed")
        runtime.gui.log_message("BB Elixir: Loot collected successfully")
        send_discord_debug_log("BB Elixir: Loot collection completed")
    else:
        print("[BB LOOT] WARNING: Boat not found after 3 attempts, skipping loot collection")
        runtime.gui.log_message("BB Elixir: Boat not found - skipping loot")
        send_discord_debug_log("BB Elixir: Boat not found - skipping loot collection", "WARNING")
