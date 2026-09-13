import pyautogui
import timer
from pynput import keyboard

def on_press(key):
    try:
        if key.char and key.char.lower() == 'r':
            x, y = pyautogui.position()
            print(f'X={x}, Y={y}')
    except AttributeError:
        pass

with keyboard.Listener(on_press=on_press) as listener:
    print("Naciśnij 'R', aby zobaczyć współrzędne. Ctrl+C kończy.")
    listener.join()

