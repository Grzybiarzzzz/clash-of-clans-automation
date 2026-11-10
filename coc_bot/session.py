"""Per-session bookkeeping: loot records, scheduled breaks and auto-pause."""

import os
import random
import time

from coc_bot import runtime
from coc_bot.controls import update_status
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.storages import (
    check_and_pause_if_storages_full,
    read_bb_base_storages,
    read_own_base_storages,
)


def save_loot_data(loot_data, loop_count):
    """
    Save loot data to a CSV file for tracking.
    """
    import csv
    from datetime import datetime

    filename = "data/loot_tracking.csv"
    file_exists = os.path.exists(filename)

    try:
        with open(filename, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["timestamp", "attack_number", "gold", "elixir", "dark_elixir", "total_loot"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header if file is new
            if not file_exists:
                writer.writeheader()

            # Calculate total loot value
            total_loot = (
                loot_data["gold"] + loot_data["elixir"] + (loot_data["dark_elixir"] * 100)
            )  # Dark elixir worth more

            # Write loot data
            writer.writerow(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "attack_number": loop_count,
                    "gold": loot_data["gold"],
                    "elixir": loot_data["elixir"],
                    "dark_elixir": loot_data["dark_elixir"],
                    "total_loot": total_loot,
                }
            )

        print(f"Loot data saved to {filename}")
        runtime.gui.log_message(f"Loot data saved to {filename}")

    except Exception as e:
        print(f"Error saving loot data: {e}")
        runtime.gui.log_message(f"Error saving loot data: {e}")


# Main action loop
# Setup automatic break timing
def schedule_next_break():
    # Get settings from GUI
    settings = runtime.gui.get_settings()
    break_interval = settings.get("break_interval", 45)  # minutes
    auto_pause_enabled = settings.get("auto_pause_enabled", True)

    if not auto_pause_enabled:
        return None  # No break scheduled

    # Add some randomization (±5 minutes)
    interval_seconds = (break_interval + random.uniform(-5, 5)) * 60
    return time.time() + interval_seconds


def check_auto_pause():
    """Check if auto-pause condition is met and pause bot if needed"""

    settings = runtime.gui.get_settings()
    auto_pause_mode = settings.get("auto_pause_mode", "manual")
    auto_pause_value = settings.get("auto_pause_value", 50)

    # Debug: Log auto-pause mode
    print(f"[AUTO-PAUSE] Mode: {auto_pause_mode}")

    should_pause = False
    pause_reason = ""

    if auto_pause_mode == "loops":
        # Check if loop count reached target
        if runtime.loop_count >= auto_pause_value:
            should_pause = True
            pause_reason = f"Auto-pause: {auto_pause_value} attacks completed"

    elif auto_pause_mode == "time":
        # Check if time limit reached (read from GUI to avoid circular import)
        if hasattr(runtime.gui, "auto_pause_start_time") and runtime.gui.auto_pause_start_time is not None:
            elapsed_minutes = (time.time() - runtime.gui.auto_pause_start_time) / 60
            if elapsed_minutes >= auto_pause_value:
                should_pause = True
                pause_reason = f"Auto-pause: {auto_pause_value} minutes elapsed"

    elif auto_pause_mode == "storage_full":
        # Check if storages are full based on current profile and user-selected resources
        current_profile = runtime.gui.current_profile
        settings = runtime.gui.get_settings()
        check_gold = settings.get("storage_full_gold", True)
        check_elixir = settings.get("storage_full_elixir", True)
        check_de = settings.get("storage_full_de", False)
        print(f"[AUTO-PAUSE] Storage Full check - Gold:{check_gold}, Elixir:{check_elixir}, DE:{check_de}")

        # Get the selected preset's max values for storage full check
        storage_full_preset = settings.get("storage_full_preset", "main")
        storage_presets = settings.get("storage_presets", {})
        preset_values = storage_presets.get(storage_full_preset, {})

        # Use preset values if available, otherwise fall back to global settings
        max_gold = preset_values.get("max_gold_storage", settings.get("max_gold_storage", 18000000))
        max_elixir = preset_values.get("max_elixir_storage", settings.get("max_elixir_storage", 14000000))
        max_de = preset_values.get("max_dark_elixir_storage", settings.get("max_dark_elixir_storage", 240000))
        max_bb_gold = preset_values.get("max_bb_gold_storage", settings.get("max_bb_gold_storage", 5000000))
        max_bb_elixir = preset_values.get("max_bb_elixir_storage", settings.get("max_bb_elixir_storage", 5000000))

        if current_profile in ["BB Gold", "BB Elixir"]:
            # Check Builder Base storages (DE is ignored for BB)
            # Note: track_resources is called internally by read_bb_base_storages()
            bb_storages = read_bb_base_storages()
            if bb_storages["success"]:
                # Check if 3-consecutive-same-readings triggered a pause
                if check_and_pause_if_storages_full(base_type="builder_base"):
                    return True  # Already paused by consecutive readings check

                # Calculate percentages using preset's max values
                bb_gold_percent = (
                    min(100, int((bb_storages["gold_absolute"] / max_bb_gold) * 100)) if max_bb_gold > 0 else 0
                )
                bb_elixir_percent = (
                    min(100, int((bb_storages["elixir_absolute"] / max_bb_elixir) * 100)) if max_bb_elixir > 0 else 0
                )
                bb_gold_full = bb_gold_percent >= 99
                bb_elixir_full = bb_elixir_percent >= 99

                # Check only the resources the user selected (DE ignored for BB)
                resources_to_check = []
                full_status = []
                if check_gold:
                    resources_to_check.append("Gold")
                    full_status.append(bb_gold_full)
                if check_elixir:
                    resources_to_check.append("Elixir")
                    full_status.append(bb_elixir_full)

                # Pause if ALL selected resources are full
                if resources_to_check and all(full_status):
                    should_pause = True
                    pause_reason = f"Auto-pause: BB {'+'.join(resources_to_check)} full using '{storage_full_preset}' preset (Gold: {bb_gold_percent}%, Elixir: {bb_elixir_percent}%)"
        else:
            # Check main base storages
            # Note: track_resources is called internally by read_own_base_storages()
            storages = read_own_base_storages()
            if storages["success"]:
                # Check if 3-consecutive-same-readings triggered a pause
                if check_and_pause_if_storages_full(base_type="main_base"):
                    return True  # Already paused by consecutive readings check

                # Calculate percentages using preset's max values
                gold_percent = min(100, int((storages["gold_absolute"] / max_gold) * 100)) if max_gold > 0 else 0
                elixir_percent = (
                    min(100, int((storages["elixir_absolute"] / max_elixir) * 100)) if max_elixir > 0 else 0
                )
                de_percent = min(100, int((storages["de_absolute"] / max_de) * 100)) if max_de > 0 else 0
                gold_full = gold_percent >= 99
                elixir_full = elixir_percent >= 99
                de_full = de_percent >= 99

                # Check only the resources the user selected
                resources_to_check = []
                full_status = []
                if check_gold:
                    resources_to_check.append("Gold")
                    full_status.append(gold_full)
                if check_elixir:
                    resources_to_check.append("Elixir")
                    full_status.append(elixir_full)
                if check_de:
                    resources_to_check.append("DE")
                    full_status.append(de_full)

                # Debug output
                print(
                    f"[AUTO-PAUSE] Calculated: Gold={gold_percent}% (full:{gold_full}), Elixir={elixir_percent}% (full:{elixir_full}), DE={de_percent}% (full:{de_full})"
                )
                print(
                    f"[AUTO-PAUSE] Checking: {resources_to_check}, Status: {full_status}, All full: {all(full_status) if full_status else False}"
                )

                # Pause if ALL selected resources are full
                if resources_to_check and all(full_status):
                    should_pause = True
                    pause_reason = f"Auto-pause: {'+'.join(resources_to_check)} full using '{storage_full_preset}' preset (Gold: {gold_percent}%, Elixir: {elixir_percent}%, DE: {de_percent}%)"

    if should_pause:
        runtime.paused = True
        runtime.gui.bot_paused = True
        print(f"[AUTO-PAUSE] {pause_reason}")
        runtime.gui.log_message(pause_reason)
        send_discord_debug_log(pause_reason, "INFO")
        runtime.root.after(0, update_status)
        return True

    return False
