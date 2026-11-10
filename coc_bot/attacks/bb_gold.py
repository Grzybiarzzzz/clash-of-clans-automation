"""Builder Base gold farming routine, driven by an explicit state machine."""

import time
from enum import auto, Enum

import config
from coc_bot import runtime
from coc_bot.attacks.bb_gold_battle import (
    deploy_bb_gold_troops,
    end_bb_gold_battle,
    increment_bb_gold_counter,
    monitor_bb_gold_battle,
    save_bb_gold_attack_duration,
)
from coc_bot.discord_log import send_discord_debug_log
from coc_bot.humanized_input import fast_click
from coc_bot.input.camera import click_in_square
from coc_bot.vision.ocr import check_bb_attacker_text
from coc_bot.vision.screens import (
    detect_current_game_state,
    detect_end_battle_button,
    detect_end_screen_state,
    detect_ghost_attack,
    detect_in_base_state,
    detect_return_home_button,
    detect_surrender_or_end_battle,
)


# BB Gold State Machine Enum
class BBGoldState(Enum):
    """BB Gold mode states - explicit lifecycle tracking"""

    IN_BASE = auto()  # At home base, army_button.png visible
    SEARCHING = auto()  # Search button clicked, waiting for match
    ATTACK_READY = auto()  # "Attacker" text confirmed, ready to deploy
    TROOPS_DEPLOYING = auto()  # Battle Machine/Night Witches being placed
    BATTLE_ACTIVE = auto()  # All troops deployed, monitoring stars
    BATTLE_ENDING = auto()  # 2/3 stars detected or timeout, clicking surrender/end
    END_SCREEN = auto()  # Battle finished, on victory/defeat screen
    RETURNING_HOME = auto()  # Return button clicked, transitioning to base
    ERROR_RECOVERY = auto()  # Ghost attack or error state, recovering


def _state_in_base(context):
    """IN_BASE: click the search button. Returns the next state."""
    print("[BB GOLD STATE] IN_BASE: Initiating search")
    runtime.gui.log_message("BB Gold: Starting search")

    # NEW: If queue is active, wait for storage UI to stabilize before checking
    try:
        if runtime.queue_manager and runtime.queue_manager.queue_active:
            print("[BB GOLD STATE] Queue active - waiting for storage UI to stabilize")
            time.sleep(1.5)  # Allow storage bars to fully render
    except NameError:
        pass  # queue_manager not initialized yet

    # NOTE: Star bonus handling is done by main loop's blind click at (73, 820)
    # No detection needed here - blind click handles all popups efficiently

    # Click search button - use fast click for instant response
    fast_click(*config.BB_SEARCH_BUTTON[:2])  # Extract (x, y) from (x1, y1, x2, y2)

    # Update state immediately after clicking
    current_state = BBGoldState.SEARCHING
    context["search_start_time"] = time.time()
    runtime.gui.update_bb_gold_state(current_state.name)
    return current_state


def _state_searching(current_state, state_timeout):
    """SEARCHING: wait for an opponent, or detect a ghost attack. Returns the next state."""
    print("[BB GOLD STATE] SEARCHING: Waiting for match...")

    # Wait for either attack ready or timeout
    timeout_start = time.time()
    while time.time() - timeout_start < state_timeout:
        # Check if attack ready
        if check_bb_attacker_text():
            print("[BB GOLD STATE] SEARCHING -> ATTACK_READY: Attacker text detected")
            current_state = BBGoldState.ATTACK_READY
            runtime.gui.update_bb_gold_state(current_state.name)
            break

        # Check for ghost attack after 10 seconds
        if time.time() - timeout_start > 10:
            if detect_ghost_attack():
                print("[BB GOLD STATE] SEARCHING -> ERROR_RECOVERY: Ghost attack")
                current_state = BBGoldState.ERROR_RECOVERY
                runtime.gui.update_bb_gold_state(current_state.name)
                break

        time.sleep(config.BB_LOAD_CHECK_INTERVAL)

    # Timeout handling
    if current_state == BBGoldState.SEARCHING:
        print("[BB GOLD STATE] SEARCHING timeout - assuming ghost attack")
        current_state = BBGoldState.ERROR_RECOVERY
        runtime.gui.update_bb_gold_state(current_state.name)
    return current_state


