# queue_manager.py
"""
Queue Manager for Clash of Clans Bot
Handles queue state and logic for both Smart and Manual modes.
"""

import time
from typing import Optional, Dict, List, Tuple

# Mode categorization
MAIN_BASE_MODES = [
    'Farming', 'Trophy Push', 'Derank', 'SGoblin Farm',
    'SBarb Farm', 'Achievement Farm', 'Custom'
]

BUILDER_BASE_MODES = ['BB Elixir', 'BB Gold']


def get_village_for_mode(mode_name: str) -> str:
    """
    Determine which village a mode belongs to.

    Args:
        mode_name: Name of the attack mode

    Returns:
        "main" for main base modes, "builder" for builder base modes

    Raises:
        ValueError: If mode_name is not recognized
    """
    if mode_name in MAIN_BASE_MODES:
        return "main"
    elif mode_name in BUILDER_BASE_MODES:
        return "builder"
    else:
        raise ValueError(f"Unknown mode: {mode_name}")


class QueueManager:
    """
    Manages queue state and execution logic for both Smart and Manual modes.

    Smart Mode: Auto-selects modes based on storage levels and user rules
    Manual Mode: Executes user-defined task schedule with time or storage conditions
    """

    def __init__(self, gui, read_own_base_storages=None, read_bb_storages=None, switch_village=None):
        """
        Initialize Queue Manager.

        Args:
            gui: Reference to BotGUI instance for settings and logging
            read_own_base_storages: Callback function to read main base storage percentages
            read_bb_storages: Callback function to read builder base storage percentages
            switch_village: Callback function to switch between villages
        """
        self.gui = gui

        # Store callback functions to avoid circular imports
        self.read_own_base_storages = read_own_base_storages
        self.read_bb_storages = read_bb_storages
        self.switch_village = switch_village

        # Queue state
        self.queue_active = False
        self.current_task_index = 0
        self.task_start_time = None
        self.current_village = "main"  # "main" or "builder"

        # Achievement Farm end behavior state
        self.achievement_farm_active = False
        self.achievement_farm_start_time = None

        print("[QUEUE MANAGER] Initialized")

    def set_callbacks(self, read_own_base_storages, read_bb_storages, switch_village):
        """
        Set callback functions after initialization.

        Args:
            read_own_base_storages: Callback function to read main base storage percentages
            read_bb_storages: Callback function to read builder base storage percentages
            switch_village: Callback function to switch between villages
        """
        self.read_own_base_storages = read_own_base_storages
        self.read_bb_storages = read_bb_storages
        self.switch_village = switch_village
        print("[QUEUE MANAGER] Callbacks set")

    def start_queue(self):
        """
        Initialize queue execution.
        Called when bot starts with queue_enabled=True.
        """
        self.queue_active = True
        self.current_task_index = 0
        self.task_start_time = None
        self.current_village = "main"  # Always start in main base
        self.achievement_farm_active = False
        self.achievement_farm_start_time = None

        settings = self.gui.get_settings()
        queue_mode = settings.get('queue_mode', 'smart')

        print(f"[QUEUE MANAGER] Queue started in {queue_mode.upper()} mode")
        self.gui.log_message(f"Queue System: Started in {queue_mode.upper()} mode")

    def reset_queue(self):
        """
        Reset queue state.
        Called on bot restart or when queue is disabled.
        """
        self.queue_active = False
        self.current_task_index = 0
        self.task_start_time = None
        self.current_village = "main"
        self.achievement_farm_active = False
        self.achievement_farm_start_time = None

        print("[QUEUE MANAGER] Queue reset")

    def get_next_mode(self) -> Optional[str]:
        """
        Determine next mode to execute based on queue type (Smart or Manual).

        Returns:
            Mode name string (e.g., "SBarb Farm", "BB Gold") or None if queue complete
        """
        # Check Achievement Farm completion first (applies to both modes)
        if self.achievement_farm_active:
            if self.check_achievement_farm_completion():
                return None  # Stop bot
            return "Achievement Farm"  # Continue Achievement Farm

        # Get current settings
        settings = self.gui.get_settings()
        queue_mode = settings.get('queue_mode', 'smart')

        # Route to appropriate queue mode logic
        if queue_mode == 'smart':
            return self.execute_smart_mode()
        else:  # manual
            return self.execute_manual_mode()

    def execute_smart_mode(self) -> Optional[str]:
        """
        Execute Smart Mode queue logic.

        Flow:
        1. Start with main base mode (user-selected: SBarb or SGoblin)
        2. Check storages after each attack
        3. When full → switch to BB
        4. Auto-select BB mode (Gold or Elixir based on 3x rule)
        5. Check BB storages
        6. When full → Stop or Achievement Farm

        Returns:
            Mode name to execute, or None if queue complete
        """
        settings = self.gui.get_settings()
        config = settings.get('smart_mode_config', {})

        # Check if storage reading functions are available
        if not self.read_own_base_storages or not self.read_bb_storages:
            # Functions not yet implemented - return default mode
            print("[QUEUE MANAGER] Storage functions not yet implemented - using default mode")
            return config.get('main_base_mode', 'SBarb Farm')

        # PHASE 1: Main Base Farming
        if self.current_village == "main":
            mode = config.get('main_base_mode', 'SBarb Farm')

            # Check if storages full
            storages = self.read_own_base_storages()
            if storages['success']:
                storage_targets = config.get('storage_targets', {})
                gold_full = storages['gold_percent'] >= storage_targets.get('gold_threshold', 100)
                elixir_full = storages['elixir_percent'] >= storage_targets.get('elixir_threshold', 100)

                if storage_targets.get('wait_for_de', False):
                    de_full = storages['de_percent'] >= storage_targets.get('de_threshold', 100)
                    main_base_complete = gold_full and elixir_full and de_full
                else:
                    main_base_complete = gold_full and elixir_full

                if main_base_complete:
                    print("[SMART MODE] Main base storages full - switching to BB")
                    print(f"[SMART MODE] Gold: {storages['gold_percent']:.1f}%, Elixir: {storages['elixir_percent']:.1f}%, DE: {storages['de_percent']:.1f}%")
                    self.gui.log_message("Smart Mode: Main storages full, switching to Builder Base")

                    # Determine BB mode based on 3x rule or default
                    bb_mode = self.select_bb_mode(config)

                    if self.ensure_correct_village(bb_mode):
                        return bb_mode
                    else:
                        print("[SMART MODE] Failed to switch to BB - continuing main base")
                        return mode

            return mode  # Continue main base farming

        # PHASE 2: Builder Base Farming
        elif self.current_village == "builder":
            # Check BB storages and handle completion
            bb_storages = self.read_bb_storages()

            if bb_storages['success']:
                bb_gold_full = bb_storages['gold_percent'] >= 100
                bb_elixir_full = bb_storages['elixir_percent'] >= 100

                if bb_gold_full and bb_elixir_full:
                    # PHASE 3: BB Complete - Stop or Achievement Farm
                    after_behavior = config.get('after_bb_behavior', 'stop')
                    print(f"[SMART MODE] BB storages full - Gold: {bb_storages['gold_percent']:.1f}%, Elixir: {bb_storages['elixir_percent']:.1f}%")

                    if after_behavior == "achievement_farm":
                        print("[SMART MODE] BB storages full - switching to Achievement Farm")
                        self.gui.log_message("Smart Mode: BB full, switching to Achievement Farm")

                        if self.ensure_correct_village("Achievement Farm"):
                            self.achievement_farm_active = True
                            self.achievement_farm_start_time = time.time()
                            return "Achievement Farm"
                    else:  # "stop"
                        print("[SMART MODE] Queue complete - stopping bot")
                        self.gui.log_message("Smart Mode: Queue complete - stopping bot")
                        self.gui.stop_bot()
                        return None

            # Continue BB farming - return current mode or default
            # Get current mode from gui profile
            current_mode = self.gui.current_profile
            if current_mode in BUILDER_BASE_MODES:
                return current_mode
            return "BB Gold"  # Default fallback

        # Fallback
        return config.get('main_base_mode', 'SBarb Farm')

    def select_bb_mode(self, config: Dict) -> str:
        """
        Select BB mode based on 3x gold/elixir ratio rule.

        Args:
            config: Smart mode configuration

        Returns:
            "BB Gold" or "BB Elixir"
        """
        try:
            if config.get('bb_auto_select_enabled', True) and self.read_bb_storages:
                bb_storages = self.read_bb_storages()
                if bb_storages['success']:
                    ratio = config.get('bb_gold_elixir_ratio', 3.0)
                    gold_pct = bb_storages['gold_percent']
                    elixir_pct = bb_storages['elixir_percent']

                    print(f"[SMART MODE] BB Storage check - Gold: {gold_pct:.1f}%, Elixir: {elixir_pct:.1f}%")

                    # If gold is more than 3x elixir, farm elixir instead
                    if gold_pct > (elixir_pct * ratio):
                        print(f"[SMART MODE] Gold > {ratio}x Elixir - selecting BB Elixir mode")
                        self.gui.log_message(f"Smart Mode: Selecting BB Elixir (Gold {gold_pct:.0f}% > {ratio}x Elixir {elixir_pct:.0f}%)")
                        return "BB Elixir"
                    else:
                        print(f"[SMART MODE] Selecting BB Gold mode (default)")
                        self.gui.log_message(f"Smart Mode: Selecting BB Gold")
                        return "BB Gold"
        except Exception as e:
            print(f"[SMART MODE] Error selecting BB mode: {e}")

        return "BB Gold"  # Default

    def execute_manual_mode(self) -> Optional[str]:
        """
        Execute Manual Mode queue logic.

        Flow:
        1. Execute tasks in order from manual_mode_schedule
        2. Check task completion condition (time or storage)
        3. Advance to next task when complete
        4. Stop when all tasks done (optionally run Achievement Farm)

        Returns:
            Mode name to execute, or None if queue complete
        """
        settings = self.gui.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        # Check if queue complete
        if self.current_task_index >= len(schedule):
            print("[MANUAL MODE] All tasks complete")

            # Check for Achievement Farm end behavior
            achievement_config = settings.get('achievement_farm_end_config', {})
            if achievement_config.get('enabled', False):
                if not self.achievement_farm_active:
                    print("[MANUAL MODE] Starting Achievement Farm end behavior")
                    self.gui.log_message("Manual Mode: Starting Achievement Farm")

                    if self.ensure_correct_village("Achievement Farm"):
                        self.achievement_farm_active = True
                        self.achievement_farm_start_time = time.time()
                        return "Achievement Farm"

            # No more tasks - stop bot
            print("[MANUAL MODE] Queue complete - stopping bot")
            self.gui.log_message("Manual Mode: Queue complete")
            self.gui.stop_bot()
            return None

        # Get current task
        task = schedule[self.current_task_index]
        mode = task.get('mode', 'SBarb Farm')

        # Ensure correct village for this mode
        if not self.ensure_correct_village(mode):
            print(f"[MANUAL MODE] ERROR: Failed to switch to village for {mode}")
            return None

        # Check if task complete
        if self.check_manual_task_completion(task):
            print(f"[MANUAL MODE] Task {self.current_task_index + 1} complete: {mode}")
            self.gui.log_message(f"Task {self.current_task_index + 1} complete: {mode}")
            self.current_task_index += 1

            # Recursive call to get next task
            return self.execute_manual_mode()

        return mode

    def check_manual_task_completion(self, task: Dict) -> bool:
        """
        Check if manual task condition is met.

        Args:
            task: Task dictionary with condition_type, time_minutes, or storage_target

        Returns:
            True if task is complete, False otherwise
        """
        condition_type = task.get('condition_type', 'time')

        if condition_type == 'time':
            # Time-based condition
            if self.task_start_time is None:
                self.task_start_time = time.time()
                return False

            elapsed_minutes = (time.time() - self.task_start_time) / 60
            target_minutes = task.get('time_minutes', 30)

            if elapsed_minutes >= target_minutes:
                self.task_start_time = None  # Reset for next task
                return True
            return False

        elif condition_type == 'storage':
            # Storage-based condition
            storage_target = task.get('storage_target', {})

            # Read appropriate storages based on current village
            try:
                if self.current_village == "main":
                    if not self.read_own_base_storages:
                        print("[MANUAL MODE] Storage reading function not available")
                        return False
                    storages = self.read_own_base_storages()
                    if not storages['success']:
                        print("[MANUAL MODE] Failed to read main base storages")
                        return False

                    gold_met = storage_target.get('gold') is None or storages['gold_percent'] >= storage_target['gold']
                    elixir_met = storage_target.get('elixir') is None or storages['elixir_percent'] >= storage_target['elixir']
                    de_met = storage_target.get('de') is None or storages['de_percent'] >= storage_target['de']

                    is_complete = gold_met and elixir_met and de_met

                    if is_complete:
                        print(f"[MANUAL MODE] Storage target reached - Gold: {storages['gold_percent']:.1f}%, Elixir: {storages['elixir_percent']:.1f}%, DE: {storages['de_percent']:.1f}%")

                    return is_complete

                elif self.current_village == "builder":
                    if not self.read_bb_storages:
                        print("[MANUAL MODE] Storage reading function not available")
                        return False
                    storages = self.read_bb_storages()
                    if not storages['success']:
                        print("[MANUAL MODE] Failed to read BB storages")
                        return False

                    gold_met = storage_target.get('gold') is None or storages['gold_percent'] >= storage_target['gold']
                    elixir_met = storage_target.get('elixir') is None or storages['elixir_percent'] >= storage_target['elixir']

                    is_complete = gold_met and elixir_met

                    if is_complete:
                        print(f"[MANUAL MODE] Storage target reached - Gold: {storages['gold_percent']:.1f}%, Elixir: {storages['elixir_percent']:.1f}%")

                    return is_complete
            except Exception as e:
                print(f"[MANUAL MODE] Error checking storage condition: {e}")
                return False

            return False

        return False

    def check_achievement_farm_completion(self) -> bool:
        """
        Check if Achievement Farm end behavior duration is complete.

        Returns:
            True if Achievement Farm should stop, False otherwise
        """
        if not self.achievement_farm_active:
            return False

        settings = self.gui.get_settings()
        achievement_config = settings.get('achievement_farm_end_config', {})
        duration_minutes = achievement_config.get('duration_minutes', 20)

        elapsed_minutes = (time.time() - self.achievement_farm_start_time) / 60

        if elapsed_minutes >= duration_minutes:
            print(f"[QUEUE] Achievement Farm complete ({duration_minutes} min)")
            self.gui.log_message(f"Achievement Farm complete - {duration_minutes} min elapsed")
            self.gui.stop_bot()
            return True

        return False

    def ensure_correct_village(self, mode_name: str) -> bool:
        """
        Ensure bot is in correct village for given mode.
        Switches villages if necessary.

        Args:
            mode_name: Name of the mode to execute

        Returns:
            True if in correct village (or successfully switched), False if switch failed
        """
        required_village = get_village_for_mode(mode_name)

        if self.current_village != required_village:
            print(f"[QUEUE] Village switch needed: {self.current_village} → {required_village}")
            self.gui.log_message(f"Queue: Switching to {required_village} village for {mode_name}")

            try:
                if not self.switch_village:
                    print("[QUEUE] Village switching function not available")
                    self.gui.log_message("ERROR: Village switching not available", "ERROR")
                    return False

                # Map village names to switch_village parameter format
                target = "builder_base" if required_village == "builder" else "main"
                success = self.switch_village(target)

                if success:
                    self.current_village = required_village
                    print(f"[QUEUE] Successfully switched to {required_village} village")
                    return True
                else:
                    print(f"[QUEUE] Failed to switch to {required_village} village")
                    self.gui.log_message(f"ERROR: Failed to switch to {required_village} village", "ERROR")
                    return False
            except Exception as e:
                print(f"[QUEUE] Error during village switch: {e}")
                self.gui.log_message(f"ERROR: Village switch failed - {e}", "ERROR")
                return False

        return True

    def update_village_state(self, new_village: str):
        """
        Update current village state.

        Args:
            new_village: "main" or "builder"
        """
        self.current_village = new_village
        print(f"[QUEUE] Village state updated: {new_village}")

    def validate_manual_schedule(self, schedule: List[Dict]) -> Tuple[bool, str]:
        """
        Validate manual schedule for invalid transitions.

        Rules:
        - No main base mode → main base mode (except Achievement Farm)

        Args:
            schedule: List of task dictionaries

        Returns:
            (is_valid, error_message) tuple
        """
        for i in range(len(schedule) - 1):
            current_mode = schedule[i].get('mode', '')
            next_mode = schedule[i + 1].get('mode', '')

            try:
                current_village = get_village_for_mode(current_mode)
                next_village = get_village_for_mode(next_mode)
            except ValueError as e:
                return False, str(e)

            # Check for invalid main base → main base
            if current_village == "main" and next_village == "main":
                if current_mode != "Achievement Farm" and next_mode != "Achievement Farm":
                    return False, f"Invalid transition: {current_mode} → {next_mode} (no main base mode switching allowed)"

        return True, "Schedule valid"
