"""Turbo deployment: rapid SendInput clicks along a side of the map."""

import time

import keyboard

import config
from coc_bot.geometry import interpolate_points
from coc_bot.input.win32 import turbo_fast_click, turbo_move_cursor

# Turbo deployment corner coordinates (extracted from full SIDE_DEPLOYMENT_COORDS)
TURBO_SIDE_CORNERS = {
    'up': [
        (229, 903),    # Left edge start
        (1299, 121),   # Apex (middle-top)
        (2330, 894),   # Right edge end
    ],
    'down': [
        (273, 415),    # Left edge start
        (1281, 1143),  # Apex (middle-bottom)
        (2301, 424),   # Right edge end
    ],
}

# Turbo deployment configuration
TURBO_CLICK_DELAY_MS = 60  # 60ms delay = ~16 CPS (tested reliable)


def turbo_deploy_along_path(corners, num_clicks, delay_ms, sbarb_hotkey, destruction_check=None):
    """
    Deploy units by moving along path defined by corners while fast-clicking.
    Uses Windows API for maximum speed. Stops immediately if 50% destruction reached.

    Args:
        corners: List of (x, y) corner points defining the path
        num_clicks: Total number of clicks (units) to deploy
        delay_ms: Delay between clicks in milliseconds
        sbarb_hotkey: Hotkey to select the troop before deployment
        destruction_check: Optional dict with 'value' key to check for early exit
    """
    # Select the troop
    keyboard.send(sbarb_hotkey)
    time.sleep(0.05)

    # Calculate clicks per segment
    num_segments = len(corners) - 1
    clicks_per_segment = num_clicks // num_segments
    extra_clicks = num_clicks % num_segments

    total_deployed = 0
    start_time = time.perf_counter()
    stopped_early = False

    for seg_idx in range(num_segments):
        # Check for early exit
        if destruction_check and destruction_check.get('value', False):
            stopped_early = True
            break

        start_corner = corners[seg_idx]
        end_corner = corners[seg_idx + 1]

        # Add extra click to early segments if needed
        segment_clicks = clicks_per_segment + (1 if seg_idx < extra_clicks else 0)

        # Generate points along this segment
        points = interpolate_points(start_corner, end_corner, segment_clicks)

        for point in points:
            # Check for early exit inside inner loop
            if destruction_check and destruction_check.get('value', False):
                stopped_early = True
                break
            turbo_move_cursor(point[0], point[1])
            turbo_fast_click()
            total_deployed += 1
            time.sleep(delay_ms / 1000)

        if stopped_early:
            break

    elapsed = time.perf_counter() - start_time
    if stopped_early:
        print(f"[TURBO DEPLOY] STOPPED EARLY - deployed {total_deployed}/{num_clicks} units in {elapsed*1000:.0f}ms (50% reached)")
    else:
        print(f"[TURBO DEPLOY] Deployed {total_deployed} units in {elapsed*1000:.0f}ms ({total_deployed/elapsed:.0f} CPS)")
    return total_deployed


def turbo_deploy_heroes(side, hero_timings, destruction_check=None):
    """
    Deploy all 4 heroes at the hero position for turbo mode.
    Stops immediately if 50% destruction reached.

    Args:
        side: 'up' or 'down'
        hero_timings: dict with queen/king/warden/rc timings
        destruction_check: Optional dict with 'value' key to check for early exit
    """
    hero_pos = config.SIDE_DEPLOYMENT_COORDS[side]['hero']
    print(f"[TURBO DEPLOY] Deploying heroes at {hero_pos}")

    KEYS = config.KEYS
    hero_keys = ['queen', 'king', 'warden', 'rc']
    deployed_count = 0

    for hero_key in hero_keys:
        # Check for early exit
        if destruction_check and destruction_check.get('value', False):
            print(f"[TURBO DEPLOY] STOPPED EARLY - deployed {deployed_count}/4 heroes (50% reached)")
            return
        keyboard.send(KEYS[hero_key])
        time.sleep(0.08)  # Wait for hotkey to register
        turbo_move_cursor(hero_pos[0], hero_pos[1])
        turbo_fast_click()
        time.sleep(0.05)
        deployed_count += 1

    print(f"[TURBO DEPLOY] All heroes deployed")


def turbo_deploy_siege(side, destruction_check=None):
    """Deploy siege machine at hero position for turbo mode."""
    # Check for early exit
    if destruction_check and destruction_check.get('value', False):
        print(f"[TURBO DEPLOY] Skipping siege (50% reached)")
        return

    hero_pos = config.SIDE_DEPLOYMENT_COORDS[side]['hero']
    print(f"[TURBO DEPLOY] Deploying siege at {hero_pos}")

    keyboard.send(config.KEYS['siege'])
    time.sleep(0.08)
    turbo_move_cursor(hero_pos[0], hero_pos[1])
    turbo_fast_click()
    time.sleep(0.1)
    print(f"[TURBO DEPLOY] Siege deployed")
