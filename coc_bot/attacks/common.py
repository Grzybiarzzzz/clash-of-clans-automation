"""Attack steps shared by the Home Village routines."""

import random
import time

import keyboard
import pyautogui

import config
from coc_bot import runtime
from coc_bot.controls import pause_bot
from coc_bot.discord_log import send_discord_debug_log, send_discord_notification
from coc_bot.geometry import calculate_lightning_spells_needed
from coc_bot.humanized_input import human_like_move_click, mouse_drift_idle, random_sleep
from coc_bot.input.camera import click_in_square
from coc_bot.overlay import overlay_draw_side, overlay_update
from coc_bot.profiles import get_global_reinforcements_enabled, get_global_skip_on_th_fail
from coc_bot.session import save_loot_data
from coc_bot.storages import (
    check_and_pause_if_storages_full,
    find_loot_mismatches,
    previous_storage_values,
    read_storage_values,
    track_resources,
)
from coc_bot.vision.buildings import detect_air_sweepers
from coc_bot.vision.capture import grab as grab_screen
from coc_bot.vision.ocr import evaluate_base_resources, ocr_loot
from coc_bot.vision.screens import detect_army_button, wait_for_base_screen


SCOUT_LOOT_TIMEOUT = 3.0  # seconds to wait for the loot of a scouted base to become readable
MAX_UNREADABLE_BASES = 5  # this many unreadable bases in a row pause the bot

_unreadable_bases = 0


def read_scouted_loot():
    """The loot of the base on screen as (gold, elixir), or None when it stayed unreadable."""
    global _unreadable_bases
    gold, elixir = evaluate_base_resources(timeout=SCOUT_LOOT_TIMEOUT)
    if gold is None or elixir is None:
        return None
    _unreadable_bases = 0
    return gold, elixir


def leave_unreadable_base():
    """Skip a base whose loot could not be read. Returns "skipped", or "paused" when it keeps happening.

    One unreadable base is bad luck with the scenery. Several in a row mean the reader does not
    work on this screen at all, and skipping on would only burn gold, so the bot pauses with the
    last base still on screen.
    """
    global _unreadable_bases
    _unreadable_bases += 1
    if _unreadable_bases >= MAX_UNREADABLE_BASES:
        _unreadable_bases = 0
        pause_bot(
            f"loot unreadable on {MAX_UNREADABLE_BASES} bases in a row - check the crops in "
            f"{getattr(config, 'OCR_CORPUS_DIR', 'data/ocr_corpus')} (OCR_ENGINE = \"legacy\" in config.py "
            "switches back to the old reader)"
        )
        return "paused"
    message = f"Loot unreadable - skipping base ({_unreadable_bases}/{MAX_UNREADABLE_BASES} in a row)"
    print(message)
    runtime.gui.log_message(message)
    send_discord_debug_log(message, "WARNING")
    skip_base()
    return "skipped"


