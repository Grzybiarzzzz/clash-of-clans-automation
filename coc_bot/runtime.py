"""Shared session state.

The bot thread, the Tkinter GUI, the hotkey handlers and the web server all
read and write these values. They live in one module so that every other
module refers to the same objects: always access them as ``runtime.<name>``
(never ``from coc_bot.runtime import <name>``, which would copy the value).
"""

# Application objects, created once in coc_bot.app.main()
root = None           # tk.Tk root window
gui = None            # BotGUI instance
state_manager = None  # BotStateManager shared with the web server
queue_manager = None  # QueueManager, or None when unavailable

# Control flags
paused = True
running = True

# Session counters
loop_count = 0
skipped_bases = 0
attacked_bases = 0

# Timestamp of the next scheduled break
break_time = None
