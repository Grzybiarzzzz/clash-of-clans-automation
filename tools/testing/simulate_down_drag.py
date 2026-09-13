import pyautogui
import keyboard
import time

# These should match your bot's drag_map for 'down'
DRAG_START = (1280, 1100)  # Starting point for 'down' drag
DRAG_END = (1280, 700)     # Ending point for 'down' drag
DRAG_DURATION_START = 0.01
DRAG_DURATION_END = 0.02
DRAG_DELAY = 0.05

def simulate_down_drag():
    print("Simulating camera drag for 'down' (bottom) attack...")
    pyautogui.moveTo(*DRAG_START, duration=DRAG_DURATION_START)
    time.sleep(DRAG_DELAY)
    pyautogui.mouseDown()
    time.sleep(DRAG_DELAY)
    pyautogui.moveTo(*DRAG_END, duration=DRAG_DURATION_END)
    time.sleep(DRAG_DELAY)
    pyautogui.mouseUp()
    print("Camera drag complete.")

def test_zoom_out():
    print("Testing zoom out (mouse wheel down)...")
    # Move mouse to center of screen first
    pyautogui.moveTo(1280, 700, duration=0)
    time.sleep(0.1)
    # Scroll down to zoom out (negative value)
    pyautogui.scroll(-300)  # -10 = scroll down = zoom out
    print("Zoom out complete.")

print("="*60)
print("CAMERA DRAG & ZOOM TESTER")
print("="*60)
print("CONTROLS:")
print("  T   - Simulate 'down' camera drag")
print("  R   - Test zoom out (mouse wheel down)")
print("  ESC - Exit program")
print("="*60)

while True:
    if keyboard.is_pressed('t'):
        simulate_down_drag()
        time.sleep(0.5)  # Prevent multiple triggers
    if keyboard.is_pressed('r'):
        test_zoom_out()
        time.sleep(0.5)  # Prevent multiple triggers
    if keyboard.is_pressed('esc'):
        print("Exiting.")
        break
    time.sleep(0.05) 