def _state_attack_ready(context):
    """ATTACK_READY: deploy the troops. Returns the next state."""
    print("[BB GOLD STATE] ATTACK_READY: Deploying troops")
    runtime.gui.log_message("BB Gold: Deploying troops")

    # Set attack start time
    context["attack_start_time"] = time.time()

    # Deploy troops using helper function
    deployment_success = deploy_bb_gold_troops(context)

    if deployment_success:
        context["troops_deployed"] = True
        current_state = BBGoldState.BATTLE_ACTIVE
        runtime.gui.update_bb_gold_state(current_state.name)
        print("[BB GOLD STATE] ATTACK_READY -> BATTLE_ACTIVE: Troops deployed")
    else:
        print("[BB GOLD STATE] ATTACK_READY -> ERROR_RECOVERY: Deployment failed")
        current_state = BBGoldState.ERROR_RECOVERY
        runtime.gui.update_bb_gold_state(current_state.name)
    return current_state


def _state_battle_active(context):
    """BATTLE_ACTIVE: monitor the battle until stars are earned or it ends. Returns the next state."""
    print("[BB GOLD STATE] BATTLE_ACTIVE: Monitoring for stars")
    runtime.gui.log_message("BB Gold: Monitoring battle...")

    # Monitor for stars or Return Home button (battle ended)
    battle_result = monitor_bb_gold_battle(context)

    context["stars_detected"] = battle_result["stars"]
    context["battle_lost"] = battle_result["timeout_without_stars"]

    # Cache Return Home button position if detected (for faster END_SCREEN handling)
    if battle_result.get("return_home_pos"):
        context["return_home_button_pos"] = battle_result["return_home_pos"]

    current_state = BBGoldState.BATTLE_ENDING
    runtime.gui.update_bb_gold_state(current_state.name)
    print(
        f"[BB GOLD STATE] BATTLE_ACTIVE -> BATTLE_ENDING: {battle_result['stars']} stars, lost={battle_result['timeout_without_stars']}"
    )
    return current_state


