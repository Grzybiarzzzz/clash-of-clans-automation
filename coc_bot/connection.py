"""Recovery from the connection-lost screen and its background monitor."""

import threading
import time

from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.vision.screens import detect_connection_lost, detect_in_base_state
from humanized_input import fast_click

# Global flag to track if connection monitor is running
_connection_monitor_running = False
_connection_monitor_paused = False


def handle_connection_lost():
    """
    Handle connection lost by clicking "TRY AGAIN" and waiting for reconnection.
    After reconnect, detects current screen state.

    Returns:
        bool: True if reconnection successful, False otherwise
    """
    global _connection_monitor_paused

    try_again_pos = detect_connection_lost()
    if try_again_pos is None:
        return False

    # Pause the monitor while handling reconnection
    _connection_monitor_paused = True

    print("[CONNECTION] *** CONNECTION LOST - Attempting reconnect ***")
    runtime.gui.log_message("Connection lost! Clicking Try Again...")
    send_discord_debug_log("Connection lost detected - attempting reconnect", "WARNING")

    # Click "TRY AGAIN" button
    fast_click(try_again_pos[0], try_again_pos[1])
    time.sleep(2)  # Wait for reconnection attempt

    # Wait for reconnection (check if popup disappears and base loads)
    max_wait = 30  # seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Check if still showing connection lost
        if detect_connection_lost() is not None:
            # Still showing popup - click again
            print("[CONNECTION] Still disconnected, clicking Try Again...")
            fast_click(try_again_pos[0], try_again_pos[1])
            time.sleep(3)
            continue

        # Popup gone - wait a moment for screen to settle
        time.sleep(1)

        # Try to detect where we are
        if detect_in_base_state():
            print("[CONNECTION] ✓ Reconnected - at home base")
            runtime.gui.log_message("Reconnected successfully - at home base")
            send_discord_debug_log("Reconnected successfully - at home base", "INFO")
            _connection_monitor_paused = False
            return True

        # Could be in attack screen or elsewhere - just continue
        print("[CONNECTION] ✓ Reconnected - determining screen state...")
        runtime.gui.log_message("Reconnected - screen state unknown, continuing...")
        send_discord_debug_log("Reconnected - screen state unknown", "INFO")
        _connection_monitor_paused = False
        return True

    print("[CONNECTION] ✗ Failed to reconnect after 30 seconds")
    runtime.gui.log_message("Failed to reconnect after 30 seconds")
    send_discord_debug_log("Failed to reconnect after 30 seconds", "ERROR")
    _connection_monitor_paused = False
    return False


def connection_monitor_loop():
    """
    Background thread that checks for connection lost every 5 seconds.
    Runs continuously while the bot is active.
    """
    global _connection_monitor_running, _connection_monitor_paused

    print("[CONNECTION MONITOR] Started - checking every 5 seconds")

    while _connection_monitor_running:
        try:
            # Skip check if paused or handling reconnection
            if not _connection_monitor_paused:
                try_again_pos = detect_connection_lost()
                if try_again_pos is not None:
                    handle_connection_lost()

            # Wait 5 seconds before next check
            time.sleep(5)

        except Exception as e:
            print(f"[CONNECTION MONITOR] Error: {e}")
            time.sleep(5)

    print("[CONNECTION MONITOR] Stopped")


def start_connection_monitor():
    """Start the connection monitor background thread."""
    global _connection_monitor_running

    if _connection_monitor_running:
        print("[CONNECTION MONITOR] Already running")
        return

    _connection_monitor_running = True
    monitor_thread = threading.Thread(target=connection_monitor_loop, daemon=True)
    monitor_thread.start()
    print("[CONNECTION MONITOR] Thread started")


def stop_connection_monitor():
    """Stop the connection monitor background thread."""
    global _connection_monitor_running
    _connection_monitor_running = False
    print("[CONNECTION MONITOR] Stop requested")
