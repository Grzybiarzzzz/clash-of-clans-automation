"""Shared fixtures.

The bot targets Windows. These stubs let the package be imported on any
platform so that import errors and pure logic can be tested in CI.
"""
import ctypes
import sys
from unittest.mock import MagicMock

for _name in ("keyboard", "pyautogui"):
    sys.modules.setdefault(_name, MagicMock(name=_name))

if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock(name="windll")