def _state_battle_ending(context, current_state):
    """BATTLE_ENDING: surrender or end the battle and find the end screen. Returns the next state."""
    print("[BB GOLD STATE] BATTLE_ENDING: Clicking surrender/end battle")

    # Skip if battle ended (Return Home button detected without stars)
    if not context.get("battle_lost", False):
        end_result = end_bb_gold_battle(context["stars_detected"], context)

        if not end_result["success"]:
            print("[BB GOLD STATE] BATTLE_ENDING: End button click failed, retrying")
            time.sleep(1)
            return current_state

        # Update final stars from end result
        context["final_stars"] = end_result["final_stars"]
    else:
        print("[BB GOLD STATE] BATTLE_ENDING: Battle ended (Return Home detected), skipping surrender")
        context["final_stars"] = 0
        # Return Home button position already cached from monitor_bb_gold_battle()

    # Special handling for 3 stars - FORCE return home button detection
    if context.get("final_stars", 0) == 3:
        print("[BB GOLD STATE] BATTLE_ENDING: 3 stars - forcing return home button detection (no fallback)")
        send_discord_debug_log("BB Gold: 3 stars - waiting for return home button confirmation")

        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            print(
                f"[BB GOLD STATE] BATTLE_ENDING: Checking for return home button (attempt {attempt}/{max_attempts})..."
            )

            # Wait up to 5 seconds for return home button to appear
            timeout_start = time.time()
            return_home_found = False

            while time.time() - timeout_start < 5:
                return_home_pos = detect_return_home_button()
                if return_home_pos:
                    print(f"[BB GOLD STATE] BATTLE_ENDING: ✓ Return home button confirmed at {return_home_pos}")
                    send_discord_debug_log("BB Gold: Return home button confirmed (3 stars)")
                    # Cache position for END_SCREEN state
                    context["return_home_button_pos"] = return_home_pos
                    return_home_found = True
                    break
                time.sleep(0.3)  # Optimized: reduced from 0.5s

            if return_home_found:
                # Success - transition to END_SCREEN
                print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed (return home visible)")
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                break
            else:
                # Return home button not visible - end battle/surrender didn't work
                print(
                    f"[BB GOLD STATE] BATTLE_ENDING: ✗ Return home button not visible (attempt {attempt}/{max_attempts})"
                )
                send_discord_debug_log(
                    f"BB Gold: Return home not visible - clicking end battle again (attempt {attempt})", "WARNING"
                )

                # Click end battle button again
                end_battle_pos = detect_end_battle_button()
                if end_battle_pos:
                    print(f"[BB GOLD STATE] BATTLE_ENDING: Clicking end battle button at {end_battle_pos}")
                    fast_click(*end_battle_pos)
                else:
                    print("[BB GOLD STATE] BATTLE_ENDING: End battle button not detected, using fallback")
                    fast_click(144, 1080)

                time.sleep(1.0)

                # Click confirm
                print("[BB GOLD STATE] BATTLE_ENDING: Clicking confirmation")
                fast_click(1483, 898)
                time.sleep(1.0)  # Optimized: reduced from 2.0s

        if current_state != BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] BATTLE_ENDING: ERROR - Failed to confirm return home button after 5 attempts")
            send_discord_debug_log("BB Gold: CRITICAL - Failed to confirm end screen after 5 attempts", "ERROR")
            # Assume end screen present to avoid getting stuck
            current_state = BBGoldState.END_SCREEN
            runtime.gui.update_bb_gold_state(current_state.name)

    else:
        # 0/1/2 stars - use standard end screen detection with fallback
        print("[BB GOLD STATE] BATTLE_ENDING: 0/1/2 stars - standard end screen detection")
        end_screen_timeout = getattr(config, "BB_END_SCREEN_TIMEOUT", 10)
        timeout_start = time.time()
        while time.time() - timeout_start < end_screen_timeout:
            end_screen = detect_end_screen_state()
            if end_screen["detected"]:
                print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed")
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                context["star_bonus"] = end_screen["star_bonus"]
                # Cache return home button position if detected
                if end_screen.get("return_button_pos"):
                    context["return_home_button_pos"] = end_screen["return_button_pos"]
                break
            time.sleep(0.3)  # Optimized: reduced from 0.5s

        if current_state != BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] BATTLE_ENDING: End screen not detected, assuming present")
            current_state = BBGoldState.END_SCREEN
            runtime.gui.update_bb_gold_state(current_state.name)
    return current_state


