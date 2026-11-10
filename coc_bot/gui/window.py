"""The main Tkinter window: BotGUI assembles every panel mixin."""

import json
import tkinter as tk
from tkinter import ttk

from coc_bot.gui.bot_control import BotControlMixin
from coc_bot.gui.log_panel import LogPanelMixin
from coc_bot.gui.main_sections import MainSectionsMixin
from coc_bot.gui.night_mode import NightModeMixin
from coc_bot.gui.overlay_support import OVERLAY_AVAILABLE, VisualizationOverlay
from coc_bot.gui.priority_panel import PriorityPanelMixin
from coc_bot.gui.profile_data import ProfileDataMixin
from coc_bot.gui.profile_sections import ProfileSectionsMixin
from coc_bot.gui.queue_panel import QueuePanelMixin
from coc_bot.gui.settings_io import SettingsIOMixin
from coc_bot.gui.state_sync import StateSyncMixin
from coc_bot.gui.stats_panel import StatsPanelMixin
from coc_bot.gui.visibility import VisibilityMixin

class BotGUI(
    StateSyncMixin,
    ProfileDataMixin,
    MainSectionsMixin,
    ProfileSectionsMixin,
    VisibilityMixin,
    QueuePanelMixin,
    PriorityPanelMixin,
    LogPanelMixin,
    BotControlMixin,
    SettingsIOMixin,
    StatsPanelMixin,
    NightModeMixin,
):
    """The desktop control panel. Behaviour is split across the mixins by panel."""

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
        except Exception:
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
                print("[GUI] Second monitor preferred but not detected, using primary")
            # Center on primary monitor
            x = (primary_width // 2) - (window_width // 2)
            y = (primary_height // 2) - (window_height // 2)
            print("[GUI] Positioning on primary monitor")

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
        except Exception:
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


if __name__ == "__main__":
    # Preview the control panel on its own: python -m coc_bot.gui.window
    preview_root = tk.Tk()
    BotGUI(preview_root)
    preview_root.mainloop()
