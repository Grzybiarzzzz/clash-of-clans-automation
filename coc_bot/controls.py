"""Pause, stop and exit controls for hotkeys, the GUI and Discord commands."""

import json
import os
import time

import keyboard
import pyautogui

from coc_bot import runtime
from coc_bot.connection import stop_connection_monitor
from coc_bot.discord_log import send_discord_debug_log

# Discord control integration
last_settings_check = 0
settings_check_interval = 1.0  # Check every second


# Register pause callback to update main.py's global paused variable
def on_pause_from_web(new_paused_state):
    """Called when web GUI toggles pause - updates main.py global."""
    runtime.paused = new_paused_state
    print(f"[MAIN] Pause state updated from web GUI: {runtime.paused}")


def update_status():
    """Update GUI status from bot state (both main status and quick status indicator)"""
    if runtime.gui.bot_running:
        if runtime.gui.bot_paused:
            runtime.gui.status_label.config(text='PAUSED', foreground='orange')
            runtime.gui.quick_status_label.config(text='● Paused', foreground='orange')
        else:
            runtime.gui.status_label.config(text='RUNNING', foreground='green')
            runtime.gui.quick_status_label.config(text='● Running', foreground='green')
    else:
        runtime.gui.status_label.config(text='STOPPED', foreground='red')
        runtime.gui.quick_status_label.config(text='● Stopped', foreground='red')


def toggle_pause():
    runtime.paused = not runtime.paused
    runtime.gui.bot_paused = runtime.paused
    print(f"Paused set to {runtime.paused}")
    runtime.gui.log_message(f"Bot {'paused' if runtime.paused else 'resumed'}")
    runtime.root.after(0, update_status)


def stop_bot():
    """Stop the bot immediately without closing the GUI"""
    runtime.running = False
    runtime.paused = True

    # Release all held keys immediately
    try:
        pyautogui.keyUp('shift')
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('alt')
        # Release mouse buttons if held
        try:
            pyautogui.mouseUp()
        except Exception:
            pass
    except Exception as e:
        print(f"Error releasing keys: {e}")

    # Stop any ongoing PyAutoGUI operations
    pyautogui.PAUSE = 0

    print("Bot stopped immediately by user (F2)")
    send_discord_debug_log("Bot stopped immediately by user hotkey (F2)", "INFO")

    # Update GUI on main thread (handles button states and status labels)
    runtime.root.after(0, runtime.gui.stop_bot)


def exit_app():
    """Stop the bot and close the entire program"""
    runtime.running = False
    runtime.gui.bot_running = False
    runtime.gui.log_message("Bot stopped - closing program")

    # Stop connection monitor
    stop_connection_monitor()

    # Unhook all keyboard hotkeys to prevent clicks after exit
    try:
        keyboard.unhook_all()
        print("Keyboard hotkeys cleaned up")
    except Exception as e:
        print(f"Error unhooking keyboard: {e}")

    # Stop any PyAutoGUI operations
    pyautogui.PAUSE = 0  # Disable pause between actions for faster shutdown

    runtime.root.quit()


def check_discord_commands():
    """
    Check for Discord commands by monitoring bot_settings.json file.
    This allows the main bot to respond to Discord controller commands.
    """
    global last_settings_check
    current_time = time.time()
    if current_time - last_settings_check < settings_check_interval:
        return
    last_settings_check = current_time
    try:
        # Check if bot_settings.json exists and has been modified
        if not os.path.exists('bot_settings.json'):
            return
        # Load current settings from file
        with open('bot_settings.json', 'r', encoding='utf-8') as f:
            file_settings = json.load(f)
        # Check for Discord control flags
        discord_running = file_settings.get('discord_running', None)
        discord_paused = file_settings.get('discord_paused', None)
        # Only apply Discord commands if the flags actually exist in the file
        if discord_running is not None and discord_paused is not None:
            # Apply Discord commands
            if discord_running and not runtime.gui.bot_running:
                runtime.gui.bot_running = True
                runtime.gui.bot_paused = False
                runtime.paused = False
                runtime.running = True
                runtime.gui.log_message("Bot started via Discord command")
                print("Bot started via Discord command")
                runtime.root.after(0, update_status)
            elif not discord_running and runtime.gui.bot_running:
                runtime.gui.bot_running = False
                runtime.gui.bot_paused = True
                runtime.paused = True
                runtime.running = False
                runtime.gui.log_message("Bot stopped via Discord command")
                print("Bot stopped via Discord command")
                runtime.root.after(0, update_status)
            elif discord_running and runtime.gui.bot_running:
                if discord_paused and not runtime.gui.bot_paused:
                    runtime.gui.bot_paused = True
                    runtime.paused = True
                    runtime.gui.log_message("Bot paused via Discord command")
                    print("Bot paused via Discord command")
                    runtime.root.after(0, update_status)
                elif not discord_paused and runtime.gui.bot_paused:
                    runtime.gui.bot_paused = False
                    runtime.paused = False
                    runtime.gui.log_message("Bot resumed via Discord command")
                    print("Bot resumed via Discord command")
                    runtime.root.after(0, update_status)
    except Exception as e:
        print(f"Error checking Discord commands: {e}")