def handle_bb_gold_mode_stateful():
    """
    Handle BB Gold mode using explicit state machine.

    States:
    1. IN_BASE -> SEARCHING: Click search button
    2. SEARCHING -> ATTACK_READY: "Attacker" text detected
    3. ATTACK_READY -> BATTLE_ACTIVE: Deploy Battle Machine + Night Witches
    4. BATTLE_ACTIVE -> BATTLE_ENDING: 2/3 stars or Return Home detected (battle ended)
    5. BATTLE_ENDING -> END_SCREEN: Surrender/end clicked, confirm end screen
    6. END_SCREEN -> RETURNING_HOME: Click return button
    7. RETURNING_HOME -> IN_BASE: Verify back at base
    8. ERROR_RECOVERY -> IN_BASE: Click return button, verify arrival

    Returns:
        bool: True if attack completed successfully, False if error
    """
    current_state = BBGoldState.IN_BASE
    context = {
        "retry_count": 0,
        "troops_deployed": False,
        "stars_detected": 0,
        "attack_start_time": None,
        "battle_machine_ability_time": None,
        "battle_lost": False,
    }

    state_timeout = getattr(config, "BB_STATE_DETECTION_TIMEOUT", 30)
    max_retries = getattr(config, "BB_LOAD_MAX_RETRIES", 3)

    print("[BB GOLD STATE] Starting stateful attack")
    send_discord_debug_log("BB Gold: Starting state machine attack")

    # Main state machine loop
    iteration_count = 0
    max_iterations = 100  # Safety limit to prevent infinite loops

    while iteration_count < max_iterations:
        iteration_count += 1

        # UNIVERSAL: Return Home detection - if found in any state, we're on end screen
        # This provides reliable error recovery since Return Home ONLY appears on end screen
        if current_state not in [BBGoldState.END_SCREEN, BBGoldState.RETURNING_HOME]:
            # Throttle checks to every 0.5 seconds to minimize performance impact
            last_universal_check = context.get("last_return_home_universal_check", 0)
            current_time = time.time()
            if current_time - last_universal_check >= 0.5:
                context["last_return_home_universal_check"] = current_time
                return_home_pos = detect_return_home_button(quiet=True)
                if return_home_pos:
                    print(
                        f"[BB GOLD STATE] !! Return Home detected in {current_state.name} - transitioning to END_SCREEN"
                    )
                    context["return_home_button_pos"] = return_home_pos
                    current_state = BBGoldState.END_SCREEN
                    runtime.gui.update_bb_gold_state(current_state.name)
                    continue  # Skip to END_SCREEN handling

        # STATE 1: IN_BASE -> SEARCHING
        if current_state == BBGoldState.IN_BASE and context["retry_count"] == 0:
            current_state = _state_in_base(context)
            continue

        # STATE 2: SEARCHING -> ATTACK_READY
        if current_state == BBGoldState.SEARCHING:
            current_state = _state_searching(current_state, state_timeout)
            continue

        # STATE 3: ATTACK_READY -> BATTLE_ACTIVE
        if current_state == BBGoldState.ATTACK_READY:
            current_state = _state_attack_ready(context)
            continue

        # STATE 4: BATTLE_ACTIVE -> BATTLE_ENDING
        if current_state == BBGoldState.BATTLE_ACTIVE:
            current_state = _state_battle_active(context)
            continue

        # STATE 5: BATTLE_ENDING -> END_SCREEN
        if current_state == BBGoldState.BATTLE_ENDING:
            current_state = _state_battle_ending(context, current_state)

            continue

        # STATE 6: END_SCREEN -> RETURNING_HOME
        if current_state == BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] END_SCREEN: Detecting and clicking return button")
            runtime.gui.log_message("BB Gold: Returning home")

            # Use cached position if available (from BATTLE_ENDING state for 3 stars)
            cached_pos = context.get("return_home_button_pos")
            clicked = False  # Initialize clicked variable

            if cached_pos:
                # Use cached position - no need to detect again
                print(
                    f"[BB GOLD STATE] END_SCREEN: Using cached return home position {cached_pos} - clicking instantly"
                )
                send_discord_debug_log(f"BB Gold: Clicking cached return home at {cached_pos}")
                fast_click(*cached_pos)
                clicked = True  # Mark as clicked
            else:
                # No cached position - actively detect
                print("[BB GOLD STATE] END_SCREEN: Scanning for return home button...")
                max_wait = 10  # Maximum 10 seconds to find button
                start_time = time.time()

                # Exponential backoff - fast checks early, slower later
                import itertools

                check_intervals = [0.05, 0.05, 0.1, 0.1, 0.2, 0.2, 0.3]
                for interval in itertools.cycle(check_intervals):
                    if time.time() - start_time >= max_wait:
                        break
                    return_home_pos = detect_return_home_button()
                    if return_home_pos:
                        print(
                            f"[BB GOLD STATE] END_SCREEN: ✓ Return home button detected at {return_home_pos} - clicking instantly"
                        )
                        send_discord_debug_log(f"BB Gold: Clicking return home at {return_home_pos}")
                        fast_click(*return_home_pos)
                        clicked = True
                        break
                    time.sleep(interval)  # Exponential backoff

                if not clicked:
                    # NO FALLBACK - Detect actual state and handle appropriately
                    print(
                        "[BB GOLD STATE] END_SCREEN: Return home button not detected after 10s - detecting actual state"
                    )
                    send_discord_debug_log("BB Gold: Return home button not found - detecting state", "WARNING")

                    detected_state = detect_current_game_state()

                    if detected_state == "in_base":
                        # Already at base - skip to IN_BASE state
                        print("[BB GOLD STATE] END_SCREEN: Already at base - transitioning to IN_BASE")
                        send_discord_debug_log("BB Gold: Already at base (return button not needed)")
                        current_state = BBGoldState.IN_BASE
                        runtime.gui.update_bb_gold_state(current_state.name)
                        save_bb_gold_attack_duration(context)
                        increment_bb_gold_counter()
                        return True

                    elif detected_state == "battle_active":
                        # Still in battle - need to surrender
                        print("[BB GOLD STATE] END_SCREEN: Still in active battle - attempting surrender")
                        send_discord_debug_log("BB Gold: Stuck in battle - surrendering", "WARNING")
                        button_type, x, y = detect_surrender_or_end_battle()
                        if button_type == "surrender":
                            fast_click(x, y)
                            time.sleep(0.5)
                            # Click confirmation
                            fast_click(1483, 898)
                            time.sleep(2.0)
                        current_state = BBGoldState.BATTLE_ENDING
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == "battle_ending":
                        # Battle ending - transition to BATTLE_ENDING state
                        print("[BB GOLD STATE] END_SCREEN: Battle still ending - transitioning to BATTLE_ENDING")
                        current_state = BBGoldState.BATTLE_ENDING
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == "end_screen":
                        # This shouldn't happen (we just failed to detect return button)
                        # But detection succeeded now - retry click
                        print("[BB GOLD STATE] END_SCREEN: Return button now detected - retrying click")
                        return_home_pos = detect_return_home_button()
                        if return_home_pos:
                            fast_click(*return_home_pos)
                            clicked = True
                        else:
                            # Still can't find it - enter error recovery
                            print("[BB GOLD STATE] END_SCREEN: Return button still not found - entering ERROR_RECOVERY")
                            send_discord_debug_log("BB Gold: Return button inconsistent - error recovery", "ERROR")
                            current_state = BBGoldState.ERROR_RECOVERY
                            runtime.gui.update_bb_gold_state(current_state.name)
                            continue

                    else:  # 'unknown'
                        # Unknown state - enter error recovery
                        print("[BB GOLD STATE] END_SCREEN: Unknown state detected - entering ERROR_RECOVERY")
                        send_discord_debug_log("BB Gold: Unknown state - entering error recovery", "ERROR")
                        current_state = BBGoldState.ERROR_RECOVERY
                        runtime.gui.update_bb_gold_state(current_state.name)
                        continue

            # Only proceed to RETURNING_HOME if return button was actually clicked
            if clicked:
                time.sleep(1.0)  # Brief wait for transition
                current_state = BBGoldState.RETURNING_HOME
                runtime.gui.update_bb_gold_state(current_state.name)
                print("[BB GOLD STATE] END_SCREEN -> RETURNING_HOME: Return clicked")
            continue

        # STATE 7: RETURNING_HOME -> IN_BASE
        if current_state == BBGoldState.RETURNING_HOME:
            print("[BB GOLD STATE] RETURNING_HOME: Waiting for base arrival")

            # Wait for IN_BASE confirmation
            return_timeout = getattr(config, "BB_RETURN_HOME_TIMEOUT", 15)
            timeout_start = time.time()
            while time.time() - timeout_start < return_timeout:
                if detect_in_base_state():
                    print("[BB GOLD STATE] RETURNING_HOME -> IN_BASE: Army button detected")
                    runtime.gui.update_bb_gold_state("IN_BASE")

                    # Save attack duration to CSV
                    save_bb_gold_attack_duration(context)

                    # Update attack counter
                    increment_bb_gold_counter()

                    return True  # Success!
                time.sleep(0.3)  # Optimized: reduced from 0.5s

            # Timeout - assume we're back anyway
            print("[BB GOLD STATE] RETURNING_HOME: Base detection timeout, assuming success")
            save_bb_gold_attack_duration(context)
            increment_bb_gold_counter()
            return True

        # STATE 8: ERROR_RECOVERY -> IN_BASE
        if current_state == BBGoldState.ERROR_RECOVERY:
            print("[BB GOLD STATE] ERROR_RECOVERY: Attempting recovery")
            runtime.gui.log_message("BB Gold: Error recovery")
            send_discord_debug_log("BB Gold: Entering error recovery", "WARNING")

            # Quick check: Return Home button means we're on end screen (cache position for fast click)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                print("[BB GOLD STATE] ERROR_RECOVERY: Return Home detected - on end screen")
                context["return_home_button_pos"] = return_home_pos
                current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)
                continue

            # If not on end screen, detect what state we're actually in
            detected_state = detect_current_game_state()

            if detected_state == "in_base":
                # Already recovered - return to IN_BASE
                print("[BB GOLD STATE] ERROR_RECOVERY: Already at base - recovery successful")
                send_discord_debug_log("BB Gold: Error recovery successful (already at base)")
                context["retry_count"] += 1
                if context["retry_count"] < max_retries:
                    print(f"[BB GOLD STATE] ERROR_RECOVERY -> IN_BASE: Retry {context['retry_count']}/{max_retries}")
                    current_state = BBGoldState.IN_BASE
                    runtime.gui.update_bb_gold_state(current_state.name)
                else:
                    print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                    send_discord_debug_log("BB Gold: Max retries exceeded, aborting", "ERROR")
                    return False

            elif detected_state == "battle_active":
                # Stuck in battle - surrender to exit
                print("[BB GOLD STATE] ERROR_RECOVERY: In active battle - surrendering")
                send_discord_debug_log("BB Gold: Error recovery - surrendering from battle", "WARNING")
                button_type, x, y = detect_surrender_or_end_battle()
                if button_type == "surrender":
                    fast_click(x, y)
                    time.sleep(0.5)
                    # Click confirmation
                    fast_click(1483, 898)
                    time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    runtime.gui.update_bb_gold_state(current_state.name)
                else:
                    # Can't find surrender - try minimal troop deployment to enable it
                    print("[BB GOLD STATE] ERROR_RECOVERY: Surrender not found - deploying troop")
                    fast_click(1282, 720)  # Deploy one troop
                    time.sleep(3.0)
                    # Try surrender again
                    button_type, x, y = detect_surrender_or_end_battle()
                    if button_type == "surrender":
                        fast_click(x, y)
                        time.sleep(0.5)
                        fast_click(1483, 898)
                        time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    runtime.gui.update_bb_gold_state(current_state.name)

            elif detected_state == "battle_ending" or detected_state == "end_screen":
                # Battle ending or end screen - transition appropriately
                print(f"[BB GOLD STATE] ERROR_RECOVERY: Detected {detected_state} - transitioning")
                if detected_state == "battle_ending":
                    current_state = BBGoldState.BATTLE_ENDING
                else:
                    current_state = BBGoldState.END_SCREEN
                runtime.gui.update_bb_gold_state(current_state.name)

            else:  # 'unknown'
                # Unknown state - try clicking return button and retry
                print("[BB GOLD STATE] ERROR_RECOVERY: Unknown state - clicking return button")
                send_discord_debug_log("BB Gold: Unknown state in error recovery - clicking return", "WARNING")
                click_in_square(config.BB_RETURN_BUTTON_GHOST)
                time.sleep(config.BB_RETRY_WAIT_TIME)

                # Check again if we're at base now
                if detect_in_base_state():
                    print("[BB GOLD STATE] ERROR_RECOVERY: Return click worked - at base now")
                    context["retry_count"] += 1
                    if context["retry_count"] < max_retries:
                        current_state = BBGoldState.IN_BASE
                        runtime.gui.update_bb_gold_state(current_state.name)
                    else:
                        print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                        return False
                else:
                    # Still stuck - increment retry and continue looping
                    context["retry_count"] += 1
                    if context["retry_count"] >= max_retries:
                        print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded - aborting")
                        send_discord_debug_log("BB Gold: Max error recovery retries exceeded", "ERROR")
                        return False
                    print(f"[BB GOLD STATE] ERROR_RECOVERY: Still stuck - retry {context['retry_count']}/{max_retries}")
                    time.sleep(2)

            continue

        # Safety: break infinite loops
        print(f"[BB GOLD STATE] WARNING: Unexpected state {current_state}, breaking")
        break

    # If we exit the loop without returning, something went wrong
    print("[BB GOLD STATE] ERROR: State machine exceeded max iterations or entered invalid state")
    send_discord_debug_log("BB Gold: State machine error - max iterations exceeded", "ERROR")
    return False


# Alias the new stateful function as the main function
def handle_bb_gold_mode():
    """
    Handle BB Gold mode using state machine.
    This is an alias for handle_bb_gold_mode_stateful().
    """
    return handle_bb_gold_mode_stateful()
