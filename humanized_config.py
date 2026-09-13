# humanized_config.py
"""
Configuration for humanized input features.
Adjust these settings to customize anti-detection behavior.
"""

# ==================== MOUSE MOVEMENT FEATURES ====================

# Enable overshoots - 15% chance of overshooting target then correcting
# Humans naturally overshoot and correct about 15% of the time
ENABLE_OVERSHOOTS = True

# Enable natural hand tremor - adds 0.5-2 pixel jitter to movements
# Makes mouse paths less perfect and more organic
ENABLE_TREMOR = True

# Enable mouse drift during idle/thinking periods
# Mouse makes small movements when "reading" or "analyzing"
ENABLE_DRIFT = True

# Enable occasional misclicks (DISABLED by default for safety)
# 2% chance of clicking slightly off target then correcting
# WARNING: May cause unintended actions - test thoroughly before enabling
ENABLE_MISTAKES = False

# ==================== TIMING FEATURES ====================

# Use realistic timing distributions (lognormal/gamma) instead of uniform
# Human reaction times follow lognormal distribution, not uniform
USE_REALISTIC_DISTRIBUTIONS = True

# Variance in timing (0.3 = ±30%)
# Prevents predictable timing patterns that could be detected
PAUSE_VARIANCE = 0.3

# ==================== ADVANCED SETTINGS ====================

# Mouse movement settings
OVERSHOOT_DISTANCE_MIN = 5      # Minimum overshoot in pixels
OVERSHOOT_DISTANCE_MAX = 15     # Maximum overshoot in pixels
TREMOR_INTENSITY = 1.0          # Tremor intensity multiplier (0.5-2.0)
DRIFT_PROBABILITY = 0.3         # 30% chance of drift during pauses
MAX_DRIFT_DISTANCE = 5          # Maximum drift in pixels

# Bezier curve settings (NOTE: Now using pyautogui's tweening for smooth, fast movement)
BEZIER_CONTROL_POINTS = 2       # Number of control points (1-3) - legacy setting
BEZIER_NUM_POINTS = 40          # Number of points along curve - legacy setting

# Timing distribution parameters
LOGNORMAL_MU = 5.5              # Mean of underlying normal distribution
LOGNORMAL_SIGMA = 0.5           # Standard deviation
GAMMA_SHAPE = 2.0               # Gamma distribution shape parameter
GAMMA_SCALE = 0.15              # Gamma distribution scale parameter

# Context-aware timing defaults (in seconds) - optimized for speed
THINKING_PAUSE_MIN = 0.3        # Minimum thinking time (reduced from 0.5)
THINKING_PAUSE_MAX = 1.0        # Maximum thinking time (reduced from 2.0)
READING_PAUSE_BASE = 0.5        # Base reading time (reduced from 1.0)
REACTION_DELAY_MIN = 0.10       # Minimum reaction time (100ms, reduced from 150ms)
REACTION_DELAY_MAX = 0.25       # Maximum reaction time (250ms, reduced from 350ms)

# ==================== SAFETY FEATURES ====================

# Minimum delays to prevent too-fast actions (safety thresholds)
ABSOLUTE_MIN_DELAY = 0.02       # Never go below 20ms between actions
ABSOLUTE_MIN_CLICK_DELAY = 0.03 # Never go below 30ms for clicks

# Maximum delays to prevent too-slow actions (functional limits)
ABSOLUTE_MAX_DELAY = 5.0        # Never exceed 5 seconds for basic actions
ABSOLUTE_MAX_THINKING = 3.0     # Never exceed 3 seconds for thinking pauses

# ==================== DEBUG SETTINGS ====================

# Enable detailed logging of mouse movements and timings
DEBUG_LOGGING = False           # Set to True to log all humanized actions

# Log file for debugging (if DEBUG_LOGGING is True)
DEBUG_LOG_FILE = "humanized_input_debug.log"
