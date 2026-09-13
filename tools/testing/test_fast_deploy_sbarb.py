"""
Fast SBarb Deployment Test - Full simulation with zoom and camera drag

Tests the complete SBarb Farm deployment flow:
1. Zoom out
2. Camera drag to first side
3. Fast-click deploy 32 units along the edge
4. Camera drag to opposite side
5. Fast-click deploy remaining 32 units

Press F3 while in attack screen (after clicking Attack button) to start.
Press ESC to exit.

Usage:
1. Run this script
2. In CoC, find a base and click Attack button
3. Wait for attack screen to load
4. Press F3 to execute full deployment sequence
"""

import ctypes
from ctypes import wintypes
import keyboard
import time
import pyautogui
import random

# Disable pyautogui delays
pyautogui.PAUSE = 0

# Windows API constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0

# Windows API structures
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT),
    ]

# Load user32.dll
user32 = ctypes.windll.user32

def create_mouse_input(flags):
    """Create a mouse input event."""
    return INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(
            dx=0,
            dy=0,
            mouseData=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=None
        )
    )

def get_cursor_pos():
    """Get current cursor position."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

def move_cursor(x, y):
    """Move cursor to absolute position."""
    user32.SetCursorPos(int(x), int(y))

def fast_click():
    """Send a single fast click at current position."""
    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)
    user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

# ============================================================
# DEPLOYMENT COORDINATES (from config.py)
# ============================================================

# Corner/key points for each side (extracted from full coordinate lists)
# Format: list of (x, y) tuples defining the deployment path

SIDE_CORNERS = {
    'up': [
        (229, 903),    # Left edge start
        (1299, 121),   # Apex (middle-top)
        (2330, 894),   # Right edge end
    ],
    'down': [
        (273, 415),    # Left edge start
        (1281, 1143),  # Apex (middle-bottom)
        (2301, 424),   # Right edge end
    ],
}

# Camera drag coordinates for each side (extended drag distances)
DRAG_MAP = {
    'up': ((1280, 200), (1280, 1100)),    # Drag from very top to bottom
    'down': ((1280, 1200), (1280, 400)),  # Drag from very bottom to top
}

# Hero deployment position per side
HERO_POS = {
    'up': (1299, 121),
    'down': (1281, 1143),
}

# ============================================================
# CONFIGURATION
# ============================================================

CLICK_DELAY_MS = 60          # Delay between clicks (2x slower for reliability)
TOTAL_TROOPS = 64            # Total Super Barbarians
TROOPS_PER_SIDE = 32         # Half on each side
SBARB_HOTKEY = '3'           # Troop slot 1 hotkey (adjust if different)

# ============================================================
# DEPLOYMENT FUNCTIONS
# ============================================================

def zoom_out():
    """Zoom out to see full base."""
    print("[ZOOM] Moving to center and zooming out...")
    pyautogui.moveTo(1280, 700, duration=0)
    time.sleep(0.1)

    # 5 aggressive scroll-outs
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)

    time.sleep(0.1)  # Wait for zoom animation
    print("[ZOOM] Complete")

def camera_drag(side):
    """Drag camera to specified side."""
    drag_start, drag_end = DRAG_MAP[side]
    print(f"[CAMERA] Dragging to {side} side: {drag_start} -> {drag_end}")

    # Click neutral area first to deselect any troops/spells
    pyautogui.click(1280, 400)
    time.sleep(0.1)

    # Move to start position and wait for cursor to settle
    pyautogui.moveTo(*drag_start, duration=0.05)
    time.sleep(0.05)

    # Perform drag with longer duration for reliability
    pyautogui.mouseDown()
    time.sleep(0.05)  # Small delay after mouseDown
    pyautogui.moveTo(*drag_end, duration=0.15)
    time.sleep(0.05)  # Small delay before mouseUp
    pyautogui.mouseUp()

    time.sleep(0.2)  # Wait for camera to settle
    print(f"[CAMERA] Now viewing {side} side")

def interpolate_points(p1, p2, num_points):
    """Generate intermediate points between two coordinates."""
    points = []
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        points.append((x, y))
    return points

def fast_deploy_along_path(corners, num_clicks, delay_ms):
    """
    Deploy units by moving along path defined by corners while fast-clicking.

    Args:
        corners: List of (x, y) corner points defining the path
        num_clicks: Total number of clicks (units) to deploy
        delay_ms: Delay between clicks in milliseconds
    """
    # Calculate clicks per segment
    num_segments = len(corners) - 1
    clicks_per_segment = num_clicks // num_segments
    extra_clicks = num_clicks % num_segments  # Distribute remainder

    print(f"[DEPLOY] {num_clicks} clicks across {num_segments} segments ({clicks_per_segment} each)")

    total_deployed = 0
    start_time = time.perf_counter()

    for seg_idx in range(num_segments):
        start_corner = corners[seg_idx]
        end_corner = corners[seg_idx + 1]

        # Add extra click to early segments if needed
        segment_clicks = clicks_per_segment + (1 if seg_idx < extra_clicks else 0)

        # Generate points along this segment
        points = interpolate_points(start_corner, end_corner, segment_clicks)

        print(f"  Segment {seg_idx + 1}: {start_corner} -> {end_corner} ({segment_clicks} clicks)")

        for point in points:
            move_cursor(point[0], point[1])
            fast_click()
            total_deployed += 1
            time.sleep(delay_ms / 1000)

    elapsed = time.perf_counter() - start_time
    print(f"[DEPLOY] Deployed {total_deployed} units in {elapsed*1000:.0f}ms ({total_deployed/elapsed:.0f} CPS)")
    return total_deployed

def deploy_heroes(side):
    """Deploy all 4 heroes at the hero position for this side."""
    hero_pos = HERO_POS[side]
    print(f"[HEROES] Deploying at {hero_pos}")

    hero_keys = ['q', 'w', 'e', 'r']  # Queen, King, Warden, RC (slots 2-5)

    for key in hero_keys:
        keyboard.send(key)
        time.sleep(0.08)  # Wait for hotkey to register
        move_cursor(hero_pos[0], hero_pos[1])
        fast_click()
        time.sleep(0.05)  # Brief pause after click

    print("[HEROES] All heroes deployed")

def deploy_siege(side):
    """Deploy siege machine at hero position."""
    hero_pos = HERO_POS[side]
    print(f"[SIEGE] Deploying at {hero_pos}")

    keyboard.send('z')  # Siege hotkey
    time.sleep(0.08)  # Wait for hotkey to register
    move_cursor(hero_pos[0], hero_pos[1])
    fast_click()
    time.sleep(0.1)
    print("[SIEGE] Siege deployed")

# ============================================================
# MAIN TEST SEQUENCE
# ============================================================

running = True

def execute_full_deployment():
    """Execute the complete SBarb Farm deployment sequence."""
    print("\n" + "="*60)
    print("STARTING FULL SBARB DEPLOYMENT TEST")
    print("="*60)

    # Choose random starting side
    sides = ['up', 'down']
    first_side = random.choice(sides)
    opposite_side = 'down' if first_side == 'up' else 'up'

    print(f"First side: {first_side}, Opposite: {opposite_side}")

    # ===== PHASE 1: ZOOM OUT =====
    zoom_out()

    # ===== PHASE 2: CAMERA TO FIRST SIDE =====
    camera_drag(first_side)

    # ===== PHASE 3: DEPLOY FIRST HALF =====
    print(f"\n[PHASE 3] Deploying {TROOPS_PER_SIDE} troops on {first_side}...")
    keyboard.send(SBARB_HOTKEY)
    time.sleep(0.05)

    corners = SIDE_CORNERS[first_side]
    # Randomly reverse direction sometimes
    if random.random() < 0.5:
        corners = list(reversed(corners))
        print(f"  (Reversed direction)")

    deployed_first = fast_deploy_along_path(corners, TROOPS_PER_SIDE, CLICK_DELAY_MS)

    # ===== PHASE 4: DEPLOY HEROES + SIEGE =====
    print(f"\n[PHASE 4] Deploying heroes and siege on {first_side}...")
    deploy_heroes(first_side)
    deploy_siege(first_side)

    # ===== PHASE 5: CAMERA TO OPPOSITE SIDE =====
    print(f"\n[PHASE 5] Moving camera to {opposite_side}...")

    # Use the camera_drag function for consistency (already has extended distances)
    camera_drag(opposite_side)

    # ===== PHASE 6: DEPLOY SECOND HALF =====
    print(f"\n[PHASE 6] Deploying {TROOPS_PER_SIDE} troops on {opposite_side}...")
    keyboard.send(SBARB_HOTKEY)
    time.sleep(0.05)

    corners = SIDE_CORNERS[opposite_side]
    if random.random() < 0.5:
        corners = list(reversed(corners))
        print(f"  (Reversed direction)")

    deployed_second = fast_deploy_along_path(corners, TROOPS_PER_SIDE, CLICK_DELAY_MS)

    # ===== SUMMARY =====
    print("\n" + "="*60)
    print(f"DEPLOYMENT COMPLETE: {deployed_first + deployed_second} total units")
    print("="*60 + "\n")

def on_f3():
    """F3 pressed - execute full deployment."""
    execute_full_deployment()

def on_f7():
    """F7 - Quick test: deploy 16 units at current position (no zoom/camera)."""
    print("\n[F7] Quick deploy test - 16 units in place...")
    keyboard.send(SBARB_HOTKEY)
    time.sleep(0.05)

    start = time.perf_counter()
    for _ in range(16):
        fast_click()
        time.sleep(CLICK_DELAY_MS / 1000)
    elapsed = time.perf_counter() - start

    print(f"  16 clicks in {elapsed*1000:.0f}ms ({16/elapsed:.0f} CPS)")

def on_f8():
    """F8 - Test zoom and camera only (no deployment)."""
    print("\n[F8] Testing zoom and camera movement...")

    zoom_out()

    print("\nDragging to UP side...")
    camera_drag('up')
    time.sleep(1)

    print("\nDragging to DOWN side...")
    camera_drag('down')

    print("[F8] Camera test complete")

def on_esc():
    """ESC pressed - exit."""
    global running
    running = False
    print("\n[ESC] Exiting...")

def main():
    global running

    print("="*60)
    print("Fast SBarb Deployment Test")
    print("="*60)
    print(f"Troops: {TOTAL_TROOPS} ({TROOPS_PER_SIDE} per side)")
    print(f"Click delay: {CLICK_DELAY_MS}ms ({1000/CLICK_DELAY_MS:.0f} CPS)")
    print(f"Troop hotkey: {SBARB_HOTKEY}")
    print()
    print("Controls:")
    print("  F3  - FULL TEST (zoom + camera + deploy both sides)")
    print("  F7  - Quick test (16 clicks in place, no camera)")
    print("  F8  - Camera test (zoom + camera movement only)")
    print("  ESC - Exit")
    print()
    print("Instructions:")
    print("  1. Start a CoC attack (click Attack button)")
    print("  2. Wait for attack screen to load")
    print("  3. Press F3 to execute full deployment")
    print("="*60)

    # Register hotkeys
    keyboard.on_press_key('f3', lambda _: on_f3())
    keyboard.on_press_key('f7', lambda _: on_f7())
    keyboard.on_press_key('f8', lambda _: on_f8())
    keyboard.on_press_key('esc', lambda _: on_esc())

    try:
        while running:
            time.sleep(0.1)
    finally:
        keyboard.unhook_all()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
