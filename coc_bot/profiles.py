"""Profile selection and automatic switching based on storage levels."""

import json

from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log

def get_global_reinforcements_enabled():
    """Get the global reinforcements enabled setting from bot_settings.json"""
    try:
        with open('bot_settings.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('reinforcements_enabled', False)
    except Exception:
        return False


def get_global_skip_on_th_fail():
    """Get the global skip on town hall detection fail setting from bot_settings.json"""
    try:
        with open('bot_settings.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('skip_on_th_fail', False)
    except Exception:
        return False


def find_best_matching_profile(gold, elixir, dark_elixir=None):
    """
    Find the profile that best matches the given resources.
    Used for auto-switching profiles when resources exceed current max.

    Args:
        gold (int): Gold amount
        elixir (int): Elixir amount
        dark_elixir (int, optional): Dark elixir amount (None for Builder Base)

    Returns:
        tuple: (profile_name, match_score, reason) or (None, 0, None) if no better match
    """
    current_profile = runtime.gui.current_profile
    all_profiles = runtime.gui.profiles

    current_settings = all_profiles.get(current_profile, {})
    current_max_gold = current_settings.get('max_gold_storage', 18000000)
    current_max_elixir = current_settings.get('max_elixir_storage', 14000000)
    current_max_dark = current_settings.get('max_dark_elixir_storage', 240000)

    best_match = None
    best_score = 0
    best_reason = None

    # Tolerance for "at max" detection (98% = nearly full)
    FULL_THRESHOLD = 0.98

    for profile_name, profile_settings in all_profiles.items():
        if profile_name == current_profile:
            continue  # Skip current profile

        max_gold = profile_settings.get('max_gold_storage', 18000000)
        max_elixir = profile_settings.get('max_elixir_storage', 14000000)
        max_dark = profile_settings.get('max_dark_elixir_storage', 240000)

        score = 0
        reasons = []

        # Check if resources exceed current profile's max
        exceeds_current = False
        if gold > current_max_gold or elixir > current_max_elixir:
            exceeds_current = True
        if dark_elixir is not None and dark_elixir > current_max_dark:
            exceeds_current = True

        # Check if resources fit well within this profile's max
        fits_this_profile = True
        if gold > max_gold or elixir > max_elixir:
            fits_this_profile = False
        if dark_elixir is not None and dark_elixir > max_dark:
            fits_this_profile = False

        # Calculate how close resources are to this profile's maximums
        if dark_elixir is not None:
            # Main base (3 resources)
            gold_pct = gold / max_gold if max_gold > 0 else 0
            elixir_pct = elixir / max_elixir if max_elixir > 0 else 0
            dark_pct = dark_elixir / max_dark if max_dark > 0 else 0

            # Check if all 3 resources are at/near max for this profile
            at_max_count = sum([
                gold_pct >= FULL_THRESHOLD,
                elixir_pct >= FULL_THRESHOLD,
                dark_pct >= FULL_THRESHOLD
            ])

            if at_max_count >= 2 and exceeds_current and fits_this_profile:
                score = at_max_count * 100  # Prioritize profiles where most resources are full
                reasons.append(f"{at_max_count}/3 resources at max")

                # Extra score if ALL resources match very closely (±2%)
                if all([0.98 <= pct <= 1.02 for pct in [gold_pct, elixir_pct, dark_pct]]):
                    score += 50
                    reasons.append("all resources match maximums")
        else:
            # Builder base (2 resources)
            gold_pct = gold / max_gold if max_gold > 0 else 0
            elixir_pct = elixir / max_elixir if max_elixir > 0 else 0

            at_max_count = sum([
                gold_pct >= FULL_THRESHOLD,
                elixir_pct >= FULL_THRESHOLD
            ])

            if at_max_count >= 1 and exceeds_current and fits_this_profile:
                score = at_max_count * 100
                reasons.append(f"{at_max_count}/2 resources at max")

                if all([0.98 <= pct <= 1.02 for pct in [gold_pct, elixir_pct]]):
                    score += 50
                    reasons.append("both resources match maximums")

        if score > best_score:
            best_score = score
            best_match = profile_name
            best_reason = ", ".join(reasons)

    if best_match and best_score > 0:
        return (best_match, best_score, best_reason)
    return (None, 0, None)


def auto_switch_profile_if_needed(gold, elixir, dark_elixir=None):
    """
    Auto-switch profile if resources suggest we're on the wrong account.
    Checks if resources match another profile's maximums better than current profile.

    Args:
        gold (int): Gold amount
        elixir (int): Elixir amount
        dark_elixir (int, optional): Dark elixir amount (None for Builder Base)

    Returns:
        bool: True if profile was switched, False otherwise
    """
    try:
        profile_name, score, reason = find_best_matching_profile(gold, elixir, dark_elixir)

        if profile_name:
            # Found a better matching profile - auto-switch
            current_profile = runtime.gui.current_profile

            if dark_elixir is not None:
                resource_str = f"Gold: {gold:,}, Elixir: {elixir:,}, Dark: {dark_elixir:,}"
            else:
                resource_str = f"Gold: {gold:,}, Elixir: {elixir:,}"

            print(f"⚠️ AUTO-SWITCH: Resources ({resource_str}) suggest profile '{profile_name}'")
            print(f"   Current: {current_profile} → Switching to: {profile_name}")
            print(f"   Reason: {reason}")
            runtime.gui.log_message(f"⚠️ Auto-switching profile: {current_profile} → {profile_name}")
            runtime.gui.log_message(f"   Reason: {reason}")
            send_discord_debug_log(f"Auto-switching profile: {current_profile} → {profile_name} ({reason})", "WARNING")

            # Switch profile
            runtime.gui.profile_var.set(profile_name)
            runtime.gui.apply_profile(silent=True)

            return True
        return False
    except Exception as e:
        print(f"Error in auto_switch_profile_if_needed: {e}")
        return False
