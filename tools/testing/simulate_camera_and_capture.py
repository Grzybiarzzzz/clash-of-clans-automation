"""
Simulate bot's camera movement and capture deployment coordinates.

This tool:
1. Performs the EXACT camera drag the bot uses for each side
2. Lets you capture troop deployment coordinates from that view
3. Saves coordinates ready to paste into config.py

Usage:
1. Start in Clash of Clans attack screen (after clicking "Attack")
2. Run this script
3. Choose which side to simulate (left/up/right/down)
4. Camera will move exactly like the bot
5. Drag your mouse along deployment path
6. Coordinates are saved automatically

Press ESC to exit
"""

import pyautogui
import time
from pynput import mouse, keyboard as kb
import json
from datetime import datetime
import sys
import os

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

# Camera drag patterns (same as bot uses)
CAMERA_DRAG_MAP = {
    'left': ((600, 700), (1500, 700)),    # Drag right to see left
    'right': ((2000, 700), (1000, 700)),  # Drag left to see right
    'up': ((1280, 300), (1280, 900)),     # Drag down to see up (top)
    'down': ((1280, 1100), (1280, 700)),  # Drag up to see down (bottom)
}

# State
coordinates = []
is_dragging = False
running = True
current_side = None

def move_camera_to_side(side):
    """Perform exact camera drag that bot uses"""
    print(f"\n[CAMERA] Moving camera to {side} side...")

    drag_start, drag_end = CAMERA_DRAG_MAP[side]

    # Use exact same timing as bot
    pyautogui.moveTo(*drag_start, duration=config.DRAG_DURATION_START)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseDown()
    time.sleep(config.DRAG_DELAY)
    pyautogui.moveTo(*drag_end, duration=config.DRAG_DURATION_END)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseUp()
    time.sleep(config.DRAG_POST_DELAY)

    print(f"[CAMERA] Camera moved! View now shows {side} side")
    print(f"[INFO] Drag pattern: {drag_start} → {drag_end}")

def on_click(x, y, button, pressed):
    """Track mouse drag for coordinate capture"""
    global is_dragging, coordinates

    if button == mouse.Button.left:
        if pressed:
            is_dragging = True
            coordinates = []
            print(f"\n[CAPTURE] Recording started at ({x}, {y})")
            coordinates.append((x, y))
        else:
            if is_dragging:
                is_dragging = False
                coordinates.append((x, y))
                print(f"\n[CAPTURE] Recording stopped at ({x}, {y})")
                print(f"[INFO] Captured {len(coordinates)} coordinates")
                save_coordinates()

def on_move(x, y):
    """Record coordinates during drag"""
    global is_dragging, coordinates

    if is_dragging:
        # Record every ~20 pixels
        if not coordinates or abs(x - coordinates[-1][0]) > 20 or abs(y - coordinates[-1][1]) > 20:
            coordinates.append((x, y))
            print(f"  Position: ({x}, {y})", end='\r')

def on_key_press(key):
    """Handle keyboard input"""
    global running

    try:
        if key == kb.Key.esc:
            print("\n\n[EXIT] ESC pressed - exiting...")
            running = False
            return False
    except AttributeError:
        pass

def save_coordinates():
    """Save captured coordinates"""
    if len(coordinates) < 2:
        print("[WARNING] Not enough coordinates captured")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"coords_{current_side}_{timestamp}.json"

    data = {
        "side": current_side,
        "coordinates": coordinates,
        "count": len(coordinates),
        "camera_drag": {
            "start": CAMERA_DRAG_MAP[current_side][0],
            "end": CAMERA_DRAG_MAP[current_side][1]
        },
        "timestamp": timestamp
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n[SAVED] Coordinates saved to: {filename}")
    print(f"\n{'='*70}")
    print(f"COORDINATES FOR config.py - SIDE: {current_side.upper()}")
    print(f"{'='*70}")
    print(f"\nSIDE_DEPLOYMENT_COORDS = {{")
    print(f"    '{current_side}': {{")
    print(f"        'units': [")
    for coord in coordinates:
        print(f"            {coord},")
    print(f"        ],")
    print(f"        'hero': {coordinates[len(coordinates)//2]},  # Middle position")
    print(f"    }},")
    print(f"}}")
    print(f"\nTotal: {len(coordinates)} coordinates")
    print(f"{'='*70}\n")

def choose_side():
    """Let user choose which side to simulate"""
    print("\n" + "="*70)
    print("CHOOSE ATTACK SIDE TO SIMULATE")
    print("="*70)
    print("\n1. LEFT   - Attack from left side")
    print("2. UP     - Attack from top")
    print("3. RIGHT  - Attack from right side")
    print("4. DOWN   - Attack from bottom")
    print("\nEnter number (1-4): ", end='')

    choice = input().strip()

    side_map = {
        '1': 'left',
        '2': 'up',
        '3': 'right',
        '4': 'down'
    }

    return side_map.get(choice)

def main():
    global current_side, running

    print("="*70)
    print("BOT CAMERA SIMULATION & COORDINATE CAPTURE TOOL")
    print("="*70)
    print("\nThis tool simulates the EXACT camera movement the bot uses,")
    print("then lets you capture deployment coordinates from that view.")
    print("\nPrerequisites:")
    print("✓ Clash of Clans must be open")
    print("✓ Must be in ATTACK SCREEN (after clicking 'Attack' button)")
    print("✓ Bot should NOT be running")
    print("="*70)

    # Choose side
    current_side = choose_side()
    if not current_side:
        print("[ERROR] Invalid choice. Exiting.")
        return

    print(f"\n[SELECTED] {current_side.upper()} side")
    print("\n[INFO] Camera will move in 3 seconds...")
    print("[INFO] Position your Clash of Clans window now!")

    for i in range(3, 0, -1):
        print(f"  {i}...", end='\r')
        time.sleep(1)

    # Perform camera drag
    move_camera_to_side(current_side)

    print("\n" + "="*70)
    print("CAMERA POSITIONED - READY TO CAPTURE COORDINATES")
    print("="*70)
    print("\nInstructions:")
    print("1. CLICK and HOLD left mouse button where deployment should START")
    print("2. DRAG along the path where you want troops deployed")
    print("3. RELEASE mouse button where deployment should END")
    print("4. Coordinates will be saved automatically")
    print("\nPress ESC to exit")
    print("="*70)
    print("\nWaiting for mouse drag...")

    # Start listeners
    mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)
    keyboard_listener = kb.Listener(on_press=on_key_press)

    mouse_listener.start()
    keyboard_listener.start()

    # Keep running
    try:
        while running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[EXIT] Interrupted")

    # Stop listeners
    mouse_listener.stop()
    keyboard_listener.stop()

    print("\n[INFO] Tool closed")
    print("\nTo test another side, run the script again!")

if __name__ == "__main__":
    # Disable PyAutoGUI failsafe for this tool
    pyautogui.FAILSAFE = False
    main()
