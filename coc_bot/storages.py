"""Reading own storages and pausing when they stop growing."""

import time

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.profiles import auto_switch_profile_if_needed
from coc_bot.vision.capture import frozen_frame, grab as grab_screen
from coc_bot.vision.ocr import read_resource

# Resource tracking for full storage detection (auto-pause when no loot gained)
last_3_resources = {
    "main_base": [],  # List of (gold, elixir, dark_elixir) tuples
    "builder_base": [],  # List of (gold, elixir) tuples
}


def track_resources(gold, elixir, dark_elixir=None, base_type="main_base"):
    """
    Track resource readings to detect full storages (no loot gained over 3 attacks).

    Args:
        gold (int): Gold amount
        elixir (int): Elixir amount
        dark_elixir (int, optional): Dark elixir amount (None for Builder Base)
        base_type (str): 'main_base' or 'builder_base'
    """
    global last_3_resources

    # Create resource tuple
    if base_type == "main_base" and dark_elixir is not None:
        resource_tuple = (gold, elixir, dark_elixir)
    else:
        resource_tuple = (gold, elixir)

    # Add to tracking list
    last_3_resources[base_type].append(resource_tuple)

    # Keep only last 3
    if len(last_3_resources[base_type]) > 3:
        last_3_resources[base_type] = last_3_resources[base_type][-3:]


def check_and_pause_if_storages_full(base_type="main_base"):
    """
    Check if last 3 resource readings are the same (storages full, no loot gained).
    If so, pause the bot and notify the user.

    Args:
        base_type (str): 'main_base' or 'builder_base'

    Returns:
        bool: True if bot was paused, False otherwise
    """
    global last_3_resources

    readings = last_3_resources[base_type]

    # Need exactly 3 readings
    if len(readings) < 3:
        return False

    # Check if all 3 readings are exactly the same
    first = readings[0]
    all_same = all(reading == first for reading in readings[1:])

    if all_same:
        # All 3 consecutive attacks had same resources - storages are full!
        if base_type == "main_base":
            resource_str = f"Gold: {first[0]:,}, Elixir: {first[1]:,}"
            if len(first) == 3:
                resource_str += f", Dark: {first[2]:,}"
        else:
            resource_str = f"Gold: {first[0]:,}, Elixir: {first[1]:,}"

        print(f"\n{'=' * 60}")
        print("⚠️ STORAGES FULL - NO LOOT GAINED")
        print(f"{'=' * 60}")
        print("Same resources detected for 3 consecutive attacks:")
        print(f"  {resource_str}")
        print("Likely max storage values are outdated or storages are full.")
        print("AUTO-PAUSING BOT - Please update profile storage maximums!")
        print(f"{'=' * 60}\n")

        runtime.gui.log_message("⚠️ STORAGES FULL - Pausing bot")
        runtime.gui.log_message(f"Same resources: {resource_str}")
        runtime.gui.log_message("Update profile storage maximums!")

        send_discord_debug_log(
            f"🛑 Storages Full - Auto-pausing bot\n"
            f"Same resources for 3 attacks: {resource_str}\n"
            f"Update profile storage maximums!",
            "WARNING",
        )

        # Pause the bot
        runtime.paused = True
        runtime.gui.toggle_pause()  # Update GUI state

        # Clear tracking to avoid repeated pauses
        last_3_resources[base_type] = []

        return True

    return False


# Last successful reading per base, for comparing storage growth with the loot screen
_previous_values = {"main_base": None, "builder_base": None}

# How much a storage may grow beyond the loot shown (league and star bonuses)
LOOT_AUDIT_BONUS = {"gold": 600_000, "elixir": 600_000, "dark_elixir": 6_000}


def read_storage_values(base_type="main_base", attempts=3, delay=0.2):
    """Read the storage numbers of the village on screen.

    Returns {'gold', 'elixir', 'dark_elixir'}, or None when gold or elixir stayed
    unreadable after ``attempts`` captures (the screen may still be loading). Dark elixir
    is optional: it is 0 when it cannot be read, and always 0 for the Builder Base.
    """
    if base_type == "builder_base":
        gold_region, elixir_region, dark_region = config.BB_BASE_GOLD_REGION, config.BB_BASE_ELIXIR_REGION, None
        context = "bb_base_screen"
    else:
        gold_region, elixir_region = config.BASE_GOLD_REGION, config.BASE_ELIXIR_REGION
        dark_region = getattr(config, "BASE_DARK_ELIXIR_REGION", None)
        context = "base_screen"

    for attempt in range(attempts):
        with frozen_frame():
            gold = read_resource(grab_screen(gold_region), context, "gold")
            elixir = read_resource(grab_screen(elixir_region), context, "elixir")
            dark = None
            if dark_region is not None:
                dark = read_resource(grab_screen(dark_region), "base_dark_elixir", "dark_elixir")
        if gold is not None and elixir is not None:
            values = {"gold": gold, "elixir": elixir, "dark_elixir": dark or 0}
            _previous_values[base_type] = dict(values)
            return values
        if attempt < attempts - 1:
            print(f"[STORAGE] Storage numbers unreadable, retrying ({attempt + 1}/{attempts})...")
            time.sleep(delay)
    return None


def previous_storage_values(base_type="main_base"):
    """The last successful ``read_storage_values`` result for that base, or None."""
    return _previous_values[base_type]


