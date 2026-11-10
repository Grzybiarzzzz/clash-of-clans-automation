# humanized_input.py
"""
Enhanced mouse movement and timing functions with realistic human behavior patterns.
Includes overshoots, micro-corrections, natural tremor, and variable acceleration.
"""

import pyautogui
import time
import random
import numpy as np
from typing import Tuple, List
import math

# Import configuration
try:
    from coc_bot.humanized_config import *
except ImportError:
    # Fallback to default values if config file is missing
    print("Warning: humanized_config.py not found, using default settings")
    ENABLE_OVERSHOOTS = True
    ENABLE_TREMOR = True
    ENABLE_DRIFT = True
    ENABLE_MISTAKES = False
    USE_REALISTIC_DISTRIBUTIONS = True
    PAUSE_VARIANCE = 0.3
    OVERSHOOT_DISTANCE_MIN = 5
    OVERSHOOT_DISTANCE_MAX = 15
    TREMOR_INTENSITY = 1.0
    DRIFT_PROBABILITY = 0.3
    MAX_DRIFT_DISTANCE = 5
    BEZIER_CONTROL_POINTS = 2
    BEZIER_NUM_POINTS = 40
    LOGNORMAL_MU = 5.5
    LOGNORMAL_SIGMA = 0.5
    GAMMA_SHAPE = 2.0
    GAMMA_SCALE = 0.15
    THINKING_PAUSE_MIN = 0.5
    THINKING_PAUSE_MAX = 2.0
    READING_PAUSE_BASE = 1.0
    REACTION_DELAY_MIN = 0.15
    REACTION_DELAY_MAX = 0.35
    ABSOLUTE_MIN_DELAY = 0.02
    ABSOLUTE_MIN_CLICK_DELAY = 0.03
    ABSOLUTE_MAX_DELAY = 5.0
    ABSOLUTE_MAX_THINKING = 3.0
    DEBUG_LOGGING = False
    DEBUG_LOG_FILE = "humanized_input_debug.log"


def lognormal_delay(min_ms: float = 100, max_ms: float = 500, mu: float = None, sigma: float = None) -> float:
    """
    Generate a more realistic delay using lognormal distribution.
    Humans have faster reactions with a long tail (occasional slow reactions).

    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
        mu: Mean of the underlying normal distribution
        sigma: Standard deviation of the underlying normal distribution

    Returns:
        Delay in seconds
    """
    if not USE_REALISTIC_DISTRIBUTIONS:
        return random.uniform(min_ms / 1000, max_ms / 1000)

    # Use config defaults if not specified
    if mu is None:
        mu = LOGNORMAL_MU
    if sigma is None:
        sigma = LOGNORMAL_SIGMA

    delay = np.random.lognormal(mu, sigma) / 100
    # Clamp to min/max range
    delay = max(min_ms / 1000, min(max_ms / 1000, delay))
    # Apply absolute minimum safety
    delay = max(ABSOLUTE_MIN_DELAY, delay)

    # Add variance to avoid patterns
    if PAUSE_VARIANCE > 0:
        variance = delay * PAUSE_VARIANCE
        delay += random.uniform(-variance, variance)
        delay = max(min_ms / 1000, delay)

    return delay


def gamma_delay(min_ms: float = 100, max_ms: float = 500, shape: float = 2.0, scale: float = 0.15) -> float:
    """
    Alternative realistic delay using gamma distribution.
    Good for modeling reaction times.

    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
        shape: Shape parameter (k)
        scale: Scale parameter (θ)

    Returns:
        Delay in seconds
    """
    if not USE_REALISTIC_DISTRIBUTIONS:
        return random.uniform(min_ms / 1000, max_ms / 1000)

    delay = np.random.gamma(shape, scale)
    delay = max(min_ms / 1000, min(max_ms / 1000, delay))

    # Add variance
    if PAUSE_VARIANCE > 0:
        variance = delay * PAUSE_VARIANCE
        delay += random.uniform(-variance, variance)
        delay = max(min_ms / 1000, delay)

    return delay


def human_delay(min_ms: float = 60, max_ms: float = 130, distribution: str = 'lognormal') -> float:
    """
    Unified delay function with multiple distribution options.

    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
        distribution: 'lognormal', 'gamma', or 'uniform'

    Returns:
        Delay in seconds
    """
    if distribution == 'lognormal':
        return lognormal_delay(min_ms, max_ms)
    elif distribution == 'gamma':
        return gamma_delay(min_ms, max_ms)
    else:  # uniform fallback
        return random.uniform(min_ms / 1000, max_ms / 1000)


