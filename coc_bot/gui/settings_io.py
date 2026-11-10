"""Reading, validating, saving and applying settings, profiles and storage presets."""

import json
import tkinter as tk
from tkinter import messagebox


class SettingsIOMixin:
    """Reading, validating, saving and applying settings, profiles and storage presets. Mixin for BotGUI."""

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
