# bot_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
from datetime import datetime, timedelta
import csv
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
import pandas as pd

# Optional visualization overlay import
try:
    from visualization_overlay import VisualizationOverlay
    OVERLAY_AVAILABLE = True
except ImportError:
    OVERLAY_AVAILABLE = False
    print("Warning: visualization_overlay module not found. Overlay feature disabled.")

class BotGUI:
    def __init__(self, root, state_manager=None):
        self.root = root
        self.state_manager = state_manager
        self.root.title("Clash of Clans Bot Control Panel")

        # Load 2nd monitor setting early (before positioning window)
        prefer_second_monitor = False
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
                prefer_second_monitor = settings_data.get('use_second_monitor', False)
        except:
            pass

        # Set window size and position
        window_width = 900
        window_height = 800

        # Get primary monitor dimensions
        primary_width = root.winfo_screenwidth()
        primary_height = root.winfo_screenheight()

        # Update window to get accurate multi-monitor info
        root.update_idletasks()

        # Detect available monitors using Win32 API
        monitors = self._enumerate_monitors()

        second_monitor = None
        if prefer_second_monitor and len(monitors) > 1:
            # Find a non-primary monitor (one that doesn't start at 0,0)
            for mon in monitors:
                if mon['x'] != 0 or mon['y'] != 0:
                    second_monitor = mon
                    break

        if second_monitor:
            # Center window on the second monitor
            mon_x, mon_y = second_monitor['x'], second_monitor['y']
            mon_w, mon_h = second_monitor['width'], second_monitor['height']
            x = mon_x + (mon_w // 2) - (window_width // 2)
            y = mon_y + (mon_h // 2) - (window_height // 2)
            print(f"[GUI] Positioning on second monitor ({mon_w}x{mon_h} at {mon_x},{mon_y})")
        else:
            if prefer_second_monitor:
                print(f"[GUI] Second monitor preferred but not detected, using primary")
            # Center on primary monitor
            x = (primary_width // 2) - (window_width // 2)
            y = (primary_height // 2) - (window_height // 2)
            print(f"[GUI] Positioning on primary monitor")

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Make window resizable
        self.root.resizable(True, True)

        # Set minimum window size to prevent UI from breaking
        self.root.minsize(700, 600)

        # Fullscreen toggle with F11
        self.is_fullscreen = False
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)

        # Style will be applied after loading settings
        # Removed top-right dropdown - night mode controlled via Global settings checkbox
        
        # Bot state
        self.bot_running = False
        self.bot_paused = True
        self.start_time = None
        self.loop_count = 0
        self.current_status = "PAUSED"

        # External control callbacks (set by main.py for web GUI integration)
        self._control_callbacks = {
            'start': None,   # Called when web GUI requests start
            'stop': None,    # Called when web GUI requests stop
            'pause': None,   # Called when web GUI toggles pause (passes new paused state)
        }

        # Settings
        settings = self.load_settings()
        self.night_mode = settings.get('night_mode', False)
        self.overlay_enabled = settings.get('overlay_enabled', False)
        self.overlay_hide_low_conf = settings.get('overlay_hide_low_conf', False)
        self.overlay = None  # Will be initialized after GUI creation

        # Initialize manual mode schedule early (before GUI creation)
        self.manual_mode_schedule = settings.get('manual_mode_schedule', [])

        # Profile system - use the loaded current profile
        self.profile_var = tk.StringVar(value=self.current_profile)
        
        # Flag to prevent recursive saving
        self.is_saving = False

        # Collapsible sections state tracking
        self.section_states = {}

        # --- Initialize all settings variables used in the settings sections ---
        # Use the current profile's settings for initialization
        profile_settings = self.profiles.get(self.current_profile, self.get_hardcoded_profiles()['Farming'])
        self.min_resources_var = tk.StringVar(value=str(profile_settings.get('min_resources', 1200000)))
        self.max_th_var = tk.StringVar(value=str(profile_settings.get('max_th_level', 15)))

        # Initialize troop count variables (7 generic troop slots)
        troop_counts = profile_settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])
        self.troop_count_vars = [tk.StringVar(value=str(count)) for count in troop_counts]

        self.lightning_damage_var = tk.StringVar(value=str(profile_settings.get('lightning_damage', 300)))
        self.auto_pause_var = tk.BooleanVar(value=profile_settings.get('auto_pause_enabled', True))
        self.break_interval_var = tk.StringVar(value=str(profile_settings.get('break_interval', 45)))
        self.break_duration_var = tk.StringVar(value=str(profile_settings.get('break_duration', 5)))
        self.reinforcements_var = tk.BooleanVar(value=profile_settings.get('reinforcements_enabled', False))
        self.ad_target_mode_var = tk.StringVar(value=profile_settings.get('ad_target_mode', 'level'))
        self.attack_side_mode_var = tk.StringVar(value=profile_settings.get('attack_side_mode', 'random'))
        self.bb_collect_interval_var = tk.StringVar(value=str(settings.get('bb_collect_interval', profile_settings.get('bb_collect_interval', 12))))
        
        # Hero ability activation timing variables (seconds after deployment)
        self.queen_ability_timing_var = tk.StringVar(value=str(profile_settings.get('queen_ability_timing', 15)))
        self.king_ability_timing_var = tk.StringVar(value=str(profile_settings.get('king_ability_timing', 15)))
        self.warden_ability_timing_var = tk.StringVar(value=str(profile_settings.get('warden_ability_timing', 15)))
        self.rc_ability_timing_var = tk.StringVar(value=str(profile_settings.get('rc_ability_timing', 15)))

        # Create GUI
        self.create_widgets()

        # Update profile-specific visibility with stabilization
        self.update_profile_description()  # Ensure correct description on startup
        self.update_achievement_building_visibility()  # Show achievement farm settings if needed
        self.root.update_idletasks()  # Let GUI stabilize

        self.update_sgoblin_spell_casting_visibility()  # Show sgoblin spell casting checkbox if needed
        self.update_sbarb_deployment_visibility()  # Show sbarb heroes first checkbox if needed
        self.update_bb_gold_visibility()  # Show BB Gold bomber checkbox if needed
        self.update_priority_section_visibility()  # Show/hide priority section based on profile
        self.root.update_idletasks()  # Stabilize again

        # Initialize storage preset dropdown
        self.update_storage_preset_dropdown()
        # Load active preset and its values (use settings already loaded on line 90)
        try:
            active_preset = settings.get('active_storage_preset', 'main')
            self.storage_preset_var.set(active_preset)
            # Trigger preset loading to update spinbox values
            self.on_storage_preset_selected()
        except:
            pass

        # Initialize queue settings from loaded settings
        # Always start with queue disabled (user preference - prevent accidental auto-runs)
        try:
            self.queue_enabled_var.set(False)  # Force disabled on startup
            self.queue_mode_var.set(settings.get('queue_mode', 'smart'))

            # Initialize Smart Mode settings
            smart_config = settings.get('smart_mode_config', {})
            self.smart_main_mode_var.set(smart_config.get('main_base_mode', 'SBarb Farm'))
            storage_targets = smart_config.get('storage_targets', {})
            self.smart_gold_threshold_var.set(str(storage_targets.get('gold_threshold', 100)))
            self.smart_elixir_threshold_var.set(str(storage_targets.get('elixir_threshold', 100)))
            self.smart_de_threshold_var.set(str(storage_targets.get('de_threshold', 100)))
            self.smart_wait_de_var.set(storage_targets.get('wait_for_de', False))
            self.smart_bb_auto_var.set(smart_config.get('bb_auto_select_enabled', True))
            self.smart_bb_ratio_var.set(str(smart_config.get('bb_gold_elixir_ratio', 3.0)))
            self.smart_after_bb_var.set(smart_config.get('after_bb_behavior', 'stop'))

            # Initialize Achievement Farm end behavior settings
            achievement_end_config = settings.get('achievement_farm_end_config', {})
            self.achievement_end_enabled_var.set(achievement_end_config.get('enabled', False))
            self.achievement_end_duration_var.set(str(achievement_end_config.get('duration_minutes', 20)))

            # Initialize Manual Mode schedule
            self.manual_mode_schedule = settings.get('manual_mode_schedule', [])

            # Update visibility
            self.update_queue_mode_visibility()
        except Exception as e:
            print(f"[GUI] Failed to initialize queue settings: {e}")

        self.update_timer()
        
        # Capture console output
        self.capture_console_output()
        
        # Bind hotkeys
        self.root.bind('<F1>', lambda e: self.toggle_pause())
        self.root.bind('<Escape>', lambda e: self.stop_bot())
        
        # Apply night mode if enabled
        if self.night_mode:
            self.enable_night_mode()
        else:
            self.disable_night_mode()

        # Initialize visualization overlay (if available)
        if OVERLAY_AVAILABLE:
            try:
                self.overlay = VisualizationOverlay(self.root)
                if self.overlay_enabled:
                    self.overlay.show()
            except Exception as e:
                print(f"Warning: Failed to initialize overlay: {e}")
                self.overlay = None

        # Subscribe to state manager for web GUI sync
        if self.state_manager:
            self.state_manager.subscribe(self._on_state_change)
            # Initialize state manager with current GUI state
            self._sync_state_to_manager()

    @staticmethod
    def _enumerate_monitors():
        """Enumerate all monitors using Win32 API. Returns list of dicts with x, y, width, height."""
        import ctypes
        import ctypes.wintypes

        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            monitors.append({
                'x': rect.left,
                'y': rect.top,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top,
            })
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double,
        )
        try:
            ctypes.windll.user32.EnumDisplayMonitors(
                None, None, MONITORENUMPROC(callback), 0
            )
        except Exception as e:
            print(f"[GUI] Monitor enumeration failed: {e}")

        return monitors

    def set_control_callback(self, action, callback):
        """Register a callback for external control actions (e.g., from web GUI).

        Args:
            action: 'start', 'stop', or 'pause'
            callback: Function to call. For 'pause', receives new paused state as argument.
        """
        if action in self._control_callbacks:
            self._control_callbacks[action] = callback

    def _on_state_change(self, key, value):
        """Handle state changes from web GUI or other sources.

        This method is called when state changes externally (e.g., from web GUI).
        It updates the Tkinter GUI elements to reflect the new state.
        """
        # Use after() to ensure GUI updates happen on the main thread
        def update_gui():
            try:
                if key == "paused":
                    # Only update if state actually differs to prevent loops
                    if self.bot_paused != value:
                        self.bot_paused = value
                        if self.bot_running:
                            if value:
                                self.status_label.config(text="PAUSED", foreground="orange")
                                self.quick_status_label.config(text="● Paused", foreground="orange")
                            else:
                                self.status_label.config(text="RUNNING", foreground="green")
                                self.quick_status_label.config(text="● Running", foreground="green")

                            # Trigger external pause callback (for main.py global variable)
                            if self._control_callbacks.get('pause'):
                                try:
                                    self._control_callbacks['pause'](value)
                                except Exception as e:
                                    print(f"[GUI] Error in pause callback: {e}")

                elif key == "running":
                    if self.bot_running != value:
                        if value and not self.bot_running:
                            # Start requested externally - trigger start_bot
                            print("[GUI] Start requested from web GUI")
                            self.root.after(10, self.start_bot)
                        elif not value and self.bot_running:
                            # Stop requested externally - trigger stop_bot
                            print("[GUI] Stop requested from web GUI")
                            self.root.after(10, self.stop_bot)

                elif key == "current_profile":
                    if self.profile_var.get() != value:
                        self.profile_var.set(value)
                        # Apply the full profile settings (troop counts, resources, etc.)
                        self.apply_current_profile(silent=True)

                elif key == "loop_count":
                    if self.loop_count != value:
                        self.loop_count = value
                        self.loop_label.config(text=str(value))

                # Handle individual setting changes from web GUI
                elif key == "troop_counts":
                    if isinstance(value, list) and len(value) >= 7:
                        for i in range(7):
                            self.troop_count_vars[i].set(str(value[i]))
                        self.save_settings()

                elif key == "min_resources":
                    self.min_resources_var.set(int(value))
                    self.save_settings()

                elif key == "max_th_level":
                    self.max_th_var.set(int(value))
                    self.save_settings()

                elif key == "lightning_damage":
                    self.lightning_damage_var.set(int(value))
                    self.save_settings()

                elif key == "queen_ability_timing":
                    self.queen_ability_timing_var.set(int(value))
                    self.save_settings()

                elif key == "king_ability_timing":
                    self.king_ability_timing_var.set(int(value))
                    self.save_settings()

                elif key == "warden_ability_timing":
                    self.warden_ability_timing_var.set(int(value))
                    self.save_settings()

                elif key == "rc_ability_timing":
                    self.rc_ability_timing_var.set(int(value))
                    self.save_settings()

                elif key == "sgoblin_cast_spells":
                    self.sgoblin_cast_spells_var.set(bool(value))
                    self.save_settings()

                elif key == "sgoblin_use_wallbreakers":
                    self.sgoblin_use_wallbreakers_var.set(bool(value))
                    self.save_settings()

                elif key == "sgoblin_skip_logging":
                    self.sgoblin_skip_logging_var.set(bool(value))
                    self.save_settings()

                elif key == "sbarb_heroes_first":
                    self.sbarb_heroes_first_var.set(bool(value))
                    self.save_settings()

                elif key == "sbarb_queen_arrow_spells":
                    self.sbarb_queen_arrow_spells_var.set(bool(value))
                    self.save_settings()

                elif key == "sbarb_cast_spells":
                    self.sbarb_cast_spells_var.set(bool(value))
                    self.save_settings()

                elif key == "sbarb_turbo_deployment":
                    self.sbarb_turbo_deployment_var.set(bool(value))
                    self.save_settings()

                elif key == "bb_gold_troop_mode":
                    display_mode = self.bb_gold_troop_mode_reverse_map.get(value, 'Night Witches')
                    self.bb_gold_troop_mode_var.set(display_mode)
                    self.save_settings()

                elif key == "bb_gold_try_3_stars":
                    self.bb_gold_try_3_stars_var.set(bool(value))
                    self.save_settings()

                elif key == "bb_gold_dragon_debug_positions":
                    self.bb_gold_dragon_debug_var.set(bool(value))
                    self.save_settings()

                # Auto-pause settings
                elif key == "auto_pause_mode":
                    self.auto_pause_mode.set(str(value))
                    self.save_settings()

                elif key == "auto_pause_value":
                    self.auto_pause_value.set(str(value))
                    self.save_settings()

                elif key == "storage_full_gold":
                    self.storage_full_gold_var.set(bool(value))
                    self.save_settings()

                elif key == "storage_full_elixir":
                    self.storage_full_elixir_var.set(bool(value))
                    self.save_settings()

                elif key == "storage_full_de":
                    self.storage_full_de_var.set(bool(value))
                    self.save_settings()

                elif key == "storage_full_preset":
                    self.storage_full_preset_var.set(str(value))
                    self.save_settings()

                # Queue system settings
                elif key == "queue_enabled":
                    if self.queue_enabled_var.get() != value:
                        self.queue_enabled_var.set(bool(value))
                        # Start/stop queue manager
                        try:
                            import sys
                            main_module = sys.modules.get('__main__')
                            if main_module:
                                queue_manager = getattr(main_module, 'queue_manager', None)
                                if queue_manager:
                                    if value:
                                        queue_manager.start_queue()
                                        self.log_message("Queue System: STARTED (from web)")
                                    else:
                                        queue_manager.reset_queue()
                                        self.log_message("Queue System: STOPPED (from web)")
                        except Exception as e:
                            print(f"[GUI] Error toggling queue: {e}")
                        self.save_settings()
                        self.update_queue_mode_visibility()

                elif key == "queue_mode":
                    if self.queue_mode_var.get() != value:
                        self.queue_mode_var.set(str(value))
                        self.save_settings()
                        self.update_queue_mode_visibility()

                elif key == "smart_mode_config":
                    if isinstance(value, dict):
                        # Update smart mode settings
                        self.smart_main_mode_var.set(value.get('main_base_mode', 'SBarb Farm'))
                        storage_targets = value.get('storage_targets', {})
                        self.smart_wait_de_var.set(storage_targets.get('wait_for_de', False))
                        self.smart_after_bb_var.set(value.get('after_bb_behavior', 'stop'))
                        # Sync threshold values
                        if hasattr(self, 'smart_gold_threshold_var'):
                            self.smart_gold_threshold_var.set(str(storage_targets.get('gold_threshold', 100)))
                        if hasattr(self, 'smart_elixir_threshold_var'):
                            self.smart_elixir_threshold_var.set(str(storage_targets.get('elixir_threshold', 100)))
                        if hasattr(self, 'smart_de_threshold_var'):
                            self.smart_de_threshold_var.set(str(storage_targets.get('de_threshold', 100)))
                        self.save_settings()

                elif key == "achievement_farm_end_config":
                    if isinstance(value, dict):
                        self.achievement_end_duration_var.set(str(value.get('duration_minutes', 20)))
                        if hasattr(self, 'achievement_end_enabled_var'):
                            self.achievement_end_enabled_var.set(bool(value.get('enabled', False)))
                        self.save_settings()

                # Achievement building scan settings (sync from Web GUI)
                elif key == "achievement_scan_eagle_artillery":
                    self.achievement_eagle_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_monolith":
                    self.achievement_monolith_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_xbow":
                    self.achievement_xbow_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_inferno_tower":
                    self.achievement_inferno_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_scattershot":
                    self.achievement_scattershot_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_spell_tower":
                    self.achievement_spell_tower_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_multi_archer_tower":
                    self.achievement_multi_archer_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_ricochet_cannon":
                    self.achievement_ricochet_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_firespitter":
                    self.achievement_firespitter_var.set(bool(value))
                    self.save_settings()
                elif key == "achievement_scan_multi_gear_tower":
                    self.achievement_multi_gear_var.set(bool(value))
                    self.save_settings()

                # Achievement priority list (sync from Web GUI)
                elif key == "achievement_priority_list":
                    if isinstance(value, list):
                        self.achievement_priority_list = value
                        self.save_settings()

                # SBarb targeting mode (sync from Web GUI)
                elif key == "sbarb_cast_spells_target_mode":
                    if hasattr(self, 'sbarb_cast_spells_mode_var'):
                        # Convert to display name for dropdown
                        mode_display = {
                            'target': 'Target',
                            'clumps': 'Clumps',
                            'first_detected': 'First Detected'
                        }.get(value, 'Clumps')
                        self.sbarb_cast_spells_mode_var.set(mode_display)
                        self.save_settings()

                # Global settings (sync from Web GUI)
                elif key == "reinforcements_enabled":
                    self.reinforcements_var.set(bool(value))
                    self.save_settings()
                elif key == "skip_on_th_fail":
                    self.skip_on_th_fail_var.set(bool(value))
                    self.save_settings()
                elif key == "parallel_scanning":
                    self.parallel_scanning = bool(value)
                    self.achievement_parallel_scan_var.set(bool(value))
                    self.save_settings()
                elif key == "gpu_scanning":
                    self.gpu_scanning = bool(value)
                    self.save_settings()
                elif key == "overlay_enabled":
                    self.overlay_enabled = bool(value)
                    self.save_settings()
                elif key == "overlay_hide_low_conf":
                    self.overlay_hide_low_conf = bool(value)
                    self.save_settings()
                elif key == "auto_pause_enabled":
                    self.auto_pause_enabled_var.set(bool(value))
                    self.save_settings()
                elif key == "break_interval":
                    self.break_interval_var.set(int(value))
                    self.save_settings()
                elif key == "break_duration":
                    self.break_duration_var.set(int(value))
                    self.save_settings()
                elif key == "bb_collect_interval":
                    self.bb_collect_interval_var.set(int(value))
                    self.save_settings()

                # Storage max values (sync from Web GUI - used for percentage calculations)
                elif key == "max_gold_storage":
                    self.max_gold_storage_var.set(str(int(value)))
                    self.save_settings()
                elif key == "max_elixir_storage":
                    self.max_elixir_storage_var.set(str(int(value)))
                    self.save_settings()
                elif key == "max_dark_elixir_storage":
                    self.max_dark_elixir_storage_var.set(str(int(value)))
                    self.save_settings()
                elif key == "max_bb_gold_storage":
                    self.max_bb_gold_storage_var.set(str(int(value)))
                    self.save_settings()
                elif key == "max_bb_elixir_storage":
                    self.max_bb_elixir_storage_var.set(str(int(value)))
                    self.save_settings()
                elif key == "active_storage_preset":
                    # Update the preset dropdown and load preset values
                    self.storage_preset_var.set(str(value))
                    # Note: Don't call on_storage_preset_selected() here to avoid circular updates
                    # The preset values should already be updated via individual max_*_storage keys

            except Exception as e:
                print(f"[GUI] Error in _on_state_change: {e}")

        self.root.after(0, update_gui)

    def _sync_state_to_manager(self):
        """Sync current GUI state to state manager."""
        if not self.state_manager:
            return

        # Get current profile settings
        profile_settings = self.profiles.get(self.current_profile, {})

        self.state_manager.update({
            "running": self.bot_running,
            "paused": self.bot_paused,
            "current_profile": self.current_profile,
            "loop_count": self.loop_count,
            "status": self.current_status,
            # Include profile settings for web GUI
            "troop_counts": profile_settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0]),
            "min_resources": profile_settings.get('min_resources', 100000),
            "max_th_level": profile_settings.get('max_th_level', 17),
            "lightning_damage": profile_settings.get('lightning_damage', 600),
            "queen_ability_timing": profile_settings.get('queen_ability_timing', 15),
            "king_ability_timing": profile_settings.get('king_ability_timing', 15),
            "warden_ability_timing": profile_settings.get('warden_ability_timing', 15),
            "rc_ability_timing": profile_settings.get('rc_ability_timing', 15),
            "sgoblin_cast_spells": profile_settings.get('sgoblin_cast_spells', False),
            "sgoblin_use_wallbreakers": profile_settings.get('sgoblin_use_wallbreakers', False),
            "sbarb_heroes_first": profile_settings.get('sbarb_heroes_first', False),
            "sbarb_queen_arrow_spells": profile_settings.get('sbarb_queen_arrow_spells', False),
            "sbarb_cast_spells": profile_settings.get('sbarb_cast_spells', False),
            "sbarb_cast_spells_target_mode": profile_settings.get('sbarb_cast_spells_target_mode', 'clumps'),
            "sbarb_turbo_deployment": profile_settings.get('sbarb_turbo_deployment', False),
            "bb_gold_troop_mode": profile_settings.get('bb_gold_troop_mode', 'night_witches'),
            # Achievement building scan settings (uses full key names)
            "achievement_scan_eagle_artillery": profile_settings.get('achievement_scan_eagle_artillery', True),
            "achievement_scan_monolith": profile_settings.get('achievement_scan_monolith', True),
            "achievement_scan_xbow": profile_settings.get('achievement_scan_xbow', True),
            "achievement_scan_inferno_tower": profile_settings.get('achievement_scan_inferno_tower', True),
            "achievement_scan_scattershot": profile_settings.get('achievement_scan_scattershot', True),
            "achievement_scan_spell_tower": profile_settings.get('achievement_scan_spell_tower', True),
            "achievement_scan_multi_archer_tower": profile_settings.get('achievement_scan_multi_archer_tower', True),
            "achievement_scan_ricochet_cannon": profile_settings.get('achievement_scan_ricochet_cannon', True),
            "achievement_scan_firespitter": profile_settings.get('achievement_scan_firespitter', True),
            "achievement_scan_multi_gear_tower": profile_settings.get('achievement_scan_multi_gear_tower', True),
            "achievement_priority_list": profile_settings.get('achievement_priority_list', [
                'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
            ]),
            # Global settings
            "reinforcements_enabled": getattr(self, 'reinforcements_var', tk.BooleanVar()).get() if hasattr(self, 'reinforcements_var') else False,
            "skip_on_th_fail": getattr(self, 'skip_on_th_fail_var', tk.BooleanVar()).get() if hasattr(self, 'skip_on_th_fail_var') else True,
            "parallel_scanning": getattr(self, 'parallel_scanning', False),
            "gpu_scanning": getattr(self, 'gpu_scanning', False),
            "overlay_enabled": getattr(self, 'overlay_enabled', False),
            "overlay_hide_low_conf": getattr(self, 'overlay_hide_low_conf', False),
            "auto_pause_enabled": getattr(self, 'auto_pause_enabled_var', tk.BooleanVar()).get() if hasattr(self, 'auto_pause_enabled_var') else False,
            "break_interval": getattr(self, 'break_interval_var', tk.IntVar()).get() if hasattr(self, 'break_interval_var') else 60,
            "break_duration": getattr(self, 'break_duration_var', tk.IntVar()).get() if hasattr(self, 'break_duration_var') else 5,
            "bb_collect_interval": getattr(self, 'bb_collect_interval_var', tk.IntVar()).get() if hasattr(self, 'bb_collect_interval_var') else 12,
            # Auto-pause settings
            "auto_pause_mode": self.auto_pause_mode.get(),
            "auto_pause_value": self.auto_pause_value.get(),
            "storage_full_gold": self.storage_full_gold_var.get(),
            "storage_full_elixir": self.storage_full_elixir_var.get(),
            "storage_full_de": self.storage_full_de_var.get(),
            "storage_full_preset": self.storage_full_preset_var.get(),
            "storage_presets": self.get_storage_presets(),
        })

    def make_collapsible(self, label_frame, section_name, default_expanded=True):
        """
        Makes a LabelFrame collapsible by adding a toggle button to the header.

        Args:
            label_frame: The ttk.LabelFrame to make collapsible
            section_name: Unique identifier for this section (for state tracking)
            default_expanded: Whether the section should start expanded
        """
        # Initialize section state
        if section_name not in self.section_states:
            self.section_states[section_name] = default_expanded

        # Store original text and children
        original_text = label_frame.cget('text')

        # Get all children widgets for later hide/show
        children = []

        def collect_children():
            """Collect all child widgets recursively"""
            children.clear()
            for child in label_frame.winfo_children():
                children.append(child)

        def toggle_collapse():
            """Toggle the collapsed/expanded state"""
            is_expanded = self.section_states[section_name]

            if is_expanded:
                # Collapse: hide all children and shrink frame
                for child in children:
                    child.grid_remove()
                self.section_states[section_name] = False
                # Update arrow to point right
                label_frame.configure(text=f"▶ {original_text}")

                # Prevent frame from auto-sizing and set minimal height
                label_frame.grid_propagate(False)
                label_frame.configure(height=40)  # Just enough for header

                # Force parent layout to recompute
                parent = label_frame.master
                parent.update_idletasks()
            else:
                # Expand: show all children and let frame auto-size
                # Re-enable auto-sizing first
                label_frame.grid_propagate(True)
                label_frame.configure(height=1)  # Reset height (will be overridden by content)

                for child in children:
                    child.grid()
                self.section_states[section_name] = True
                # Update arrow to point down
                label_frame.configure(text=f"▼ {original_text}")

                # Force parent layout to recompute
                parent = label_frame.master
                parent.update_idletasks()

        # Set initial state
        collect_children()
        if default_expanded:
            label_frame.configure(text=f"▼ {original_text}")
            # Ensure auto-sizing is enabled for expanded state
            label_frame.grid_propagate(True)
        else:
            label_frame.configure(text=f"▶ {original_text}")
            # Hide children if starting collapsed
            for child in children:
                child.grid_remove()
            # Set minimal height and disable auto-sizing
            label_frame.grid_propagate(False)
            label_frame.configure(height=40)

        # Make the label frame itself clickable
        label_frame.bind('<Button-1>', lambda e: toggle_collapse())

        # Store the toggle function for external access if needed
        label_frame.toggle_collapse = toggle_collapse
        label_frame.collect_children = collect_children

        return label_frame

    def define_profiles(self):
        """Define the preset profiles for different gameplay modes"""
        return {
            'Farming': {
                'min_resources': 2000000,
                'max_th_level': 14,
                'troop_counts': [9, 2, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 580,
                'reinforcements_enabled': False,
                'ad_target_mode': 'proximity',
                'attack_side_mode': 'random',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Optimized for resource farming with high resource requirements and efficient attacks'
            },
            'Trophy Push': {
                'min_resources': 1,
                'max_th_level': 13,
                'troop_counts': [9, 2, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 30,
                'break_duration': 3,
                'lightning_damage': 580,
                'reinforcements_enabled': False,
                'ad_target_mode': 'proximity',
                'attack_side_mode': 'th_side',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Focused on trophy gain with lower resource requirements and strategic attacks'
            },
            'Derank': {
                'min_resources': 0,
                'max_th_level': 16,
                'troop_counts': [1, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 60,
                'break_duration': 2,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'derank_mode': True,
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Quick deranking by placing one unit and surrendering immediately'
            },
            'SGoblin Farm': {
                'min_resources': 800000,
                'max_th_level': 16,
                'troop_counts': [96, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'sgoblin_cast_spells': False,  # Cast spells on achievement buildings during attack
                'sgoblin_use_wallbreakers': False,  # Deploy Super Wall Breakers interspersed with goblins
                'sgoblin_skip_logging': False,  # Skip loot logging for faster attacks
                'queen_ability_timing': 1,
                'king_ability_timing': 1,
                'warden_ability_timing': 1,
                'rc_ability_timing': 1,
                'sgoblin_farm_mode': True,
                'description': 'Super Goblin farming - splits army on opposite sides and surrenders after deployment'
            },
            'SBarb Farm': {
                'min_resources': 0,
                'max_th_level': 16,
                'troop_counts': [64, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 30,
                'break_duration': 3,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'sbarb_heroes_first': False,  # Deploy heroes before army (vs army first)
                'sbarb_queen_arrow_spells': False,  # Cast 11 Earthquakes on Queen arrow path
                'sbarb_cast_spells': False,  # Cast spells on achievement buildings
                'sbarb_cast_spells_target_mode': 'clumps',  # Targeting mode: 'target', 'clumps', 'first_detected'
                'sbarb_turbo_deployment': False,  # Use Windows API fast-click deployment
                'queen_ability_timing': 1,
                'king_ability_timing': 1,
                'warden_ability_timing': 1,
                'rc_ability_timing': 1,
                'derank_mode': False,
                'sgoblin_farm_mode': False,
                'sbarb_farm_mode': True,
                'bb_elixir_mode': False,
                'bb_gold_mode': False,
                'achievement_farm_mode': False,
                'description': 'Super Barbarian farming - attacks first base, deploys on two sides with 2 Earthquake + 9 Lightning (or 11 Earthquakes on Queen arrow path), surrenders at 50% destruction (60s max)'
            },
            'BB Elixir': {
                'min_resources': 1,
                'max_th_level': 15,
                'troop_counts': [1, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': -1,
                'king_ability_timing': -1,
                'warden_ability_timing': -1,
                'rc_ability_timing': -1,
                'bb_elixir_mode': True,
                'bb_collect_interval': 12,
                'description': 'Builder Base elixir farming - detects red deployment lines, places one troop and surrenders'
            },
            'BB Gold': {
                'min_resources': 1,
                'max_th_level': 15,
                'troop_counts': [6, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': -1,
                'king_ability_timing': -1,
                'warden_ability_timing': -1,
                'rc_ability_timing': -1,
                'bb_gold_mode': True,
                'bb_collect_interval': 12,
                'bb_gold_troop_mode': 'night_witches',
                'description': 'Builder Base gold farming - deploys Battle Machine + troops, waits for 2 stars, then surrenders'
            },
            'Custom': {
                'min_resources': 1200000,
                'max_th_level': 15,
                'troop_counts': [7, 8, 0, 0, 0, 0, 0],
                'auto_pause_enabled': True,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Custom settings - modify as needed'
            }
        }
    
    def get_hardcoded_profiles(self):
        """Get hard-coded profile defaults (Trophy Push, Farming, Derank)"""
        return {
            'Farming': {
                'min_resources': 2000000,
                'max_th_level': 13,
                'troop_counts': [9, 2, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 580,
                'reinforcements_enabled': True,
                'ad_target_mode': 'level',
                'attack_side_mode': 'th_side',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Optimized for resource farming with high resource requirements and efficient attacks'
            },
            'Trophy Push': {
                'min_resources': 500000,
                'max_th_level': 15,
                'troop_counts': [8, 3, 0, 0, 0, 0, 0],
                'auto_pause_enabled': True,
                'break_interval': 30,
                'break_duration': 3,
                'lightning_damage': 600,
                'reinforcements_enabled': False,
                'ad_target_mode': 'proximity',
                'attack_side_mode': 'th_side',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Focused on trophy gain with lower resource requirements and strategic attacks'
            },
            'Derank': {
                'min_resources': 0,
                'max_th_level': 16,
                'troop_counts': [1, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 60,
                'break_duration': 2,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'derank_mode': True,
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15,
                'description': 'Quick deranking by placing one unit and surrendering immediately'
            },
            'SGoblin Farm': {
                'min_resources': 800000,
                'max_th_level': 16,
                'troop_counts': [96, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'sgoblin_cast_spells': False,  # Cast spells on achievement buildings during attack
                'sgoblin_use_wallbreakers': False,  # Deploy Super Wall Breakers interspersed with goblins
                'sgoblin_skip_logging': False,  # Skip loot logging for faster attacks
                'queen_ability_timing': 1,
                'king_ability_timing': 1,
                'warden_ability_timing': 1,
                'rc_ability_timing': 1,
                'sgoblin_farm_mode': True,
                'description': 'Super Goblin farming - splits army on opposite sides and surrenders after deployment'
            },
            'SBarb Farm': {
                'min_resources': 0,
                'max_th_level': 16,
                'troop_counts': [64, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 30,
                'break_duration': 3,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'sbarb_heroes_first': False,  # Deploy heroes before army (vs army first)
                'sbarb_queen_arrow_spells': False,  # Cast 11 Earthquakes on Queen arrow path
                'sbarb_cast_spells': False,  # Cast spells on achievement buildings
                'sbarb_cast_spells_target_mode': 'clumps',  # Targeting mode: 'target', 'clumps', 'first_detected'
                'sbarb_turbo_deployment': False,  # Use Windows API fast-click deployment
                'queen_ability_timing': 1,
                'king_ability_timing': 1,
                'warden_ability_timing': 1,
                'rc_ability_timing': 1,
                'derank_mode': False,
                'sgoblin_farm_mode': False,
                'sbarb_farm_mode': True,
                'bb_elixir_mode': False,
                'bb_gold_mode': False,
                'achievement_farm_mode': False,
                'description': 'Super Barbarian farming - attacks first base, deploys on two sides with 2 Earthquake + 9 Lightning (or 11 Earthquakes on Queen arrow path), surrenders at 50% destruction (60s max)'
            },
            'BB Elixir': {
                'min_resources': 1,
                'max_th_level': 15,
                'troop_counts': [1, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': -1,
                'king_ability_timing': -1,
                'warden_ability_timing': -1,
                'rc_ability_timing': -1,
                'bb_elixir_mode': True,
                'bb_collect_interval': 12,
                'description': 'Builder Base elixir farming - detects red deployment lines, places one troop and surrenders'
            },
            'BB Gold': {
                'min_resources': 1,
                'max_th_level': 15,
                'troop_counts': [6, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': -1,
                'king_ability_timing': -1,
                'warden_ability_timing': -1,
                'rc_ability_timing': -1,
                'bb_gold_mode': True,
                'bb_collect_interval': 12,
                'bb_gold_troop_mode': 'night_witches',
                'description': 'Builder Base gold farming - deploys Battle Machine + troops, waits for 2 stars, then surrenders'
            },
            'Achievement Farm': {
                'min_resources': 0,
                'max_th_level': 16,
                'troop_counts': [0, 0, 0, 0, 0, 0, 0],
                'auto_pause_enabled': False,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'reinforcements_enabled': False,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': -1,
                'king_ability_timing': -1,
                'warden_ability_timing': -1,
                'rc_ability_timing': -1,
                'achievement_farm_mode': True,
                'achievement_target_building': 'eagle_artillery',
                'achievement_farm_target_mode': 'clumps',  # Options: 'target', 'clumps', 'first_detected'
                'achievement_scan_eagle_artillery': True,
                'achievement_scan_monolith': True,
                'achievement_scan_xbow': True,
                'achievement_scan_inferno_tower': True,
                'achievement_scan_scattershot': True,
                'achievement_scan_spell_tower': True,
                'achievement_scan_multi_archer_tower': True,
                'achievement_scan_ricochet_cannon': True,
                'achievement_scan_firespitter': True,
                'achievement_scan_multi_gear_tower': True,
                'achievement_priority_list': ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot', 'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'],
                'achievement_parallel_scan': False,  # Sequential by default (low CPU, stable)
                'description': 'Achievement farming - searches for specific buildings and destroys with 1 Earthquake + 10 Lightning spells'
            }
        }
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky='nsew')
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        # Make the settings section row expandable
        main_frame.rowconfigure(2, weight=1)  # Settings section expands
        # Other rows (status, controls, loot, log) do not expand
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=0)
        main_frame.rowconfigure(3, weight=0)
        main_frame.rowconfigure(4, weight=0)
        main_frame.rowconfigure(5, weight=0)
        
        # Title with improved styling
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky='ew')
        title_frame.columnconfigure(0, weight=1)

        # Main title
        title_label = ttk.Label(title_frame, text="⚔️ Clash of Clans Bot", font=('Segoe UI', 20, 'bold'))
        title_label.grid(row=0, column=0)

        # Version and status indicator
        version_frame = ttk.Frame(title_frame)
        version_frame.grid(row=1, column=0, pady=(5, 0))
        version_label = ttk.Label(version_frame, text="v2.5", font=('Segoe UI', 9), foreground='gray')
        version_label.pack(side=tk.LEFT, padx=(0, 10))

        # Quick status indicator
        self.quick_status_label = ttk.Label(version_frame, text="● Paused", font=('Segoe UI', 9), foreground='red')
        self.quick_status_label.pack(side=tk.LEFT)
        
        # Status Section
        self.create_status_section(main_frame)
        
        # Settings Section
        self.create_settings_section(main_frame)
        
        # Control Section
        self.create_control_section(main_frame)

        # Loot Statistics Section
        self.create_loot_section(main_frame)

        # Log Section
        self.create_log_section(main_frame)

        # Make sections collapsible (must be done after all children are added)
        # Bot Status, Bot Controls, Army, and Attack collapsed by default to reduce clutter
        self.make_collapsible(self.status_frame, "bot_status", default_expanded=True)
        self.make_collapsible(self.profile_frame, "profile_selection", default_expanded=True)
        self.make_collapsible(self.army_frame, "army", default_expanded=False)
        self.make_collapsible(self.attack_frame, "attack", default_expanded=False)
        self.make_collapsible(self.global_frame, "global_settings", default_expanded=False)
        self.make_collapsible(self.queue_frame, "queue_system", default_expanded=False)
        self.make_collapsible(self.priority_frame, "achievement_priority", default_expanded=False)
        self.make_collapsible(self.control_frame, "bot_controls", default_expanded=True)
        self.make_collapsible(self.loot_frame, "loot_statistics", default_expanded=False)
        self.make_collapsible(self.log_frame, "logs", default_expanded=False)
        
    def create_status_section(self, parent):
        # Status Frame - improved 2-column layout with better spacing
        status_frame = ttk.LabelFrame(parent, text="📊 Bot Status", padding="15")
        status_frame.grid(row=1, column=0, columnspan=2, sticky='we', pady=(0, 15))

        # Store reference for making collapsible after children are added
        self.status_frame = status_frame

        # Configure columns for better distribution
        status_frame.columnconfigure(0, weight=0)
        status_frame.columnconfigure(1, weight=1)
        status_frame.columnconfigure(2, weight=0, pad=40)
        status_frame.columnconfigure(3, weight=1)

        # Left column - Status and Time
        ttk.Label(status_frame, text="Status:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, text="PAUSED", foreground="red", font=('Segoe UI', 11, 'bold'))
        self.status_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Running Time:", font=('Segoe UI', 10)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.time_label = ttk.Label(status_frame, text="00:00:00", font=('Segoe UI', 10))
        self.time_label.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        # BB Gold State display (only shown during BB Gold attacks)
        ttk.Label(status_frame, text="BB State:", font=('Segoe UI', 10)).grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.bb_state_label = ttk.Label(status_frame, text="N/A", foreground="gray", font=('Segoe UI', 10))
        self.bb_state_label.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        # Right column - Loops and Rate
        ttk.Label(status_frame, text="Loops Completed:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.loop_label = ttk.Label(status_frame, text="0", font=('Segoe UI', 11, 'bold'))
        self.loop_label.grid(row=0, column=3, sticky=tk.W)

        ttk.Label(status_frame, text="Loops/Hour:", font=('Segoe UI', 10)).grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.rate_label = ttk.Label(status_frame, text="0", font=('Segoe UI', 10))
        self.rate_label.grid(row=1, column=3, sticky=tk.W, pady=(8, 0))
        
    def create_settings_section(self, parent):
        # Create a frame for 2-column layout (better for vertical monitors)
        settings_outer_frame = ttk.Frame(parent)
        settings_outer_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(0, 10))
        parent.grid_rowconfigure(2, weight=0)  # Allow settings to shrink when collapsed
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # Configure 2-column grid with better spacing
        settings_outer_frame.columnconfigure(0, weight=1, minsize=400)
        settings_outer_frame.columnconfigure(1, weight=1, minsize=400)
        settings_outer_frame.rowconfigure(0, weight=0)
        settings_outer_frame.rowconfigure(1, weight=0)  # Changed from weight=1 to allow collapsible sections to shrink
        settings_outer_frame.rowconfigure(2, weight=0)

        # Profile Selection Frame (spans 2 columns for more visibility)
        profile_frame = ttk.LabelFrame(settings_outer_frame, text="🎯 Profile Selection", padding="12")
        profile_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.profile_frame = profile_frame  # Store for collapsible
        self.create_profile_section(profile_frame)

        # Army Frame
        army_frame = ttk.LabelFrame(settings_outer_frame, text="🪖 Army", padding="12")
        army_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        self.army_frame = army_frame  # Store for collapsible
        self.create_army_section(army_frame)

        # Attack Frame
        attack_frame = ttk.LabelFrame(settings_outer_frame, text="⚡ Attack", padding="12")
        attack_frame.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        self.attack_frame = attack_frame  # Store for collapsible
        self.create_attack_section(attack_frame)

        # Global Frame (now includes all former Functionality settings)
        global_frame = ttk.LabelFrame(settings_outer_frame, text="⚙️ Global Settings", padding="12")
        global_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.global_frame = global_frame  # Store for collapsible
        self.create_global_section(global_frame)

        # Queue System Frame
        queue_frame = ttk.LabelFrame(settings_outer_frame, text="🔄 Queue System", padding="12")
        queue_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.queue_frame = queue_frame  # Store for collapsible
        self.create_queue_section(queue_frame)

        # Achievement Priority Frame (conditionally visible for Achievement Farm and SBarb Farm)
        priority_frame = ttk.LabelFrame(settings_outer_frame, text="🎯 Achievement Building Priority", padding="12")
        priority_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.priority_frame = priority_frame  # Store for collapsible
        self.create_achievement_priority_section(priority_frame)

    # The following methods should be defined to create the widgets for each section
    def create_profile_section(self, frame):
        # Profile Frame - improved layout
        frame.columnconfigure(1, weight=1)

        # Profile selector with apply button in same row
        ttk.Label(frame, text="Profile:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 15))
        profile_dropdown = ttk.Combobox(frame, textvariable=self.profile_var,
                                       values=list(self.profiles.keys()), state='readonly', width=20, font=('Segoe UI', 10))
        profile_dropdown.grid(row=0, column=1, sticky=tk.EW, padx=(0, 15))
        profile_dropdown.bind('<<ComboboxSelected>>', self.on_profile_changed)

        apply_button = ttk.Button(frame, text="Apply Profile", command=self.apply_current_profile)
        apply_button.grid(row=0, column=2, sticky=tk.E)

        # Profile description - wraps better now with better styling
        self.profile_desc_label = ttk.Label(frame, text="", wraplength=700, justify=tk.LEFT, foreground='gray', font=('Segoe UI', 9))
        self.profile_desc_label.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(12, 5))

        # Achievement Farm target building dropdown (conditionally visible)
        self.achievement_building_label = ttk.Label(frame, text="Target Building:")
        # Map display names to internal names
        self.achievement_building_map = {
            'Eagle Artillery': 'eagle_artillery',
            'Monolith': 'monolith',
            'X-Bow': 'xbow',
            'Inferno Tower': 'inferno_tower',
            'Scattershot': 'scattershot',
            'Spell Tower': 'spell_tower',
            'Multi-Archer Tower': 'multi_archer_tower',
            'Ricochet Cannon': 'ricochet_cannon',
            'Firespitter': 'firespitter',
            'Multi-Gear Tower': 'multi_gear_tower'
        }
        # Initialize from current profile settings
        profile_settings_target = self.profiles.get(self.current_profile, {})
        saved_target = profile_settings_target.get('achievement_target_building', 'eagle_artillery')
        display_target = next((k for k, v in self.achievement_building_map.items() if v == saved_target), 'Eagle Artillery')
        self.achievement_building_var = tk.StringVar(value=display_target)
        self.achievement_building_dropdown = ttk.Combobox(
            frame,
            textvariable=self.achievement_building_var,
            values=['Eagle Artillery', 'Monolith', 'X-Bow', 'Inferno Tower', 'Scattershot', 'Spell Tower', 'Multi-Archer Tower', 'Ricochet Cannon', 'Firespitter', 'Multi-Gear Tower'],
            state='readonly',
            width=15
        )
        self.achievement_building_reverse_map = {v: k for k, v in self.achievement_building_map.items()}

        # Achievement Farm targeting mode dropdown (conditionally visible)
        self.achievement_mode_label = ttk.Label(frame, text="Targeting Mode:")
        # Map display names to internal names
        self.achievement_mode_map = {
            'Target': 'target',
            'Clumps': 'clumps',
            'First Detected': 'first_detected'
        }
        self.achievement_mode_reverse_map = {v: k for k, v in self.achievement_mode_map.items()}
        # Initialize from current profile settings
        saved_mode = profile_settings_target.get('achievement_farm_target_mode', 'clumps')
        display_mode = next((k for k, v in self.achievement_mode_map.items() if v == saved_mode), 'Clumps')
        self.achievement_mode_var = tk.StringVar(value=display_mode)
        self.achievement_mode_dropdown = ttk.Combobox(
            frame,
            textvariable=self.achievement_mode_var,
            values=['Target', 'Clumps', 'First Detected'],
            state='readonly',
            width=15
        )

        # Achievement Farm building checkboxes (conditionally visible)
        # Initialize from current profile settings
        profile_settings_achievement = self.profiles.get(self.current_profile, {})
        self.achievement_buildings_label = ttk.Label(frame, text="Buildings to Scan:", font=('Arial', 9, 'bold'))
        self.achievement_eagle_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_eagle_artillery', True))
        self.achievement_monolith_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_monolith', True))
        self.achievement_xbow_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_xbow', True))
        self.achievement_inferno_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_inferno_tower', True))
        self.achievement_scattershot_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_scattershot', True))
        self.achievement_spell_tower_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_spell_tower', True))
        self.achievement_multi_archer_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_multi_archer_tower', True))
        self.achievement_ricochet_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_ricochet_cannon', True))
        self.achievement_firespitter_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_firespitter', True))
        self.achievement_multi_gear_var = tk.BooleanVar(value=profile_settings_achievement.get('achievement_scan_multi_gear_tower', True))

        # Parallel vs Sequential scanning option (global setting)
        self.achievement_parallel_scan_var = tk.BooleanVar(value=getattr(self, 'parallel_scanning', False))

        self.achievement_eagle_check = ttk.Checkbutton(frame, text="Eagle Artillery", variable=self.achievement_eagle_var, command=lambda: self._on_achievement_building_toggled('eagle_artillery'))
        self.achievement_monolith_check = ttk.Checkbutton(frame, text="Monolith", variable=self.achievement_monolith_var, command=lambda: self._on_achievement_building_toggled('monolith'))
        self.achievement_xbow_check = ttk.Checkbutton(frame, text="X-Bow", variable=self.achievement_xbow_var, command=lambda: self._on_achievement_building_toggled('xbow'))
        self.achievement_inferno_check = ttk.Checkbutton(frame, text="Inferno Tower", variable=self.achievement_inferno_var, command=lambda: self._on_achievement_building_toggled('inferno_tower'))
        self.achievement_scattershot_check = ttk.Checkbutton(frame, text="Scattershot", variable=self.achievement_scattershot_var, command=lambda: self._on_achievement_building_toggled('scattershot'))
        self.achievement_spell_tower_check = ttk.Checkbutton(frame, text="Spell Tower", variable=self.achievement_spell_tower_var, command=lambda: self._on_achievement_building_toggled('spell_tower'))
        self.achievement_multi_archer_check = ttk.Checkbutton(frame, text="Multi-Archer Tower", variable=self.achievement_multi_archer_var, command=lambda: self._on_achievement_building_toggled('multi_archer_tower'))
        self.achievement_ricochet_check = ttk.Checkbutton(frame, text="Ricochet Cannon", variable=self.achievement_ricochet_var, command=lambda: self._on_achievement_building_toggled('ricochet_cannon'))
        self.achievement_firespitter_check = ttk.Checkbutton(frame, text="Firespitter", variable=self.achievement_firespitter_var, command=lambda: self._on_achievement_building_toggled('firespitter'))
        self.achievement_multi_gear_check = ttk.Checkbutton(frame, text="Multi-Gear Tower", variable=self.achievement_multi_gear_var, command=lambda: self._on_achievement_building_toggled('multi_gear_tower'))

        # Parallel scanning checkbox with warning (for Achievement Farm)
        self.achievement_parallel_scan_frame = ttk.Frame(frame)
        self.achievement_parallel_scan_check = ttk.Checkbutton(
            self.achievement_parallel_scan_frame,
            text="⚡ Enable parallel scanning (3-5x faster)",
            variable=self.achievement_parallel_scan_var,
            command=self.on_parallel_scan_toggle
        )
        self.achievement_parallel_scan_check.pack(side='left', padx=(0, 5))

        self.achievement_parallel_warning = ttk.Label(
            self.achievement_parallel_scan_frame,
            text="⚠ WARNING: May cause CPU spikes (28-32%) and game crashes",
            foreground='orange',
            font=('Segoe UI', 8)
        )
        self.achievement_parallel_warning.pack(side='left')

        # SGoblin Farm spell casting checkbox (conditionally visible)
        # Initialize from current profile settings
        profile_settings = self.profiles.get(self.current_profile, {})
        self.sgoblin_cast_spells_var = tk.BooleanVar(value=profile_settings.get('sgoblin_cast_spells', False))
        self.sgoblin_cast_spells_check = ttk.Checkbutton(
            frame,
            text="Cast spells on achievement buildings (1 Earthquake + 10 Lightning)",
            variable=self.sgoblin_cast_spells_var
        )

        # SGoblin Farm wall breaker checkbox (conditionally visible)
        self.sgoblin_use_wallbreakers_var = tk.BooleanVar(value=profile_settings.get('sgoblin_use_wallbreakers', False))
        self.sgoblin_use_wallbreakers_check = ttk.Checkbutton(
            frame,
            text="Deploy Super Wall Breakers (4 total, interspersed with goblins)",
            variable=self.sgoblin_use_wallbreakers_var
        )

        # SGoblin Farm skip logging checkbox (conditionally visible)
        self.sgoblin_skip_logging_var = tk.BooleanVar(value=profile_settings.get('sgoblin_skip_logging', False))
        self.sgoblin_skip_logging_check = ttk.Checkbutton(
            frame,
            text="Skip loot logging (faster attacks - no CSV tracking)",
            variable=self.sgoblin_skip_logging_var,
            command=self._on_sgoblin_skip_logging_changed
        )

        # SBarb Farm deployment order checkbox (conditionally visible)
        self.sbarb_heroes_first_var = tk.BooleanVar(value=profile_settings.get('sbarb_heroes_first', False))
        self.sbarb_heroes_first_check = ttk.Checkbutton(
            frame,
            text="Deploy heroes first (vs army first - current behavior)",
            variable=self.sbarb_heroes_first_var
        )

        # SBarb Farm Queen arrow targeting checkbox (conditionally visible)
        self.sbarb_queen_arrow_spells_var = tk.BooleanVar(value=profile_settings.get('sbarb_queen_arrow_spells', False))
        self.sbarb_queen_arrow_spells_check = ttk.Checkbutton(
            frame,
            text="Cast spells on Queen arrow path (11 Earthquakes on damaged buildings)",
            variable=self.sbarb_queen_arrow_spells_var
        )

        # SBarb Farm achievement building spell casting checkbox (conditionally visible)
        self.sbarb_cast_spells_var = tk.BooleanVar(value=profile_settings.get('sbarb_cast_spells', False))
        self.sbarb_cast_spells_check = ttk.Checkbutton(
            frame,
            text="Cast spells on achievement buildings (1 Earthquake + 10 Lightning)",
            variable=self.sbarb_cast_spells_var,
            command=self.on_sbarb_cast_spells_toggled
        )

        # SBarb Farm cast spells targeting mode dropdown (conditionally visible when cast spells is enabled)
        self.sbarb_cast_spells_mode_frame = ttk.Frame(frame)
        self.sbarb_cast_spells_mode_label = ttk.Label(self.sbarb_cast_spells_mode_frame, text="Targeting Mode:")
        self.sbarb_cast_spells_mode_label.pack(side='left', padx=(20, 5))

        # Map display names to internal names (reuse same mapping as Achievement Farm)
        self.sbarb_cast_spells_mode_map = {
            'Target': 'target',
            'Clumps': 'clumps',
            'First Detected': 'first_detected'
        }
        self.sbarb_cast_spells_mode_reverse_map = {v: k for k, v in self.sbarb_cast_spells_mode_map.items()}

        # Initialize from current profile settings
        saved_mode = profile_settings.get('sbarb_cast_spells_target_mode', 'clumps')
        display_mode = self.sbarb_cast_spells_mode_reverse_map.get(saved_mode, 'Clumps')
        self.sbarb_cast_spells_mode_var = tk.StringVar(value=display_mode)
        self.sbarb_cast_spells_mode_dropdown = ttk.Combobox(
            self.sbarb_cast_spells_mode_frame,
            textvariable=self.sbarb_cast_spells_mode_var,
            values=['Target', 'Clumps', 'First Detected'],
            state='readonly',
            width=15
        )
        self.sbarb_cast_spells_mode_dropdown.pack(side='left')
        # Save when dropdown selection changes (but not during profile switching)
        self.sbarb_cast_spells_mode_dropdown.bind('<<ComboboxSelected>>', lambda e: self.save_settings() if not self.is_saving else None)

        # SBarb Farm turbo deployment checkbox (conditionally visible)
        self.sbarb_turbo_deployment_var = tk.BooleanVar(value=profile_settings.get('sbarb_turbo_deployment', False))
        self.sbarb_turbo_deployment_check = ttk.Checkbutton(
            frame,
            text="Turbo-Fast Deployment (~16 CPS, overrides hero timing/order settings)",
            variable=self.sbarb_turbo_deployment_var,
            command=self.on_turbo_mode_toggled  # Save settings and update visibility
        )

        # BB Gold troop mode dropdown (conditionally visible)
        self.bb_gold_troop_mode_map = {
            'Night Witches': 'night_witches',
            'Bomber + Night Witches': 'bomber_night_witches',
            'Baby Dragons': 'baby_dragons'
        }
        self.bb_gold_troop_mode_reverse_map = {v: k for k, v in self.bb_gold_troop_mode_map.items()}

        # Migrate from old bb_gold_using_bomber setting
        saved_mode = profile_settings.get('bb_gold_troop_mode', None)
        if saved_mode is None:
            # Migrate from old setting
            if profile_settings.get('bb_gold_using_bomber', False):
                saved_mode = 'bomber_night_witches'
            else:
                saved_mode = 'night_witches'

        display_mode = self.bb_gold_troop_mode_reverse_map.get(saved_mode, 'Night Witches')
        self.bb_gold_troop_mode_var = tk.StringVar(value=display_mode)

        # Create frame for label + dropdown
        self.bb_gold_troop_mode_frame = ttk.Frame(frame)
        ttk.Label(self.bb_gold_troop_mode_frame, text="Troop Mode:").pack(side=tk.LEFT, padx=(0, 5))
        self.bb_gold_troop_mode_dropdown = ttk.Combobox(
            self.bb_gold_troop_mode_frame,
            textvariable=self.bb_gold_troop_mode_var,
            values=['Night Witches', 'Bomber + Night Witches', 'Baby Dragons'],
            state='readonly',
            width=20
        )
        self.bb_gold_troop_mode_dropdown.pack(side=tk.LEFT)
        self.bb_gold_troop_mode_dropdown.bind('<<ComboboxSelected>>', self._on_bb_gold_troop_mode_changed)

        # BB Gold Baby Dragons debug checkbox (always starts unchecked, not persisted)
        self.bb_gold_dragon_debug_var = tk.BooleanVar(value=False)
        self.bb_gold_dragon_debug_frame = ttk.Frame(frame)
        self.bb_gold_dragon_debug_check = ttk.Checkbutton(
            self.bb_gold_dragon_debug_frame,
            text="Debug detection (mask + positions)",
            variable=self.bb_gold_dragon_debug_var,
            command=self._on_bb_gold_dragon_debug_changed
        )
        self.bb_gold_dragon_debug_check.pack(side=tk.LEFT)

        # BB Gold Baby Dragons "try for 3 stars" checkbox
        self.bb_gold_try_3_stars_var = tk.BooleanVar(value=profile_settings.get('bb_gold_try_3_stars', False))
        self.bb_gold_try_3_stars_frame = ttk.Frame(frame)
        self.bb_gold_try_3_stars_check = ttk.Checkbutton(
            self.bb_gold_try_3_stars_frame,
            text="Try for 3 stars (no surrender at 2)",
            variable=self.bb_gold_try_3_stars_var,
            command=self._on_bb_gold_try_3_stars_changed
        )
        self.bb_gold_try_3_stars_check.pack(side=tk.LEFT)

        # Hide achievement building dropdown by default
        self.achievement_building_row_visible = False
        # Hide sgoblin spell casting checkbox by default
        self.sgoblin_cast_spells_row_visible = False
        # Hide sgoblin wall breaker checkbox by default
        self.sgoblin_use_wallbreakers_row_visible = False
        # Hide sgoblin skip logging checkbox by default
        self.sgoblin_skip_logging_row_visible = False
        # Hide sbarb heroes first checkbox by default
        self.sbarb_heroes_first_row_visible = False
        # Hide sbarb queen arrow spells checkbox by default
        self.sbarb_queen_arrow_spells_row_visible = False
        # Hide sbarb cast spells checkbox by default
        self.sbarb_cast_spells_row_visible = False
        # Hide sbarb cast spells targeting mode dropdown by default
        self.sbarb_cast_spells_mode_row_visible = False
        # Hide sbarb turbo deployment checkbox by default
        self.sbarb_turbo_deployment_row_visible = False
        # Hide BB Gold troop mode dropdown by default
        self.bb_gold_troop_mode_row_visible = False
        # Hide BB Gold dragon debug checkbox by default
        self.bb_gold_dragon_debug_row_visible = False
        # Hide BB Gold try 3 stars checkbox by default
        self.bb_gold_try_3_stars_row_visible = False

        self.update_profile_description()

    def create_army_section(self, frame):
        frame.columnconfigure(1, weight=1)

        # Standardize row heights for consistent alignment
        for i in range(8):  # 7 troop rows + 1 lightning row
            frame.rowconfigure(i, minsize=32)

        # Create widgets but don't grid them yet - we'll control visibility dynamically
        # Create 7 generic troop slots
        self.troop_labels = []
        self.troop_spinboxes = []

        for i in range(7):
            label = ttk.Label(frame, text=f"Troop {i+1}:")
            spinbox = ttk.Spinbox(frame, from_=0, to=30, textvariable=self.troop_count_vars[i], width=10)
            self.troop_labels.append(label)
            self.troop_spinboxes.append(spinbox)

        # Lightning Damage
        self.lightning_label = ttk.Label(frame, text="Lightning Damage:")
        self.lightning_damage_spinbox = ttk.Spinbox(frame, from_=100, to=500, increment=25, textvariable=self.lightning_damage_var, width=10)

        # Initially show all widgets (will be updated when profile changes)
        self.update_army_section_visibility()

    def update_army_section_visibility(self):
        """Update visibility of army section widgets based on current profile"""
        current_profile = self.current_profile

        # Define which widgets should be visible for each profile
        profile_visibility = {
            'Derank': {
                'troops': False,
                'lightning_damage': False
            },
            'Farming': {
                'troops': True,
                'lightning_damage': True
            },
            'Trophy Push': {
                'troops': True,
                'lightning_damage': True
            },
            'SGoblin Farm': {
                'troops': True,
                'lightning_damage': False
            },
            'SBarb Farm': {
                'troops': True,
                'lightning_damage': True
            },
            'BB Elixir': {
                'troops': False,
                'lightning_damage': False
            },
            'BB Gold': {
                'troops': False,
                'lightning_damage': False
            },
            'Achievement Farm': {
                'troops': False,
                'lightning_damage': True
            },
            'Custom': {
                'troops': True,
                'lightning_damage': True
            }
        }

        # Get visibility settings for current profile (default to all visible)
        visibility = profile_visibility.get(current_profile, {
            'troops': True,
            'lightning_damage': True
        })

        # Clear all widgets first
        for i in range(7):
            self.troop_labels[i].grid_remove()
            self.troop_spinboxes[i].grid_remove()
        self.lightning_label.grid_remove()
        self.lightning_damage_spinbox.grid_remove()

        # Grid widgets based on visibility
        row = 0

        if visibility['troops']:
            for i in range(7):
                self.troop_labels[i].grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
                self.troop_spinboxes[i].grid(row=row, column=1, sticky=tk.W)
                row += 1

        if visibility['lightning_damage']:
            self.lightning_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            self.lightning_damage_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1

    def create_attack_section(self, frame):
        frame.columnconfigure(1, weight=1)

        # Standardize row heights for consistent alignment
        for i in range(12):  # Enough rows for all possible widgets
            frame.rowconfigure(i, minsize=32)

        # Create widgets but don't grid them yet - we'll control visibility dynamically
        # Minimum Resources
        self.min_resources_label = ttk.Label(frame, text="Minimum Resources:")
        self.min_resources_entry = ttk.Entry(frame, textvariable=self.min_resources_var, width=10)

        # Max Town Hall Level
        self.max_th_label = ttk.Label(frame, text="Max Town Hall Level:")
        self.max_th_spinbox = ttk.Spinbox(frame, from_=1, to=16, textvariable=self.max_th_var, width=10)
        
        # Air Defense Targeting
        self.ad_target_label = ttk.Label(frame, text="Air Defense Targeting:")
        self.ad_target_mode_frame = ttk.Frame(frame)
        ttk.Radiobutton(self.ad_target_mode_frame, text="By Level", variable=self.ad_target_mode_var, value='level', command=self.save_settings).pack(side=tk.LEFT)
        ttk.Radiobutton(self.ad_target_mode_frame, text="By Proximity to Attack Side", variable=self.ad_target_mode_var, value='proximity', command=self.save_settings).pack(side=tk.LEFT)
        
        # Attack Side Selection
        self.attack_side_label = ttk.Label(frame, text="Attack Side Selection:")
        self.attack_side_mode_frame = ttk.Frame(frame)
        ttk.Radiobutton(self.attack_side_mode_frame, text="Random", variable=self.attack_side_mode_var, value='random', command=self.save_settings).pack(side=tk.LEFT)
        ttk.Radiobutton(self.attack_side_mode_frame, text="Town Hall Side", variable=self.attack_side_mode_var, value='th_side', command=self.save_settings).pack(side=tk.LEFT)

        # Hero Ability Activation Timing
        self.hero_timing_label = ttk.Label(frame, text="Hero Ability Activation (seconds after deployment, -1 = disabled):")
        
        # Queen ability timing
        self.queen_timing_label = ttk.Label(frame, text="Queen:")
        self.queen_timing_spinbox = ttk.Spinbox(frame, from_=-1, to=60, increment=1, textvariable=self.queen_ability_timing_var, width=10)

        # King ability timing
        self.king_timing_label = ttk.Label(frame, text="King:")
        self.king_timing_spinbox = ttk.Spinbox(frame, from_=-1, to=60, increment=1, textvariable=self.king_ability_timing_var, width=10)

        # Warden ability timing
        self.warden_timing_label = ttk.Label(frame, text="Warden:")
        self.warden_timing_spinbox = ttk.Spinbox(frame, from_=-1, to=60, increment=1, textvariable=self.warden_ability_timing_var, width=10)

        # Royal Champion ability timing
        self.rc_timing_label = ttk.Label(frame, text="Royal Champion:")
        self.rc_timing_spinbox = ttk.Spinbox(frame, from_=-1, to=60, increment=1, textvariable=self.rc_ability_timing_var, width=10)
        
        # Bind spinbox changes to save settings
        self.queen_timing_spinbox.bind('<KeyRelease>', lambda e: self.save_settings())
        self.queen_timing_spinbox.bind('<<Increment>>', lambda e: self.save_settings())
        self.queen_timing_spinbox.bind('<<Decrement>>', lambda e: self.save_settings())
        
        self.king_timing_spinbox.bind('<KeyRelease>', lambda e: self.save_settings())
        self.king_timing_spinbox.bind('<<Increment>>', lambda e: self.save_settings())
        self.king_timing_spinbox.bind('<<Decrement>>', lambda e: self.save_settings())
        
        self.warden_timing_spinbox.bind('<KeyRelease>', lambda e: self.save_settings())
        self.warden_timing_spinbox.bind('<<Increment>>', lambda e: self.save_settings())
        self.warden_timing_spinbox.bind('<<Decrement>>', lambda e: self.save_settings())
        
        self.rc_timing_spinbox.bind('<KeyRelease>', lambda e: self.save_settings())
        self.rc_timing_spinbox.bind('<<Increment>>', lambda e: self.save_settings())
        self.rc_timing_spinbox.bind('<<Decrement>>', lambda e: self.save_settings())
        
        # Initially show all widgets (will be updated when profile changes)
        self.update_attack_section_visibility()

    def update_attack_section_visibility(self):
        """Update visibility of attack section widgets based on current profile"""
        current_profile = self.current_profile
        
        # Define which widgets should be visible for each profile
        profile_visibility = {
            'Derank': {
                'min_resources': False,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': True,
                'hero_ability_timing': False
            },
            'Farming': {
                'min_resources': True,
                'max_th_level': True,
                'ad_target_mode': True,
                'attack_side_mode': True,
                'hero_ability_timing': True
            },
            'Trophy Push': {
                'min_resources': True,
                'max_th_level': True,
                'ad_target_mode': True,
                'attack_side_mode': True,
                'hero_ability_timing': True
            },
            'SGoblin Farm': {
                'min_resources': True,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': False,
                'hero_ability_timing': True
            },
            'SBarb Farm': {
                'min_resources': True,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': False,
                'hero_ability_timing': False
            },
            'BB Elixir': {
                'min_resources': False,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': False,
                'hero_ability_timing': False
            },
            'BB Gold': {
                'min_resources': False,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': False,
                'hero_ability_timing': False
            },
            'Achievement Farm': {
                'min_resources': True,
                'max_th_level': False,
                'ad_target_mode': False,
                'attack_side_mode': False,
                'hero_ability_timing': False
            },
            'Custom': {
                'min_resources': True,
                'max_th_level': True,
                'ad_target_mode': True,
                'attack_side_mode': True,
                'hero_ability_timing': True
            }
        }

        # Get visibility settings for current profile (default to all visible)
        visibility = profile_visibility.get(current_profile, {
            'min_resources': True,
            'max_th_level': True,
            'ad_target_mode': True,
            'attack_side_mode': True,
            'hero_ability_timing': True
        })
        
        # Clear all widgets first
        for widget in [self.min_resources_label, self.min_resources_entry,
                      self.max_th_label, self.max_th_spinbox,
                      self.ad_target_label, self.ad_target_mode_frame,
                      self.attack_side_label, self.attack_side_mode_frame,
                      self.hero_timing_label, self.queen_timing_label, self.queen_timing_spinbox,
                      self.king_timing_label, self.king_timing_spinbox,
                      self.warden_timing_label, self.warden_timing_spinbox,
                      self.rc_timing_label, self.rc_timing_spinbox]:
            widget.grid_remove()
        
        # Grid widgets based on visibility
        row = 0
        
        if visibility['min_resources']:
            self.min_resources_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            self.min_resources_entry.grid(row=row, column=1, sticky=tk.W)
            row += 1
            
        if visibility['max_th_level']:
            self.max_th_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            self.max_th_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1
            
        if visibility['ad_target_mode']:
            self.ad_target_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            self.ad_target_mode_frame.grid(row=row, column=1, sticky=tk.W)
            row += 1
            
        if visibility['attack_side_mode']:
            self.attack_side_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            self.attack_side_mode_frame.grid(row=row, column=1, sticky=tk.W)
            row += 1

        if visibility['hero_ability_timing']:
            self.hero_timing_label.grid(row=row, column=0, sticky=tk.W, padx=(0, 10))
            row += 1
            
            # Queen timing
            self.queen_timing_label.grid(row=row, column=0, sticky=tk.W, padx=(5, 10))
            self.queen_timing_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1

            # King timing
            self.king_timing_label.grid(row=row, column=0, sticky=tk.W, padx=(5, 10))
            self.king_timing_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1

            # Warden timing
            self.warden_timing_label.grid(row=row, column=0, sticky=tk.W, padx=(5, 10))
            self.warden_timing_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1

            # Royal Champion timing
            self.rc_timing_label.grid(row=row, column=0, sticky=tk.W, padx=(5, 10))
            self.rc_timing_spinbox.grid(row=row, column=1, sticky=tk.W)
            row += 1

    def create_global_section(self, frame):
        frame.columnconfigure(1, weight=1)
        # Global Reinforcements
        ttk.Label(frame, text="Reinforcements:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.global_reinforcements_var = tk.BooleanVar(value=self.global_reinforcements_enabled)
        reinforcements_check = ttk.Checkbutton(frame, variable=self.global_reinforcements_var, command=self.save_global_settings)
        reinforcements_check.grid(row=0, column=1, sticky=tk.W)
        # Global Night Mode
        ttk.Label(frame, text="Night Mode:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.night_mode_var = tk.BooleanVar(value=self.night_mode)
        night_mode_check = ttk.Checkbutton(frame, variable=self.night_mode_var, command=self.toggle_night_mode)
        night_mode_check.grid(row=1, column=1, sticky=tk.W)
        # Detection Overlay (visualization of what the bot sees)
        ttk.Label(frame, text="Detection Overlay:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.overlay_enabled_var = tk.BooleanVar(value=self.overlay_enabled)
        overlay_check = ttk.Checkbutton(frame, variable=self.overlay_enabled_var, command=self.toggle_overlay)
        overlay_check.grid(row=2, column=1, sticky=tk.W)
        if not OVERLAY_AVAILABLE:
            overlay_check.configure(state='disabled')

        # Hide Low Confidence Detections (only show proper detections, no red rectangles)
        self.overlay_hide_low_conf_label = ttk.Label(frame, text="  Hide Low Confidence:")
        self.overlay_hide_low_conf_var = tk.BooleanVar(value=getattr(self, 'overlay_hide_low_conf', False))
        self.overlay_hide_low_conf_check = ttk.Checkbutton(
            frame,
            variable=self.overlay_hide_low_conf_var,
            command=self.save_global_settings
        )
        # Show/hide based on overlay enabled state
        if self.overlay_enabled:
            self.overlay_hide_low_conf_label.grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
            self.overlay_hide_low_conf_check.grid(row=3, column=1, sticky=tk.W)
            self.overlay_hide_low_conf_row_visible = True
        else:
            self.overlay_hide_low_conf_row_visible = False

        # Parallel Scanning (for Achievement/SBarb Farm - uses more CPU but faster)
        ttk.Label(frame, text="Parallel Scanning:").grid(row=4, column=0, sticky=tk.W, padx=(0, 10))
        parallel_scan_check = ttk.Checkbutton(frame, variable=self.achievement_parallel_scan_var, command=self.save_global_settings)
        parallel_scan_check.grid(row=4, column=1, sticky=tk.W)
        # GPU Scanning (offloads template matching to GPU - experimental)
        ttk.Label(frame, text="GPU Scanning (WIP):").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        gpu_frame = ttk.Frame(frame)
        gpu_frame.grid(row=5, column=1, sticky=tk.W)
        self.gpu_scanning_var = tk.BooleanVar(value=getattr(self, 'gpu_scanning', False))
        gpu_scan_check = ttk.Checkbutton(gpu_frame, variable=self.gpu_scanning_var, command=self.save_global_settings)
        gpu_scan_check.pack(side='left')
        ttk.Label(gpu_frame, text="(issues with Firespitter/Spell Tower)", foreground='orange', font=('Segoe UI', 8)).pack(side='left', padx=(5, 0))
        # Prefer 2nd Monitor (auto-detected)
        ttk.Label(frame, text="Prefer 2nd Monitor:").grid(row=6, column=0, sticky=tk.W, padx=(0, 10))
        self.use_second_monitor_var = tk.BooleanVar(value=self.use_second_monitor)
        second_monitor_check = ttk.Checkbutton(frame, variable=self.use_second_monitor_var, command=self.save_global_settings)
        second_monitor_check.grid(row=6, column=1, sticky=tk.W)
        # Global Town Hall Detection Behavior
        ttk.Label(frame, text="Skip on TH Detection Fail:").grid(row=7, column=0, sticky=tk.W, padx=(0, 10))
        self.skip_on_th_fail_var = tk.BooleanVar(value=self.skip_on_th_fail)
        skip_on_th_fail_check = ttk.Checkbutton(frame, variable=self.skip_on_th_fail_var, command=self.save_global_settings)
        skip_on_th_fail_check.grid(row=7, column=1, sticky=tk.W)
        # Global Auto Pause
        ttk.Label(frame, text="Auto Pause Enabled:").grid(row=8, column=0, sticky=tk.W, padx=(0, 10))
        auto_pause_check = ttk.Checkbutton(frame, variable=self.auto_pause_var, command=self.save_settings)
        auto_pause_check.grid(row=8, column=1, sticky=tk.W)
        # Global Break Interval
        ttk.Label(frame, text="Break Interval (minutes):").grid(row=9, column=0, sticky=tk.W, padx=(0, 10))
        break_interval_spinbox = ttk.Spinbox(frame, from_=15, to=120, increment=5, textvariable=self.break_interval_var, width=15)
        break_interval_spinbox.grid(row=9, column=1, sticky=tk.W)
        # Global Break Duration
        ttk.Label(frame, text="Break Duration (minutes):").grid(row=10, column=0, sticky=tk.W, padx=(0, 10))
        break_duration_spinbox = ttk.Spinbox(frame, from_=1, to=30, increment=1, textvariable=self.break_duration_var, width=15)
        break_duration_spinbox.grid(row=10, column=1, sticky=tk.W)

        # BB Loot Collection Interval
        ttk.Label(frame, text="BB Collect Interval (attacks):").grid(row=11, column=0, sticky=tk.W, padx=(0, 10))
        bb_collect_spinbox = ttk.Spinbox(frame, from_=1, to=50, increment=1, textvariable=self.bb_collect_interval_var, width=15,
                                         command=lambda: self.save_settings())
        bb_collect_spinbox.grid(row=11, column=1, sticky=tk.W)

        # Storage Preset Selector
        ttk.Label(frame, text="Storage Preset:").grid(row=12, column=0, sticky=tk.W, padx=(0, 10))
        self.storage_preset_var = tk.StringVar(value="main")
        preset_frame = ttk.Frame(frame)
        preset_frame.grid(row=12, column=1, sticky=tk.W)
        self.storage_preset_dropdown = ttk.Combobox(preset_frame, textvariable=self.storage_preset_var,
                                                     state='readonly', width=18)
        self.storage_preset_dropdown.pack(side='left', padx=(0, 5))
        self.storage_preset_dropdown.bind('<<ComboboxSelected>>', self.on_storage_preset_selected)
        ttk.Button(preset_frame, text="Save", command=self.save_storage_preset, width=6).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="New", command=self.create_storage_preset, width=6).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="Del", command=self.delete_storage_preset, width=6).pack(side='left', padx=2)

        # Max Storage Capacities
        ttk.Label(frame, text="Max Gold Storage:").grid(row=13, column=0, sticky=tk.W, padx=(0, 10))
        # Note: self.max_gold_storage_var already created in load_settings()
        self.max_gold_storage_spinbox = ttk.Spinbox(frame, from_=1000000, to=20000000, increment=100000, textvariable=self.max_gold_storage_var, width=15)
        self.max_gold_storage_spinbox.grid(row=13, column=1, sticky=tk.W)
        ttk.Label(frame, text="Max Elixir Storage:").grid(row=14, column=0, sticky=tk.W, padx=(0, 10))
        # Note: self.max_elixir_storage_var already created in load_settings()
        self.max_elixir_storage_spinbox = ttk.Spinbox(frame, from_=1000000, to=20000000, increment=100000, textvariable=self.max_elixir_storage_var, width=15)
        self.max_elixir_storage_spinbox.grid(row=14, column=1, sticky=tk.W)
        ttk.Label(frame, text="Max Dark Elixir Storage:").grid(row=15, column=0, sticky=tk.W, padx=(0, 10))
        # Note: self.max_dark_elixir_storage_var already created in load_settings()
        self.max_dark_elixir_storage_spinbox = ttk.Spinbox(frame, from_=10000, to=500000, increment=10000, textvariable=self.max_dark_elixir_storage_var, width=15)
        self.max_dark_elixir_storage_spinbox.grid(row=15, column=1, sticky=tk.W)

        # BB Storage Capacities
        ttk.Label(frame, text="Max BB Gold Storage:").grid(row=16, column=0, sticky=tk.W, padx=(0, 10))
        # Note: self.max_bb_gold_storage_var already created in load_settings()
        self.max_bb_gold_storage_spinbox = ttk.Spinbox(frame, from_=1000000, to=10000000, increment=100000, textvariable=self.max_bb_gold_storage_var, width=15)
        self.max_bb_gold_storage_spinbox.grid(row=16, column=1, sticky=tk.W)
        ttk.Label(frame, text="Max BB Elixir Storage:").grid(row=17, column=0, sticky=tk.W, padx=(0, 10))
        # Note: self.max_bb_elixir_storage_var already created in load_settings()
        self.max_bb_elixir_storage_spinbox = ttk.Spinbox(frame, from_=1000000, to=10000000, increment=100000, textvariable=self.max_bb_elixir_storage_var, width=15)
        self.max_bb_elixir_storage_spinbox.grid(row=17, column=1, sticky=tk.W)

    def create_queue_section(self, frame):
        """Create Queue System configuration section"""
        frame.columnconfigure(1, weight=1)

        # Queue Enable/Disable
        ttk.Label(frame, text="Enable Queue:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.queue_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.queue_enabled_var, command=self.on_queue_enabled_changed).grid(row=0, column=1, sticky=tk.W)

        # Queue Mode (Smart/Manual)
        ttk.Label(frame, text="Queue Mode:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.queue_mode_var = tk.StringVar(value="smart")
        queue_mode_combo = ttk.Combobox(frame, textvariable=self.queue_mode_var, values=["smart", "manual"], state='readonly', width=15)
        queue_mode_combo.grid(row=1, column=1, sticky=tk.W)
        queue_mode_combo.bind('<<ComboboxSelected>>', self.on_queue_mode_changed)

        # Smart Mode Configuration (collapsible)
        self.smart_mode_frame = ttk.LabelFrame(frame, text="Smart Mode Settings", padding="10")
        self.smart_mode_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_smart_mode_controls(self.smart_mode_frame)

        # Manual Mode Configuration (collapsible)
        self.manual_mode_frame = ttk.LabelFrame(frame, text="Manual Mode Settings", padding="10")
        self.manual_mode_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_manual_mode_controls(self.manual_mode_frame)

        # Achievement Farm End Behavior
        self.achievement_end_frame = ttk.LabelFrame(frame, text="Achievement Farm End Behavior", padding="10")
        self.achievement_end_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_achievement_end_controls(self.achievement_end_frame)

        # Update visibility based on queue mode
        self.update_queue_mode_visibility()

    def create_smart_mode_controls(self, frame):
        """Create Smart Mode configuration controls"""
        frame.columnconfigure(1, weight=1)

        # Main Base Mode Selection
        ttk.Label(frame, text="Main Base Mode:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_main_mode_var = tk.StringVar(value="SBarb Farm")
        main_mode_combo = ttk.Combobox(frame, textvariable=self.smart_main_mode_var,
                                       values=["SBarb Farm", "SGoblin Farm"], state='readonly', width=15)
        main_mode_combo.grid(row=0, column=1, sticky=tk.W)

        # Storage Thresholds
        ttk.Label(frame, text="Gold Threshold (%):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_gold_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_gold_threshold_var, width=15).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(frame, text="Elixir Threshold (%):").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_elixir_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_elixir_threshold_var, width=15).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(frame, text="DE Threshold (%):").grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_de_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_de_threshold_var, width=15).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(frame, text="Wait for DE:").grid(row=4, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_wait_de_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.smart_wait_de_var).grid(row=4, column=1, sticky=tk.W)

        # BB Settings
        ttk.Label(frame, text="BB Auto-Select:").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_bb_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, variable=self.smart_bb_auto_var).grid(row=5, column=1, sticky=tk.W)

        ttk.Label(frame, text="BB Gold/Elixir Ratio:").grid(row=6, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_bb_ratio_var = tk.StringVar(value="3.0")
        ttk.Spinbox(frame, from_=1.0, to=10.0, increment=0.5, textvariable=self.smart_bb_ratio_var, width=15).grid(row=6, column=1, sticky=tk.W)

        ttk.Label(frame, text="After BB Behavior:").grid(row=7, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_after_bb_var = tk.StringVar(value="stop")
        after_bb_combo = ttk.Combobox(frame, textvariable=self.smart_after_bb_var,
                                      values=["stop", "achievement_farm"], state='readonly', width=15)
        after_bb_combo.grid(row=7, column=1, sticky=tk.W)

    def create_manual_mode_controls(self, frame):
        """Create Manual Mode schedule editor"""
        frame.columnconfigure(0, weight=1)

        # Subtitle explaining usage
        subtitle = ttk.Label(frame,
            text="Define a sequence of tasks to execute in order. Each task runs until its condition is met.",
            font=('Segoe UI', 8, 'italic'),
            foreground='gray')
        subtitle.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Create frame for schedule list with scrollbar
        self.manual_schedule_frame = ttk.Frame(frame, relief='solid', borderwidth=1)

        schedule_canvas_frame = ttk.Frame(self.manual_schedule_frame)
        schedule_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.manual_schedule_canvas = tk.Canvas(schedule_canvas_frame, height=200, bg='#f0f0f0', highlightthickness=0)
        self.manual_schedule_scrollbar = ttk.Scrollbar(schedule_canvas_frame, orient="vertical", command=self.manual_schedule_canvas.yview)
        self.manual_schedule_scroll_frame = ttk.Frame(self.manual_schedule_canvas)

        self.manual_schedule_scroll_frame.bind(
            "<Configure>",
            lambda e: self.manual_schedule_canvas.configure(scrollregion=self.manual_schedule_canvas.bbox("all"))
        )

        self.manual_schedule_canvas.create_window((0, 0), window=self.manual_schedule_scroll_frame, anchor="nw")
        self.manual_schedule_canvas.configure(yscrollcommand=self.manual_schedule_scrollbar.set)

        self.manual_schedule_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.manual_schedule_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store task card references
        self.manual_task_cards = []
        self.manual_selected_task_index = None

        # Grid the schedule list frame
        self.manual_schedule_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Buttons frame
        self.manual_buttons_frame = ttk.Frame(frame)

        ttk.Button(
            self.manual_buttons_frame,
            text="➕ Add Task",
            command=self.add_manual_task,
            width=12
        ).grid(row=0, column=0, padx=(0, 5))

        ttk.Button(
            self.manual_buttons_frame,
            text="✏️ Edit Task",
            command=self.edit_manual_task,
            width=12
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="❌ Remove",
            command=self.remove_manual_task,
            width=12
        ).grid(row=0, column=2, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="⬆ Move Up",
            command=self.move_manual_task_up,
            width=12
        ).grid(row=0, column=3, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="⬇ Move Down",
            command=self.move_manual_task_down,
            width=12
        ).grid(row=0, column=4, padx=(5, 0))

        # Clear All button on second row
        ttk.Button(
            self.manual_buttons_frame,
            text="🗑️ Clear All Tasks",
            command=self.clear_all_manual_tasks,
            width=20
        ).grid(row=1, column=0, columnspan=2, pady=(5, 0), padx=(0, 5))

        self.manual_buttons_frame.grid(row=2, column=0, pady=(5, 0))

        # Initialize task list display
        self.refresh_manual_schedule_display()

    def create_achievement_end_controls(self, frame):
        """Create Achievement Farm end behavior controls"""
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Enable:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.achievement_end_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.achievement_end_enabled_var).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(frame, text="Duration (minutes):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.achievement_end_duration_var = tk.StringVar(value="20")
        ttk.Spinbox(frame, from_=5, to=120, increment=5, textvariable=self.achievement_end_duration_var, width=15).grid(row=1, column=1, sticky=tk.W)

    def on_queue_enabled_changed(self):
        """Handle queue enable/disable toggle"""
        print(f"[GUI] on_queue_enabled_changed called, checkbox value: {self.queue_enabled_var.get()}")

        # Start or stop the queue manager
        try:
            import sys
            # Get queue_manager from main module (already imported)
            main_module = sys.modules.get('__main__')

            if main_module is None:
                print("[GUI] ERROR: Cannot access main module")
                self.save_settings()
                return

            queue_manager = getattr(main_module, 'queue_manager', None)
            print(f"[GUI] queue_manager reference: {queue_manager}")

            if self.queue_enabled_var.get():
                # Queue enabled - start it
                if queue_manager:
                    queue_manager.start_queue()
                    self.log_message("Queue System: STARTED")
                    print("[GUI] ✓ Queue system started successfully")
                else:
                    print("[GUI] ERROR: queue_manager not found")
                    self.log_message("Queue System: ERROR - queue_manager not initialized")
            else:
                # Queue disabled - reset it
                if queue_manager:
                    queue_manager.reset_queue()
                    self.log_message("Queue System: STOPPED")
                    print("[GUI] ✓ Queue system stopped")
                else:
                    print("[GUI] WARNING: queue_manager not found (queue already stopped)")
        except Exception as e:
            print(f"[GUI] ERROR toggling queue: {e}")
            import traceback
            traceback.print_exc()

        self.save_global_settings()

    def on_queue_mode_changed(self, event=None):
        """Handle queue mode selection"""
        self.update_queue_mode_visibility()
        self.save_global_settings()

    def update_queue_mode_visibility(self):
        """Show/hide Smart/Manual mode controls based on selection"""
        mode = self.queue_mode_var.get()

        if mode == "smart":
            self.smart_mode_frame.grid()
            self.manual_mode_frame.grid_remove()
        else:
            self.smart_mode_frame.grid_remove()
            self.manual_mode_frame.grid()

    def create_achievement_priority_section(self, frame):
        """Create achievement building priority list section"""
        frame.columnconfigure(0, weight=1)

        # Subtitle explaining usage
        subtitle = ttk.Label(frame,
            text="Top = highest priority, used by Achievement/SBarb Farm modes",
            font=('Segoe UI', 8, 'italic'),
            foreground='gray')
        subtitle.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Create modern styled frame for priority list
        self.achievement_priority_frame = ttk.Frame(frame, relief='solid', borderwidth=1)

        # Create canvas with scrollbar for modern scrollable list
        priority_canvas_frame = ttk.Frame(self.achievement_priority_frame)
        priority_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.achievement_priority_canvas = tk.Canvas(priority_canvas_frame, height=250, bg='#f0f0f0', highlightthickness=0)
        self.achievement_priority_scrollbar = ttk.Scrollbar(priority_canvas_frame, orient="vertical", command=self.achievement_priority_canvas.yview)
        self.achievement_priority_scroll_frame = ttk.Frame(self.achievement_priority_canvas)

        self.achievement_priority_scroll_frame.bind(
            "<Configure>",
            lambda e: self.achievement_priority_canvas.configure(scrollregion=self.achievement_priority_canvas.bbox("all"))
        )

        self.achievement_priority_canvas.create_window((0, 0), window=self.achievement_priority_scroll_frame, anchor="nw")
        self.achievement_priority_canvas.configure(yscrollcommand=self.achievement_priority_scrollbar.set)

        self.achievement_priority_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.achievement_priority_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store building card references for updates
        self.priority_building_cards = []

        # Grid the priority list frame
        self.achievement_priority_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Buttons frame with modern styling
        self.achievement_priority_buttons_frame = ttk.Frame(frame)
        self.achievement_move_up_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="⬆ Move Up",
            command=self.move_building_up,
            width=15
        )
        self.achievement_move_up_btn.pack(side=tk.LEFT, padx=5)

        self.achievement_move_down_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="⬇ Move Down",
            command=self.move_building_down,
            width=15
        )
        self.achievement_move_down_btn.pack(side=tk.LEFT, padx=5)

        self.achievement_reset_priority_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="🔄 Reset Order",
            command=self.reset_building_priority,
            width=15
        )
        self.achievement_reset_priority_btn.pack(side=tk.LEFT, padx=5)

        # Grid buttons
        self.achievement_priority_buttons_frame.grid(row=2, column=0, sticky=tk.W)

        # Initialize priority list from current profile
        profile_settings = self.profiles.get(self.current_profile, {})
        self.achievement_priority_list = profile_settings.get('achievement_priority_list', [
            'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
            'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
        ])
        self.selected_priority_building = None
        self.update_priority_listbox()

    def create_control_section(self, parent):
        # Control Frame with improved layout
        control_frame = ttk.LabelFrame(parent, text="🎮 Bot Controls", padding="15")
        control_frame.grid(row=3, column=0, columnspan=2, sticky='we', pady=(0, 15))
        self.control_frame = control_frame  # Store for collapsible

        # Make control frame responsive
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)
        control_frame.columnconfigure(4, weight=1)
        control_frame.columnconfigure(5, weight=1)

        # Primary control buttons (row 0) - larger and more prominent
        self.start_button = ttk.Button(control_frame, text="▶ Start Bot", command=self.start_bot)
        self.start_button.grid(row=0, column=0, columnspan=2, sticky='ew', padx=(0, 10))

        self.pause_button = ttk.Button(control_frame, text="⏸ Pause/Resume (F1)", command=self.toggle_pause, state="disabled")
        self.pause_button.grid(row=0, column=2, columnspan=2, sticky='ew', padx=(0, 10))

        self.stop_button = ttk.Button(control_frame, text="⏹ Stop Bot (F2)", command=self.stop_bot, state="disabled")
        self.stop_button.grid(row=0, column=4, columnspan=2, sticky='ew')

        # Secondary buttons (row 1) - utilities
        template_button = ttk.Button(control_frame, text="Template Tools", command=self.open_template_tools)
        template_button.grid(row=1, column=0, columnspan=2, sticky='ew', padx=(0, 10), pady=(10, 0))

        save_button = ttk.Button(control_frame, text="Save Settings", command=lambda: self.save_settings(show_popup=True))
        save_button.grid(row=1, column=2, columnspan=2, sticky='ew', padx=(0, 10), pady=(10, 0))

        reset_profile_button = ttk.Button(control_frame, text="Reset Profile", command=self.reset_profile_to_defaults)
        reset_profile_button.grid(row=1, column=4, columnspan=2, sticky='ew', pady=(10, 0))

        # Auto-pause controls (row 2-4, cleaner layout)
        auto_pause_label = ttk.Label(control_frame, text="Auto-Pause:", font=('Segoe UI', 9))
        auto_pause_label.grid(row=2, column=0, sticky='w', pady=(10, 0))

        # Auto-pause mode variable
        self.auto_pause_mode = tk.StringVar(value="manual")

        # Storage full resource checkboxes (which resources must be full)
        self.storage_full_gold_var = tk.BooleanVar(value=True)
        self.storage_full_elixir_var = tk.BooleanVar(value=True)
        self.storage_full_de_var = tk.BooleanVar(value=False)
        self.storage_full_preset_var = tk.StringVar(value="main")

        # Row 2: Manual option
        manual_frame = ttk.Frame(control_frame)
        manual_frame.grid(row=2, column=1, columnspan=4, sticky='w', pady=(10, 0))

        manual_radio = ttk.Radiobutton(manual_frame, text="Manual", variable=self.auto_pause_mode, value="manual")
        manual_radio.pack(side='left')

        # Row 3: Storage Full option with resource checkboxes
        storage_frame = ttk.Frame(control_frame)
        storage_frame.grid(row=3, column=1, columnspan=4, sticky='w', pady=(5, 0))

        storage_radio = ttk.Radiobutton(storage_frame, text="Storage Full:", variable=self.auto_pause_mode, value="storage_full")
        storage_radio.pack(side='left')

        # Resource checkboxes (compact, inline)
        self.storage_gold_cb = ttk.Checkbutton(storage_frame, text="Gold", variable=self.storage_full_gold_var,
                                                command=self.save_settings)
        self.storage_gold_cb.pack(side='left', padx=(8, 0))

        self.storage_elixir_cb = ttk.Checkbutton(storage_frame, text="Elixir", variable=self.storage_full_elixir_var,
                                                  command=self.save_settings)
        self.storage_elixir_cb.pack(side='left', padx=(4, 0))

        self.storage_de_cb = ttk.Checkbutton(storage_frame, text="DE", variable=self.storage_full_de_var,
                                              command=self.save_settings)
        self.storage_de_cb.pack(side='left', padx=(4, 0))

        # Storage preset dropdown
        ttk.Label(storage_frame, text="Preset:").pack(side='left', padx=(12, 2))
        self.storage_full_preset_dropdown = ttk.Combobox(storage_frame, textvariable=self.storage_full_preset_var,
                                                          state='readonly', width=10)
        self.storage_full_preset_dropdown.pack(side='left')
        self.storage_full_preset_dropdown.bind('<<ComboboxSelected>>', self.on_storage_full_preset_selected)
        # Initialize dropdown values
        self.update_storage_full_preset_dropdown()

        # Row 4: After X attacks option (in a frame for tight spacing)
        attacks_frame = ttk.Frame(control_frame)
        attacks_frame.grid(row=4, column=1, columnspan=4, sticky='w', pady=(5, 0))

        attacks_radio = ttk.Radiobutton(attacks_frame, text="After", variable=self.auto_pause_mode, value="loops")
        attacks_radio.pack(side='left')

        self.auto_pause_value = tk.StringVar(value="50")
        self.attacks_entry = ttk.Entry(attacks_frame, textvariable=self.auto_pause_value, width=6)
        self.attacks_entry.pack(side='left', padx=(3, 3))

        attacks_label = ttk.Label(attacks_frame, text="attacks", font=('Segoe UI', 9))
        attacks_label.pack(side='left')

        # Row 5: After X minutes option (in a frame for tight spacing)
        minutes_frame = ttk.Frame(control_frame)
        minutes_frame.grid(row=5, column=1, columnspan=4, sticky='w', pady=(5, 0))

        time_radio = ttk.Radiobutton(minutes_frame, text="After", variable=self.auto_pause_mode, value="time")
        time_radio.pack(side='left')

        self.minutes_entry = ttk.Entry(minutes_frame, textvariable=self.auto_pause_value, width=6)
        self.minutes_entry.pack(side='left', padx=(3, 3))

        minutes_label = ttk.Label(minutes_frame, text="minutes", font=('Segoe UI', 9))
        minutes_label.pack(side='left')

        # Hotkey info label (moved to row 6)
        hotkey_info = ttk.Label(control_frame, text="Hotkeys: F1=Pause/Resume | F2=Stop | F11=Fullscreen | ESC=Exit Program",
                               font=('Segoe UI', 8), foreground='gray')
        hotkey_info.grid(row=6, column=0, columnspan=6, pady=(8, 0))

    def create_loot_section(self, parent):
        """Create loot statistics section with improved layout"""
        # Loot Frame
        loot_frame = ttk.LabelFrame(parent, text="💰 Loot Statistics", padding="15")
        loot_frame.grid(row=4, column=0, columnspan=2, sticky='we', pady=(0, 15))
        self.loot_frame = loot_frame  # Store for collapsible

        # Configure grid for better responsive layout
        loot_frame.columnconfigure(1, weight=1)
        loot_frame.columnconfigure(3, weight=1)
        loot_frame.columnconfigure(4, weight=1)

        # Initialize loot tracking variables
        self.total_gold = 0
        self.total_elixir = 0
        self.total_dark_elixir = 0
        self.attacks_with_loot = 0
        self.skipped_bases = 0
        self.skip_ratio = 0.0

        # --- CSV-based total statistics with icons ---
        self.gold_img = ImageTk.PhotoImage(Image.open('assets/gold.png').resize((24, 24)))
        self.elixir_img = ImageTk.PhotoImage(Image.open('assets/elixir.png').resize((24, 24)))
        self.dark_img = ImageTk.PhotoImage(Image.open('assets/dark_elixir.png').resize((24, 24)))
        self.csv_gold = 0
        self.csv_elixir = 0
        self.csv_dark_elixir = 0
        self.csv_gold_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.gold_img, compound='left')
        self.csv_gold_label.grid(row=0, column=4, sticky=tk.W, padx=(30, 0))
        self.csv_elixir_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.elixir_img, compound='left')
        self.csv_elixir_label.grid(row=1, column=4, sticky=tk.W, padx=(30, 0))
        self.csv_dark_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.dark_img, compound='left')
        self.csv_dark_label.grid(row=2, column=4, sticky=tk.W, padx=(30, 0))
        self.update_csv_totals()

        # Loot statistics labels - current session
        ttk.Label(loot_frame, text="Total Gold:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.gold_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.gold_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(loot_frame, text="Total Elixir:", font=('Segoe UI', 10)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.elixir_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Total Dark Elixir:", font=('Segoe UI', 10)).grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.dark_elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.dark_elixir_label.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Attacks with Loot:", font=('Segoe UI', 10)).grid(row=3, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.attacks_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.attacks_label.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))

        # Skipped bases and skip/attack ratio
        # ttk.Label(loot_frame, text="Skipped Bases:").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        # self.skipped_label = ttk.Label(loot_frame, text="0", font=('Arial', 10))
        # self.skipped_label.grid(row=5, column=1, sticky=tk.W)

        # ttk.Label(loot_frame, text="Skip/Attack Ratio:").grid(row=6, column=0, sticky=tk.W, padx=(0, 10))
        # self.skip_ratio_label = ttk.Label(loot_frame, text="0.00", font=('Arial', 10))
        # self.skip_ratio_label.grid(row=6, column=1, sticky=tk.W)

        # Average loot per attack
        ttk.Label(loot_frame, text="Avg Gold/Attack:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(30, 10))
        self.avg_gold_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_gold_label.grid(row=0, column=3, sticky=tk.W)

        ttk.Label(loot_frame, text="Avg Elixir/Attack:", font=('Segoe UI', 10)).grid(row=1, column=2, sticky=tk.W, padx=(30, 10), pady=(5, 0))
        self.avg_elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_elixir_label.grid(row=1, column=3, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Avg Dark/Attack:", font=('Segoe UI', 10)).grid(row=2, column=2, sticky=tk.W, padx=(30, 10), pady=(5, 0))
        self.avg_dark_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_dark_label.grid(row=2, column=3, sticky=tk.W, pady=(5, 0))

        # Reload CSV stats button
        reload_csv_button = ttk.Button(loot_frame, text="Reload CSV Totals", command=self.update_csv_totals)
        reload_csv_button.grid(row=3, column=4, padx=(30, 0))

        # Reset loot button
        reset_loot_button = ttk.Button(loot_frame, text="Reset Loot Stats", command=self.reset_loot_stats)
        reset_loot_button.grid(row=4, column=0, columnspan=4, pady=(10, 0))

    def create_log_section(self, parent):
        # Log Frame
        log_frame = ttk.LabelFrame(parent, text="📝 Logs", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky='nsew', pady=(0, 10))
        self.log_frame = log_frame  # Store for collapsible
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)
        
        # Create notebook for tabs
        self.log_notebook = ttk.Notebook(log_frame)
        self.log_notebook.grid(row=0, column=0, sticky='nsew')
        
        # Bot Log Tab
        bot_log_frame = ttk.Frame(self.log_notebook)
        self.log_notebook.add(bot_log_frame, text="Bot Log")
        bot_log_frame.columnconfigure(0, weight=1)
        bot_log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(bot_log_frame, height=10, width=70)
        bot_log_scrollbar = ttk.Scrollbar(bot_log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=bot_log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky='nsew')
        bot_log_scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Debug Log Tab
        debug_log_frame = ttk.Frame(self.log_notebook)
        self.log_notebook.add(debug_log_frame, text="Debug Log")
        debug_log_frame.columnconfigure(0, weight=1)
        debug_log_frame.rowconfigure(0, weight=1)
        
        self.debug_text = tk.Text(debug_log_frame, height=10, width=70)
        debug_log_scrollbar = ttk.Scrollbar(debug_log_frame, orient="vertical", command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=debug_log_scrollbar.set)
        
        self.debug_text.grid(row=0, column=0, sticky='nsew')
        debug_log_scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Control buttons frame
        button_frame = ttk.Frame(log_frame)
        button_frame.grid(row=1, column=0, pady=(5, 0))
        
        # Clear buttons
        clear_bot_log_button = ttk.Button(button_frame, text="Clear Bot Log", command=self.clear_log)
        clear_bot_log_button.grid(row=0, column=0, padx=(0, 10))
        
        clear_debug_log_button = ttk.Button(button_frame, text="Clear Debug Log", command=self.clear_debug_log)
        clear_debug_log_button.grid(row=0, column=1)
        
    def log_message(self, message, level="info"):
        """Add message to log with timestamp and broadcast to web GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # Broadcast to web GUI
        if self.state_manager:
            self.state_manager.set("log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": level
            })
        
    def clear_log(self):
        """Clear the bot log text area"""
        self.log_text.delete(1.0, tk.END)
        
    def clear_debug_log(self):
        """Clear the debug log text area"""
        self.debug_text.delete(1.0, tk.END)
        
    def debug_message(self, message, level="debug"):
        """Add message to debug log with timestamp and broadcast to web GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        debug_entry = f"[{timestamp}] {message}\n"
        self.debug_text.insert(tk.END, debug_entry)
        self.debug_text.see(tk.END)

        # Broadcast to web GUI
        if self.state_manager:
            self.state_manager.set("debug_log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": level
            })

    def ocr_log(self, ocr_type, value, raw_value=None, confidence=None):
        """Log OCR reading to web GUI only (not to Tkinter to avoid spam)"""
        if self.state_manager:
            message = f"{ocr_type}: {value}"
            if raw_value is not None and raw_value != value:
                message += f" (raw: {raw_value})"
            if confidence is not None:
                message += f" [{confidence:.0f}%]"

            self.state_manager.set("ocr_log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": "info",
                "ocr_type": ocr_type,
                "value": value,
                "raw_value": raw_value,
                "confidence": confidence
            })

    def capture_console_output(self):
        """Capture console output and redirect to debug log"""
        import sys
        
        class ConsoleCapture:
            def __init__(self, gui):
                self.gui = gui
                self.original_stdout = sys.stdout
                self.original_stderr = sys.stderr
                
            def write(self, text):
                # Write to original console
                self.original_stdout.write(text)
                self.original_stdout.flush()
                
                # Also write to GUI debug log
                if text.strip():  # Only log non-empty lines
                    self.gui.root.after(0, lambda: self.gui.debug_message(text.strip()))
                    
            def flush(self):
                self.original_stdout.flush()

            def isatty(self):
                """Required for uvicorn logging compatibility."""
                return False

        # Set up console capture
        self.console_capture = ConsoleCapture(self)
        sys.stdout = self.console_capture
        sys.stderr = self.console_capture
        
    def update_timer(self):
        """Update the running time display"""
        if self.start_time and not self.bot_paused:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_label.config(text=time_str)
            
            # Calculate loops per hour
            if elapsed > 0:
                loops_per_hour = (self.loop_count / elapsed) * 3600
                self.rate_label.config(text=f"{loops_per_hour:.1f}")
        
        # Schedule next update
        self.root.after(1000, self.update_timer)
        
    def start_bot(self):
        """Start the bot with 3-second countdown"""
        try:
            # Validate settings
            self.validate_settings()
            
            # Disable start button during countdown
            self.start_button.config(state="disabled", text="Starting...")
            self.log_message("Starting bot in 3 seconds...")
            
            # Start countdown
            self.countdown_thread = threading.Thread(target=self.countdown_and_start, daemon=True)
            self.countdown_thread.start()
            
        except ValueError as e:
            messagebox.showerror("Settings Error", str(e))
            
    def countdown_and_start(self):
        """Countdown and then start the bot"""
        for i in range(3, 0, -1):
            # Check if bot was cancelled during countdown
            if not hasattr(self, 'bot_running') or self.bot_running is None:
                self.root.after(0, self.cancel_start)
                return
                
            self.root.after(0, lambda count=i: self.status_label.config(text=f"Starting in {count}...", foreground="orange"))
            self.root.after(0, lambda count=i: self.log_message(f"Starting in {count} seconds..."))
            time.sleep(1)
        
        # Check one more time before starting
        if not hasattr(self, 'bot_running') or self.bot_running is None:
            self.root.after(0, self.cancel_start)
            return
            
        # Start the bot
        self.root.after(0, self.actually_start_bot)
        
    def actually_start_bot(self):
        """Actually start the bot after countdown"""
        # Update bot state
        self.bot_running = True
        self.bot_paused = False
        self.start_time = time.time()
        self.loop_count = 0
        self.auto_pause_start_time = time.time()  # Track auto-pause timer

        # Update GUI
        self.status_label.config(text="RUNNING", foreground="green")
        self.quick_status_label.config(text="● Running", foreground="green")
        self.start_button.config(state="disabled", text="Start Bot")
        self.pause_button.config(state="normal")
        self.stop_button.config(state="normal")

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.update({
                "running": True,
                "paused": False,
                "status": "RUNNING",
                "loop_count": 0
            })

        # Start bot thread
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

        self.log_message("Bot started successfully")
            
    def stop_bot(self):
        """Stop the bot"""
        self.bot_running = False
        self.bot_paused = True
        self.start_time = None

        # Reset queue system
        try:
            import sys
            main_module = sys.modules.get('__main__')
            if main_module:
                queue_manager = getattr(main_module, 'queue_manager', None)
                if queue_manager:
                    queue_manager.reset_queue()
                    print("[GUI] Queue manager reset on bot stop")
        except Exception as e:
            print(f"[GUI] Error resetting queue manager: {e}")

        # Clear manual mode schedule
        if self.manual_mode_schedule:
            print(f"[GUI] Clearing {len(self.manual_mode_schedule)} manual tasks on bot stop")
            self.manual_mode_schedule = []
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()

        # Update GUI
        self.status_label.config(text="STOPPED", foreground="red")
        self.quick_status_label.config(text="● Stopped", foreground="red")
        self.start_button.config(state="normal", text="Start Bot")
        self.pause_button.config(state="disabled")
        self.stop_button.config(state="disabled")

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.update({
                "running": False,
                "paused": True,
                "status": "STOPPED"
            })

        self.log_message("Bot stopped")

    def cancel_start(self):
        """Cancel the countdown and reset start button"""
        self.bot_running = False
        self.status_label.config(text="PAUSED", foreground="red")
        self.quick_status_label.config(text="● Paused", foreground="red")
        self.start_button.config(state="normal", text="Start Bot")
        self.log_message("Bot start cancelled")

    def toggle_pause(self):
        """Toggle bot pause/resume"""
        if self.bot_running:
            self.bot_paused = not self.bot_paused

            if self.bot_paused:
                self.status_label.config(text="PAUSED", foreground="orange")
                self.quick_status_label.config(text="● Paused", foreground="orange")
                self.log_message("Bot paused")
            else:
                self.status_label.config(text="RUNNING", foreground="green")
                self.quick_status_label.config(text="● Running", foreground="green")
                self.log_message("Bot resumed")

            # Sync to state manager for web GUI
            if self.state_manager:
                self.state_manager.set("paused", self.bot_paused)
                self.state_manager.set("status", "PAUSED" if self.bot_paused else "RUNNING")

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11"""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)

        if self.is_fullscreen:
            print("[GUI] Fullscreen mode enabled")
        else:
            print("[GUI] Fullscreen mode disabled")

        return "break"  # Prevent event propagation

    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode with Escape"""
        # Only exit fullscreen if we're in fullscreen mode
        # Don't interfere with ESC hotkey for stopping bot
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes('-fullscreen', False)
            print("[GUI] Exited fullscreen mode")
            return "break"  # Prevent event propagation

    def validate_settings(self):
        """Validate all settings before starting bot"""
        try:
            min_resources = int(self.min_resources_var.get())
            if min_resources < 0:
                raise ValueError("Minimum resources must be positive")
                
            max_th = int(self.max_th_var.get())
            if max_th < 1 or max_th > 16:
                raise ValueError("Max Town Hall level must be between 1 and 16")
                
            # Auto pause settings validation
            break_interval = int(self.break_interval_var.get())
            if break_interval < 15 or break_interval > 120:
                raise ValueError("Break interval must be between 15 and 120 minutes")
                
            break_duration = int(self.break_duration_var.get())
            if break_duration < 1 or break_duration > 30:
                raise ValueError("Break duration must be between 1 and 30 minutes")
                
        except ValueError as e:
            raise ValueError(f"Invalid setting: {str(e)}")
            
    def save_settings(self, show_popup=False):
        """Save current settings to file, updating the current profile"""
        if self.is_saving:
            return  # Prevent recursive saving
        try:
            self.is_saving = True
            self.validate_settings()
            
            # Get current settings from GUI
            # Get achievement building target (convert display name to internal name)
            display_name = self.achievement_building_var.get()
            achievement_target = self.achievement_building_map.get(display_name, 'eagle_artillery')

            # Get achievement farm targeting mode (convert display name to internal name)
            mode_display_name = self.achievement_mode_var.get()
            achievement_target_mode = self.achievement_mode_map.get(mode_display_name, 'clumps')

            profile_settings = {
                'min_resources': int(self.min_resources_var.get()),
                'max_th_level': int(self.max_th_var.get()),
                'troop_counts': [int(var.get()) for var in self.troop_count_vars],
                'auto_pause_enabled': self.auto_pause_var.get(),
                'break_interval': int(self.break_interval_var.get()),
                'break_duration': int(self.break_duration_var.get()),
                'bb_collect_interval': int(self.bb_collect_interval_var.get()),
                'night_mode': self.night_mode,
                'ad_target_mode': self.ad_target_mode_var.get(),
                'attack_side_mode': self.attack_side_mode_var.get(),
                'lightning_damage': int(self.lightning_damage_var.get()),
                'reinforcements_enabled': self.reinforcements_var.get(),
                'description': self.profiles.get(self.current_profile, {}).get('description', ''),
                'queen_ability_timing': int(self.queen_ability_timing_var.get()),
                'king_ability_timing': int(self.king_ability_timing_var.get()),
                'warden_ability_timing': int(self.warden_ability_timing_var.get()),
                'rc_ability_timing': int(self.rc_ability_timing_var.get()),
                # Achievement Farm settings
                'achievement_target_building': achievement_target,
                'achievement_farm_target_mode': achievement_target_mode,
                'achievement_scan_eagle_artillery': self.achievement_eagle_var.get(),
                'achievement_scan_monolith': self.achievement_monolith_var.get(),
                'achievement_scan_xbow': self.achievement_xbow_var.get(),
                'achievement_scan_inferno_tower': self.achievement_inferno_var.get(),
                'achievement_scan_scattershot': self.achievement_scattershot_var.get(),
                'achievement_scan_spell_tower': self.achievement_spell_tower_var.get(),
                'achievement_scan_multi_archer_tower': self.achievement_multi_archer_var.get(),
                'achievement_scan_ricochet_cannon': self.achievement_ricochet_var.get(),
                'achievement_scan_firespitter': self.achievement_firespitter_var.get(),
                'achievement_scan_multi_gear_tower': self.achievement_multi_gear_var.get(),
                'achievement_priority_list': self.achievement_priority_list,
                'achievement_parallel_scan': self.achievement_parallel_scan_var.get(),
                # SGoblin Farm settings
                'sgoblin_cast_spells': self.sgoblin_cast_spells_var.get(),
                'sgoblin_use_wallbreakers': self.sgoblin_use_wallbreakers_var.get(),
                'sgoblin_skip_logging': self.sgoblin_skip_logging_var.get(),
                # SBarb Farm settings
                'sbarb_heroes_first': self.sbarb_heroes_first_var.get(),
                'sbarb_queen_arrow_spells': self.sbarb_queen_arrow_spells_var.get(),
                'sbarb_cast_spells': self.sbarb_cast_spells_var.get(),
                'sbarb_cast_spells_target_mode': self.sbarb_cast_spells_mode_map.get(self.sbarb_cast_spells_mode_var.get(), 'clumps'),
                'sbarb_turbo_deployment': self.sbarb_turbo_deployment_var.get(),
                # BB Gold settings
                'bb_gold_troop_mode': self.bb_gold_troop_mode_map.get(self.bb_gold_troop_mode_var.get(), 'night_witches'),
                'bb_gold_try_3_stars': self.bb_gold_try_3_stars_var.get()
            }

            # Load existing file data
            try:
                with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
            except Exception:
                file_data = {}
            
            # Initialize profiles if not present
            if 'profiles' not in file_data:
                file_data['profiles'] = {}
            
            # Update the current profile's settings
            file_data['profiles'][self.current_profile] = profile_settings
            file_data['current_profile'] = self.current_profile
            # Save global max storage settings
            file_data['max_gold_storage'] = int(self.max_gold_storage_var.get())
            file_data['max_elixir_storage'] = int(self.max_elixir_storage_var.get())
            file_data['max_dark_elixir_storage'] = int(self.max_dark_elixir_storage_var.get())
            file_data['max_bb_gold_storage'] = int(self.max_bb_gold_storage_var.get())
            file_data['max_bb_elixir_storage'] = int(self.max_bb_elixir_storage_var.get())
            file_data['bb_collect_interval'] = int(self.bb_collect_interval_var.get())

            # Save queue system settings
            queue_enabled_value = self.queue_enabled_var.get()
            print(f"[SAVE_SETTINGS] Saving queue_enabled: {queue_enabled_value}")
            file_data['queue_enabled'] = queue_enabled_value
            file_data['queue_mode'] = self.queue_mode_var.get()
            file_data['smart_mode_config'] = {
                'main_base_mode': self.smart_main_mode_var.get(),
                'storage_targets': {
                    'wait_for_de': self.smart_wait_de_var.get(),
                    'gold_threshold': int(self.smart_gold_threshold_var.get()),
                    'elixir_threshold': int(self.smart_elixir_threshold_var.get()),
                    'de_threshold': int(self.smart_de_threshold_var.get())
                },
                'bb_auto_select_enabled': self.smart_bb_auto_var.get(),
                'bb_gold_elixir_ratio': float(self.smart_bb_ratio_var.get()),
                'after_bb_behavior': self.smart_after_bb_var.get()
            }
            file_data['achievement_farm_end_config'] = {
                'enabled': self.achievement_end_enabled_var.get(),
                'duration_minutes': int(self.achievement_end_duration_var.get())
            }

            # Save to file
            with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2)
            
            # Update internal profiles
            self.profiles[self.current_profile] = profile_settings
            
            self.log_message("Settings saved.")
            if show_popup:
                messagebox.showinfo("Success", "Settings saved successfully!")
        except ValueError as e:
            messagebox.showerror("Settings Error", str(e))
        finally:
            self.is_saving = False

    def on_storage_preset_selected(self, event=None):
        """Handle storage preset selection"""
        preset_name = self.storage_preset_var.get()

        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' in settings and preset_name in settings['storage_presets']:
                preset = settings['storage_presets'][preset_name]

                # Update the storage values
                self.max_gold_storage_var.set(str(preset['max_gold_storage']))
                self.max_elixir_storage_var.set(str(preset['max_elixir_storage']))
                self.max_dark_elixir_storage_var.set(str(preset['max_dark_elixir_storage']))
                self.max_bb_gold_storage_var.set(str(preset.get('max_bb_gold_storage', 5000000)))
                self.max_bb_elixir_storage_var.set(str(preset.get('max_bb_elixir_storage', 5000000)))

                # Update active preset in settings
                settings['active_storage_preset'] = preset_name
                settings['max_gold_storage'] = preset['max_gold_storage']
                settings['max_elixir_storage'] = preset['max_elixir_storage']
                settings['max_dark_elixir_storage'] = preset['max_dark_elixir_storage']
                settings['max_bb_gold_storage'] = preset.get('max_bb_gold_storage', 5000000)
                settings['max_bb_elixir_storage'] = preset.get('max_bb_elixir_storage', 5000000)

                with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)

                self.log_message(f"Loaded storage preset: {preset_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset: {e}")

    def save_storage_preset(self):
        """Save current storage values to the selected preset"""
        preset_name = self.storage_preset_var.get()

        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' not in settings:
                settings['storage_presets'] = {}

            # Update preset with current values
            settings['storage_presets'][preset_name] = {
                'max_gold_storage': int(self.max_gold_storage_var.get()),
                'max_elixir_storage': int(self.max_elixir_storage_var.get()),
                'max_dark_elixir_storage': int(self.max_dark_elixir_storage_var.get()),
                'max_bb_gold_storage': int(self.max_bb_gold_storage_var.get()),
                'max_bb_elixir_storage': int(self.max_bb_elixir_storage_var.get())
            }

            with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

            self.log_message(f"Saved storage preset: {preset_name}")
            messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preset: {e}")

    def create_storage_preset(self):
        """Create a new storage preset"""
        from tkinter import simpledialog

        preset_name = simpledialog.askstring("New Preset", "Enter preset name:")
        if not preset_name:
            return

        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' not in settings:
                settings['storage_presets'] = {}

            # Check if preset already exists
            if preset_name in settings['storage_presets']:
                messagebox.showerror("Error", f"Preset '{preset_name}' already exists!")
                return

            # Create new preset with current values
            settings['storage_presets'][preset_name] = {
                'max_gold_storage': int(self.max_gold_storage_var.get()),
                'max_elixir_storage': int(self.max_elixir_storage_var.get()),
                'max_dark_elixir_storage': int(self.max_dark_elixir_storage_var.get()),
                'max_bb_gold_storage': int(self.max_bb_gold_storage_var.get()),
                'max_bb_elixir_storage': int(self.max_bb_elixir_storage_var.get())
            }

            with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

            # Update dropdowns
            self.update_storage_preset_dropdown()
            self.update_storage_full_preset_dropdown()
            self.storage_preset_var.set(preset_name)

            # Sync to state manager for web GUI
            if self.state_manager:
                self.state_manager.set("storage_presets", self.get_storage_presets())

            self.log_message(f"Created storage preset: {preset_name}")
            messagebox.showinfo("Success", f"Preset '{preset_name}' created!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create preset: {e}")

    def delete_storage_preset(self):
        """Delete the selected storage preset"""
        preset_name = self.storage_preset_var.get()

        # Don't allow deleting default presets
        if preset_name in ['main', 'alt']:
            messagebox.showerror("Error", "Cannot delete default presets!")
            return

        if not messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            return

        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' in settings and preset_name in settings['storage_presets']:
                del settings['storage_presets'][preset_name]

                with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)

                # Update dropdowns and select first preset
                self.update_storage_preset_dropdown()
                self.update_storage_full_preset_dropdown()
                if self.storage_preset_dropdown['values']:
                    self.storage_preset_var.set(self.storage_preset_dropdown['values'][0])
                    self.on_storage_preset_selected()

                # Sync to state manager for web GUI
                if self.state_manager:
                    self.state_manager.set("storage_presets", self.get_storage_presets())

                self.log_message(f"Deleted storage preset: {preset_name}")
                messagebox.showinfo("Success", f"Preset '{preset_name}' deleted!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete preset: {e}")

    def update_storage_preset_dropdown(self):
        """Update the storage preset dropdown with current presets"""
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' in settings:
                preset_names = list(settings['storage_presets'].keys())
                self.storage_preset_dropdown['values'] = preset_names
        except Exception as e:
            print(f"Error updating preset dropdown: {e}")

    def update_storage_full_preset_dropdown(self):
        """Update the storage full preset dropdown with current presets"""
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if 'storage_presets' in settings:
                preset_names = list(settings['storage_presets'].keys())
                self.storage_full_preset_dropdown['values'] = preset_names
                # Set to current value if valid, otherwise first preset
                current = self.storage_full_preset_var.get()
                if current not in preset_names and preset_names:
                    self.storage_full_preset_var.set(preset_names[0])
        except Exception as e:
            print(f"Error updating storage full preset dropdown: {e}")

    def on_storage_full_preset_selected(self, event=None):
        """Handle storage full preset selection"""
        self.save_settings()
        # Also sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.set("storage_full_preset", self.storage_full_preset_var.get())

    def get_storage_presets(self):
        """Get storage presets from settings file for state sync"""
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            return settings.get('storage_presets', {
                'main': {
                    'max_gold_storage': 18000000,
                    'max_elixir_storage': 14000000,
                    'max_dark_elixir_storage': 240000,
                    'max_bb_gold_storage': 5000000,
                    'max_bb_elixir_storage': 5000000
                },
                'alt': {
                    'max_gold_storage': 18000000,
                    'max_elixir_storage': 14000000,
                    'max_dark_elixir_storage': 240000,
                    'max_bb_gold_storage': 5000000,
                    'max_bb_elixir_storage': 5000000
                }
            })
        except Exception:
            return {}

    def load_settings(self):
        """Load settings from file, including all profiles and global settings"""
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Get hard-coded profiles
            hardcoded_profiles = self.get_hardcoded_profiles()
            
            # Initialize profiles with hard-coded defaults
            profiles = hardcoded_profiles.copy()
            
            # Add Custom profile (load from file if exists, otherwise use default)
            if 'profiles' in settings and 'Custom' in settings['profiles']:
                profiles['Custom'] = settings['profiles']['Custom']
            else:
                profiles['Custom'] = {
                    'min_resources': 1200000,
                    'max_th_level': 15,
                    'troop_counts': [7, 8, 0, 0, 0, 0, 0],
                    'auto_pause_enabled': True,
                    'break_interval': 45,
                    'break_duration': 5,
                    'lightning_damage': 300,
                    'ad_target_mode': 'level',
                    'attack_side_mode': 'random',
                    'queen_ability_timing': 15,
                    'king_ability_timing': 15,
                    'warden_ability_timing': 15,
                    'rc_ability_timing': 15,
                    'description': 'Custom settings - modify as needed'
                }
            
            # Update hard-coded profiles with any user modifications from JSON
            if 'profiles' in settings:
                for profile_name in ['Farming', 'Trophy Push', 'Derank', 'SGoblin Farm', 'SBarb Farm', 'BB Elixir', 'BB Gold', 'Achievement Farm']:
                    if profile_name in settings['profiles']:
                        profiles[profile_name].update(settings['profiles'][profile_name])
            
            self.profiles = profiles
            
            # Get current profile (default to Custom if not specified)
            self.current_profile = settings.get('current_profile', 'Custom')
            
            # Load global settings
            self.global_reinforcements_enabled = settings.get('reinforcements_enabled', False)
            self.night_mode = settings.get('night_mode', False)
            self.overlay_enabled = settings.get('overlay_enabled', False)
            self.overlay_hide_low_conf = settings.get('overlay_hide_low_conf', False)
            self.skip_on_th_fail = settings.get('skip_on_th_fail', False)
            self.use_second_monitor = settings.get('use_second_monitor', False)
            self.parallel_scanning = settings.get('parallel_scanning', False)
            self.gpu_scanning = settings.get('gpu_scanning', False)

            # Load global max storage settings
            self.max_gold_storage_var = tk.StringVar(value=str(settings.get('max_gold_storage', 18000000)))
            self.max_elixir_storage_var = tk.StringVar(value=str(settings.get('max_elixir_storage', 14000000)))
            self.max_dark_elixir_storage_var = tk.StringVar(value=str(settings.get('max_dark_elixir_storage', 240000)))
            self.max_bb_gold_storage_var = tk.StringVar(value=str(settings.get('max_bb_gold_storage', 5000000)))
            self.max_bb_elixir_storage_var = tk.StringVar(value=str(settings.get('max_bb_elixir_storage', 5000000)))

            # Load queue system settings with defaults
            if 'queue_enabled' not in settings:
                settings['queue_enabled'] = False
            if 'queue_mode' not in settings:
                settings['queue_mode'] = 'smart'
            if 'smart_mode_config' not in settings:
                settings['smart_mode_config'] = {
                    'main_base_mode': 'SBarb Farm',
                    'storage_targets': {
                        'wait_for_de': False,
                        'gold_threshold': 100,
                        'elixir_threshold': 100,
                        'de_threshold': 100
                    },
                    'bb_auto_select_enabled': True,
                    'bb_gold_elixir_ratio': 3.0,
                    'after_bb_behavior': 'stop'
                }
            if 'manual_mode_schedule' not in settings:
                settings['manual_mode_schedule'] = []
            if 'achievement_farm_end_config' not in settings:
                settings['achievement_farm_end_config'] = {
                    'enabled': False,
                    'duration_minutes': 20
                }

            # Load storage presets with defaults
            if 'storage_presets' not in settings:
                settings['storage_presets'] = {
                    'main': {
                        'max_gold_storage': 18000000,
                        'max_elixir_storage': 14000000,
                        'max_dark_elixir_storage': 240000,
                        'max_bb_gold_storage': 5000000,
                        'max_bb_elixir_storage': 5000000
                    },
                    'alt': {
                        'max_gold_storage': 18000000,
                        'max_elixir_storage': 14000000,
                        'max_dark_elixir_storage': 240000,
                        'max_bb_gold_storage': 5000000,
                        'max_bb_elixir_storage': 5000000
                    }
                }
            if 'active_storage_preset' not in settings:
                settings['active_storage_preset'] = 'main'

            return settings
        except Exception:
            # Defaults if file doesn't exist or is corrupted
            hardcoded_profiles = self.get_hardcoded_profiles()
            profiles = hardcoded_profiles.copy()
            profiles['Custom'] = {
                'min_resources': 1200000,
                'max_th_level': 15,
                'troop_counts': [7, 8, 0, 0, 0, 0, 0],
                'auto_pause_enabled': True,
                'break_interval': 45,
                'break_duration': 5,
                'lightning_damage': 300,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'queen_ability_timing': 15,
                'king_ability_timing': 15,
                'warden_ability_timing': 15,
                'rc_ability_timing': 15
            }
            # Save initial profiles to file
            try:
                with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                    json.dump({
                        'profiles': profiles,
                        'current_profile': 'Custom',
                        'reinforcements_enabled': False,
                        'night_mode': False,
                        'use_second_monitor': False,
                        'queue_enabled': False,
                        'queue_mode': 'smart',
                        'smart_mode_config': {
                            'main_base_mode': 'SBarb Farm',
                            'storage_targets': {
                                'wait_for_de': False,
                                'gold_threshold': 100,
                                'elixir_threshold': 100,
                                'de_threshold': 100
                            },
                            'bb_auto_select_enabled': True,
                            'bb_gold_elixir_ratio': 3.0,
                            'after_bb_behavior': 'stop'
                        },
                        'manual_mode_schedule': [],
                        'achievement_farm_end_config': {
                            'enabled': False,
                            'duration_minutes': 20
                        }
                    }, f, indent=2)
            except Exception:
                pass

            self.profiles = profiles
            self.current_profile = 'Custom'
            self.global_reinforcements_enabled = False
            self.night_mode = False
            self.overlay_enabled = False
            self.overlay_hide_low_conf = False
            self.skip_on_th_fail = False
            self.use_second_monitor = False
            self.parallel_scanning = False
            self.gpu_scanning = False

            return {
                'profiles': profiles,
                'current_profile': 'Custom',
                'reinforcements_enabled': False,
                'night_mode': False,
                'overlay_enabled': False,
                'overlay_hide_low_conf': False,
                'min_resources': 1200000,
                'max_th_level': 15,
                'troop_counts': [7, 8, 0, 0, 0, 0, 0],
                'auto_pause_enabled': True,
                'break_interval': 45,
                'break_duration': 5,
                'ad_target_mode': 'level',
                'attack_side_mode': 'random',
                'lightning_damage': 300,
                'queue_enabled': False,
                'queue_mode': 'smart',
                'smart_mode_config': {
                    'main_base_mode': 'SBarb Farm',
                    'storage_targets': {
                        'wait_for_de': False,
                        'gold_threshold': 100,
                        'elixir_threshold': 100,
                        'de_threshold': 100
                    },
                    'bb_auto_select_enabled': True,
                    'bb_gold_elixir_ratio': 3.0,
                    'after_bb_behavior': 'stop'
                },
                'manual_mode_schedule': [],
                'achievement_farm_end_config': {
                    'enabled': False,
                    'duration_minutes': 20
                }
            }
    
    def update_settings_from_file(self):
        """Update GUI settings from file without triggering automatic saves"""
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                file_settings = json.load(f)
            
            # Temporarily disable automatic saving
            self.is_saving = True
            
            # Update GUI variables with file settings
            if 'min_resources' in file_settings:
                self.min_resources_var.set(file_settings['min_resources'])
            if 'max_th_level' in file_settings:
                self.max_th_var.set(file_settings['max_th_level'])
            if 'troop_counts' in file_settings:
                troop_counts = file_settings['troop_counts']
                for i in range(min(7, len(troop_counts))):
                    self.troop_count_vars[i].set(str(troop_counts[i]))
            if 'lightning_damage' in file_settings:
                self.lightning_damage_var.set(file_settings['lightning_damage'])
            if 'auto_pause_enabled' in file_settings:
                self.auto_pause_var.set(file_settings['auto_pause_enabled'])
            if 'break_interval' in file_settings:
                self.break_interval_var.set(file_settings['break_interval'])
            if 'break_duration' in file_settings:
                self.break_duration_var.set(file_settings['break_duration'])
            if 'current_profile' in file_settings:
                self.current_profile = file_settings['current_profile']
                self.profile_var.set(self.current_profile)
                self.update_profile_description()
            
            # Update internal settings
            # self.settings.update(file_settings) # This line is removed
            
            self.log_message("Settings updated from file")
            
        except Exception as e:
            self.log_message(f"Error updating settings from file: {e}")
        finally:
            self.is_saving = False
        
    def open_template_tools(self):
        """Open template capture tools"""
        import subprocess
        try:
            subprocess.Popen(['python', 'capture_templates.py'])
            self.log_message("Template tools opened")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open template tools: {e}")
            
    def run_bot(self):
        """Main bot loop - this will be called from main.py"""
        # This method will be overridden by the main bot
        pass
        
    def update_loop_count(self, count):
        """Update loop count from main bot"""
        self.loop_count = count
        self.loop_label.config(text=str(count))

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.set("loop_count", count)

    def update_bb_gold_state(self, state_name):
        """Update BB Gold state display from main bot (thread-safe)"""
        # Color mapping for different states (dark mode compatible)
        state_colors = {
            'IN_BASE': '#4A9EFF',          # Light blue
            'SEARCHING': '#FFA500',        # Orange
            'ATTACK_READY': '#BB86FC',     # Light purple
            'BATTLE_ACTIVE': '#03DAC6',    # Cyan/teal
            'BATTLE_ENDING': '#00C853',    # Light green
            'END_SCREEN': '#4A9EFF',       # Light blue
            'RETURNING_HOME': '#4A9EFF',   # Light blue
            'ERROR_RECOVERY': '#FF5252'    # Light red
        }

        # Get color for this state
        color = state_colors.get(state_name, '#B0B0B0')  # Light gray default

        # Queue update to main GUI thread (proper threading)
        self.root.after(0, self._update_bb_state_label, state_name, color)

    def _update_bb_state_label(self, state_name, color):
        """Internal method - runs on GUI thread"""
        self.bb_state_label.config(text=state_name, foreground=color)

    def get_settings(self):
        """Get current settings for main bot"""
        # Get achievement building target (convert display name to internal name)
        display_name = self.achievement_building_var.get()
        achievement_target = self.achievement_building_map.get(display_name, 'eagle_artillery')

        # Get achievement farm targeting mode (convert display name to internal name)
        mode_display_name = self.achievement_mode_var.get()
        achievement_target_mode = self.achievement_mode_map.get(mode_display_name, 'clumps')

        return {
            'min_resources': int(self.min_resources_var.get()),
            'max_th_level': int(self.max_th_var.get()),
            'troop_counts': [int(var.get()) for var in self.troop_count_vars],
            'auto_pause_enabled': self.auto_pause_var.get(),
            'break_interval': int(self.break_interval_var.get()),
            'break_duration': int(self.break_duration_var.get()),
            'bb_collect_interval': int(self.bb_collect_interval_var.get()),
            'night_mode': self.night_mode,
            'overlay_hide_low_conf': self.overlay_hide_low_conf_var.get(),
            'ad_target_mode': self.ad_target_mode_var.get(),
            'attack_side_mode': self.attack_side_mode_var.get(),
            'lightning_damage': int(self.lightning_damage_var.get()),
            'reinforcements_enabled': self.reinforcements_var.get(),
            'current_profile': self.current_profile,
            'derank_mode': self.current_profile == 'Derank',
            'sgoblin_farm_mode': self.current_profile == 'SGoblin Farm',
            'sbarb_farm_mode': self.current_profile == 'SBarb Farm',
            'bb_elixir_mode': self.current_profile == 'BB Elixir',
            'bb_gold_mode': self.current_profile == 'BB Gold',
            'achievement_farm_mode': self.current_profile == 'Achievement Farm',
            'achievement_target_building': achievement_target,
            'achievement_farm_target_mode': achievement_target_mode,
            'achievement_scan_eagle_artillery': self.achievement_eagle_var.get(),
            'achievement_scan_monolith': self.achievement_monolith_var.get(),
            'achievement_scan_xbow': self.achievement_xbow_var.get(),
            'achievement_scan_inferno_tower': self.achievement_inferno_var.get(),
            'achievement_scan_scattershot': self.achievement_scattershot_var.get(),
            'achievement_scan_spell_tower': self.achievement_spell_tower_var.get(),
            'achievement_scan_multi_archer_tower': self.achievement_multi_archer_var.get(),
            'achievement_scan_ricochet_cannon': self.achievement_ricochet_var.get(),
            'achievement_scan_firespitter': self.achievement_firespitter_var.get(),
            'achievement_scan_multi_gear_tower': self.achievement_multi_gear_var.get(),
            'achievement_priority_list': self.achievement_priority_list,
            'achievement_parallel_scan': self.achievement_parallel_scan_var.get(),
            'sgoblin_cast_spells': self.sgoblin_cast_spells_var.get(),
            'sgoblin_use_wallbreakers': self.sgoblin_use_wallbreakers_var.get(),
            'sgoblin_skip_logging': self.sgoblin_skip_logging_var.get(),
            'sbarb_heroes_first': self.sbarb_heroes_first_var.get(),
            'sbarb_queen_arrow_spells': self.sbarb_queen_arrow_spells_var.get(),
            'sbarb_cast_spells': self.sbarb_cast_spells_var.get(),
            'sbarb_cast_spells_target_mode': self.sbarb_cast_spells_mode_map.get(self.sbarb_cast_spells_mode_var.get(), 'clumps'),
            'sbarb_turbo_deployment': self.sbarb_turbo_deployment_var.get(),
            'bb_gold_troop_mode': self.bb_gold_troop_mode_map.get(self.bb_gold_troop_mode_var.get(), 'night_witches'),
            'bb_gold_dragon_debug_positions': self.bb_gold_dragon_debug_var.get(),
            'bb_gold_try_3_stars': self.bb_gold_try_3_stars_var.get(),
            'queen_ability_timing': int(self.queen_ability_timing_var.get()),
            'king_ability_timing': int(self.king_ability_timing_var.get()),
            'warden_ability_timing': int(self.warden_ability_timing_var.get()),
            'rc_ability_timing': int(self.rc_ability_timing_var.get()),
            'auto_pause_mode': self.auto_pause_mode.get(),
            'auto_pause_value': int(self.auto_pause_value.get()) if self.auto_pause_value.get().isdigit() else 50,
            'storage_full_gold': self.storage_full_gold_var.get(),
            'storage_full_elixir': self.storage_full_elixir_var.get(),
            'storage_full_de': self.storage_full_de_var.get(),
            'storage_full_preset': self.storage_full_preset_var.get(),
            # Queue system settings
            'queue_enabled': self.queue_enabled_var.get(),
            'queue_mode': self.queue_mode_var.get(),
            'smart_mode_config': {
                'main_base_mode': self.smart_main_mode_var.get(),
                'storage_targets': {
                    'wait_for_de': self.smart_wait_de_var.get(),
                    'gold_threshold': int(self.smart_gold_threshold_var.get()),
                    'elixir_threshold': int(self.smart_elixir_threshold_var.get()),
                    'de_threshold': int(self.smart_de_threshold_var.get())
                },
                'bb_auto_select_enabled': self.smart_bb_auto_var.get(),
                'bb_gold_elixir_ratio': float(self.smart_bb_ratio_var.get()),
                'after_bb_behavior': self.smart_after_bb_var.get()
            },
            'achievement_farm_end_config': {
                'enabled': self.achievement_end_enabled_var.get(),
                'duration_minutes': int(self.achievement_end_duration_var.get())
            },
            'manual_mode_schedule': getattr(self, 'manual_mode_schedule', []),
            # Max storage values for percentage calculations
            'max_gold_storage': int(self.max_gold_storage_var.get()),
            'max_elixir_storage': int(self.max_elixir_storage_var.get()),
            'max_dark_elixir_storage': int(self.max_dark_elixir_storage_var.get()),
            'max_bb_gold_storage': int(self.max_bb_gold_storage_var.get()),
            'max_bb_elixir_storage': int(self.max_bb_elixir_storage_var.get()),
            # Storage presets (needed for storage_full_preset lookup)
            'storage_presets': self.get_storage_presets()
        }
    
    def on_profile_changed(self, event):
        """Callback when profile is changed in the dropdown."""
        selected_profile = self.profile_var.get()
        self.current_profile = selected_profile

        # Temporarily disable saving while updating visibility
        # (setting checkbox values triggers commands that call save_settings)
        was_saving = self.is_saving
        self.is_saving = True

        self.update_profile_description()
        self.update_achievement_building_visibility()
        self.update_sgoblin_spell_casting_visibility()
        self.update_sbarb_deployment_visibility()
        self.update_bb_gold_visibility()
        self.update_priority_section_visibility()
        self.log_message(f"Profile changed to: {selected_profile}")
        # Update visibility of settings widgets based on new profile
        self.update_attack_section_visibility()
        self.update_army_section_visibility()
        # Don't auto-apply - user needs to click "Apply Profile" button

        # Restore saving state
        self.is_saving = was_saving

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.set("current_profile", selected_profile)

    def update_achievement_building_visibility(self):
        """Show/hide achievement building dropdown based on current profile"""
        current_profile = self.profile_var.get()

        if current_profile == 'Achievement Farm':
            # Show achievement building dropdown
            if not self.achievement_building_row_visible:
                self.achievement_building_label.grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
                self.achievement_building_dropdown.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))
                # Show targeting mode dropdown on row 3
                self.achievement_mode_label.grid(row=3, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
                self.achievement_mode_dropdown.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))
                self.achievement_building_row_visible = True

                # Set initial values from profile if available
                if current_profile in self.profiles:
                    target = self.profiles[current_profile].get('achievement_target_building', 'eagle_artillery')
                    display_name = self.achievement_building_reverse_map.get(target, 'Eagle Artillery')
                    self.achievement_building_var.set(display_name)

                    mode = self.profiles[current_profile].get('achievement_farm_target_mode', 'clumps')
                    mode_display_name = self.achievement_mode_reverse_map.get(mode, 'Clumps')
                    self.achievement_mode_var.set(mode_display_name)

                    # Set checkbox values from profile (uses full key names to match Web GUI)
                    self.achievement_eagle_var.set(self.profiles[current_profile].get('achievement_scan_eagle_artillery', True))
                    self.achievement_monolith_var.set(self.profiles[current_profile].get('achievement_scan_monolith', True))
                    self.achievement_xbow_var.set(self.profiles[current_profile].get('achievement_scan_xbow', True))
                    self.achievement_inferno_var.set(self.profiles[current_profile].get('achievement_scan_inferno_tower', True))
                    self.achievement_scattershot_var.set(self.profiles[current_profile].get('achievement_scan_scattershot', True))
                    self.achievement_spell_tower_var.set(self.profiles[current_profile].get('achievement_scan_spell_tower', True))
                    self.achievement_multi_archer_var.set(self.profiles[current_profile].get('achievement_scan_multi_archer_tower', True))
                    self.achievement_ricochet_var.set(self.profiles[current_profile].get('achievement_scan_ricochet_cannon', True))
                    self.achievement_firespitter_var.set(self.profiles[current_profile].get('achievement_scan_firespitter', True))
                    self.achievement_multi_gear_var.set(self.profiles[current_profile].get('achievement_scan_multi_gear_tower', True))

                    # Load priority list
                    self.achievement_priority_list = self.profiles[current_profile].get('achievement_priority_list', [
                        'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                        'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
                    ])
                    self.update_priority_listbox()

                # Show building checkboxes on rows 4-14
                self.achievement_buildings_label.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
                self.achievement_eagle_check.grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_monolith_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_xbow_check.grid(row=7, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_inferno_check.grid(row=8, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_scattershot_check.grid(row=9, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_spell_tower_check.grid(row=10, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_multi_archer_check.grid(row=11, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_ricochet_check.grid(row=12, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_firespitter_check.grid(row=13, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
                self.achievement_multi_gear_check.grid(row=14, column=0, columnspan=3, sticky=tk.W, padx=(20, 0))
        else:
            # Hide achievement building dropdown and checkboxes
            # Always hide regardless of flag state (grid_forget is safe to call on non-gridded widgets)
            self.achievement_building_label.grid_forget()
            self.achievement_building_dropdown.grid_forget()
            self.achievement_mode_label.grid_forget()
            self.achievement_mode_dropdown.grid_forget()
            self.achievement_buildings_label.grid_forget()
            self.achievement_eagle_check.grid_forget()
            self.achievement_monolith_check.grid_forget()
            self.achievement_xbow_check.grid_forget()
            self.achievement_inferno_check.grid_forget()
            self.achievement_scattershot_check.grid_forget()
            self.achievement_spell_tower_check.grid_forget()
            self.achievement_multi_archer_check.grid_forget()
            self.achievement_ricochet_check.grid_forget()
            self.achievement_firespitter_check.grid_forget()
            self.achievement_multi_gear_check.grid_forget()
            self.achievement_building_row_visible = False

    def update_sgoblin_spell_casting_visibility(self):
        """Show/hide SGoblin spell casting and wall breaker checkboxes based on current profile"""
        current_profile = self.profile_var.get()

        if current_profile == 'SGoblin Farm':
            # Show spell casting checkbox
            if not self.sgoblin_cast_spells_row_visible:
                self.sgoblin_cast_spells_check.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))
                self.sgoblin_cast_spells_row_visible = True

                # Set initial value from profile if available
                if current_profile in self.profiles:
                    cast_spells = self.profiles[current_profile].get('sgoblin_cast_spells', False)
                    self.sgoblin_cast_spells_var.set(cast_spells)

            # Show wall breaker checkbox
            if not self.sgoblin_use_wallbreakers_row_visible:
                self.sgoblin_use_wallbreakers_check.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sgoblin_use_wallbreakers_row_visible = True

                # Set initial value from profile if available
                if current_profile in self.profiles:
                    use_wallbreakers = self.profiles[current_profile].get('sgoblin_use_wallbreakers', False)
                    self.sgoblin_use_wallbreakers_var.set(use_wallbreakers)

            # Show skip logging checkbox
            if not self.sgoblin_skip_logging_row_visible:
                self.sgoblin_skip_logging_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sgoblin_skip_logging_row_visible = True

                # Set initial value from profile if available
                if current_profile in self.profiles:
                    skip_logging = self.profiles[current_profile].get('sgoblin_skip_logging', False)
                    self.sgoblin_skip_logging_var.set(skip_logging)
        else:
            # Hide spell casting checkbox
            # Always hide regardless of flag state (grid_forget is safe to call on non-gridded widgets)
            self.sgoblin_cast_spells_check.grid_forget()
            self.sgoblin_cast_spells_row_visible = False

            # Hide wall breaker checkbox
            self.sgoblin_use_wallbreakers_check.grid_forget()
            self.sgoblin_use_wallbreakers_row_visible = False

            # Hide skip logging checkbox
            self.sgoblin_skip_logging_check.grid_forget()
            self.sgoblin_skip_logging_row_visible = False

    def update_sbarb_deployment_visibility(self):
        """Show/hide SBarb Farm checkboxes based on current profile and turbo mode"""
        current_profile = self.profile_var.get()

        if current_profile == 'SBarb Farm':
            # Get turbo mode state
            turbo_enabled = self.sbarb_turbo_deployment_var.get()

            # Set initial values from profile if available
            if current_profile in self.profiles:
                turbo_deployment = self.profiles[current_profile].get('sbarb_turbo_deployment', False)
                self.sbarb_turbo_deployment_var.set(turbo_deployment)
                turbo_enabled = turbo_deployment

            # ALWAYS show turbo deployment checkbox FIRST (row 5)
            if not self.sbarb_turbo_deployment_row_visible:
                self.sbarb_turbo_deployment_check.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))
                self.sbarb_turbo_deployment_row_visible = True

            # Show/hide other options based on turbo mode
            if turbo_enabled:
                # Turbo mode: hide heroes first, queen arrow (turbo has fixed logic for these)
                self.sbarb_heroes_first_check.grid_forget()
                self.sbarb_heroes_first_row_visible = False

                self.sbarb_queen_arrow_spells_check.grid_forget()
                self.sbarb_queen_arrow_spells_row_visible = False

                # Keep cast spells visible - turbo mode uses this setting
                if not self.sbarb_cast_spells_row_visible:
                    self.sbarb_cast_spells_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                    self.sbarb_cast_spells_row_visible = True

                    if current_profile in self.profiles:
                        cast_spells = self.profiles[current_profile].get('sbarb_cast_spells', False)
                        self.sbarb_cast_spells_var.set(cast_spells)
                        # Also load the targeting mode
                        target_mode = self.profiles[current_profile].get('sbarb_cast_spells_target_mode', 'clumps')
                        display_mode = self.sbarb_cast_spells_mode_reverse_map.get(target_mode, 'Clumps')
                        self.sbarb_cast_spells_mode_var.set(display_mode)
            else:
                # Standard mode: show all options
                # Show heroes first checkbox
                if not self.sbarb_heroes_first_row_visible:
                    self.sbarb_heroes_first_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                    self.sbarb_heroes_first_row_visible = True

                    if current_profile in self.profiles:
                        heroes_first = self.profiles[current_profile].get('sbarb_heroes_first', False)
                        self.sbarb_heroes_first_var.set(heroes_first)

                # Show queen arrow spells checkbox
                if not self.sbarb_queen_arrow_spells_row_visible:
                    self.sbarb_queen_arrow_spells_check.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                    self.sbarb_queen_arrow_spells_row_visible = True

                    if current_profile in self.profiles:
                        queen_arrow = self.profiles[current_profile].get('sbarb_queen_arrow_spells', False)
                        self.sbarb_queen_arrow_spells_var.set(queen_arrow)

                # Show achievement building spell casting checkbox
                if not self.sbarb_cast_spells_row_visible:
                    self.sbarb_cast_spells_check.grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                    self.sbarb_cast_spells_row_visible = True

                    if current_profile in self.profiles:
                        cast_spells = self.profiles[current_profile].get('sbarb_cast_spells', False)
                        self.sbarb_cast_spells_var.set(cast_spells)
                        # Also load the targeting mode
                        target_mode = self.profiles[current_profile].get('sbarb_cast_spells_target_mode', 'clumps')
                        display_mode = self.sbarb_cast_spells_mode_reverse_map.get(target_mode, 'Clumps')
                        self.sbarb_cast_spells_mode_var.set(display_mode)

            # Update targeting mode visibility (depends on cast spells state)
            self.update_sbarb_cast_spells_mode_visibility()
        else:
            # Hide all SBarb-specific options
            self.sbarb_turbo_deployment_check.grid_forget()
            self.sbarb_turbo_deployment_row_visible = False

            self.sbarb_heroes_first_check.grid_forget()
            self.sbarb_heroes_first_row_visible = False

            self.sbarb_queen_arrow_spells_check.grid_forget()
            self.sbarb_queen_arrow_spells_row_visible = False

            self.sbarb_cast_spells_check.grid_forget()
            self.sbarb_cast_spells_row_visible = False

            self.sbarb_cast_spells_mode_frame.grid_forget()
            self.sbarb_cast_spells_mode_row_visible = False

    def on_turbo_mode_toggled(self):
        """Called when turbo deployment checkbox is toggled - updates visibility and saves"""
        self.on_turbo_mode_changed()
        # Don't save if we're in the middle of loading/applying a profile
        if not self.is_saving:
            self.save_settings()

    def on_sbarb_cast_spells_toggled(self):
        """Called when SBarb cast spells checkbox is toggled - updates visibility and saves"""
        self.update_sbarb_cast_spells_mode_visibility()
        # Don't save if we're in the middle of loading/applying a profile
        if not self.is_saving:
            self.save_settings()

    def update_sbarb_cast_spells_mode_visibility(self):
        """Show/hide SBarb cast spells targeting mode dropdown based on checkbox state"""
        current_profile = self.profile_var.get()
        if current_profile != 'SBarb Farm':
            return

        cast_spells_enabled = self.sbarb_cast_spells_var.get()

        if cast_spells_enabled:
            # Show targeting mode dropdown below the checkbox
            if not self.sbarb_cast_spells_mode_row_visible:
                # Get current row of cast spells checkbox and add dropdown below it
                turbo_enabled = self.sbarb_turbo_deployment_var.get()
                if turbo_enabled:
                    # Turbo mode: cast spells is at row 6, mode dropdown at row 7
                    self.sbarb_cast_spells_mode_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
                else:
                    # Standard mode: cast spells is at row 8, mode dropdown at row 9
                    self.sbarb_cast_spells_mode_frame.grid(row=9, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
                self.sbarb_cast_spells_mode_row_visible = True
        else:
            # Hide targeting mode dropdown
            self.sbarb_cast_spells_mode_frame.grid_forget()
            self.sbarb_cast_spells_mode_row_visible = False

    def on_turbo_mode_changed(self):
        """Updates option visibility based on turbo mode state"""
        current_profile = self.profile_var.get()
        if current_profile != 'SBarb Farm':
            return

        turbo_enabled = self.sbarb_turbo_deployment_var.get()

        if turbo_enabled:
            # Hide options that turbo mode overrides (heroes first, queen arrow)
            self.sbarb_heroes_first_check.grid_forget()
            self.sbarb_heroes_first_row_visible = False

            self.sbarb_queen_arrow_spells_check.grid_forget()
            self.sbarb_queen_arrow_spells_row_visible = False

            # Keep cast spells visible - turbo mode uses this setting
            if not self.sbarb_cast_spells_row_visible:
                self.sbarb_cast_spells_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sbarb_cast_spells_row_visible = True
        else:
            # Show all options for standard mode
            if not self.sbarb_heroes_first_row_visible:
                self.sbarb_heroes_first_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sbarb_heroes_first_row_visible = True

            if not self.sbarb_queen_arrow_spells_row_visible:
                self.sbarb_queen_arrow_spells_check.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sbarb_queen_arrow_spells_row_visible = True

            if not self.sbarb_cast_spells_row_visible:
                self.sbarb_cast_spells_check.grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.sbarb_cast_spells_row_visible = True

        # Update targeting mode visibility (depends on cast spells state)
        self.update_sbarb_cast_spells_mode_visibility()

    def update_bb_gold_visibility(self):
        """Show/hide BB Gold troop mode dropdown and debug checkbox based on current profile"""
        current_profile = self.profile_var.get()

        if current_profile == 'BB Gold':
            # Show troop mode dropdown
            if not self.bb_gold_troop_mode_row_visible:
                self.bb_gold_troop_mode_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))
                self.bb_gold_troop_mode_row_visible = True

                # Set initial value from profile if available
                if current_profile in self.profiles:
                    # Try new setting first, fall back to migration from old setting
                    saved_mode = self.profiles[current_profile].get('bb_gold_troop_mode', None)
                    if saved_mode is None:
                        if self.profiles[current_profile].get('bb_gold_using_bomber', False):
                            saved_mode = 'bomber_night_witches'
                        else:
                            saved_mode = 'night_witches'
                    display_mode = self.bb_gold_troop_mode_reverse_map.get(saved_mode, 'Night Witches')
                    self.bb_gold_troop_mode_var.set(display_mode)

            # Update debug checkbox visibility based on troop mode
            self._update_bb_gold_dragon_debug_visibility()
        else:
            # Hide troop mode dropdown
            self.bb_gold_troop_mode_frame.grid_forget()
            self.bb_gold_troop_mode_row_visible = False
            # Hide debug checkbox
            self.bb_gold_dragon_debug_frame.grid_forget()
            self.bb_gold_dragon_debug_row_visible = False
            # Hide "try for 3 stars" checkbox
            self.bb_gold_try_3_stars_frame.grid_forget()
            self.bb_gold_try_3_stars_row_visible = False

    def _update_bb_gold_dragon_debug_visibility(self):
        """Show/hide BB Gold Baby Dragons options based on troop mode"""
        current_mode = self.bb_gold_troop_mode_var.get()

        if current_mode == 'Baby Dragons':
            # Show debug checkbox
            if not self.bb_gold_dragon_debug_row_visible:
                self.bb_gold_dragon_debug_frame.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.bb_gold_dragon_debug_row_visible = True
                # Reset to unchecked when shown (always starts unchecked)
                self.bb_gold_dragon_debug_var.set(False)

            # Show "try for 3 stars" checkbox and restore saved value
            if not self.bb_gold_try_3_stars_row_visible:
                self.bb_gold_try_3_stars_frame.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
                self.bb_gold_try_3_stars_row_visible = True
                saved_value = self.profiles.get(self.current_profile, {}).get('bb_gold_try_3_stars', False)
                self.bb_gold_try_3_stars_var.set(saved_value)
        else:
            # Hide debug checkbox
            self.bb_gold_dragon_debug_frame.grid_forget()
            self.bb_gold_dragon_debug_row_visible = False
            # Hide "try for 3 stars" checkbox
            self.bb_gold_try_3_stars_frame.grid_forget()
            self.bb_gold_try_3_stars_row_visible = False

    def _on_bb_gold_troop_mode_changed(self, event=None):
        """Handle BB Gold troop mode dropdown change"""
        self.save_settings()
        # Sync to web GUI
        if hasattr(self, 'state_manager') and self.state_manager:
            mode = self.bb_gold_troop_mode_map.get(self.bb_gold_troop_mode_var.get(), 'night_witches')
            self.state_manager.set('bb_gold_troop_mode', mode)
        # Update debug checkbox visibility
        self._update_bb_gold_dragon_debug_visibility()

    def _on_bb_gold_try_3_stars_changed(self):
        """Handle BB Gold try 3 stars checkbox change"""
        self.save_settings()
        # Sync to web GUI
        if hasattr(self, 'state_manager') and self.state_manager:
            self.state_manager.set('bb_gold_try_3_stars', self.bb_gold_try_3_stars_var.get())

    def _on_achievement_building_toggled(self, building_type):
        """Sync achievement building scan toggle to web GUI."""
        var_map = {
            'eagle_artillery': self.achievement_eagle_var,
            'monolith': self.achievement_monolith_var,
            'xbow': self.achievement_xbow_var,
            'inferno_tower': self.achievement_inferno_var,
            'scattershot': self.achievement_scattershot_var,
            'spell_tower': self.achievement_spell_tower_var,
            'multi_archer_tower': self.achievement_multi_archer_var,
            'ricochet_cannon': self.achievement_ricochet_var,
            'firespitter': self.achievement_firespitter_var,
            'multi_gear_tower': self.achievement_multi_gear_var,
        }
        value = var_map[building_type].get()
        self.save_settings()
        if hasattr(self, 'state_manager') and self.state_manager:
            self.state_manager.set(f'achievement_scan_{building_type}', value)

    def _on_sgoblin_skip_logging_changed(self):
        """Handle SGoblin skip logging checkbox change."""
        self.save_settings()
        if hasattr(self, 'state_manager') and self.state_manager:
            self.state_manager.set('sgoblin_skip_logging', self.sgoblin_skip_logging_var.get())

    def _on_bb_gold_dragon_debug_changed(self):
        """Handle BB Gold dragon debug checkbox change."""
        self.save_settings()
        if hasattr(self, 'state_manager') and self.state_manager:
            self.state_manager.set('bb_gold_dragon_debug_positions', self.bb_gold_dragon_debug_var.get())

    def update_priority_section_visibility(self):
        """Show/hide entire priority section based on profile"""
        current_profile = self.profile_var.get()

        # Show for Achievement Farm and SBarb Farm only
        relevant_profiles = ['Achievement Farm', 'SBarb Farm']

        if current_profile in relevant_profiles:
            # Show priority section
            self.priority_frame.grid()
        else:
            # Hide priority section completely
            self.priority_frame.grid_remove()

    def apply_current_profile(self, silent=False):
        """
        Apply the currently selected profile's settings.

        Args:
            silent: If True, suppress the success messagebox (for queue auto-switching)
        """
        selected_profile = self.profile_var.get()
        
        # Get profile settings
        if selected_profile in self.profiles:
            profile_settings = self.profiles[selected_profile]
            
            # Temporarily disable auto-saving to prevent recursive saves
            self.is_saving = True
            
            # Apply settings to GUI
            self.min_resources_var.set(profile_settings['min_resources'])
            self.max_th_var.set(profile_settings['max_th_level'])

            # Apply troop counts
            troop_counts = profile_settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])
            for i in range(7):
                self.troop_count_vars[i].set(str(troop_counts[i] if i < len(troop_counts) else 0))

            self.lightning_damage_var.set(profile_settings['lightning_damage'])
            self.auto_pause_var.set(profile_settings['auto_pause_enabled'])
            self.break_interval_var.set(profile_settings['break_interval'])
            self.break_duration_var.set(profile_settings['break_duration'])
            # bb_collect_interval is global, don't overwrite on profile switch

            # Apply hero ability timing
            self.queen_ability_timing_var.set(profile_settings.get('queen_ability_timing', 15))
            self.king_ability_timing_var.set(profile_settings.get('king_ability_timing', 15))
            self.warden_ability_timing_var.set(profile_settings.get('warden_ability_timing', 15))
            self.rc_ability_timing_var.set(profile_settings.get('rc_ability_timing', 15))

            # Apply Achievement Farm settings
            achievement_target = profile_settings.get('achievement_target_building', 'eagle_artillery')
            # Convert internal name to display name for dropdown
            display_name = next((k for k, v in self.achievement_building_map.items() if v == achievement_target), 'Eagle Artillery')
            self.achievement_building_var.set(display_name)

            achievement_mode = profile_settings.get('achievement_farm_target_mode', 'clumps')
            # Convert internal name to display name for dropdown
            mode_display = next((k for k, v in self.achievement_mode_map.items() if v == achievement_mode), 'Clumps (2+ buildings)')
            self.achievement_mode_var.set(mode_display)

            # Set all building scan checkboxes (uses full key names to match Web GUI)
            self.achievement_eagle_var.set(profile_settings.get('achievement_scan_eagle_artillery', True))
            self.achievement_monolith_var.set(profile_settings.get('achievement_scan_monolith', True))
            self.achievement_xbow_var.set(profile_settings.get('achievement_scan_xbow', True))
            self.achievement_inferno_var.set(profile_settings.get('achievement_scan_inferno_tower', True))
            self.achievement_scattershot_var.set(profile_settings.get('achievement_scan_scattershot', True))
            self.achievement_spell_tower_var.set(profile_settings.get('achievement_scan_spell_tower', True))
            self.achievement_multi_archer_var.set(profile_settings.get('achievement_scan_multi_archer_tower', True))
            self.achievement_ricochet_var.set(profile_settings.get('achievement_scan_ricochet_cannon', True))
            self.achievement_firespitter_var.set(profile_settings.get('achievement_scan_firespitter', True))
            self.achievement_multi_gear_var.set(profile_settings.get('achievement_scan_multi_gear_tower', True))
            self.achievement_parallel_scan_var.set(profile_settings.get('achievement_parallel_scan', False))

            # Apply SGoblin Farm settings
            self.sgoblin_cast_spells_var.set(profile_settings.get('sgoblin_cast_spells', False))
            self.sgoblin_use_wallbreakers_var.set(profile_settings.get('sgoblin_use_wallbreakers', False))
            self.sgoblin_skip_logging_var.set(profile_settings.get('sgoblin_skip_logging', False))

            # Apply SBarb Farm settings
            self.sbarb_heroes_first_var.set(profile_settings.get('sbarb_heroes_first', False))
            self.sbarb_queen_arrow_spells_var.set(profile_settings.get('sbarb_queen_arrow_spells', False))
            self.sbarb_cast_spells_var.set(profile_settings.get('sbarb_cast_spells', False))
            # Apply targeting mode for SBarb cast spells
            sbarb_target_mode = profile_settings.get('sbarb_cast_spells_target_mode', 'clumps')
            sbarb_mode_display = self.sbarb_cast_spells_mode_reverse_map.get(sbarb_target_mode, 'Clumps')
            self.sbarb_cast_spells_mode_var.set(sbarb_mode_display)
            self.sbarb_turbo_deployment_var.set(profile_settings.get('sbarb_turbo_deployment', False))

            # Apply BB Gold settings
            self.bb_gold_try_3_stars_var.set(profile_settings.get('bb_gold_try_3_stars', False))

            # Apply auto-pause settings
            self.auto_pause_mode.set(profile_settings.get('auto_pause_mode', 'manual'))
            self.auto_pause_value.set(str(profile_settings.get('auto_pause_value', 50)))
            self.storage_full_gold_var.set(profile_settings.get('storage_full_gold', True))
            self.storage_full_elixir_var.set(profile_settings.get('storage_full_elixir', True))
            self.storage_full_de_var.set(profile_settings.get('storage_full_de', False))
            self.storage_full_preset_var.set(profile_settings.get('storage_full_preset', 'main'))

            # Update current profile
            self.current_profile = selected_profile
            
            # Re-enable auto-saving
            self.is_saving = False
            
            # Save the profile switch to file
            self.save_settings()
            
            # Update visibility of settings widgets based on new profile
            self.update_attack_section_visibility()
            self.update_army_section_visibility()
            self.update_achievement_building_visibility()
            self.update_sgoblin_spell_casting_visibility()
            self.update_sbarb_deployment_visibility()
            self.update_bb_gold_visibility()

            # Sync profile settings to state manager for web GUI
            if self.state_manager:
                self.state_manager.update({
                    "current_profile": selected_profile,
                    "troop_counts": profile_settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0]),
                    "min_resources": profile_settings.get('min_resources', 100000),
                    "max_th_level": profile_settings.get('max_th_level', 17),
                    "lightning_damage": profile_settings.get('lightning_damage', 600),
                    "queen_ability_timing": profile_settings.get('queen_ability_timing', 15),
                    "king_ability_timing": profile_settings.get('king_ability_timing', 15),
                    "warden_ability_timing": profile_settings.get('warden_ability_timing', 15),
                    "rc_ability_timing": profile_settings.get('rc_ability_timing', 15),
                    "sgoblin_cast_spells": profile_settings.get('sgoblin_cast_spells', False),
                    "sgoblin_use_wallbreakers": profile_settings.get('sgoblin_use_wallbreakers', False),
                    "sbarb_heroes_first": profile_settings.get('sbarb_heroes_first', False),
                    "sbarb_queen_arrow_spells": profile_settings.get('sbarb_queen_arrow_spells', False),
                    "sbarb_cast_spells": profile_settings.get('sbarb_cast_spells', False),
                    "sbarb_cast_spells_target_mode": profile_settings.get('sbarb_cast_spells_target_mode', 'clumps'),
                    "sbarb_turbo_deployment": profile_settings.get('sbarb_turbo_deployment', False),
                    "achievement_target_building": profile_settings.get('achievement_target_building', 'eagle_artillery'),
                    "achievement_farm_target_mode": profile_settings.get('achievement_farm_target_mode', 'clumps'),
                })

            self.log_message(f"Applied profile '{selected_profile}' settings.")

            # Only show messagebox if not in silent mode (queue auto-switching)
            if not silent:
                messagebox.showinfo("Profile Applied", f"Profile '{selected_profile}' settings applied successfully!")
        else:
            if not silent:
                messagebox.showwarning("Profile Error", "Selected profile not found.")

    def update_profile_description(self):
        """Update the profile description label with the current profile's details."""
        selected_profile = self.profile_var.get()
        if selected_profile in self.profiles:
            profile_settings = self.profiles[selected_profile]
            desc = profile_settings.get('description', 'No description available.')
            self.profile_desc_label.config(text=f"Profile: {selected_profile}\nDescription: {desc}")
        else:
            self.profile_desc_label.config(text="No profile selected or profile not found.")
    
    def update_loot_stats(self, loot_data):
        """Update loot statistics with new loot data"""
        self.total_gold += loot_data['gold']
        self.total_elixir += loot_data['elixir']
        self.total_dark_elixir += loot_data['dark_elixir']
        self.attacks_with_loot += 1

        # Update labels
        self.gold_label.config(text=f"{self.total_gold:,}")
        self.elixir_label.config(text=f"{self.total_elixir:,}")
        self.dark_elixir_label.config(text=f"{self.total_dark_elixir:,}")
        self.attacks_label.config(text=str(self.attacks_with_loot))

        # Update averages
        if self.attacks_with_loot > 0:
            self.avg_gold_label.config(text=f"{self.total_gold // self.attacks_with_loot:,}")
            self.avg_elixir_label.config(text=f"{self.total_elixir // self.attacks_with_loot:,}")
            self.avg_dark_label.config(text=f"{self.total_dark_elixir // self.attacks_with_loot:,}")
        
    def update_skipped_stats(self, skipped_bases, attacked_bases):
        """Update skipped bases and skip/attack ratio statistics in the GUI."""
        self.skipped_bases = skipped_bases
        #self.skipped_label.config(text=str(skipped_bases))
        if attacked_bases > 0:
            skip_ratio = skipped_bases / attacked_bases
        else:
            skip_ratio = 0.0
        self.skip_ratio = skip_ratio
        #self.skip_ratio_label.config(text=f"{skip_ratio:.2f}")
        
    def reset_loot_stats(self):
        """Reset all loot statistics"""
        self.total_gold = 0
        self.total_elixir = 0
        self.total_dark_elixir = 0
        self.attacks_with_loot = 0
        #self.skipped_bases = 0
        self.skip_ratio = 0.0
        
        # Reset labels
        self.gold_label.config(text="0")
        self.elixir_label.config(text="0")
        self.dark_elixir_label.config(text="0")
        self.trophies_label.config(text="0")
        self.attacks_label.config(text="0")
        #self.skipped_label.config(text="0")
        #self.skip_ratio_label.config(text="0.00")
        self.avg_gold_label.config(text="0")
        self.avg_elixir_label.config(text="0")
        self.avg_dark_label.config(text="0")
        self.avg_trophies_label.config(text="0")
        
        self.log_message("Loot statistics reset")
        
    def update_csv_totals(self):
        """Read loot_tracking.csv and update total plundered stats in the GUI."""
        gold = 0
        elixir = 0
        dark = 0
        try:
            if os.path.exists('loot_tracking.csv'):
                with open('loot_tracking.csv', 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        gold += int(row.get('gold', 0))
                        elixir += int(row.get('elixir', 0))
                        dark += int(row.get('dark_elixir', 0))
        except Exception as e:
            print(f"Error reading loot_tracking.csv: {e}")
        self.csv_gold = gold
        self.csv_elixir = elixir
        self.csv_dark_elixir = dark
        self.csv_gold_label.config(text=f"Total Gold: {gold:,}")
        self.csv_elixir_label.config(text=f"Total Elixir: {elixir:,}")
        self.csv_dark_label.config(text=f"Total Dark Elixir: {dark:,}")
        
    def reset_profile_to_defaults(self):
        """Reset the current profile to its hard-coded defaults"""
        current_profile = self.current_profile
        
        if current_profile == 'Custom':
            messagebox.showwarning("Reset Profile", "Cannot reset Custom profile to defaults. Custom profile is user-editable.")
            return
            
        # Get hard-coded defaults for this profile
        hardcoded_profiles = self.get_hardcoded_profiles()
        if current_profile in hardcoded_profiles:
            default_settings = hardcoded_profiles[current_profile]
            
            # Temporarily disable auto-saving
            self.is_saving = True
            
            # Apply default settings to GUI
            self.min_resources_var.set(default_settings['min_resources'])
            self.max_th_var.set(default_settings['max_th_level'])

            # Apply troop counts
            troop_counts = default_settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])
            for i in range(7):
                self.troop_count_vars[i].set(str(troop_counts[i] if i < len(troop_counts) else 0))

            self.lightning_damage_var.set(default_settings['lightning_damage'])
            self.auto_pause_var.set(default_settings['auto_pause_enabled'])
            self.break_interval_var.set(default_settings['break_interval'])
            self.break_duration_var.set(default_settings['break_duration'])
            # bb_collect_interval is global, don't reset with profile

            # Re-enable auto-saving
            self.is_saving = False
            
            # Save the reset settings
            self.save_settings()
            
            self.log_message(f"Profile '{current_profile}' reset to defaults.")
            messagebox.showinfo("Profile Reset", f"Profile '{current_profile}' has been reset to its default settings.")
        else:
            messagebox.showwarning("Reset Profile", f"Profile '{current_profile}' not found in hard-coded defaults.")

    def update_priority_listbox(self):
        """Update the priority list display with modern card-based design"""
        # Clear existing cards
        for card in self.priority_building_cards:
            card.destroy()
        self.priority_building_cards.clear()

        building_display_names = {
            'eagle_artillery': 'Eagle Artillery',
            'monolith': 'Monolith',
            'xbow': 'X-Bow',
            'inferno_tower': 'Inferno Tower',
            'scattershot': 'Scattershot',
            'spell_tower': 'Spell Tower',
            'multi_archer_tower': 'Multi-Archer Tower',
            'ricochet_cannon': 'Ricochet Cannon',
            'firespitter': 'Firespitter',
            'multi_gear_tower': 'Multi-Gear Tower'
        }

        # Priority badge emojis (or numbers)
        priority_badges = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

        # Create card for each building
        for index, building in enumerate(self.achievement_priority_list):
            display_name = building_display_names.get(building, building.replace('_', ' ').title())

            # Create card frame with gradient-like colors (higher priority = stronger color)
            card_frame = tk.Frame(
                self.achievement_priority_scroll_frame,
                relief='raised',
                borderwidth=1,
                padx=10,
                pady=8,
                bg=self.get_priority_color(index)
            )
            card_frame.pack(fill=tk.X, pady=3, padx=5)

            # Priority badge
            badge_label = tk.Label(
                card_frame,
                text=priority_badges[index] if index < len(priority_badges) else f"{index+1}.",
                font=('Segoe UI', 12, 'bold'),
                bg=self.get_priority_color(index),
                fg='#333333'
            )
            badge_label.pack(side=tk.LEFT, padx=(0, 10))

            # Building name
            name_label = tk.Label(
                card_frame,
                text=display_name,
                font=('Segoe UI', 10),
                bg=self.get_priority_color(index),
                fg='#000000',
                anchor='w'
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Priority rank text
            rank_label = tk.Label(
                card_frame,
                text=f"Priority #{index+1}",
                font=('Segoe UI', 8, 'italic'),
                bg=self.get_priority_color(index),
                fg='#666666'
            )
            rank_label.pack(side=tk.RIGHT, padx=(10, 0))

            # Store building ID with the card
            card_frame.building_id = building

            # Make card clickable for selection
            def make_select_handler(card, bldg):
                def handler(event):
                    self.select_priority_building(card, bldg)
                return handler

            for widget in [card_frame, badge_label, name_label, rank_label]:
                widget.bind('<Button-1>', make_select_handler(card_frame, building))

            # Add hover effect
            def on_enter(event, card=card_frame):
                if card != self.selected_priority_building:
                    card.config(relief='solid', borderwidth=2)

            def on_leave(event, card=card_frame):
                if card != self.selected_priority_building:
                    card.config(relief='raised', borderwidth=1)

            card_frame.bind('<Enter>', on_enter)
            card_frame.bind('<Leave>', on_leave)

            self.priority_building_cards.append(card_frame)

        # Update canvas scroll region
        self.achievement_priority_scroll_frame.update_idletasks()
        self.achievement_priority_canvas.configure(scrollregion=self.achievement_priority_canvas.bbox("all"))

    def get_priority_color(self, index):
        """Get color for priority card based on index (gradient from high to low priority)"""
        # Gradient from gold (high priority) to light blue (low priority)
        colors = [
            '#FFD700',  # Gold
            '#FFA500',  # Orange
            '#FFB347',  # Light Orange
            '#FFDAB9',  # Peach
            '#FFFACD',  # Lemon
            '#E0FFE0',  # Light Green
            '#B0E0E6',  # Powder Blue
            '#ADD8E6',  # Light Blue
            '#D3D3D3',  # Light Gray
            '#E0E0E0'   # Lighter Gray
        ]
        return colors[index] if index < len(colors) else '#F0F0F0'

    def select_priority_building(self, card_frame, building_id):
        """Select a building card for move operations"""
        # Deselect previous selection
        if self.selected_priority_building:
            # Check if old selection still exists in current cards list
            if self.selected_priority_building in self.priority_building_cards:
                index = self.priority_building_cards.index(self.selected_priority_building)
                self.selected_priority_building.config(relief='raised', borderwidth=1, bg=self.get_priority_color(index))

        # Select new card
        self.selected_priority_building = card_frame
        card_frame.config(relief='solid', borderwidth=3, bg='#4A90E2')  # Blue highlight

        # Update all labels in the selected card to match the blue background
        for child in card_frame.winfo_children():
            if isinstance(child, tk.Label):
                child.config(bg='#4A90E2', fg='white')

    def on_parallel_scan_toggle(self):
        """Show warning when parallel scanning is enabled"""
        if self.achievement_parallel_scan_var.get():
            from tkinter import messagebox
            messagebox.showwarning(
                "CPU Warning",
                "Parallel scanning is faster but may cause:\n\n"
                "• CPU spikes up to 28-32%\n"
                "• Possible game crashes on slower systems\n"
                "• Brief system lag during scans\n\n"
                "Sequential scanning (default) is slower but stable.\n\n"
                "Only enable parallel mode if you have a fast CPU and "
                "haven't experienced crashes."
            )

    def move_building_up(self):
        """Move selected building up in priority list"""
        if not self.selected_priority_building:
            messagebox.showinfo("No Selection", "Please select a building card to move.")
            return

        # Find index of selected building
        index = self.priority_building_cards.index(self.selected_priority_building)

        if index == 0:
            return  # Already at top

        # Swap with previous item
        self.achievement_priority_list[index], self.achievement_priority_list[index-1] = \
            self.achievement_priority_list[index-1], self.achievement_priority_list[index]

        # Rebuild display and maintain selection
        selected_building = self.selected_priority_building.building_id
        self.update_priority_listbox()

        # Re-select the moved building
        if index-1 < len(self.priority_building_cards):
            self.select_priority_building(self.priority_building_cards[index-1], selected_building)
            # Scroll to show the selected card
            self.achievement_priority_canvas.yview_moveto(max(0, (index-1) / len(self.priority_building_cards)))

        # Save changes to settings
        self.save_settings()

    def move_building_down(self):
        """Move selected building down in priority list"""
        if not self.selected_priority_building:
            messagebox.showinfo("No Selection", "Please select a building card to move.")
            return

        # Find index of selected building
        index = self.priority_building_cards.index(self.selected_priority_building)

        if index == len(self.achievement_priority_list) - 1:
            return  # Already at bottom

        # Swap with next item
        self.achievement_priority_list[index], self.achievement_priority_list[index+1] = \
            self.achievement_priority_list[index+1], self.achievement_priority_list[index]

        # Rebuild display and maintain selection
        selected_building = self.selected_priority_building.building_id
        self.update_priority_listbox()

        # Re-select the moved building
        if index+1 < len(self.priority_building_cards):
            self.select_priority_building(self.priority_building_cards[index+1], selected_building)
            # Scroll to show the selected card
            self.achievement_priority_canvas.yview_moveto(min(1.0, (index+1) / len(self.priority_building_cards)))

        # Save changes to settings
        self.save_settings()

    def reset_building_priority(self):
        """Reset building priority to default order"""
        default_order = [
            'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
            'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
        ]
        self.achievement_priority_list = default_order.copy()
        self.selected_priority_building = None
        self.update_priority_listbox()
        self.save_settings()
        messagebox.showinfo("Priority Reset", "Building priority order has been reset to default.")

    # ============================================================================
    # MANUAL MODE SCHEDULE METHODS
    # ============================================================================

    def refresh_manual_schedule_display(self):
        """Refresh the manual mode schedule display"""
        # Clear existing cards
        for widget in self.manual_schedule_scroll_frame.winfo_children():
            widget.destroy()

        self.manual_task_cards = []

        # Get schedule from settings or instance variable
        if hasattr(self, 'manual_mode_schedule'):
            schedule = self.manual_mode_schedule
        else:
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])

        if not schedule:
            # Show empty state message
            empty_label = ttk.Label(
                self.manual_schedule_scroll_frame,
                text="No tasks in schedule. Click 'Add Task' to begin.",
                foreground='gray',
                font=('Segoe UI', 9, 'italic')
            )
            empty_label.pack(pady=30)
            return

        # Create task cards
        for i, task in enumerate(schedule):
            self.create_manual_task_card(i, task)

    def create_manual_task_card(self, index, task):
        """Create a visual card for a manual mode task"""
        # Main card frame
        card_frame = ttk.Frame(self.manual_schedule_scroll_frame, relief='raised', borderwidth=1)
        card_frame.pack(fill=tk.X, padx=5, pady=3)

        # Configure colors based on selection
        bg_color = '#e3f2fd' if index == self.manual_selected_task_index else '#ffffff'

        # Inner frame with padding
        inner_frame = tk.Frame(card_frame, bg=bg_color, padx=10, pady=8)
        inner_frame.pack(fill=tk.BOTH, expand=True)

        # Task number and mode
        mode = task.get('mode', 'Unknown')
        header_label = tk.Label(
            inner_frame,
            text=f"Task {index + 1}: {mode}",
            font=('Segoe UI', 10, 'bold'),
            bg=bg_color,
            fg='#1976d2'
        )
        header_label.pack(anchor=tk.W)

        # Condition details
        condition_type = task.get('condition_type', 'time')
        if condition_type == 'time':
            condition_text = f"⏱️ Run for {task.get('time_minutes', 30)} minutes"
        else:  # storage
            storage_target = task.get('storage_target', {})
            parts = []
            if 'gold' in storage_target and storage_target['gold'] is not None:
                parts.append(f"Gold {storage_target['gold']}%")
            if 'elixir' in storage_target and storage_target['elixir'] is not None:
                parts.append(f"Elixir {storage_target['elixir']}%")
            if 'de' in storage_target and storage_target['de'] is not None:
                parts.append(f"DE {storage_target['de']}%")
            condition_text = f"📦 Until storage: {', '.join(parts) if parts else 'No targets set'}"

        condition_label = tk.Label(
            inner_frame,
            text=condition_text,
            font=('Segoe UI', 9),
            bg=bg_color,
            fg='#555555'
        )
        condition_label.pack(anchor=tk.W, pady=(2, 0))

        # Make card clickable
        def make_click_handler(idx):
            def handler(event):
                self.select_manual_task(idx)
            return handler

        for widget in [card_frame, inner_frame, header_label, condition_label]:
            widget.bind('<Button-1>', make_click_handler(index))

        # Hover effects
        def on_enter(event, card=inner_frame):
            if index != self.manual_selected_task_index:
                card.config(bg='#f5f5f5')

        def on_leave(event, card=inner_frame):
            if index != self.manual_selected_task_index:
                card.config(bg='#ffffff')

        card_frame.bind('<Enter>', on_enter)
        card_frame.bind('<Leave>', on_leave)

        self.manual_task_cards.append(card_frame)

    def select_manual_task(self, index):
        """Select a task in the manual schedule"""
        self.manual_selected_task_index = index
        self.refresh_manual_schedule_display()

    def add_manual_task(self):
        """Open dialog to add a new task"""
        self.show_manual_task_dialog(mode='add')

    def edit_manual_task(self):
        """Open dialog to edit selected task"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to edit.")
            return

        self.show_manual_task_dialog(mode='edit', task_index=self.manual_selected_task_index)

    def remove_manual_task(self):
        """Remove selected task from schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to remove.")
            return

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if 0 <= self.manual_selected_task_index < len(schedule):
            removed_task = schedule.pop(self.manual_selected_task_index)
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()
            print(f"[GUI] Removed task from manual schedule: {removed_task}")

    def clear_all_manual_tasks(self):
        """Remove all tasks from manual schedule"""
        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if not schedule:
            messagebox.showinfo("No Tasks", "Manual schedule is already empty.")
            return

        # Confirm with user
        result = messagebox.askyesno(
            "Clear All Tasks",
            f"Are you sure you want to remove all {len(schedule)} task(s) from the manual schedule?\n\nThis action cannot be undone."
        )

        if result:
            self.manual_mode_schedule = []
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()
            print(f"[GUI] Cleared all {len(schedule)} tasks from manual schedule")
            self.log_message(f"Cleared all manual schedule tasks ({len(schedule)} removed)")

    def move_manual_task_up(self):
        """Move selected task up in the schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to move.")
            return

        if self.manual_selected_task_index == 0:
            return  # Already at top

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        idx = self.manual_selected_task_index
        schedule[idx], schedule[idx - 1] = schedule[idx - 1], schedule[idx]
        self.manual_selected_task_index = idx - 1

        self.save_global_settings()
        self.refresh_manual_schedule_display()

    def move_manual_task_down(self):
        """Move selected task down in the schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to move.")
            return

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if self.manual_selected_task_index >= len(schedule) - 1:
            return  # Already at bottom

        idx = self.manual_selected_task_index
        schedule[idx], schedule[idx + 1] = schedule[idx + 1], schedule[idx]
        self.manual_selected_task_index = idx + 1

        self.save_global_settings()
        self.refresh_manual_schedule_display()

    def show_manual_task_dialog(self, mode='add', task_index=None):
        """Show dialog to add or edit a manual task"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Task" if mode == 'add' else "Edit Task")
        dialog.geometry("450x400")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Get existing task data if editing
        existing_task = None
        if mode == 'edit' and task_index is not None:
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])
            if 0 <= task_index < len(schedule):
                existing_task = schedule[task_index]

        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Mode selection
        ttk.Label(main_frame, text="Attack Mode:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        mode_var = tk.StringVar(value=existing_task.get('mode', 'SBarb Farm') if existing_task else 'SBarb Farm')
        mode_combo = ttk.Combobox(main_frame, textvariable=mode_var, state='readonly', width=25)
        mode_combo['values'] = [
            'Farming', 'Trophy Push', 'Derank', 'SGoblin Farm', 'SBarb Farm',
            'Achievement Farm', 'BB Elixir', 'BB Gold', 'Custom'
        ]
        mode_combo.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Condition type
        ttk.Label(main_frame, text="Completion Condition:", font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        condition_var = tk.StringVar(value=existing_task.get('condition_type', 'time') if existing_task else 'time')
        condition_frame = ttk.Frame(main_frame)
        condition_frame.grid(row=3, column=0, sticky=tk.W, pady=(0, 15))

        ttk.Radiobutton(condition_frame, text="Time-based", variable=condition_var, value='time').pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(condition_frame, text="Storage-based", variable=condition_var, value='storage').pack(side=tk.LEFT)

        # Time-based settings
        time_frame = ttk.LabelFrame(main_frame, text="Time Settings", padding="10")
        time_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(time_frame, text="Duration (minutes):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        time_var = tk.StringVar(value=str(existing_task.get('time_minutes', 30) if existing_task else 30))
        ttk.Spinbox(time_frame, from_=5, to=300, increment=5, textvariable=time_var, width=15).grid(row=0, column=1, sticky=tk.W)

        # Storage-based settings
        storage_frame = ttk.LabelFrame(main_frame, text="Storage Targets (%)", padding="10")
        storage_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        storage_target = existing_task.get('storage_target', {}) if existing_task else {}

        ttk.Label(storage_frame, text="Gold:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        gold_var = tk.StringVar(value=str(storage_target.get('gold', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=gold_var, width=10).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(storage_frame, text="Elixir:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        elixir_var = tk.StringVar(value=str(storage_target.get('elixir', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=elixir_var, width=10).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(storage_frame, text="Dark Elixir:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        de_var = tk.StringVar(value=str(storage_target.get('de', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=de_var, width=10).grid(row=2, column=1, sticky=tk.W)

        # Show/hide frames based on condition type
        def update_frame_visibility(*args):
            if condition_var.get() == 'time':
                time_frame.grid()
                storage_frame.grid_remove()
            else:
                time_frame.grid_remove()
                storage_frame.grid()

        condition_var.trace('w', update_frame_visibility)
        update_frame_visibility()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, pady=(10, 0))

        def save_task():
            # Build task dictionary
            task = {
                'mode': mode_var.get(),
                'condition_type': condition_var.get()
            }

            if condition_var.get() == 'time':
                task['time_minutes'] = int(time_var.get())
            else:
                task['storage_target'] = {
                    'gold': int(gold_var.get()),
                    'elixir': int(elixir_var.get()),
                    'de': int(de_var.get())
                }

            # Add or update task
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])

            if mode == 'add':
                schedule.append(task)
                print(f"[GUI] Added task to manual schedule: {task}")
            else:  # edit
                if 0 <= task_index < len(schedule):
                    schedule[task_index] = task
                    print(f"[GUI] Updated task in manual schedule: {task}")

            # Validate schedule
            from queue_manager import QueueManager
            is_valid, error_msg = QueueManager(self).validate_manual_schedule(schedule)

            if not is_valid:
                messagebox.showerror("Invalid Schedule", f"Cannot save task:\n\n{error_msg}")
                return

            self.save_global_settings()
            self.refresh_manual_schedule_display()
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_task, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)

    def schedule_auto_resume(self, break_duration_minutes):
        """Schedule automatic resume after break duration"""
        if self.bot_running and self.bot_paused:
            # Schedule resume after break duration
            resume_time = time.time() + (break_duration_minutes * 60)
            
            def auto_resume():
                if time.time() >= resume_time and self.bot_running and self.bot_paused:
                    self.bot_paused = False
                    self.status_label.config(text="RUNNING", foreground="green")
                    self.quick_status_label.config(text="● Running", foreground="green")
                    self.log_message("Auto-resumed after break")
                    # Schedule next break
                    self.schedule_next_break()
                elif self.bot_running:
                    # Check again in 10 seconds
                    self.root.after(10000, auto_resume)
            
            self.root.after(10000, auto_resume)  # Start checking after 10 seconds
            
    def schedule_next_break(self):
        """Schedule the next automatic break"""
        # This will be called from main.py when needed
        pass

    def toggle_night_mode(self):
        """Toggle night mode on/off and apply styles immediately"""
        # Update from checkbox state
        self.night_mode = self.night_mode_var.get()

        if self.night_mode:
            self.enable_night_mode()
        else:
            self.disable_night_mode()

        # Save settings to persist night mode preference
        self.save_global_settings()

    def toggle_overlay(self):
        """Toggle visualization overlay on/off"""
        self.overlay_enabled = self.overlay_enabled_var.get()
        print(f"[GUI] toggle_overlay called: overlay_enabled = {self.overlay_enabled}")
        print(f"[GUI] self.overlay exists: {self.overlay is not None}")
        print(f"[GUI] OVERLAY_AVAILABLE: {OVERLAY_AVAILABLE}")

        if self.overlay and OVERLAY_AVAILABLE:
            if self.overlay_enabled:
                self.overlay.show()
                self.log_message("Detection overlay enabled")
                print("[GUI] Overlay.show() called")
            else:
                self.overlay.hide()
                self.log_message("Detection overlay disabled")
                print("[GUI] Overlay.hide() called")
        else:
            print("[GUI] WARNING: Overlay not available or not initialized!")

        # Show/hide the "Hide Low Confidence" checkbox based on overlay state
        if self.overlay_enabled:
            if not getattr(self, 'overlay_hide_low_conf_row_visible', False):
                self.overlay_hide_low_conf_label.grid(row=3, column=0, sticky='w', padx=(0, 10))
                self.overlay_hide_low_conf_check.grid(row=3, column=1, sticky='w')
                self.overlay_hide_low_conf_row_visible = True
        else:
            if getattr(self, 'overlay_hide_low_conf_row_visible', False):
                self.overlay_hide_low_conf_label.grid_forget()
                self.overlay_hide_low_conf_check.grid_forget()
                self.overlay_hide_low_conf_row_visible = False

        # Save settings to persist overlay preference
        self.save_global_settings()

    def enable_night_mode(self):
        """Enable dark theme with improved colors"""
        style = ttk.Style()
        style.theme_use('clam')

        # Dark theme colors - more modern palette
        bg_dark = '#1e1e1e'
        bg_frame = '#252525'
        bg_input = '#2d2d2d'
        fg_text = '#e0e0e0'
        fg_accent = '#4a9eff'

        # Configure all ttk widgets
        style.configure('.', background=bg_dark, foreground=fg_text)
        style.configure('TLabel', background=bg_dark, foreground=fg_text)
        style.configure('TLabelframe', background=bg_dark, foreground=fg_text)
        style.configure('TLabelframe.Label', background=bg_dark, foreground=fg_accent, font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', background=bg_frame, foreground=fg_text)
        style.configure('TFrame', background=bg_dark)
        style.configure('TEntry', fieldbackground=bg_input, foreground=fg_text, insertcolor=fg_text)
        style.configure('TCheckbutton', background=bg_dark, foreground=fg_text)
        style.configure('TRadiobutton', background=bg_dark, foreground=fg_text)
        style.configure('TSpinbox', fieldbackground=bg_input, foreground=fg_text, arrowcolor=fg_text)
        style.configure('TCombobox', fieldbackground=bg_input, foreground=fg_text, arrowcolor=fg_text)
        style.configure('TNotebook', background=bg_dark)
        style.configure('TNotebook.Tab', background=bg_frame, foreground=fg_text)

        # Map states for interactive elements
        style.map('TButton',
                  background=[('active', bg_input), ('disabled', bg_frame)],
                  foreground=[('disabled', '#666666')])
        style.map('TCheckbutton',
                  background=[('active', bg_dark)])
        style.map('TCombobox',
                  fieldbackground=[('readonly', bg_input)])

        # Configure root window
        self.root.configure(bg=bg_dark)

        # Update text widgets (non-ttk)
        try:
            self.log_text.configure(bg=bg_input, fg=fg_text, insertbackground=fg_text)
            self.debug_text.configure(bg=bg_input, fg=fg_text, insertbackground=fg_text)
        except:
            pass

    def disable_night_mode(self):
        """Restore default light theme"""
        style = ttk.Style()
        style.theme_use('vista')  # Modern Windows theme

        # Reset to default colors
        style.configure('.', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabel', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabelframe', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TFrame', background='SystemButtonFace')
        style.configure('TEntry', fieldbackground='white', foreground='black')
        style.configure('TCheckbutton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TRadiobutton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TSpinbox', fieldbackground='white', foreground='black')
        style.configure('TCombobox', fieldbackground='white', foreground='black')

        # Configure root window
        self.root.configure(bg='SystemButtonFace')

        # Update text widgets (non-ttk)
        try:
            self.log_text.configure(bg='white', fg='black', insertbackground='black')
            self.debug_text.configure(bg='white', fg='black', insertbackground='black')
        except:
            pass

    def save_global_settings(self):
        # Save global settings to JSON
        try:
            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                file_data = json.load(f)
        except Exception:
            file_data = {}
        file_data['reinforcements_enabled'] = self.global_reinforcements_var.get()
        file_data['night_mode'] = self.night_mode_var.get()
        file_data['overlay_enabled'] = self.overlay_enabled_var.get()
        file_data['overlay_hide_low_conf'] = self.overlay_hide_low_conf_var.get()
        file_data['skip_on_th_fail'] = self.skip_on_th_fail_var.get()
        file_data['use_second_monitor'] = self.use_second_monitor_var.get()
        file_data['parallel_scanning'] = self.achievement_parallel_scan_var.get()
        file_data['gpu_scanning'] = self.gpu_scanning_var.get()

        # Save queue system settings
        file_data['queue_enabled'] = self.queue_enabled_var.get()
        file_data['queue_mode'] = self.queue_mode_var.get()
        file_data['smart_mode_config'] = {
            'main_base_mode': self.smart_main_mode_var.get(),
            'storage_targets': {
                'wait_for_de': self.smart_wait_de_var.get(),
                'gold_threshold': int(self.smart_gold_threshold_var.get()),
                'elixir_threshold': int(self.smart_elixir_threshold_var.get()),
                'de_threshold': int(self.smart_de_threshold_var.get())
            },
            'bb_auto_select_enabled': self.smart_bb_auto_var.get(),
            'bb_gold_elixir_ratio': float(self.smart_bb_ratio_var.get()),
            'after_bb_behavior': self.smart_after_bb_var.get()
        }
        file_data['achievement_farm_end_config'] = {
            'enabled': self.achievement_end_enabled_var.get(),
            'duration_minutes': int(self.achievement_end_duration_var.get())
        }

        # Save manual mode schedule (if it exists in current settings)
        current_settings = self.get_settings()
        if 'manual_mode_schedule' in current_settings:
            file_data['manual_mode_schedule'] = current_settings['manual_mode_schedule']

        with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
            json.dump(file_data, f, indent=2)
        self.log_message("Global settings saved.")
        self.global_reinforcements_enabled = self.global_reinforcements_var.get()
        self.night_mode = self.night_mode_var.get()
        self.overlay_enabled = self.overlay_enabled_var.get()
        self.overlay_hide_low_conf = self.overlay_hide_low_conf_var.get()
        self.skip_on_th_fail = self.skip_on_th_fail_var.get()
        self.use_second_monitor = self.use_second_monitor_var.get()

    def show_statistics(self):
        """Plot trophies and loops completed from loot_tracking.csv"""
        try:
            df = pd.read_csv('loot_tracking.csv', parse_dates=['timestamp'])
        except Exception as e:
            self.log_message(f"Error reading loot_tracking.csv: {e}")
            return
        if df.empty:
            self.log_message("No data to plot.")
            return
        now = datetime.now()
        periods = {
            'Day': now - timedelta(days=1),
            'Week': now - timedelta(weeks=1),
            'Month': now - timedelta(days=30)
        }
        plt.figure(figsize=(15, 10))
        for i, (label, start_time) in enumerate(periods.items(), 1):
            plt.subplot(2, 2, i)
            mask = df['timestamp'] >= start_time.strftime('%Y-%m-%d %H:%M:%S')
            sub = df[mask]
            if sub.empty:
                plt.title(f"No data for last {label.lower()}")
                continue
            plt.plot(sub['timestamp'], sub['trophies'], marker='o', label='Trophies')
            plt.xlabel('Time')
            plt.ylabel('Trophies')
            plt.title(f'Trophies in the last {label.lower()}' )
            plt.xticks(rotation=45)
            plt.legend()
        # Plot loops completed (attack_number)
        plt.subplot(2, 2, 4)
        plt.plot(df['timestamp'], df['attack_number'], marker='x', color='orange', label='Loops Completed')
        plt.xlabel('Time')
        plt.ylabel('Loop #')
        plt.title('Loops Completed Over Time')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.show()
        self.log_message("Statistics plotted.")

def main():
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 