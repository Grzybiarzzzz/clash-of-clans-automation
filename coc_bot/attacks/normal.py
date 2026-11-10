"""Standard attack: evaluate the base, pick a side, deploy."""

from coc_bot import runtime
from coc_bot.attacks.common import (
    check_town_hall_level,
    choose_attack_side,
    deploy_lightning_spells,
    deploy_troops,
    handle_post_battle,
    prepare_hotkeys,
    should_skip_base,
    skip_base,
    wait_for_battle_end,
)
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.geometry import get_air_defense_proximity_sorter, get_lightning_spell_targets
from coc_bot.humanized_input import reading_pause, thinking_pause
from coc_bot.input.camera import move_camera_to_side
from coc_bot.vision.buildings import detect_air_defenses, detect_town_hall
from coc_bot.vision.ocr import evaluate_base_resources
from coc_bot.vision.screens import detect_alt_hotkeys


def perform_normal_attack():
    """Perform a normal attack (non-derank mode)"""
    # SANITY CHECK: Verify we should be here
    settings = runtime.gui.get_settings()
    current_profile = settings.get("current_profile", "Unknown")
    sbarb_mode_check = settings.get("sbarb_farm_mode", False)

    if sbarb_mode_check:
        print(f"\n{'!' * 70}")
        print("[ERROR] ❌ CRITICAL: perform_normal_attack() called with sbarb_farm_mode=True!")
        print(f"[ERROR] Profile: {current_profile}")
        print("[ERROR] This should NEVER happen - SBarb Farm should skip evaluation!")
        print("[ERROR] Check that bot was restarted after code changes!")
        print(f"{'!' * 70}\n")
        send_discord_debug_log(
            f"ERROR: perform_normal_attack() called with sbarb_farm_mode=True! Profile: {current_profile}", "ERROR"
        )

    # Get current settings from GUI
    settings = runtime.gui.get_settings()

    # OCR resources
    gold, elixir = evaluate_base_resources()

    # Human-like pause to "read" the loot values
    reading_pause(0.4)  # Quick glance at loot

    # Detect air defenses
    air_defenses = detect_air_defenses()
    print(f"Air defenses detected (count): {len(air_defenses)}")
    for i, ad in enumerate(air_defenses):
        x, y, level, conf = ad
        print(f"  AD {i + 1}: ({x}, {y}), Level: {level}, Confidence: {conf:.2f}")

    # Human-like pause to "analyze" the base and make decision
    thinking_pause(0.3, 0.8)  # Quick analysis

    # Check if should skip base
    should_skip, skip_reason = should_skip_base(gold, elixir, air_defenses, settings)
    if should_skip:
        skip_base()
        return False  # Attack not completed

    send_discord_debug_log(f"Base selected for attack: {len(air_defenses)} air defenses, {gold + elixir:,} resources")

    # Choose attack side
    town_hall = detect_town_hall()
    if check_town_hall_level(town_hall, settings):
        skip_base()
        return False  # Attack not completed

    chosen_side, side_coords = choose_attack_side(settings, town_hall)

    # Brief pause before committing to attack (simulates final decision)
    thinking_pause(0.2, 0.5)  # Quick final check

    # Detect alternate hotkeys
    alt_hotkeys = detect_alt_hotkeys()
    KEYS = prepare_hotkeys(alt_hotkeys)

    # Get lightning spell targets
    ad_target_mode = settings.get("ad_target_mode", "level")
    if ad_target_mode == "proximity":
        sorter = get_air_defense_proximity_sorter(chosen_side)
        sorted_air_defenses = sorted(air_defenses, key=sorter)
        lightning_targets = [(x, y) for x, y, _, _ in sorted_air_defenses]
    else:
        lightning_targets = get_lightning_spell_targets(air_defenses)

    # Attack screen already loaded by main_loop - proceed with spell deployment
    print("[NORMAL ATTACK] Deploying lightning spells...")

    # Deploy lightning spells with smart targeting:
    # - Reinforcements mode: 13 spells on 4 air defenses (3 per AD + 1 random)
    # - Non-reinforcements mode: 9 spells on 3 air defenses + 2 spells on air sweepers
    deploy_lightning_spells(air_defenses, lightning_targets, chosen_side, settings, KEYS)

    # Move camera to chosen side
    move_camera_to_side(chosen_side)

    # Deploy troops
    deploy_troops(side_coords, settings, KEYS)

    # Wait for battle to end
    wait_for_battle_end()

    # Handle post-battle activities
    should_pause = handle_post_battle()
    if should_pause:
        return True  # Signal to pause bot

    return False  # Attack completed successfully
