"""
Fast Click Test Script - Windows API via SendInput

Tests ultra-fast unit deployment using direct Windows API calls.
Press F3 to deploy 16 clicks at current mouse position.
Press ESC to exit.

Usage:
1. Run this script
2. Start an attack in Clash of Clans
3. Hover mouse over deployment position
4. Press F3 to deploy 16 units instantly
"""

import ctypes
from ctypes import wintypes
import keyboard
import time

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

def fast_click_batch(num_clicks):
    """
    Send multiple clicks in a single SendInput call.
    This is the fastest possible method.
    """
    # Create array of INPUT events (2 per click: down + up)
    num_events = num_clicks * 2
    InputArray = INPUT * num_events
    inputs = InputArray()

    for i in range(num_clicks):
        inputs[i * 2] = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
        inputs[i * 2 + 1] = create_mouse_input(MOUSEEVENTF_LEFTUP)

    # Send all at once
    start = time.perf_counter()
    result = user32.SendInput(num_events, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    elapsed = time.perf_counter() - start

    return result, elapsed

def fast_click_sequential(num_clicks, delay_ms=0):
    """
    Send clicks one at a time with optional delay.
    Useful for testing if game has rate limiting.
    """
    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)

    start = time.perf_counter()
    for _ in range(num_clicks):
        user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
    elapsed = time.perf_counter() - start

    return num_clicks, elapsed

# State
running = True
NUM_CLICKS = 16
current_delay_ms = 30  # 30ms = ~33 CPS (tested reliable)

def on_f3():
    """F3 pressed - deploy clicks with current delay setting."""
    global current_delay_ms
    print(f"\n[F3] Deploying {NUM_CLICKS} clicks with {current_delay_ms}ms delay...")

    result, elapsed = fast_click_sequential(NUM_CLICKS, delay_ms=current_delay_ms)
    print(f"  {result} clicks in {elapsed*1000:.2f}ms")
    print(f"  Effective CPS: {NUM_CLICKS/elapsed:.0f} clicks/sec")
    print(f"  Target CPS: {1000/current_delay_ms:.0f}")

def on_f4():
    """F4 pressed - deploy with NO delay (batch, for comparison)."""
    print(f"\n[F4] Deploying {NUM_CLICKS} clicks BATCH (no delay)...")

    result, elapsed = fast_click_batch(NUM_CLICKS)
    print(f"  Batch: {result} events in {elapsed*1000:.2f}ms")
    print(f"  Effective CPS: {NUM_CLICKS/elapsed:.0f} clicks/sec")

def on_up():
    """UP arrow - increase delay (slower, safer)."""
    global current_delay_ms
    current_delay_ms = min(100, current_delay_ms + 5)
    print(f"\n[UP] Delay: {current_delay_ms}ms ({1000/current_delay_ms:.0f} CPS target)")

def on_down():
    """DOWN arrow - decrease delay (faster)."""
    global current_delay_ms
    current_delay_ms = max(5, current_delay_ms - 5)
    print(f"\n[DOWN] Delay: {current_delay_ms}ms ({1000/current_delay_ms:.0f} CPS target)")

def get_cursor_pos():
    """Get current cursor position."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

def move_cursor(x, y):
    """Move cursor to absolute position."""
    user32.SetCursorPos(x, y)

def on_f5():
    """F5 - Click-move-click pattern (burst at each position, then move)."""
    global current_delay_ms

    CLICKS_PER_POSITION = 4  # 4 clicks at each spot
    NUM_POSITIONS = 8        # 8 positions along the line
    LINE_LENGTH = 400        # pixels to travel

    start_x, start_y = get_cursor_pos()
    step_x = LINE_LENGTH // (NUM_POSITIONS - 1)

    print(f"\n[F5] Click-move-click: {CLICKS_PER_POSITION} clicks x {NUM_POSITIONS} positions")
    print(f"     Line: {LINE_LENGTH}px right from ({start_x}, {start_y})")

    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)

    start = time.perf_counter()
    total_clicks = 0

    for pos in range(NUM_POSITIONS):
        # Move to position
        current_x = start_x + (pos * step_x)
        move_cursor(current_x, start_y)

        # Burst clicks at this position
        for _ in range(CLICKS_PER_POSITION):
            user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
            user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
            total_clicks += 1
            time.sleep(current_delay_ms / 1000)

    elapsed = time.perf_counter() - start
    print(f"     {total_clicks} clicks in {elapsed*1000:.0f}ms")
    print(f"     Effective CPS: {total_clicks/elapsed:.0f}")

def on_f6():
    """F6 - Continuous clicking while dragging."""
    global current_delay_ms

    TOTAL_CLICKS = 32        # Total clicks during drag
    LINE_LENGTH = 400        # pixels to travel

    start_x, start_y = get_cursor_pos()
    step_x = LINE_LENGTH / (TOTAL_CLICKS - 1)

    print(f"\n[F6] Continuous drag-click: {TOTAL_CLICKS} clicks over {LINE_LENGTH}px")
    print(f"     Starting from ({start_x}, {start_y})")

    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)

    start = time.perf_counter()

    for i in range(TOTAL_CLICKS):
        # Move incrementally
        current_x = int(start_x + (i * step_x))
        move_cursor(current_x, start_y)

        # Click
        user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

        time.sleep(current_delay_ms / 1000)

    elapsed = time.perf_counter() - start
    print(f"     {TOTAL_CLICKS} clicks in {elapsed*1000:.0f}ms")
    print(f"     Effective CPS: {TOTAL_CLICKS/elapsed:.0f}")

def on_esc():
    """ESC pressed - exit."""
    global running
    running = False
    print("\n[ESC] Exiting...")

def main():
    global running

    print("=" * 50)
    print("Fast Click Test Script")
    print("=" * 50)
    print(f"Clicks per trigger: {NUM_CLICKS}")
    print(f"Starting delay: {current_delay_ms}ms ({1000/current_delay_ms:.0f} CPS)")
    print()
    print("Controls:")
    print("  F3   - Deploy 16 clicks in place (with current delay)")
    print("  F4   - Deploy 16 clicks in place (batch, no delay)")
    print("  F5   - Click-move-click: 4 clicks x 8 positions (32 total)")
    print("  F6   - Continuous drag-click: 32 clicks while moving")
    print("  UP   - Increase delay (+5ms, slower)")
    print("  DOWN - Decrease delay (-5ms, faster)")
    print("  ESC  - Exit")
    print()
    print("F3/F4: Position mouse, then press")
    print("F5/F6: Position at LEFT edge of deployment line")
    print("       (will move 400px to the right)")
    print("=" * 50)

    # Register hotkeys
    keyboard.on_press_key('f3', lambda _: on_f3())
    keyboard.on_press_key('f4', lambda _: on_f4())
    keyboard.on_press_key('f5', lambda _: on_f5())
    keyboard.on_press_key('f6', lambda _: on_f6())
    keyboard.on_press_key('up', lambda _: on_up())
    keyboard.on_press_key('down', lambda _: on_down())
    keyboard.on_press_key('esc', lambda _: on_esc())

    try:
        while running:
            time.sleep(0.1)
    finally:
        keyboard.unhook_all()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