def generate_bezier_points(start: Tuple[int, int], end: Tuple[int, int],
                          control_points: int = 2, num_points: int = 50) -> List[Tuple[float, float]]:
    """
    Generate points along a bezier curve with variable control points.

    Args:
        start: Starting (x, y) coordinates
        end: Ending (x, y) coordinates
        control_points: Number of control points (1-3)
        num_points: Number of points to generate along curve

    Returns:
        List of (x, y) coordinate tuples
    """
    if control_points == 1:
        # Quadratic Bezier
        cp_x = (start[0] + end[0]) / 2 + random.randint(-100, 100)
        cp_y = (start[1] + end[1]) / 2 + random.randint(-100, 100)
        control = [(cp_x, cp_y)]
    elif control_points == 2:
        # Cubic Bezier (more natural)
        cp1_x = start[0] + (end[0] - start[0]) / 3 + random.randint(-50, 50)
        cp1_y = start[1] + (end[1] - start[1]) / 3 + random.randint(-50, 50)
        cp2_x = start[0] + 2 * (end[0] - start[0]) / 3 + random.randint(-50, 50)
        cp2_y = start[1] + 2 * (end[1] - start[1]) / 3 + random.randint(-50, 50)
        control = [(cp1_x, cp1_y), (cp2_x, cp2_y)]
    else:
        # Three control points for very curved paths
        cp1_x = start[0] + (end[0] - start[0]) / 4 + random.randint(-75, 75)
        cp1_y = start[1] + (end[1] - start[1]) / 4 + random.randint(-75, 75)
        cp2_x = start[0] + (end[0] - start[0]) / 2 + random.randint(-100, 100)
        cp2_y = start[1] + (end[1] - start[1]) / 2 + random.randint(-100, 100)
        cp3_x = start[0] + 3 * (end[0] - start[0]) / 4 + random.randint(-75, 75)
        cp3_y = start[1] + 3 * (end[1] - start[1]) / 4 + random.randint(-75, 75)
        control = [(cp1_x, cp1_y), (cp2_x, cp2_y), (cp3_x, cp3_y)]

    points = []
    for i in range(num_points):
        t = i / (num_points - 1)

        if len(control) == 1:
            # Quadratic: B(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control[0][0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control[0][1] + t**2 * end[1]
        elif len(control) == 2:
            # Cubic: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
            x = (1-t)**3 * start[0] + 3*(1-t)**2*t * control[0][0] + 3*(1-t)*t**2 * control[1][0] + t**3 * end[0]
            y = (1-t)**3 * start[1] + 3*(1-t)**2*t * control[0][1] + 3*(1-t)*t**2 * control[1][1] + t**3 * end[1]
        else:
            # Higher order bezier
            x = (1-t)**4 * start[0] + 4*(1-t)**3*t * control[0][0] + 6*(1-t)**2*t**2 * control[1][0] + 4*(1-t)*t**3 * control[2][0] + t**4 * end[0]
            y = (1-t)**4 * start[1] + 4*(1-t)**3*t * control[0][1] + 6*(1-t)**2*t**2 * control[1][1] + 4*(1-t)*t**3 * control[2][1] + t**4 * end[1]

        points.append((x, y))

    return points


def add_tremor(x: float, y: float, intensity: float = 1.0) -> Tuple[float, float]:
    """
    Add natural hand tremor to coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        intensity: Tremor intensity multiplier (0.5-2.0)

    Returns:
        Adjusted (x, y) coordinates
    """
    if not ENABLE_TREMOR:
        return (x, y)

    # Human tremor is typically 0.5-2 pixels
    tremor_x = random.uniform(-1.5 * intensity, 1.5 * intensity)
    tremor_y = random.uniform(-1.5 * intensity, 1.5 * intensity)

    return (x + tremor_x, y + tremor_y)


