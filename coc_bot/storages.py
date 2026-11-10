"""Reading own storages and pausing when they stop growing."""

from PIL import ImageGrab

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.profiles import auto_switch_profile_if_needed
from coc_bot.vision.ocr import ocr_attack_resource_template_digits

# Resource tracking for full storage detection (auto-pause when no loot gained)
last_3_resources = {
    'main_base': [],  # List of (gold, elixir, dark_elixir) tuples
    'builder_base': []  # List of (gold, elixir) tuples
}


def track_resources(gold, elixir, dark_elixir=None, base_type='main_base'):
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
    if base_type == 'main_base' and dark_elixir is not None:
        resource_tuple = (gold, elixir, dark_elixir)
    else:
        resource_tuple = (gold, elixir)

    # Add to tracking list
    last_3_resources[base_type].append(resource_tuple)

    # Keep only last 3
    if len(last_3_resources[base_type]) > 3:
        last_3_resources[base_type] = last_3_resources[base_type][-3:]


def check_and_pause_if_storages_full(base_type='main_base'):
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
        if base_type == 'main_base':
            resource_str = f"Gold: {first[0]:,}, Elixir: {first[1]:,}"
            if len(first) == 3:
                resource_str += f", Dark: {first[2]:,}"
        else:
            resource_str = f"Gold: {first[0]:,}, Elixir: {first[1]:,}"

        print(f"\n{'='*60}")
        print("⚠️ STORAGES FULL - NO LOOT GAINED")
        print(f"{'='*60}")
        print("Same resources detected for 3 consecutive attacks:")
        print(f"  {resource_str}")
        print("Likely max storage values are outdated or storages are full.")
        print("AUTO-PAUSING BOT - Please update profile storage maximums!")
        print(f"{'='*60}\n")

        runtime.gui.log_message("⚠️ STORAGES FULL - Pausing bot")
        runtime.gui.log_message(f"Same resources: {resource_str}")
        runtime.gui.log_message("Update profile storage maximums!")

        send_discord_debug_log(
            f"🛑 Storages Full - Auto-pausing bot\n"
            f"Same resources for 3 attacks: {resource_str}\n"
            f"Update profile storage maximums!",
            "WARNING"
        )

        # Pause the bot
        runtime.paused = True
        runtime.gui.toggle_pause()  # Update GUI state

        # Clear tracking to avoid repeated pauses
        last_3_resources[base_type] = []

        return True

    return False


def read_own_base_storages():
    """
    Read own base storage percentages (Gold, Elixir, Dark Elixir).
    Uses existing BASE_*_REGION coordinates to read absolute values,
    then calculates percentages based on max_storage settings.

    Returns:
        dict: {
            'gold_percent': int (0-100),
            'elixir_percent': int (0-100),
            'de_percent': int (0-100),
            'gold_absolute': int,
            'elixir_absolute': int,
            'de_absolute': int,
            'success': bool
        }
    """
    result = {
        'gold_percent': 0,
        'elixir_percent': 0,
        'de_percent': 0,
        'gold_absolute': 0,
        'elixir_absolute': 0,
        'de_absolute': 0,
        'success': False
    }

    try:
        # Read absolute storage values using existing regions and OCR
        # Retry if OCR returns 0 (usually an OCR error)

        # Read Gold with template matching OCR
        base_gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
        gold_absolute = ocr_attack_resource_template_digits(base_gold_img, context='base_screen', debug=False, resource_type='gold')

        # Read Elixir with template matching OCR
        base_elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
        elixir_absolute = ocr_attack_resource_template_digits(base_elixir_img, context='base_screen', debug=False, resource_type='elixir')

        # Read Dark Elixir with template matching OCR
        de_absolute = 0
        if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
            base_dark_elixir_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
            de_absolute = ocr_attack_resource_template_digits(base_dark_elixir_img, context='base_dark_elixir', debug=False, resource_type='dark_elixir')

        # Get max storage values from settings
        settings = runtime.gui.get_settings()
        max_gold = settings.get('max_gold_storage', 18000000)
        max_elixir = settings.get('max_elixir_storage', 14000000)
        max_de = settings.get('max_dark_elixir_storage', 240000)

        # Calculate percentages
        gold_percent = min(100, int((gold_absolute / max_gold) * 100)) if max_gold > 0 else 0
        elixir_percent = min(100, int((elixir_absolute / max_elixir) * 100)) if max_elixir > 0 else 0
        de_percent = min(100, int((de_absolute / max_de) * 100)) if max_de > 0 else 0

        # Update result
        result['gold_absolute'] = gold_absolute
        result['elixir_absolute'] = elixir_absolute
        result['de_absolute'] = de_absolute
        result['gold_percent'] = gold_percent
        result['elixir_percent'] = elixir_percent
        result['de_percent'] = de_percent
        result['success'] = True

        print(f"[STORAGE] Main Base: Gold={gold_percent}% ({gold_absolute:,}/{max_gold:,}), "
              f"Elixir={elixir_percent}% ({elixir_absolute:,}/{max_elixir:,}), "
              f"DE={de_percent}% ({de_absolute:,}/{max_de:,})")

        send_discord_debug_log(
            f"Storage Check: Gold={gold_percent}%, Elixir={elixir_percent}%, DE={de_percent}%"
        )

        # Track resources for 3-consecutive-same-readings detection (fallback safety)
        # This ensures tracking happens regardless of where this function is called from
        track_resources(gold_absolute, elixir_absolute, de_absolute, base_type='main_base')
        # Check if 3 consecutive same readings detected (storages full, no loot gained)
        check_and_pause_if_storages_full(base_type='main_base')

        return result

    except Exception as e:
        print(f"[STORAGE] ERROR reading own base storages: {e}")
        send_discord_debug_log(f"Storage read error: {e}", "ERROR")
        return result


