"""Two-way synchronisation between the Tkinter widgets and the shared BotStateManager."""

import tkinter as tk

from coc_bot import runtime


class StateSyncMixin:
    """Two-way synchronisation between the Tkinter widgets and the shared BotStateManager. Mixin for BotGUI."""

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
                            if self._control_callbacks.get("pause"):
                                try:
                                    self._control_callbacks["pause"](value)
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
                    display_mode = self.bb_gold_troop_mode_reverse_map.get(value, "Night Witches")
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
                            queue_manager = runtime.queue_manager
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
                        self.smart_main_mode_var.set(value.get("main_base_mode", "SBarb Farm"))
                        storage_targets = value.get("storage_targets", {})
                        self.smart_wait_de_var.set(storage_targets.get("wait_for_de", False))
                        self.smart_after_bb_var.set(value.get("after_bb_behavior", "stop"))
                        # Sync threshold values
                        if hasattr(self, "smart_gold_threshold_var"):
                            self.smart_gold_threshold_var.set(str(storage_targets.get("gold_threshold", 100)))
                        if hasattr(self, "smart_elixir_threshold_var"):
                            self.smart_elixir_threshold_var.set(str(storage_targets.get("elixir_threshold", 100)))
                        if hasattr(self, "smart_de_threshold_var"):
                            self.smart_de_threshold_var.set(str(storage_targets.get("de_threshold", 100)))
                        self.save_settings()

                elif key == "achievement_farm_end_config":
                    if isinstance(value, dict):
                        self.achievement_end_duration_var.set(str(value.get("duration_minutes", 20)))
                        if hasattr(self, "achievement_end_enabled_var"):
                            self.achievement_end_enabled_var.set(bool(value.get("enabled", False)))
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
                    if hasattr(self, "sbarb_cast_spells_mode_var"):
                        # Convert to display name for dropdown
                        mode_display = {"target": "Target", "clumps": "Clumps", "first_detected": "First Detected"}.get(
                            value, "Clumps"
                        )
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

        self.state_manager.update(
            {
                "running": self.bot_running,
                "paused": self.bot_paused,
                "current_profile": self.current_profile,
                "loop_count": self.loop_count,
                "status": self.current_status,
                # Include profile settings for web GUI
                "troop_counts": profile_settings.get("troop_counts", [0, 0, 0, 0, 0, 0, 0]),
                "min_resources": profile_settings.get("min_resources", 100000),
                "max_th_level": profile_settings.get("max_th_level", 17),
                "lightning_damage": profile_settings.get("lightning_damage", 600),
                "queen_ability_timing": profile_settings.get("queen_ability_timing", 15),
                "king_ability_timing": profile_settings.get("king_ability_timing", 15),
                "warden_ability_timing": profile_settings.get("warden_ability_timing", 15),
                "rc_ability_timing": profile_settings.get("rc_ability_timing", 15),
                "sgoblin_cast_spells": profile_settings.get("sgoblin_cast_spells", False),
                "sgoblin_use_wallbreakers": profile_settings.get("sgoblin_use_wallbreakers", False),
                "sbarb_heroes_first": profile_settings.get("sbarb_heroes_first", False),
                "sbarb_queen_arrow_spells": profile_settings.get("sbarb_queen_arrow_spells", False),
                "sbarb_cast_spells": profile_settings.get("sbarb_cast_spells", False),
                "sbarb_cast_spells_target_mode": profile_settings.get("sbarb_cast_spells_target_mode", "clumps"),
                "sbarb_turbo_deployment": profile_settings.get("sbarb_turbo_deployment", False),
                "bb_gold_troop_mode": profile_settings.get("bb_gold_troop_mode", "night_witches"),
                # Achievement building scan settings (uses full key names)
                "achievement_scan_eagle_artillery": profile_settings.get("achievement_scan_eagle_artillery", True),
                "achievement_scan_monolith": profile_settings.get("achievement_scan_monolith", True),
                "achievement_scan_xbow": profile_settings.get("achievement_scan_xbow", True),
                "achievement_scan_inferno_tower": profile_settings.get("achievement_scan_inferno_tower", True),
                "achievement_scan_scattershot": profile_settings.get("achievement_scan_scattershot", True),
                "achievement_scan_spell_tower": profile_settings.get("achievement_scan_spell_tower", True),
                "achievement_scan_multi_archer_tower": profile_settings.get(
                    "achievement_scan_multi_archer_tower", True
                ),
                "achievement_scan_ricochet_cannon": profile_settings.get("achievement_scan_ricochet_cannon", True),
                "achievement_scan_firespitter": profile_settings.get("achievement_scan_firespitter", True),
                "achievement_scan_multi_gear_tower": profile_settings.get("achievement_scan_multi_gear_tower", True),
                "achievement_priority_list": profile_settings.get(
                    "achievement_priority_list",
                    [
                        "eagle_artillery",
                        "monolith",
                        "xbow",
                        "inferno_tower",
                        "scattershot",
                        "spell_tower",
                        "multi_archer_tower",
                        "ricochet_cannon",
                        "firespitter",
                        "multi_gear_tower",
                    ],
                ),
                # Global settings
                "reinforcements_enabled": getattr(self, "reinforcements_var", tk.BooleanVar()).get()
                if hasattr(self, "reinforcements_var")
                else False,
                "skip_on_th_fail": getattr(self, "skip_on_th_fail_var", tk.BooleanVar()).get()
                if hasattr(self, "skip_on_th_fail_var")
                else True,
                "parallel_scanning": getattr(self, "parallel_scanning", False),
                "gpu_scanning": getattr(self, "gpu_scanning", False),
                "overlay_enabled": getattr(self, "overlay_enabled", False),
                "overlay_hide_low_conf": getattr(self, "overlay_hide_low_conf", False),
                "auto_pause_enabled": getattr(self, "auto_pause_enabled_var", tk.BooleanVar()).get()
                if hasattr(self, "auto_pause_enabled_var")
                else False,
                "break_interval": getattr(self, "break_interval_var", tk.IntVar()).get()
                if hasattr(self, "break_interval_var")
                else 60,
                "break_duration": getattr(self, "break_duration_var", tk.IntVar()).get()
                if hasattr(self, "break_duration_var")
                else 5,
                "bb_collect_interval": getattr(self, "bb_collect_interval_var", tk.IntVar()).get()
                if hasattr(self, "bb_collect_interval_var")
                else 12,
                # Auto-pause settings
                "auto_pause_mode": self.auto_pause_mode.get(),
                "auto_pause_value": self.auto_pause_value.get(),
                "storage_full_gold": self.storage_full_gold_var.get(),
                "storage_full_elixir": self.storage_full_elixir_var.get(),
                "storage_full_de": self.storage_full_de_var.get(),
                "storage_full_preset": self.storage_full_preset_var.get(),
                "storage_presets": self.get_storage_presets(),
            }
        )
