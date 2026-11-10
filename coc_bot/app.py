"""Application startup: builds the GUI, wires the shared state and starts every service."""

import os
import threading
import tkinter as tk

import keyboard
import pyautogui
import pytesseract

import config
from coc_bot import runtime
from coc_bot.bot_state import BotStateManager
from coc_bot.connection import start_connection_monitor
from coc_bot.controls import exit_app, on_pause_from_web, stop_bot, toggle_pause
from coc_bot.gui.window import BotGUI
from coc_bot.loop import gui_run_bot
from coc_bot.overlay import clear_overlay_hotkey, save_overlay_screenshot_hotkey
from coc_bot.session import schedule_next_break
from coc_bot.storages import read_bb_base_storages, read_own_base_storages
from coc_bot.village import switch_village
from coc_bot.vision.buildings import load_achievement_building_templates
from coc_bot.vision.ocr import debug_save_ocr_regions
from coc_bot.vision.screens import load_bb_gold_templates
from web.server import start_web_server

def main():
    """Start the bot application. Blocks in the Tk main loop until the window closes."""
    # Ensure pytesseract knows its executable path
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    # The PyAutoGUI corner failsafe is deliberately disabled; F2 and ESC are the stop controls
    pyautogui.FAILSAFE = False
    print("PyAutoGUI corner failsafe is disabled; use F2 to stop or ESC to exit")

    # Create GUI
    runtime.root = tk.Tk()
    runtime.gui = BotGUI(runtime.root)

    # Initialize shared state manager for web GUI
    runtime.state_manager = BotStateManager()

    # Load existing state from JSON if it exists
    WEB_STATE_FILE = os.path.join("data", "web_state.json")
    if os.path.exists(WEB_STATE_FILE):
        try:
            runtime.state_manager.load_from_json(WEB_STATE_FILE)
            print("[MAIN] Loaded web state from JSON")
        except Exception as e:
            print(f"[MAIN] Failed to load web state: {e}")

    # Initialize default state values
    runtime.state_manager.update({
        "running": False,
        "paused": True,
        "status": "PAUSED",
        "current_profile": runtime.gui.current_profile,
        "loop_count": 0,
        "bases_attacked": 0,
        "bases_skipped": 0
    })

    # Connect GUI to state manager for web GUI integration
    runtime.gui.state_manager = runtime.state_manager
    runtime.gui._sync_state_to_manager()
    runtime.state_manager.subscribe(runtime.gui._on_state_change)

    runtime.gui.set_control_callback('pause', on_pause_from_web)
    print("[MAIN] GUI connected to state manager for web sync")

    # Initialize Queue Manager (callbacks are set further down)
    try:
        from coc_bot.queue_manager import QueueManager
        runtime.queue_manager = QueueManager(runtime.gui)
        print("[MAIN] Queue Manager initialized (callbacks pending)")

        # Start queue if enabled in settings
        settings = runtime.gui.get_settings()
        if settings.get('queue_enabled', False):
            runtime.queue_manager.start_queue()
    except ImportError:
        runtime.queue_manager = None
        print("[MAIN] Queue Manager not available")
    except Exception as e:
        runtime.queue_manager = None
        print(f"[MAIN] Failed to initialize Queue Manager: {e}")

    # Bind hotkeys
    keyboard.add_hotkey('f1', toggle_pause)
    keyboard.add_hotkey('f2', stop_bot)
    keyboard.add_hotkey('esc', exit_app)
    keyboard.add_hotkey('f6', debug_save_ocr_regions)

    keyboard.add_hotkey('f7', clear_overlay_hotkey)

    keyboard.add_hotkey('f8', save_overlay_screenshot_hotkey)

    runtime.break_time = schedule_next_break()

    # STORAGE READING FUNCTIONS (for Queue System)

    runtime.gui.run_bot = gui_run_bot

    # Set Queue Manager callbacks
    if runtime.queue_manager:
        runtime.queue_manager.set_callbacks(read_own_base_storages, read_bb_base_storages, switch_village)

    # Add window close handler to ensure cleanup
    runtime.root.protocol("WM_DELETE_WINDOW", exit_app)

    # Pre-load achievement building templates for faster detection (SBarb Farm optimization)
    print("\n" + "="*70)
    print("INITIALIZING TEMPLATE CACHE FOR SBARB FARM OPTIMIZATIONS")
    print("="*70)
    load_achievement_building_templates()
    print("="*70 + "\n")

    # Pre-load BB Gold templates for faster BB Gold attacks
    print("="*70)
    print("INITIALIZING BB GOLD TEMPLATE CACHE")
    print("="*70)
    load_bb_gold_templates()
    print("="*70 + "\n")

    # Start connection monitor (checks for connection lost every 5 seconds)
    print("="*70)
    print("STARTING CONNECTION MONITOR")
    print("="*70)
    start_connection_monitor()
    print("="*70 + "\n")

    # Start web server in background thread
    print("="*70)
    print("STARTING WEB GUI SERVER")
    print("="*70)
    web_thread = threading.Thread(
        target=start_web_server,
        args=(runtime.state_manager, "127.0.0.1", 8000),
        daemon=True
    )
    web_thread.start()
    print("[MAIN] Web GUI available at http://localhost:8000")
    print("="*70 + "\n")

    # Start the GUI
    runtime.root.mainloop()
