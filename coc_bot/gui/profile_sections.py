"""Widgets of the profile, army, attack and global settings sections."""

import tkinter as tk
from tkinter import ttk

from coc_bot.gui.overlay_support import OVERLAY_AVAILABLE

class ProfileSectionsMixin:
    """Widgets of the profile, army, attack and global settings sections. Mixin for BotGUI."""

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