def advanced_mouse_movement(start: Tuple[int, int], end: Tuple[int, int],
                           overshoot: bool = None, duration: float = None) -> None:
    """
    Advanced mouse movement with overshoots, tremor, and variable acceleration.
    Optimized for speed and smoothness - humans move mouse FAST.

    Args:
        start: Starting (x, y) coordinates
        end: Ending (x, y) coordinates
        overshoot: Whether to overshoot (None = random 15% chance)
        duration: Movement duration in seconds (None = calculate based on distance)
    """
    # Calculate movement distance for duration estimation
    distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

    # Much faster base duration - humans move mouse quickly
    # Short distances: 0.08-0.12s, Long distances: up to 0.25s
    if duration is None:
        if distance < 100:
            base_duration = random.uniform(0.08, 0.12)
        elif distance < 500:
            base_duration = random.uniform(0.12, 0.18)
        else:
            base_duration = random.uniform(0.18, 0.25)
    else:
        base_duration = duration

    # Decide on overshoot
    if overshoot is None:
        overshoot = ENABLE_OVERSHOOTS and random.random() < 0.15

    # If overshooting, first move past target
    if overshoot:
        # Calculate overshoot point using config values
        overshoot_distance = random.randint(OVERSHOOT_DISTANCE_MIN, OVERSHOOT_DISTANCE_MAX)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        overshoot_x = end[0] + overshoot_distance * math.cos(angle)
        overshoot_y = end[1] + overshoot_distance * math.sin(angle)

        # Fast move to overshoot using pyautogui's built-in smooth movement
        # Add slight random offset for tremor effect
        ox = int(overshoot_x + random.uniform(-1, 1))
        oy = int(overshoot_y + random.uniform(-1, 1))
        pyautogui.moveTo(ox, oy, duration=base_duration * 0.7, tween=pyautogui.easeOutQuad)

        # Quick correction back to target
        time.sleep(random.uniform(0.03, 0.08))
        ex = end[0] + random.uniform(-1, 1)
        ey = end[1] + random.uniform(-1, 1)
        pyautogui.moveTo(ex, ey, duration=base_duration * 0.3, tween=pyautogui.easeInOutQuad)

    else:
        # Fast, smooth movement using pyautogui's built-in tweening
        # Add slight tremor to destination
        ex = end[0] + random.uniform(-1.5, 1.5) if ENABLE_TREMOR else end[0]
        ey = end[1] + random.uniform(-1.5, 1.5) if ENABLE_TREMOR else end[1]

        # Use easeOutQuad for natural deceleration at end
        pyautogui.moveTo(ex, ey, duration=base_duration, tween=pyautogui.easeOutQuad)


def mouse_drift_idle(max_drift: int = None) -> None:
    """
    Small mouse movements during "thinking" or idle time.
    Simulates natural hand movements when user is reading or planning.

    Args:
        max_drift: Maximum drift distance in pixels (uses config default if None)
    """
    if max_drift is None:
        max_drift = MAX_DRIFT_DISTANCE

    if not ENABLE_DRIFT or random.random() > DRIFT_PROBABILITY:
        return

    current = pyautogui.position()
    drift_x = current[0] + random.randint(-max_drift, max_drift)
    drift_y = current[1] + random.randint(-max_drift, max_drift)

    # Quick, subtle movement - humans don't drift slowly
    duration = random.uniform(0.15, 0.4)  # Faster drift
    pyautogui.moveTo(drift_x, drift_y, duration=duration, tween=pyautogui.easeInOutQuad)


def human_like_move_click_enhanced(x: int, y: int, region_size: int = 8,
                                   pre_click_pause: bool = True) -> None:
    """
    Enhanced version of human_like_move_click with advanced features.
    Drop-in replacement for the original function.
    Optimized for fast, natural clicking.

    Args:
        x: Target X coordinate
        y: Target Y coordinate
        region_size: Randomization region size in pixels
        pre_click_pause: Whether to pause before clicking
    """
    try:
        # Get starting position
        start = pyautogui.position()

        # Randomize target within region
        rx = x + random.randint(-region_size, region_size)
        ry = y + random.randint(-region_size, region_size)

        # Occasional misclick (disabled by default)
        if ENABLE_MISTAKES and random.random() < 0.02:
            # Click slightly off target, then correct
            rx += random.randint(20, 50) * random.choice([-1, 1])
            ry += random.randint(20, 50) * random.choice([-1, 1])

        # Use advanced movement (fast and smooth)
        advanced_mouse_movement(start, (rx, ry))

        # Minimal pre-click pause (humans click quickly after arriving)
        if pre_click_pause:
            time.sleep(human_delay(10, 40))  # Reduced from 30-120 to 10-40ms

        # Click with slight variation in timing
        pyautogui.click()

        # Minimal post-click delay
        time.sleep(human_delay(10, 30))  # Reduced from 20-80 to 10-30ms
    except pyautogui.FailSafeException:
        # User moved mouse to corner for emergency stop
        print("PyAutoGUI FailSafe triggered - stopping all mouse operations")
        raise  # Re-raise to stop the bot
    except Exception as e:
        # Catch any other errors during shutdown
        print(f"Error during mouse operation: {e}")
        # Don't re-raise to allow graceful shutdown


