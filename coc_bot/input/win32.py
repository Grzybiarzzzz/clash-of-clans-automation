"""Low-level mouse input through the Windows SendInput API."""

import ctypes
from ctypes import wintypes

# Windows API constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0


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


user32 = ctypes.windll.user32


def create_mouse_input(flags):
    """Create a mouse input event for Windows API."""
    return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None))


def turbo_fast_click():
    """Send a single ultra-fast click at current cursor position using Windows API."""
    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)
    user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))


def turbo_move_cursor(x, y):
    """Move cursor to absolute position using Windows API."""
    user32.SetCursorPos(int(x), int(y))