def read_bb_base_storages():
    """
    Read Builder Base storage percentages (Gold, Elixir).
    Uses BB storage regions to read absolute values,
    then calculates percentages based on max BB storage values.

    Note: BB max storages are fixed per Builder Hall level.
    For now, we assume max values and calculate percentages.

    Returns:
        dict: {
            'gold_percent': int (0-100),
            'elixir_percent': int (0-100),
            'gold_absolute': int,
            'elixir_absolute': int,
            'success': bool
        }
    """
    result = {
        'gold_percent': 0,
        'elixir_percent': 0,
        'gold_absolute': 0,
        'elixir_absolute': 0,
        'success': False
    }

    try:
        # Check if BB storage regions are defined
        if not hasattr(config, 'BB_BASE_GOLD_REGION') or not hasattr(config, 'BB_BASE_ELIXIR_REGION'):
            print("[STORAGE] BB storage regions not defined in config.py")
            return result

        # Read absolute storage values with retry logic

        # Read BB Gold with template matching OCR
        bb_gold_img = ImageGrab.grab(bbox=config.BB_BASE_GOLD_REGION)
        gold_absolute = ocr_attack_resource_template_digits(bb_gold_img, context='bb_base_screen', debug=False, resource_type='gold')

        # Read BB Elixir with template matching OCR
        bb_elixir_img = ImageGrab.grab(bbox=config.BB_BASE_ELIXIR_REGION)
        elixir_absolute = ocr_attack_resource_template_digits(bb_elixir_img, context='bb_base_screen', debug=False, resource_type='elixir')

        # Get BB max storage values from settings
        settings = runtime.gui.get_settings()
        max_bb_gold = settings.get('max_bb_gold_storage', 5000000)
        max_bb_elixir = settings.get('max_bb_elixir_storage', 5000000)

        # Calculate percentages
        gold_percent = min(100, int((gold_absolute / max_bb_gold) * 100)) if max_bb_gold > 0 else 0
        elixir_percent = min(100, int((elixir_absolute / max_bb_elixir) * 100)) if max_bb_elixir > 0 else 0

        # Update result
        result['gold_absolute'] = gold_absolute
        result['elixir_absolute'] = elixir_absolute
        result['gold_percent'] = gold_percent
        result['elixir_percent'] = elixir_percent
        result['success'] = True

        print(f"[STORAGE] Builder Base: Gold={gold_percent}% ({gold_absolute:,}/{max_bb_gold:,}), "
              f"Elixir={elixir_percent}% ({elixir_absolute:,}/{max_bb_elixir:,})")

        send_discord_debug_log(
            f"BB Storage Check: Gold={gold_percent}%, Elixir={elixir_percent}%"
        )

        # Track resources for 3-consecutive-same-readings detection (fallback safety)
        # This ensures tracking happens regardless of where this function is called from
        track_resources(gold_absolute, elixir_absolute, dark_elixir=None, base_type='builder_base')
        # Check if 3 consecutive same readings detected (storages full, no loot gained)
        check_and_pause_if_storages_full(base_type='builder_base')

        # Auto-switch profile if BB resources suggest wrong account (no dark elixir in BB)
        auto_switch_profile_if_needed(gold_absolute, elixir_absolute, dark_elixir=None)

        return result

    except Exception as e:
        print(f"[STORAGE] ERROR reading BB storages: {e}")
        send_discord_debug_log(f"BB storage read error: {e}", "ERROR")
        return result
