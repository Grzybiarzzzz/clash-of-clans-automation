"""Lets the connection monitor abort whatever the bot thread is doing.

The monitor runs on its own thread. When it sees the connection-lost popup it calls
``interrupt()``. The bot thread then raises ``ConnectionLost`` at its next checkpoint
(every screen capture and every helper click), which unwinds the attack routine instead
of letting it keep clicking on a screen that is about to reload. The main loop catches
the exception, waits for the reconnect and starts a fresh cycle.

This module imports nothing from the package so that capture and input can use it.
"""

import threading


class ConnectionLost(BaseException):
    """Raised in the bot thread. Not an ``Exception``, so the ``except Exception`` blocks
    inside detectors and click helpers cannot swallow it."""


_bot_thread = None
_interrupted = threading.Event()


def watch_current_thread():
    """Declare the calling thread to be the bot thread; only this thread is ever interrupted."""
    global _bot_thread
    _bot_thread = threading.get_ident()
    _interrupted.clear()


def interrupt():
    """Ask the bot thread to abandon its current routine. Stays pending until ``clear()``."""
    _interrupted.set()


def pending():
    return _interrupted.is_set()


def clear():
    _interrupted.clear()


def checkpoint():
    """Raise ``ConnectionLost`` when called on the bot thread while an interrupt is pending."""
    if _interrupted.is_set() and threading.get_ident() == _bot_thread:
        raise ConnectionLost()
