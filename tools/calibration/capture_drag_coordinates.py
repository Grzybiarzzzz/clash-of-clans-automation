"""
Capture mouse drag coordinates for troop deployment.

Usage:
1. Run this script
2. Press and hold LEFT MOUSE BUTTON
3. Drag along the path where you want troops deployed
4. Release mouse button
5. Coordinates will be saved to a file

Press ESC to exit
"""

import pyautogui
import time
from pynput import mouse, keyboard
import json
from datetime import datetime

coordinates = []
is_dragging = False
running = True

def on_click(x, y, button, pressed):
    """Track mouse drag"""
    global is_dragging, coordinates

    if button == mouse.Button.left:
        if pressed:
            # Start dragging
            is_dragging = True
            coordinates = []  # Clear previous coordinates
            print(f"\n[STARTED] Drag recording started at ({x}, {y})")
            coordinates.append((x, y))
        else:
            # Stop dragging
            if is_dragging:
                is_dragging = False
                coordinates.append((x, y))
                print(f"[STOPPED] Drag recording stopped at ({x}, {y})")
                print(f"[INFO] Captured {len(coordinates)} coordinates")

                # Save to file
                save_coordinates()

def on_move(x, y):
    """Record coordinates during drag"""
    global is_dragging, coordinates

    if is_dragging:
        # Record coordinate every ~20 pixels of movement
        if not coordinates or abs(x - coordinates[-1][0]) > 20 or abs(y - coordinates[-1][1]) > 20:
            coordinates.append((x, y))
            print(f"  ({x}, {y})", end='\r')

def on_key_press(key):
    """Handle ESC to exit"""
    global running

    try:
        if key == keyboard.Key.esc:
            print("\n\n[EXIT] ESC pressed - exiting...")
            running = False
            return False  # Stop listener
    except AttributeError:
        pass

def save_coordinates():
    """Save captured coordinates to file"""
    if len(coordinates) < 2:
        print("[WARNING] Not enough coordinates captured")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"drag_coords_{timestamp}.json"

    # Save as JSON
    data = {
        "coordinates": coordinates,
        "count": len(coordinates),
        "timestamp": timestamp,
        "instructions": "Add these coordinates to config.SIDE_DEPLOYMENT_COORDS['side_name']['units']"
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n[SAVED] Coordinates saved to: {filename}")
    print(f"\nCoordinates for config.py:")
    print(f"[")
    for coord in coordinates:
        print(f"    {coord},")
    print(f"]")
    print(f"\nTotal: {len(coordinates)} coordinates")

def main():
    print("="*70)
    print("DRAG COORDINATE CAPTURE TOOL")
    print("="*70)
    print("\nInstructions:")
    print("1. Position your Clash of Clans window")
    print("2. Click and HOLD LEFT MOUSE BUTTON where you want deployment to START")
    print("3. DRAG along the path where you want troops deployed")
    print("4. RELEASE mouse button where you want deployment to END")
    print("5. Coordinates will be automatically saved")
    print("\nPress ESC to exit at any time")
    print("="*70)
    print("\nWaiting for mouse drag...")

    # Start listeners
    mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)
    keyboard_listener = keyboard.Listener(on_press=on_key_press)

    mouse_listener.start()
    keyboard_listener.start()

    # Keep running
    try:
        while running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[EXIT] Interrupted by user")

    # Stop listeners
    mouse_listener.stop()
    keyboard_listener.stop()

    print("\n[INFO] Tool closed")

if __name__ == "__main__":
    main()