def find_loot_mismatches(before, after, loot, capacity, bonus=LOOT_AUDIT_BONUS):
    """Compare storage growth across one attack with the loot the end screen showed.

    A storage should grow by the loot, plus at most a bonus, unless it is full. A change
    outside that range means one of the three readings is wrong, or resources were spent
    in between, so the result is a hint for reviewing OCR crops, not proof.
    Returns a list of {'resource', 'gained', 'loot'}.
    """
    if before is None or after is None:
        return []
    mismatches = []
    for resource in ("gold", "elixir", "dark_elixir"):
        gained = after[resource] - before[resource]
        shown = loot[resource]
        if after[resource] >= 0.98 * capacity[resource]:
            continue  # a full storage hides how much was gained
        if gained < 0.98 * shown - 500 or gained > shown + bonus[resource]:
            mismatches.append({"resource": resource, "gained": gained, "loot": shown})
    return mismatches


def _percent(value, maximum):
    return min(100, int((value / maximum) * 100)) if maximum > 0 else 0


def read_own_base_storages():
    """
    Read own base storage percentages (Gold, Elixir, Dark Elixir).
    Reads the absolute values from the BASE_*_REGION coordinates, then calculates
    percentages based on the max_storage settings.

    Returns:
        dict: {
            'gold_percent': int (0-100),
            'elixir_percent': int (0-100),
            'de_percent': int (0-100),
            'gold_absolute': int,
            'elixir_absolute': int,
            'de_absolute': int,
            'success': bool   # False when gold or elixir could not be read
        }
    """
    result = {
        "gold_percent": 0,
        "elixir_percent": 0,
        "de_percent": 0,
        "gold_absolute": 0,
        "elixir_absolute": 0,
        "de_absolute": 0,
        "success": False,
    }

    try:
        values = read_storage_values("main_base")
        if values is None:
            print("[STORAGE] Main Base storages unreadable - no decision is based on this read")
            send_discord_debug_log("Storage read failed: numbers unreadable", "WARNING")
            return result

        settings = runtime.gui.get_settings()
        max_gold = settings.get("max_gold_storage", 18000000)
        max_elixir = settings.get("max_elixir_storage", 14000000)
        max_de = settings.get("max_dark_elixir_storage", 240000)

        result["gold_absolute"] = values["gold"]
        result["elixir_absolute"] = values["elixir"]
        result["de_absolute"] = values["dark_elixir"]
        result["gold_percent"] = _percent(values["gold"], max_gold)
        result["elixir_percent"] = _percent(values["elixir"], max_elixir)
        result["de_percent"] = _percent(values["dark_elixir"], max_de)
        result["success"] = True

        print(
            f"[STORAGE] Main Base: Gold={result['gold_percent']}% ({values['gold']:,}/{max_gold:,}), "
            f"Elixir={result['elixir_percent']}% ({values['elixir']:,}/{max_elixir:,}), "
            f"DE={result['de_percent']}% ({values['dark_elixir']:,}/{max_de:,})"
        )
        send_discord_debug_log(
            f"Storage Check: Gold={result['gold_percent']}%, Elixir={result['elixir_percent']}%, "
            f"DE={result['de_percent']}%"
        )

        # Track resources for 3-consecutive-same-readings detection (fallback safety)
        track_resources(values["gold"], values["elixir"], values["dark_elixir"], base_type="main_base")
        check_and_pause_if_storages_full(base_type="main_base")

        return result

    except Exception as e:
        print(f"[STORAGE] ERROR reading own base storages: {e}")
        send_discord_debug_log(f"Storage read error: {e}", "ERROR")
        return result


def read_bb_base_storages():
    """
    Read Builder Base storage percentages (Gold, Elixir).

    The Builder Base numbers use the main-base digit templates, and BB_BASE_*_REGION in
    config.py still hold the main-base coordinates; recalibrate them if the read fails.

    Returns:
        dict: {
            'gold_percent': int (0-100),
            'elixir_percent': int (0-100),
            'gold_absolute': int,
            'elixir_absolute': int,
            'success': bool   # False when a number could not be read
        }
    """
    result = {"gold_percent": 0, "elixir_percent": 0, "gold_absolute": 0, "elixir_absolute": 0, "success": False}

    try:
        if not hasattr(config, "BB_BASE_GOLD_REGION") or not hasattr(config, "BB_BASE_ELIXIR_REGION"):
            print("[STORAGE] BB storage regions not defined in config.py")
            return result

        values = read_storage_values("builder_base")
        if values is None:
            print("[STORAGE] Builder Base storages unreadable - no decision is based on this read")
            send_discord_debug_log("BB storage read failed: numbers unreadable", "WARNING")
            return result

        settings = runtime.gui.get_settings()
        max_bb_gold = settings.get("max_bb_gold_storage", 5000000)
        max_bb_elixir = settings.get("max_bb_elixir_storage", 5000000)

        result["gold_absolute"] = values["gold"]
        result["elixir_absolute"] = values["elixir"]
        result["gold_percent"] = _percent(values["gold"], max_bb_gold)
        result["elixir_percent"] = _percent(values["elixir"], max_bb_elixir)
        result["success"] = True

        print(
            f"[STORAGE] Builder Base: Gold={result['gold_percent']}% ({values['gold']:,}/{max_bb_gold:,}), "
            f"Elixir={result['elixir_percent']}% ({values['elixir']:,}/{max_bb_elixir:,})"
        )
        send_discord_debug_log(
            f"BB Storage Check: Gold={result['gold_percent']}%, Elixir={result['elixir_percent']}%"
        )

        # Track resources for 3-consecutive-same-readings detection (fallback safety)
        track_resources(values["gold"], values["elixir"], dark_elixir=None, base_type="builder_base")
        check_and_pause_if_storages_full(base_type="builder_base")

        # Auto-switch profile if BB resources suggest wrong account (no dark elixir in BB)
        auto_switch_profile_if_needed(values["gold"], values["elixir"], dark_elixir=None)

        return result

    except Exception as e:
        print(f"[STORAGE] ERROR reading BB storages: {e}")
        send_discord_debug_log(f"BB storage read error: {e}", "ERROR")
        return result
