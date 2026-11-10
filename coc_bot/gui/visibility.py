"""Show and hide settings widgets according to the selected profile and toggles."""

import tkinter as tk

class VisibilityMixin:
    """Show and hide settings widgets according to the selected profile and toggles. Mixin for BotGUI."""

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
