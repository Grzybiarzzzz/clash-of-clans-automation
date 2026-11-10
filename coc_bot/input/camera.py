"""Camera movement and small pointer helpers."""

import random
import time

import pyautogui

import config
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import get_opposite_side
from coc_bot.humanized_input import human_like_move_click

def click_in_square(coord):  # coord: (x1,y1,x2,y2)
    x1, y1, x2, y2 = coord
    rand_x = random.randint(x1, x2)
    rand_y = random.randint(y1, y2)
    human_like_move_click(rand_x, rand_y)


def move_camera_to_opposite_side(current_side, fast_mode=False):
    """Move camera to the opposite side of the base"""
    opposite_side = get_opposite_side(current_side)

    print(f"Moving camera from {current_side} to {opposite_side}")
    send_discord_debug_log(f"Moving camera from {current_side} to {opposite_side}")

    # Define camera drag directions
    # Drag from center outward in the direction we want to move
    center_x, center_y = 1280, 720  # Screen center (adjust if needed)
    drag_distance = 800  # pixels to drag - increased for more reliable camera movement

    if opposite_side == 'left':
        # Drag from center to right (moves camera left)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x + drag_distance, center_y
    elif opposite_side == 'right':
        # Drag from center to left (moves camera right)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x - drag_distance, center_y
    elif opposite_side == 'up':
        # Drag from center down (moves camera up)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x, center_y + drag_distance
    elif opposite_side == 'down':
        # Drag from center up (moves camera down)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x, center_y - drag_distance

    # Perform the drag
    pyautogui.moveTo(start_x, start_y)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.1)
    pyautogui.moveTo(end_x, end_y, duration=0.5)  # Slower drag for more reliable movement
    time.sleep(0.1)
    pyautogui.mouseUp()

    # Fast mode for SGoblin Farm - minimal delay
    if fast_mode:
        pass  # time.sleep(0.3)  # COMMENTED OUT - no delay for maximum speed
    else:
        time.sleep(0.5)  # Wait for camera to settle

    print(f"Camera moved to {opposite_side}")
    send_discord_debug_log(f"Camera moved to {opposite_side}")


def move_camera_to_side(chosen_side, fast_mode=False):
    """Move camera to the chosen attack side"""
    send_discord_debug_log(f"Moving camera to {chosen_side} side")
    drag_map = {
        'left': ((600, 700), (1500, 700)),    # Drag right to see left
        'right': ((2000, 700), (1000, 700)),  # Drag left to see right
        'up': ((1280, 300), (1280, 900)),     # Drag down to see up (top)
        'down': ((1280, 1100), (1280, 700)),  # Drag up to see down (bottom)
    }
    drag_start, drag_end = drag_map[chosen_side]
    pyautogui.moveTo(*drag_start, duration=config.DRAG_DURATION_START)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseDown()
    time.sleep(config.DRAG_DELAY)
    pyautogui.moveTo(*drag_end, duration=config.DRAG_DURATION_END)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseUp()
    # Fast mode for SGoblin Farm - minimal delay
    if fast_mode:
        time.sleep(0.3)
    else:
        time.sleep(config.DRAG_POST_DELAY)