def humanized_sleep(base_seconds: float, variance: float = 0.3) -> None:
    """
    Sleep with human-like variance instead of exact timing.

    Args:
        base_seconds: Base sleep duration
        variance: Variance as percentage (0.3 = ±30%)
    """
    if USE_REALISTIC_DISTRIBUTIONS:
        # Use lognormal for more realistic distribution
        actual_sleep = max(0, np.random.lognormal(np.log(base_seconds), variance))
    else:
        # Simple variance
        actual_sleep = base_seconds * random.uniform(1 - variance, 1 + variance)

    time.sleep(actual_sleep)


def random_sleep_enhanced(min_ms: int, max_ms: int) -> None:
    """
    Enhanced version of random_sleep with realistic distributions.
    Drop-in replacement for the original function.

    Args:
        min_ms: Minimum sleep in milliseconds
        max_ms: Maximum sleep in milliseconds
    """
    delay = human_delay(min_ms, max_ms)
    time.sleep(delay)


# Backward compatible wrapper - can replace original function
def human_like_move_click(x: int, y: int, region_size: int = 8) -> None:
    """
    Backward compatible wrapper for enhanced mouse movement.
    Can directly replace the original function.
    """
    human_like_move_click_enhanced(x, y, region_size)


def fast_click(x: int, y: int, region_size: int = 8) -> None:
    """
    Ultra-fast click with minimal humanization.
    Use for speed-critical operations like BB surrender/return.

    Args:
        x: Target X coordinate
        y: Target Y coordinate
        region_size: Randomization region size in pixels
    """
    try:
        # Minimal randomization
        rx = x + random.randint(-region_size, region_size)
        ry = y + random.randint(-region_size, region_size)

        # Very fast movement - no overshoot, minimal tremor
        ex = rx + random.uniform(-0.5, 0.5) if ENABLE_TREMOR else rx
        ey = ry + random.uniform(-0.5, 0.5) if ENABLE_TREMOR else ry

        # Ultra-fast movement (0.05-0.08s)
        pyautogui.moveTo(ex, ey, duration=random.uniform(0.05, 0.08), tween=pyautogui.easeOutQuad)

        # Minimal pre-click pause (5-15ms)
        time.sleep(random.uniform(0.005, 0.015))

        # Click
        pyautogui.click()

        # Minimal post-click pause (5-10ms)
        time.sleep(random.uniform(0.005, 0.010))
    except pyautogui.FailSafeException:
        # User moved mouse to corner for emergency stop
        print("PyAutoGUI FailSafe triggered - stopping all mouse operations")
        raise  # Re-raise to stop the bot
    except Exception as e:
        # Catch any other errors during shutdown
        print(f"Error during fast click operation: {e}")
        # Don't re-raise to allow graceful shutdown


def random_sleep(min_ms: int, max_ms: int) -> None:
    """
    Backward compatible wrapper for enhanced sleep.
    Can directly replace the original function.
    """
    random_sleep_enhanced(min_ms, max_ms)


# Context-aware timing functions
def thinking_pause(min_seconds: float = None, max_seconds: float = None) -> None:
    """
    Pause as if "thinking" or analyzing. Includes possible mouse drift.
    Use before major decisions (attack/skip, strategy selection, etc.)

    Args:
        min_seconds: Minimum thinking time (uses config default if None)
        max_seconds: Maximum thinking time (uses config default if None)
    """
    if min_seconds is None:
        min_seconds = THINKING_PAUSE_MIN
    if max_seconds is None:
        max_seconds = THINKING_PAUSE_MAX

    # Safety clamp
    max_seconds = min(max_seconds, ABSOLUTE_MAX_THINKING)

    # Drift during thinking
    if ENABLE_DRIFT and random.random() < 0.5:
        mouse_drift_idle(max_drift=8)

    # Think time with realistic distribution
    think_time = lognormal_delay(min_seconds * 1000, max_seconds * 1000)
    time.sleep(think_time)


def reading_pause(base_seconds: float = None) -> None:
    """
    Pause as if reading information on screen (OCR results, loot values, etc.)

    Args:
        base_seconds: Base reading time (uses config default if None)
    """
    if base_seconds is None:
        base_seconds = READING_PAUSE_BASE

    # Reading time varies more than thinking
    read_time = gamma_delay(base_seconds * 500, base_seconds * 1500, shape=GAMMA_SHAPE, scale=GAMMA_SCALE)
    # Safety clamp
    read_time = min(read_time, ABSOLUTE_MAX_THINKING)
    time.sleep(read_time)


def reaction_delay() -> None:
    """
    Very short delay simulating visual reaction time.
    Use after UI changes, button appears, etc.
    """
    # Human reaction time is typically 200-300ms
    delay = lognormal_delay(REACTION_DELAY_MIN * 1000, REACTION_DELAY_MAX * 1000, mu=5.3, sigma=0.3)
    time.sleep(delay)