def should_skip_base(gold, elixir, air_defenses, settings):
    """Determine if base should be skipped based on resources and air defenses"""
    min_amount = settings.get("min_resources", config.MIN_AMOUNT)
    reinforcements_enabled = get_global_reinforcements_enabled()

    # Check resources
    if gold + elixir < min_amount:
        send_discord_debug_log(f"Insufficient resources: {gold + elixir:,} < {min_amount:,}, skipping base")
        return True, "insufficient_resources"

    # Check air defenses
    if reinforcements_enabled and len(air_defenses) < 4:
        print(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base.")
        runtime.gui.log_message(
            f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base."
        )
        send_discord_debug_log(
            f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base", "WARNING"
        )
        return True, "insufficient_air_defenses"

    if not reinforcements_enabled and len(air_defenses) < 3:
        print(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        runtime.gui.log_message(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        send_discord_debug_log(f"Only {len(air_defenses)} air defenses detected, skipping base", "WARNING")
        return True, "insufficient_air_defenses"

    return False, None


def skip_base():
    """Skip the current base"""
    x, y = config.SKIP_BUTTON
    jitter = 24
    click_in_square((x - jitter, y - jitter, x + jitter, y + jitter))


def choose_attack_side(settings, town_hall=None):
    """Choose attack side based on settings and town hall position"""
    attack_side_mode = settings.get("attack_side_mode", "random")
    sides = list(config.SIDE_DEPLOYMENT_COORDS.keys())

    if attack_side_mode == "th_side" and town_hall:
        # Base center point for side detection
        BASE_CENTER_X = 1298
        BASE_CENTER_Y = 697

        # Adjust Town Hall position to its center for side detection
        th_center = (town_hall[0] + 60, town_hall[1] + 75)

        # Determine which side of the base center the town hall is located
        th_x, th_y = th_center

        # Calculate relative position from base center
        x_diff = th_x - BASE_CENTER_X
        y_diff = th_y - BASE_CENTER_Y

        # Determine side based on which quadrant the town hall is in
        if abs(x_diff) > abs(y_diff):
            # Town hall is more horizontally offset
            if x_diff > 0:
                chosen_side = "right"
            else:
                chosen_side = "left"
        else:
            # Town hall is more vertically offset
            if y_diff > 0:
                chosen_side = "down"
            else:
                chosen_side = "up"

        # Debug information
        debug_info = f"TH at ({th_x}, {th_y}), center at ({BASE_CENTER_X}, {BASE_CENTER_Y})"
        debug_info += f", x_diff={x_diff:.1f}, y_diff={y_diff:.1f}"
        runtime.gui.debug_message(debug_info)

        side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
        runtime.gui.log_message(f"Chosen attack side: {chosen_side} (TH on {chosen_side} side of base center)")
        print(f"Chosen attack side: {chosen_side} (TH on {chosen_side} side of base center)")
        send_discord_debug_log(f"Attack side chosen: {chosen_side} (TH-based)")
        # Draw attack side indicator on overlay
        overlay_draw_side(chosen_side)
        overlay_update()
        return chosen_side, side_coords
    else:
        # Fallback to random
        chosen_side = random.choice(sides)
        side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
        runtime.gui.log_message(f"Chosen attack side: {chosen_side} (random)")
        print(f"Chosen attack side: {chosen_side} (random)")
        send_discord_debug_log(f"Attack side chosen: {chosen_side} (random)")
        # Draw attack side indicator on overlay
        overlay_draw_side(chosen_side)
        overlay_update()
        return chosen_side, side_coords


def prepare_hotkeys(alt_hotkeys):
    """Prepare hotkeys based on whether alternate hotkeys are detected"""
    KEYS = dict(config.KEYS)
    if alt_hotkeys:
        # Swap troop1 and troop2 if alternate hotkeys detected
        KEYS["troop1"], KEYS["troop2"] = KEYS["troop2"], KEYS["troop1"]
        KEYS["queen"], KEYS["warden"] = KEYS["warden"], KEYS["queen"]
    return KEYS


def check_town_hall_level(town_hall, settings):
    """Check if town hall level is acceptable, return True if should skip"""
    if town_hall:
        x, y, level, conf = town_hall
        print(f"Detected Town Hall Level {level} at ({x}, {y}) - Confidence: {conf:.2f}")
        runtime.gui.log_message(f"Town Hall Level {level} detected")

        # Check max Town Hall level from settings
        max_th_level = settings.get("max_th_level", 15)
        if level > max_th_level:
            print(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            runtime.gui.log_message(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            send_discord_debug_log(
                f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base", "WARNING"
            )
            return True
    else:
        print("Town Hall not detected")
        runtime.gui.log_message("Town Hall not detected")

        # Check if we should skip when town hall detection fails
        skip_on_th_fail = get_global_skip_on_th_fail()
        if skip_on_th_fail:
            print("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base.")
            runtime.gui.log_message(
                "Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base."
            )
            send_discord_debug_log(
                "Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base", "WARNING"
            )
            return True

    return False


def deploy_lightning_spells(air_defenses, lightning_targets, chosen_side, settings, KEYS):
    """Deploy lightning spells on air defenses"""
    if not lightning_targets:
        print("No air defenses detected - skipping lightning spells")
        runtime.gui.log_message("No air defenses detected - skipping lightning spells")
        send_discord_debug_log("No air defenses detected - skipping lightning spells", "WARNING")
        return

    reinforcements_enabled = get_global_reinforcements_enabled()

    if reinforcements_enabled:
        print("Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        runtime.gui.log_message("Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        send_discord_debug_log("Deploying 13 lightning spells (Reinforcements mode)")

        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level

        spells_used = 0
        lightning_damage = settings.get("lightning_damage", 300)

        # Use 12 spells (3 per AD) on 4 air defenses
        for idx, (x, y, level, _) in enumerate(air_defenses[:4]):
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            for i in range(spell_count):
                if spells_used < 11:
                    keyboard.send(KEYS["lightning"])
                else:
                    keyboard.send("s")  # Use 'S' for the last 2 spells
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/13 at ({x}, {y}) (AD {idx + 1})")
                spells_used += 1

        # 13th spell at random location
        random_x = random.randint(1003, 1495)
        random_y = random.randint(471, 853)
        keyboard.send("s")
        time.sleep(0.02)
        jitter = random.randint(-5, 5)
        pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
        pyautogui.click()
        print(f"    13th Lightning spell at random location ({random_x}, {random_y})")
        spells_used += 1

        runtime.gui.log_message("Lightning spell deployment completed (Reinforcements mode)")
        send_discord_debug_log("Lightning spell deployment completed (Reinforcements mode)")
    else:
        print("Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        runtime.gui.log_message("Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        send_discord_debug_log("Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")

        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level

        spells_used = 0
        lightning_damage = settings.get("lightning_damage", 300)

        # Target exactly 3 air defenses (9 spells total)
        for idx, (x, y) in enumerate(lightning_targets[:3]):  # Only first 3 air defenses
            level = position_to_level.get((x, y), 1)
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            hp = config.AIR_DEFENSE_HP.get(level, 1000)
            print(
                f"  Air Defense {idx + 1} (Level {level}) has {hp} HP, using {spell_count} lightning spells ({lightning_damage} damage each)"
            )

            for i in range(spell_count):
                keyboard.send(KEYS["lightning"])
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/9 at ({x}, {y}) (AD {idx + 1})")
                spells_used += 1

        print(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining for air sweepers")
        runtime.gui.log_message(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")
        send_discord_debug_log(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")

        # Handle remaining spells (should be 2 for air sweepers)
        handle_remaining_lightning_spells(spells_used, chosen_side, KEYS)

        runtime.gui.log_message("Lightning spell deployment completed (non-reinforcements mode)")
        send_discord_debug_log("Lightning spell deployment completed (non-reinforcements mode)")


def handle_remaining_lightning_spells(spells_used, chosen_side, KEYS):
    """Handle remaining lightning spells (air sweepers or random)"""
    if spells_used < 11:
        remaining_spells = 11 - spells_used
        print(f"Handling {remaining_spells} remaining lightning spells...")

        if remaining_spells == 2:
            # Perfect scenario: 2 spells for air sweepers
            sweepers = detect_air_sweepers()
            print(f"Detected {len(sweepers)} air sweepers for lightning targeting.")
            runtime.gui.log_message(f"Detected {len(sweepers)} air sweepers for lightning targeting.")
            send_discord_debug_log(f"Detected {len(sweepers)} air sweepers for lightning targeting")

            # Map attack side to directions
            side_to_dirs = {
                "left": ["left", "up_left", "down_left"],
                "right": ["right", "up_right", "down_right"],
                "up": ["up", "up_left", "up_right"],
                "down": ["down", "down_left", "down_right"],
            }
            preferred_dirs = side_to_dirs.get(chosen_side, [])

            # Find sweeper facing the attack side
            target_sweeper = None
            for sw in sweepers:
                if sw[2] in preferred_dirs:
                    target_sweeper = sw
                    break
            if not target_sweeper and sweepers:
                target_sweeper = random.choice(sweepers)

            if target_sweeper:
                x, y, direction, conf = target_sweeper
                print(f"Targeting air sweeper at ({x}, {y}) facing {direction} (confidence: {conf:.3f})")
                for i in range(2):
                    keyboard.send(KEYS["lightning"])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Lightning spell {spells_used + i + 1}/11 at Air Sweeper ({x}, {y}) facing {direction}")
                print("Air sweeper lightning spells deployed successfully")
                runtime.gui.log_message("Air sweeper lightning spells deployed successfully")
                send_discord_debug_log("Air sweeper lightning spells deployed successfully")
            else:
                print("No air sweeper found for remaining lightning spells.")
                runtime.gui.log_message("No air sweeper found for remaining lightning spells.")
                send_discord_debug_log("No air sweeper found for remaining lightning spells", "WARNING")
                # Use the 2 spells at random coordinates as fallback
                random_coords = [
                    (1003, 471),  # Point 1
                    (1495, 853),  # Point 2
                ]
                for i in range(2):
                    x1, y1 = random_coords[0]
                    x2, y2 = random_coords[1]
                    random_x = random.randint(min(x1, x2), max(x1, x2))
                    random_y = random.randint(min(y1, y2), max(y1, y2))
                    keyboard.send(KEYS["lightning"])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")
        else:
            # Failsafe: Use remaining lightning spells at random coordinates
            print(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            runtime.gui.log_message(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            send_discord_debug_log(f"Using {remaining_spells} remaining lightning spells at random coordinates")

            random_coords = [
                (1003, 471),  # Point 1
                (1495, 853),  # Point 2
            ]
            for i in range(remaining_spells):
                x1, y1 = random_coords[0]
                x2, y2 = random_coords[1]
                random_x = random.randint(min(x1, x2), max(x1, x2))
                random_y = random.randint(min(y1, y2), max(y1, y2))
                keyboard.send(KEYS["lightning"])
                time.sleep(0.02)
                jitter = random.randint(-5, 5)
                pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")


def deploy_troops(side_coords, settings, KEYS):
    """Deploy all troops (generic troop slots 1-7, Siege, Heroes)"""
    # Get troop counts from settings
    troop_counts = settings.get("troop_counts", [0, 0, 0, 0, 0, 0, 0])

    # Deploy each troop type that has count > 0
    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f"troop{i + 1}"

            # Get deployment coordinates
            troop_coords = random.sample(side_coords["units"], min(troop_count, len(side_coords["units"])))

            # Select troop
            keyboard.send(KEYS[troop_key])
            time.sleep(0.1)

            # Deploy troops
            for x, y in troop_coords:
                random_sleep(config.SLEEP_MIN, config.SLEEP_MAX)
                pyautogui.moveTo(x, y, duration=random.uniform(0.03, 0.07))
                pyautogui.click()

            send_discord_debug_log(f"Deployed {troop_count} troops from slot {i + 1}")
            print(f"Deployed {troop_count} troops from slot {i + 1}")

    # Deploy Siege Machine and Heroes
    print("Deploying siege machine and heroes...")
    send_discord_debug_log("Deploying siege machine and heroes")
    hero_pos = side_coords["hero"]

    # Get individual hero ability timing from settings
    settings = runtime.gui.get_settings()
    queen_timing = settings.get("queen_ability_timing", 15)
    king_timing = settings.get("king_ability_timing", 15)
    warden_timing = settings.get("warden_ability_timing", 15)
    rc_timing = settings.get("rc_ability_timing", 15)

    # Deploy siege machine
    keyboard.send(KEYS["siege"])
    time.sleep(config.HERO_DELAY)
    human_like_move_click(*hero_pos)
    time.sleep(config.POST_DEPLOY_DELAY)

    # Deploy heroes and start their ability timers individually
    hero_timings = {"queen": queen_timing, "king": king_timing, "warden": warden_timing, "rc": rc_timing}

    import threading

    def activate_hero_ability(hero_role, timing):
        """Activate a specific hero's ability after the specified timing"""
        if timing >= 0:
            if timing > 0:
                time.sleep(timing)
            keyboard.send(KEYS[hero_role])
            send_discord_debug_log(f"{hero_role.title()} ability activated after {timing} seconds")
        elif timing == -1:
            send_discord_debug_log(f"{hero_role.title()} ability disabled")

    # Deploy each hero and start their individual ability timer
    for role in ["queen", "king", "warden", "rc"]:
        # Deploy the hero
        keyboard.send(KEYS[role])
        time.sleep(config.HERO_DELAY)
        human_like_move_click(*hero_pos)
        time.sleep(config.POST_DEPLOY_DELAY)

        # Start ability timer for this specific hero
        timing = hero_timings[role]
        if timing != -1:  # Only start thread if ability is not disabled
            ability_thread = threading.Thread(target=activate_hero_ability, args=(role, timing), daemon=True)
            ability_thread.start()
            send_discord_debug_log(f"Started {role.title()} ability timer ({timing} seconds)")


def wait_for_battle_end():
    """Wait until battle ends by detecting black bar region"""
    send_discord_debug_log("Waiting for battle to end...")
    check_count = 0
    while runtime.running:
        img = grab_screen(config.BLACK_BAR_REGION)
        if all(pixel == config.BLACK_BAR_COLOR for pixel in img.getdata()):
            break

        # Occasional mouse drift during wait (every ~5 checks = ~5 seconds)
        if check_count % 5 == 0:
            mouse_drift_idle(max_drift=10)

        time.sleep(1)
        check_count += 1


def handle_post_battle():
    """Handle post-battle activities (loot capture, return home, reinforcements)"""
    # Capture loot after battle ends
    print("Battle ended, capturing loot...")
    runtime.gui.log_message("Battle ended, capturing loot...")
    send_discord_debug_log("Battle ended, capturing loot")
    time.sleep(config.LOOT_CAPTURE_DELAY)

    loot_data = ocr_loot()
    save_loot_data(loot_data, runtime.loop_count + 1)

    # Update GUI loot statistics
    runtime.root.after(0, lambda: runtime.gui.update_loot_stats(loot_data))

    # Return home
    human_like_move_click(*config.RETURN_BUTTON)

    # Wait for base screen to load (template matching army button)
    if not wait_for_base_screen(timeout=15):
        print("[WARNING] Base screen not detected after return - OCR may be inaccurate")
        send_discord_debug_log("Base screen not detected after return - OCR may fail", "WARNING")

    # Wait for resources to stabilize before reading
    time.sleep(0.3)

    settings = runtime.gui.get_settings()
    capacity = {
        "gold": int(settings.get("max_gold_storage", 14_000_000)),
        "elixir": int(settings.get("max_elixir_storage", 14_000_000)),
        "dark_elixir": int(settings.get("max_dark_elixir_storage", 240_000)),
    }

    before = previous_storage_values("main_base")
    after = read_storage_values("main_base")
    if after is None:
        # No reading is better than a wrong one: nothing below may act on guessed numbers
        print("[STORAGE] Storages unreadable after the attack - skipping the full-storage checks")
        send_discord_debug_log("Storages unreadable after attack - full-storage checks skipped", "WARNING")
    else:
        print(
            f"Base resources after attack: Gold={after['gold']:,}, Elixir={after['elixir']:,}, "
            f"Dark Elixir={after['dark_elixir']:,}"
        )
        send_discord_debug_log(
            f"Base resources after attack: Gold={after['gold']:,}, Elixir={after['elixir']:,}, "
            f"Dark Elixir={after['dark_elixir']:,}"
        )

        # Storage growth should match the loot screen; a contradiction points at a misread number
        for mismatch in find_loot_mismatches(before, after, loot_data, capacity):
            message = (
                f"[OCR AUDIT] {mismatch['resource']} storage changed by {mismatch['gained']:,} "
                f"but the loot screen showed {mismatch['loot']:,} - one of the readings is probably wrong"
            )
            print(message)
            runtime.gui.log_message(message)
            send_discord_debug_log(message, "WARNING")

        # Track resources and check for full storages (no loot gained over 3 attacks)
        track_resources(after["gold"], after["elixir"], after["dark_elixir"], base_type="main_base")
        check_and_pause_if_storages_full(base_type="main_base")

        # Farming profile: pause once at least 2 of the 3 storages reached their configured maximum
        if settings.get("current_profile", "") == "Farming":
            full_count = sum(1 for resource in capacity if after[resource] >= capacity[resource] > 0)
            if full_count >= 2:
                msg = (
                    f"<@everyone> Storages are full! Gold: {after['gold']:,}/{capacity['gold']:,}, "
                    f"Elixir: {after['elixir']:,}/{capacity['elixir']:,}, "
                    f"Dark Elixir: {after['dark_elixir']:,}/{capacity['dark_elixir']:,}. Bot paused."
                )
                send_discord_notification(msg)
                runtime.gui.log_message("At least 2 storages are full. Bot paused.")
                return True  # Signal to pause bot

    # Handle reinforcements
    reinforcements_enabled = get_global_reinforcements_enabled()
    if reinforcements_enabled:
        print("Requesting reinforcements...")
        runtime.gui.log_message("Requesting reinforcements...")
        send_discord_debug_log("Requesting reinforcements")

        # Detect and click army button
        army_button_pos = detect_army_button()
        if army_button_pos:
            human_like_move_click(*army_button_pos)
            time.sleep(0.5)

            # Click reinforce request button
            human_like_move_click(*config.REINFORCE_REQUEST_COORDS)
            time.sleep(0.5)

            # Click confirm button
            human_like_move_click(*config.Confirm_Coords)
            time.sleep(1.0)

            print("Reinforcements requested successfully")
            runtime.gui.log_message("Reinforcements requested successfully")
            send_discord_debug_log("Reinforcements requested successfully")
        else:
            print("Failed to detect army button - skipping reinforcements")
            runtime.gui.log_message("Failed to detect army button - skipping reinforcements")
            send_discord_debug_log("Failed to detect army button - skipping reinforcements", "WARNING")

    return False  # No need to pause


def deploy_wall_breaker(position):
    """Deploy a single Super Wall Breaker at the specified position"""
    keyboard.send("2")  # Wall Breaker hotkey
    time.sleep(0.05)
    pyautogui.moveTo(*position, duration=0.02)
    pyautogui.click()
    time.sleep(0.05)
