# main.py
import pyautogui
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import keyboard
from PIL import ImageGrab, Image
import pytesseract
import numpy as np
import cv2
import os
import config  # external constants
from bot_gui import BotGUI
import tkinter as tk
import requests  # Add for Discord webhook notifications
from PIL import ImageOps
import json # Added for wall coordinate saving/loading
from math import sqrt
import glob
# import easyocr # Added for EasyOCR
# easyocr_reader = easyocr.Reader(['en'], gpu=False)
from imutils.object_detection import non_max_suppression
import matplotlib.pyplot as plt  # For plotting statistics
from datetime import datetime, timedelta
from enum import Enum, auto

# Web GUI server
from bot_state import BotStateManager
from web.server import start_web_server

# Import enhanced humanized input functions
from humanized_input import (
    human_like_move_click,
    random_sleep,
    thinking_pause,
    reading_pause,
    reaction_delay,
    humanized_sleep,
    mouse_drift_idle,
    fast_click  # Ultra-fast click for speed-critical operations
)

# Ensure pytesseract knows its executable path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

# Enable PyAutoGUI failsafe - move mouse to corner to emergency stop
pyautogui.FAILSAFE = False
print("PyAutoGUI corner failsafe is disabled; use F2 to stop or ESC to exit")

# ============================================================
# GPU TEMPLATE MATCHING (optional - offloads CPU to GPU)
# ============================================================
# Always try to load GPU module, but use it only when GUI setting is enabled
try:
    from gpu_template_matching import gpu_match_template as _gpu_match_template, GPU_AVAILABLE
    if GPU_AVAILABLE:
        print("[GPU] GPU template matching AVAILABLE - toggle in Global Settings")
    else:
        print("[GPU] PyTorch CUDA not available - GPU option will use CPU fallback")
except ImportError as e:
    print(f"[GPU] gpu_template_matching module not found: {e}")
    GPU_AVAILABLE = False
    _gpu_match_template = None

def gpu_match_template(image, template, method='TM_CCOEFF_NORMED'):
    """Wrapper that checks GUI setting to decide GPU vs CPU"""
    # Check if GUI exists and GPU scanning is enabled
    use_gpu = GPU_AVAILABLE and hasattr(gui, 'gpu_scanning_var') and gui.gpu_scanning_var.get()
    if use_gpu and _gpu_match_template:
        return _gpu_match_template(image, template, method)
    else:
        return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

# ============================================================
# WINDOWS API FAST-CLICK (for Turbo Deployment mode)
# ============================================================
import ctypes
from ctypes import wintypes

# Windows API constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("mi", MOUSEINPUT),
    ]

user32 = ctypes.windll.user32

def create_mouse_input(flags):
    """Create a mouse input event for Windows API."""
    return INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(
            dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None
        )
    )

def turbo_fast_click():
    """Send a single ultra-fast click at current cursor position using Windows API."""
    down = create_mouse_input(MOUSEEVENTF_LEFTDOWN)
    up = create_mouse_input(MOUSEEVENTF_LEFTUP)
    user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

def turbo_move_cursor(x, y):
    """Move cursor to absolute position using Windows API."""
    user32.SetCursorPos(int(x), int(y))

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

def interpolate_points(p1, p2, num_points):
    """Generate intermediate points between two coordinates for turbo deployment."""
    points = []
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        x = p1[0] + (p2[0] - p1[0]) * t
        y = p1[1] + (p2[1] - p1[1]) * t
        points.append((x, y))
    return points

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

# Global control flags
paused = True
running = True
loop_count = 0

# Add global counters for statistics
skipped_bases = 0
attacked_bases = 0
bb_elixir_attack_count = 0  # Counter for BB Elixir loot collection every 12 attacks
bb_gold_attack_count = 0  # Counter for BB Gold loot collection every 12 attacks

# Resource tracking for full storage detection (auto-pause when no loot gained)
last_3_resources = {
    'main_base': [],  # List of (gold, elixir, dark_elixir) tuples
    'builder_base': []  # List of (gold, elixir) tuples
}

# BB Gold State Machine Enum
class BBGoldState(Enum):
    """BB Gold mode states - explicit lifecycle tracking"""
    IN_BASE = auto()              # At home base, army_button.png visible
    SEARCHING = auto()            # Search button clicked, waiting for match
    ATTACK_READY = auto()         # "Attacker" text confirmed, ready to deploy
    TROOPS_DEPLOYING = auto()     # Battle Machine/Night Witches being placed
    BATTLE_ACTIVE = auto()        # All troops deployed, monitoring stars
    BATTLE_ENDING = auto()        # 2/3 stars detected or timeout, clicking surrender/end
    END_SCREEN = auto()           # Battle finished, on victory/defeat screen
    RETURNING_HOME = auto()       # Return button clicked, transitioning to base
    ERROR_RECOVERY = auto()       # Ghost attack or error state, recovering

# Template cache for achievement buildings (speeds up detection by 0.5-1s per scan)
achievement_building_templates = {}

# BB Gold template cache (eliminates disk I/O during attacks)
_bb_gold_template_cache = {}

# Add a debug flag for attack OCR at the top
ATTACK_OCR_DEBUG = False

# Discord control integration
last_settings_check = 0
settings_check_interval = 1.0  # Check every second

# Debug logging configuration
DEBUG_LOG_ENABLED = getattr(config, 'DEBUG_LOG_ENABLED', True)
DEBUG_LOG_INTERVAL = getattr(config, 'DEBUG_LOG_INTERVAL', 5)  # Send debug logs every 30 seconds
DEBUG_LOG_LEVEL = getattr(config, 'DEBUG_LOG_LEVEL', 'INFO')
last_debug_log = 0
debug_log_buffer = []

# Create GUI
root = tk.Tk()
gui = BotGUI(root)

# Initialize shared state manager for web GUI
state_manager = BotStateManager()

# Load existing state from JSON if it exists
WEB_STATE_FILE = os.path.join("data", "web_state.json")
if os.path.exists(WEB_STATE_FILE):
    try:
        state_manager.load_from_json(WEB_STATE_FILE)
        print("[MAIN] Loaded web state from JSON")
    except Exception as e:
        print(f"[MAIN] Failed to load web state: {e}")

# Initialize default state values
state_manager.update({
    "running": False,
    "paused": True,
    "status": "PAUSED",
    "current_profile": gui.current_profile,
    "loop_count": 0,
    "bases_attacked": 0,
    "bases_skipped": 0
})

# Connect GUI to state manager for web GUI integration
gui.state_manager = state_manager
gui._sync_state_to_manager()
state_manager.subscribe(gui._on_state_change)

# Register pause callback to update main.py's global paused variable
def on_pause_from_web(new_paused_state):
    """Called when web GUI toggles pause - updates main.py global."""
    global paused
    paused = new_paused_state
    print(f"[MAIN] Pause state updated from web GUI: {paused}")

gui.set_control_callback('pause', on_pause_from_web)
print("[MAIN] GUI connected to state manager for web sync")

# ============================================================
# VISUALIZATION OVERLAY HELPERS
# ============================================================
def overlay_clear():
    """Clear the overlay canvas if enabled."""
    if gui.overlay and gui.overlay_enabled:
        print("[OVERLAY] Clearing overlay")
        gui.overlay.clear()

def overlay_update():
    """Update/refresh the overlay display if enabled."""
    if gui.overlay and gui.overlay_enabled:
        print("[OVERLAY] Updating overlay")
        gui.overlay.update()

def overlay_draw_ocr(region, value, confidence, resource_type=''):
    """Draw an OCR region visualization if overlay is enabled."""
    if gui.overlay and gui.overlay_enabled:
        print(f"[OVERLAY] Drawing OCR: {resource_type} = {value} ({confidence}%)")
        gui.overlay.draw_ocr_region(region, str(value), confidence, resource_type)

def overlay_draw_detection(x, y, w, h, building_type, level, confidence, color):
    """Draw a building detection box if overlay is enabled."""
    if gui.overlay and gui.overlay_enabled:
        print(f"[OVERLAY] Drawing detection: {building_type} at ({x},{y})")
        gui.overlay.draw_detection(x, y, w, h, building_type, level, confidence, color)

def overlay_draw_side(side):
    """Draw the attack side indicator if overlay is enabled."""
    if gui.overlay and gui.overlay_enabled:
        print(f"[OVERLAY] Drawing attack side: {side}")
        gui.overlay.highlight_side(side, config.OVERLAY_COLORS.get('side_indicator', '#00FF00'))

def overlay_draw_spell_target(x, y, spell_name):
    """Draw a spell target crosshair if overlay is enabled."""
    if gui.overlay and gui.overlay_enabled:
        print(f"[OVERLAY] Drawing spell target: {spell_name} at ({x},{y})")
        gui.overlay.draw_crosshair(x, y, 25, config.OVERLAY_COLORS.get('spell_target', '#FF00FF'), spell_name)

def overlay_draw_deployment(x, y):
    """Draw a troop deployment position if overlay is enabled."""
    if gui.overlay and gui.overlay_enabled:
        print(f"[OVERLAY] Drawing deployment at ({x},{y})")
        gui.overlay.draw_circle(x, y, 8, config.OVERLAY_COLORS.get('deployment', '#FFFF00'))

def overlay_debug_status():
    """Print overlay status for debugging."""
    print(f"[OVERLAY DEBUG] gui.overlay exists: {gui.overlay is not None}")
    print(f"[OVERLAY DEBUG] gui.overlay_enabled: {gui.overlay_enabled}")
    if gui.overlay:
        print(f"[OVERLAY DEBUG] overlay.enabled: {gui.overlay.enabled}")

# Initialize Queue Manager (callbacks will be set later after functions are defined)
try:
    from queue_manager import QueueManager
    queue_manager = QueueManager(gui)
    print("[MAIN] Queue Manager initialized (callbacks pending)")

    # Start queue if enabled in settings
    settings = gui.get_settings()
    if settings.get('queue_enabled', False):
        queue_manager.start_queue()
except ImportError:
    queue_manager = None
    print("[MAIN] Queue Manager not available")
except Exception as e:
    queue_manager = None
    print(f"[MAIN] Failed to initialize Queue Manager: {e}")

# Helper functions
def send_discord_ocr_log(message):
    """
    Send an OCR read log to a dedicated Discord channel using a webhook URL.
    Set your webhook URL in DISCORD_OCR_WEBHOOK_URL in config.py.
    """
    import config
    webhook_url = getattr(config, 'DISCORD_OCR_WEBHOOK_URL', None)
    if not webhook_url:
        print("No Discord OCR webhook URL set in config.py (DISCORD_OCR_WEBHOOK_URL)")
        return
    # Format numbers in the message with dots as thousands separators
    import re
    def format_number(match):
        num = int(match.group(0))
        return f"{num:,}".replace(",", ".")
    formatted_message = re.sub(r"(?<![\w.])\d{4,}(?![\w.])", format_number, str(message))
    data = {"content": formatted_message}
    try:
        # Add 5-second timeout to prevent hanging
        response = requests.post(webhook_url, json=data, timeout=5)
        # Success is silent, only report failures
        if response.status_code != 204:
            print(f"[Discord OCR] Warning: Failed with status {response.status_code}")
    except Exception as e:
        print(f"[Discord OCR] Warning: {type(e).__name__} - {e}")
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

# human_like_move_click is now imported from humanized_input module
# This provides enhanced movement with overshoots, tremor, and variable acceleration


def click_in_square(coord):  # coord: (x1,y1,x2,y2)
    x1, y1, x2, y2 = coord
    rand_x = random.randint(x1, x2)
    rand_y = random.randint(y1, y2)
    human_like_move_click(rand_x, rand_y)


# random_sleep is now imported from humanized_input module
# This provides realistic timing distributions (lognormal/gamma) instead of uniform


def get_pixel_color(x, y):
    img = ImageGrab.grab()
    return img.getpixel((x, y))


def detect_air_defenses():
    """
    Detect air defense positions in the enemy base using template matching.
    Returns list of (x, y, level, confidence) tuples sorted by priority.
    """
    air_defenses = []
    
    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    
    # Check if templates directory exists
    if not os.path.exists(config.AIR_DEFENSE_TEMPLATES_DIR):
        print(f"Air defense templates directory not found: {config.AIR_DEFENSE_TEMPLATES_DIR}")
        send_discord_debug_log(f"Air defense templates directory not found: {config.AIR_DEFENSE_TEMPLATES_DIR}", "WARNING")
        return air_defenses
    
    print(f"Testing {len([f for f in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])} templates...")
    send_discord_debug_log(f"Testing {len([f for f in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])} air defense templates")
    
    # Load and match each template
    for template_file in os.listdir(config.AIR_DEFENSE_TEMPLATES_DIR):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(config.AIR_DEFENSE_TEMPLATES_DIR, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                print(f"Failed to load template: {template_file}")
                send_discord_debug_log(f"Failed to load air defense template: {template_file}", "WARNING")
                continue
                
            # Perform template matching
            result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= config.AIR_DEFENSE_DETECTION_THRESHOLD)
            
            # Extract level from filename (e.g., "air_defense_level_5.png" -> 5)
            level = 1  # default
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Add detected positions
            matches_found = 0
            for pt in zip(*locations[::-1]):  # Switch columns and rows
                x, y = pt
                # Convert to global coordinates
                global_x = x + config.BASE_VIEW_REGION[0]
                global_y = y + config.BASE_VIEW_REGION[1]
                
                # Get confidence score
                confidence = result[y, x]
                
                air_defenses.append((global_x, global_y, level, confidence))
                matches_found += 1
            
            if matches_found > 0:
                print(f"  {template_file}: {matches_found} matches (max conf: {np.max(result):.3f})")
                send_discord_debug_log(f"Air defense {template_file}: {matches_found} matches (max conf: {np.max(result):.3f})")
            else:
                max_conf = np.max(result)
                print(f"  {template_file}: No matches (max conf: {max_conf:.3f})")
    
    # Remove duplicates (positions too close to each other)
    filtered_defenses = []
    for defense in air_defenses:
        x, y, level, conf = defense
        is_duplicate = False
        for existing in filtered_defenses:
            ex, ey, _, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates (increased from 50)
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_defenses.append(defense)

    # Sort by priority (higher level = higher priority, then by confidence)
    filtered_defenses.sort(key=lambda x: (config.AIR_DEFENSE_PRIORITY.get(f'level_{x[2]}', 1), x[3]), reverse=True)

    # If more than max count detected, prioritize by confidence score
    if len(filtered_defenses) > config.AIR_DEFENSE_MAX_COUNT:
        print(f"Detected {len(filtered_defenses)} air defenses, targeting top {config.AIR_DEFENSE_MAX_COUNT} by confidence")
        send_discord_debug_log(f"Detected {len(filtered_defenses)} air defenses, targeting top {config.AIR_DEFENSE_MAX_COUNT} by confidence")
        # Re-sort by confidence score (highest first)
        filtered_defenses.sort(key=lambda x: x[3], reverse=True)

    send_discord_debug_log(f"Air defense detection completed: {len(filtered_defenses)} defenses found")

    # Draw air defense detections on overlay
    result = filtered_defenses[:config.AIR_DEFENSE_MAX_COUNT]
    for x, y, level, conf in result:
        overlay_draw_detection(x, y, 60, 60, "Air Defense", level, conf,
                               config.OVERLAY_COLORS.get('air_defense', '#FF4444'))

    return result


def load_achievement_building_templates():
    """
    Pre-load all achievement building templates into memory for faster detection.
    Called once at bot startup to avoid repeated disk I/O during attacks.

    Returns:
        dict: Template cache with structure {building_type: [(template_cv, filename), ...]}
    """
    global achievement_building_templates

    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot', 'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
    templates_loaded = 0

    print("[TEMPLATE CACHE] Loading achievement building templates...")

    for building_type in building_types:
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"[TEMPLATE CACHE] Warning: {building_type} templates directory not found")
            achievement_building_templates[building_type] = []
            continue

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"[TEMPLATE CACHE] No {building_type} templates found")
            achievement_building_templates[building_type] = []
            continue

        # Load all templates for this building type
        templates = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)

            if template is not None:
                templates.append((template, template_file))
                templates_loaded += 1

        achievement_building_templates[building_type] = templates
        print(f"[TEMPLATE CACHE] Loaded {len(templates)} {building_type.replace('_', ' ')} templates")

    print(f"[TEMPLATE CACHE] ✓ Template cache ready: {templates_loaded} total templates loaded")
    print(f"[TEMPLATE CACHE] Cache size: {sum(len(t) for t in achievement_building_templates.values())} templates")

    return achievement_building_templates

def detect_achievement_building(building_type):
    """
    Detect ALL achievement buildings (Eagle, Monolith, X-Bow, Inferno, Scattershot) using template matching.
    OPTIMIZED: Uses pre-loaded template cache instead of disk I/O (saves ~0.5-1s per scan).

    Args:
        building_type: Type of building ('eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot')

    Returns:
        List of (x, y, confidence) tuples for all detected buildings, or empty list if none found
    """
    global achievement_building_templates

    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # Use cached templates (or fall back to loading from disk if cache empty)
    if building_type in achievement_building_templates and achievement_building_templates[building_type]:
        templates_list = achievement_building_templates[building_type]
        print(f"Testing {len(templates_list)} {building_type.replace('_', ' ')} templates (cached)...")
        send_discord_debug_log(f"Testing {len(templates_list)} {building_type.replace('_', ' ')} templates (cached)")
    else:
        # Fallback: load from disk if cache not available
        print(f"[WARNING] Template cache miss for {building_type}, loading from disk...")
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"{building_type.replace('_', ' ').title()} templates directory not found: {templates_dir}")
            send_discord_debug_log(f"{building_type.replace('_', ' ').title()} templates directory not found: {templates_dir}", "WARNING")
            return []

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"No {building_type.replace('_', ' ')} templates found")
            return []

        # Load templates on-the-fly
        templates_list = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            if template is not None:
                templates_list.append((template, template_file))

    all_buildings = []

    # Match each template (now using cached templates)
    for template, template_name in templates_list:

        # Perform template matching (GPU if available, else CPU)
        result = gpu_match_template(base_cv, template)

        # Detection threshold lowered to 0.6 for visualization (0.7+ used for attacks)
        threshold = 0.6
        locations = np.where(result >= threshold)

        # Add all detected positions
        for pt in zip(*locations[::-1]):  # Switch columns and rows
            x, y = pt
            # Convert to global coordinates
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]

            # Get confidence score
            confidence = result[y, x]

            all_buildings.append((global_x, global_y, confidence))

    # Sort by confidence FIRST (so higher confidence detections get priority in duplicate filtering)
    all_buildings.sort(key=lambda x: x[2], reverse=True)

    # Remove duplicates (positions too close to each other) - higher confidence kept
    filtered_buildings = []
    for building in all_buildings:
        x, y, conf = building
        is_duplicate = False
        for existing in filtered_buildings:
            ex, ey, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_buildings.append(building)

    # Get actual template size for this building type
    box_w, box_h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))

    # Get building-specific threshold (default 0.7)
    high_threshold = config.ACHIEVEMENT_BUILDING_THRESHOLDS.get(building_type, 0.7)

    # Separate high confidence and low confidence buildings
    high_conf_buildings = [b for b in filtered_buildings if b[2] >= high_threshold]
    low_conf_buildings = [b for b in filtered_buildings if 0.6 <= b[2] < high_threshold]

    # Draw LOW confidence buildings in RED (for debugging threshold tuning)
    # Check if user wants to hide low confidence detections
    hide_low_conf = gui.get_settings().get('overlay_hide_low_conf', False) if gui else False
    if not hide_low_conf:
        for x, y, conf in low_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, f"{building_type.replace('_', ' ').title()} (LOW)", None, conf,
                                   config.OVERLAY_COLORS.get('achievement_low', '#FF0000'))

    # Draw HIGH confidence buildings in CYAN (these are used for attacks)
    if high_conf_buildings:
        print(f"{building_type.replace('_', ' ').title()}: {len(high_conf_buildings)} building(s) detected")
        for i, (x, y, conf) in enumerate(high_conf_buildings):
            print(f"  {i+1}. Position ({x}, {y}) - Confidence: {conf:.3f}")
            overlay_draw_detection(x, y, box_w, box_h, building_type.replace('_', ' ').title(), None, conf,
                                   config.OVERLAY_COLORS.get('achievement', '#00FFFF'))
        if low_conf_buildings:
            print(f"  + {len(low_conf_buildings)} low-confidence detections (0.6-{high_threshold}) shown in red")
        send_discord_debug_log(f"{building_type.replace('_', ' ').title()}: {len(high_conf_buildings)} detected")
    else:
        print(f"{building_type.replace('_', ' ').title()}: No buildings detected (>= {high_threshold})")
        if low_conf_buildings:
            print(f"  Note: {len(low_conf_buildings)} low-confidence detections (0.6-{high_threshold}) shown in red")
        send_discord_debug_log(f"{building_type.replace('_', ' ').title()}: No buildings detected")

    # Only return high confidence buildings for attack logic
    return high_conf_buildings


def detect_achievement_building_from_image(building_type, base_cv):
    """
    Detect achievement buildings from a pre-captured screenshot (for parallel processing).

    Args:
        building_type: Type of building to detect
        base_cv: Pre-captured base screenshot in OpenCV format

    Returns:
        List of (x, y, confidence) tuples for all detected buildings, or empty list if none found
    """
    global achievement_building_templates

    # Use cached templates (or fall back to loading from disk if cache empty)
    if building_type in achievement_building_templates and achievement_building_templates[building_type]:
        templates_list = achievement_building_templates[building_type]
        print(f"  [{building_type}] Testing {len(templates_list)} templates (cached)...")
    else:
        # Fallback: load from disk if cache not available
        print(f"  [{building_type}] WARNING: Template cache miss, loading from disk...")
        templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"

        if not os.path.exists(templates_dir):
            print(f"  [{building_type}] Templates directory not found: {templates_dir}")
            return []

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"  [{building_type}] No templates found")
            return []

        # Load templates on-the-fly
        templates_list = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            if template is not None:
                templates_list.append((template, template_file))

    all_buildings = []

    # Match each template
    for template, template_name in templates_list:
        # Perform template matching (GPU if available, else CPU)
        result = gpu_match_template(base_cv, template)

        # Detection threshold lowered to 0.6 for visualization (0.7+ used for attacks)
        threshold = 0.6
        locations = np.where(result >= threshold)

        # Add all detected positions
        for pt in zip(*locations[::-1]):
            x, y = pt
            # Convert to global coordinates
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]

            # Get confidence score
            confidence = result[y, x]

            all_buildings.append((global_x, global_y, confidence))

    # Sort by confidence FIRST (so higher confidence detections get priority in duplicate filtering)
    all_buildings.sort(key=lambda x: x[2], reverse=True)

    # Remove duplicates (positions too close to each other) - higher confidence kept
    filtered_buildings = []
    for building in all_buildings:
        x, y, conf = building
        is_duplicate = False
        for existing in filtered_buildings:
            ex, ey, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:  # 80 pixel threshold for duplicates
                is_duplicate = True
                break
        if not is_duplicate:
            filtered_buildings.append(building)

    # Get actual template size for this building type
    box_w, box_h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))

    # Get building-specific threshold (default 0.7)
    high_threshold = config.ACHIEVEMENT_BUILDING_THRESHOLDS.get(building_type, 0.7)

    # Separate high confidence and low confidence buildings
    high_conf_buildings = [b for b in filtered_buildings if b[2] >= high_threshold]
    low_conf_buildings = [b for b in filtered_buildings if 0.6 <= b[2] < high_threshold]

    # Draw LOW confidence buildings in RED (for debugging threshold tuning)
    # Check if user wants to hide low confidence detections
    hide_low_conf = gui.get_settings().get('overlay_hide_low_conf', False) if gui else False
    if not hide_low_conf:
        for x, y, conf in low_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, f"{building_type.replace('_', ' ').title()} (LOW)", None, conf,
                                   config.OVERLAY_COLORS.get('achievement_low', '#FF0000'))

    # Draw HIGH confidence buildings in CYAN (these are used for attacks)
    if high_conf_buildings:
        print(f"  [{building_type}] {len(high_conf_buildings)} building(s) detected")
        for x, y, conf in high_conf_buildings:
            overlay_draw_detection(x, y, box_w, box_h, building_type.replace('_', ' ').title(), None, conf,
                                   config.OVERLAY_COLORS.get('achievement', '#00FFFF'))
        if low_conf_buildings:
            print(f"  [{building_type}] + {len(low_conf_buildings)} low-confidence (0.6-{high_threshold}) shown in red")
    else:
        print(f"  [{building_type}] No buildings detected (>= {high_threshold})")
        if low_conf_buildings:
            print(f"  [{building_type}] Note: {len(low_conf_buildings)} low-confidence (0.6-{high_threshold}) shown in red")

    # Only return high confidence buildings for attack logic
    return high_conf_buildings


def find_building_clusters(buildings_with_types, max_distance=125):
    """
    Find clusters of buildings that are ALL close together (not chained).

    Uses COMPLETE LINKAGE: Every building in a cluster must be within max_distance
    of every other building in that cluster. This ensures spells can hit all buildings.

    Args:
        buildings_with_types: List of (x, y, confidence, building_type) tuples (top-left corners)
        max_distance: Maximum center-to-center distance between ANY two buildings in cluster (default: 125px)

    Returns:
        List of clusters, each cluster is a list of (x, y, confidence, building_type) tuples
    """
    if not buildings_with_types:
        return []

    def get_center(building):
        """Get center coordinates of a building using its actual template size."""
        x, y, _, building_type = building
        w, h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
        return (x + w // 2, y + h // 2)

    def distance_between(b1, b2):
        """Calculate center-to-center distance between two buildings."""
        c1 = get_center(b1)
        c2 = get_center(b2)
        return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5

    def all_within_distance(cluster, new_building):
        """Check if new_building is within max_distance of ALL buildings in cluster."""
        for existing in cluster:
            if distance_between(existing, new_building) > max_distance:
                return False
        return True

    # Find all pairs of buildings within max_distance
    clusters = []
    used = set()

    # Sort buildings by confidence (highest first) for better cluster seeds
    sorted_buildings = sorted(buildings_with_types, key=lambda b: b[2], reverse=True)

    for i, seed in enumerate(sorted_buildings):
        if i in used:
            continue

        # Start new cluster with this seed
        cluster = [seed]
        used.add(i)

        # Try to add other buildings that are within max_distance of ALL cluster members
        for j, candidate in enumerate(sorted_buildings):
            if j in used:
                continue

            if all_within_distance(cluster, candidate):
                cluster.append(candidate)
                used.add(j)

        clusters.append(cluster)

    # Sort clusters by size (largest first)
    clusters.sort(key=lambda c: len(c), reverse=True)

    return clusters


def get_cluster_center(cluster):
    """
    Calculate the center point of a cluster of buildings.

    Note: Detection coordinates are TOP-LEFT corners of bounding boxes.
    Uses actual template sizes for each building type for accurate centering.

    Args:
        cluster: List of (x, y, confidence, building_type) tuples (top-left corners)

    Returns:
        (center_x, center_y) tuple - the center point between all buildings
    """
    if not cluster:
        return None

    # Calculate center of each building using its actual template size
    centers = []
    for building in cluster:
        x, y, _, building_type = building
        w, h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
        centers.append((x + w // 2, y + h // 2))

    avg_x = sum(c[0] for c in centers) / len(centers)
    avg_y = sum(c[1] for c in centers) / len(centers)

    return (int(avg_x), int(avg_y))


def detect_town_hall():
    """
    Detect Town Hall level in the enemy base using template matching.
    Returns (x, y, level, confidence) tuple or None if not found.
    """
    # Capture the Town Hall region
    th_img = ImageGrab.grab(bbox=config.TOWN_HALL_REGION)
    th_cv = cv2.cvtColor(np.array(th_img), cv2.COLOR_RGB2BGR)
    
    # Check if templates directory exists
    if not os.path.exists(config.TOWN_HALL_TEMPLATES_DIR):
        print(f"Town Hall templates directory not found: {config.TOWN_HALL_TEMPLATES_DIR}")
        send_discord_debug_log(f"Town Hall templates directory not found: {config.TOWN_HALL_TEMPLATES_DIR}", "WARNING")
        return None
    
    best_match = None
    best_confidence = 0
    
    # Load and match each template
    for template_file in os.listdir(config.TOWN_HALL_TEMPLATES_DIR):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(config.TOWN_HALL_TEMPLATES_DIR, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                continue
                
            # Perform template matching
            result = cv2.matchTemplate(th_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # Extract level from filename (e.g., "town_hall_level_12.png" -> 12)
            level = 1  # default
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Check if this is the best match so far
            if max_val >= config.TOWN_HALL_DETECTION_THRESHOLD and max_val > best_confidence:
                x, y = max_loc
                # Convert to global coordinates
                global_x = x + config.TOWN_HALL_REGION[0]
                global_y = y + config.TOWN_HALL_REGION[1]
                
                best_match = (global_x, global_y, level, max_val)
                best_confidence = max_val
    
    if best_match:
        x, y, level, conf = best_match
        send_discord_debug_log(f"Town Hall Level {level} detected at ({x}, {y}) with confidence {conf:.3f}")
        # Draw town hall detection on overlay (100x100 bounding box for TH)
        overlay_draw_detection(x, y, 100, 100, "Town Hall", level, conf,
                               config.OVERLAY_COLORS.get('town_hall', '#AA00FF'))
    else:
        send_discord_debug_log("No Town Hall detected", "WARNING")

    return best_match


def detect_army_button():
    """
    Detect the army button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Capture the search region
    screen_img = ImageGrab.grab(bbox=config.ARMY_BUTTON_SEARCH_REGION)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    if not os.path.exists(config.ARMY_BUTTON_TEMPLATE_DIR):
        print(f"Army button templates directory not found: {config.ARMY_BUTTON_TEMPLATE_DIR}")
        send_discord_debug_log(f"Army button templates directory not found: {config.ARMY_BUTTON_TEMPLATE_DIR}", "WARNING")
        return None

    # Load the army button template
    template_path = os.path.join(config.ARMY_BUTTON_TEMPLATE_DIR, "army_button.png")
    if not os.path.exists(template_path):
        print(f"Army button template not found: {template_path}")
        send_discord_debug_log(f"Army button template not found: {template_path}", "WARNING")
        return None

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load army button template: {template_path}")
        send_discord_debug_log(f"Failed to load army button template: {template_path}", "WARNING")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= config.ARMY_BUTTON_DETECTION_THRESHOLD:
        # Calculate center of the button
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + config.ARMY_BUTTON_SEARCH_REGION[0]
        center_y = max_loc[1] + template_height // 2 + config.ARMY_BUTTON_SEARCH_REGION[1]

        print(f"Army button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"Army button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"Army button not detected (best match confidence: {max_val:.2f})")
        send_discord_debug_log(f"Army button not detected (best match confidence: {max_val:.2f})", "WARNING")
        return None


def detect_surrender_button():
    """
    Detect the surrender button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Full screen search
    screen_img = ImageGrab.grab()
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    surrender_template_dir = "screenshots/reference/attack/"
    if not os.path.exists(surrender_template_dir):
        print(f"Surrender button templates directory not found: {surrender_template_dir}")
        send_discord_debug_log(f"Surrender button templates directory not found: {surrender_template_dir}", "WARNING")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get('surrender')
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(surrender_template_dir, "surrender.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load surrender button template: {template_path}")
        send_discord_debug_log(f"Failed to load surrender button template: {template_path}", "WARNING")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.65:  # 65% confidence threshold (lowered for better detection)
        # Calculate center of the button
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2
        center_y = max_loc[1] + template_height // 2

        print(f"Surrender button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"Surrender button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"Surrender button not detected (best match confidence: {max_val:.2f})")
        send_discord_debug_log(f"Surrender button not detected (best match confidence: {max_val:.2f})", "WARNING")
        return None


def wait_for_attack_screen_ready(timeout=10):
    """
    Wait for attack screen to be ready by detecting the End Battle button.
    Checks every 0.1 seconds until button is detected or timeout is reached.

    Args:
        timeout: Maximum time to wait in seconds (default: 10)

    Returns:
        True if attack screen is ready, False if timeout reached
    """
    print(f"[ATTACK SCREEN] Waiting for End Battle button (timeout: {timeout}s)...")
    send_discord_debug_log(f"Waiting for attack screen ready (End Battle detection, timeout={timeout}s)")

    start_time = time.time()
    check_count = 0

    while time.time() - start_time < timeout:
        check_count += 1

        # Capture screen
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load End Battle template
        template_path = "screenshots/reference/attack/end_battle.png"
        if not os.path.exists(template_path):
            print(f"[ATTACK SCREEN] End Battle template not found: {template_path}")
            send_discord_debug_log(f"End Battle template not found: {template_path}", "ERROR")
            return False

        template = cv2.imread(template_path)
        if template is None:
            print(f"[ATTACK SCREEN] Failed to load End Battle template: {template_path}")
            send_discord_debug_log(f"Failed to load End Battle template: {template_path}", "ERROR")
            return False

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            elapsed = time.time() - start_time
            print(f"[ATTACK SCREEN] End Battle button detected! (confidence: {max_val:.2f}, checks: {check_count}, time: {elapsed:.2f}s)")
            send_discord_debug_log(f"Attack screen ready - End Battle detected (conf={max_val:.2f}, {check_count} checks, {elapsed:.2f}s)")
            return True

        # Wait 0.1 seconds before next check
        time.sleep(0.1)

    # Timeout reached
    elapsed = time.time() - start_time
    print(f"[ATTACK SCREEN] TIMEOUT after {elapsed:.2f}s and {check_count} checks (best confidence: {max_val:.2f})")
    send_discord_debug_log(f"Attack screen timeout - End Battle not detected ({check_count} checks, best conf={max_val:.2f})", "WARNING")
    return False


def detect_star_bonus_screen():
    """
    Detect the star bonus screen using template matching.
    Searches in the top-middle portion of the screen.
    Returns True if star bonus screen detected, False otherwise.
    """
    # Check if templates directory exists
    star_bonus_template_dir = "screenshots/reference/attack/"
    if not os.path.exists(star_bonus_template_dir):
        print(f"Star bonus templates directory not found: {star_bonus_template_dir}")
        return False

    # Load the star bonus template
    template_path = os.path.join(star_bonus_template_dir, "home_star_bonus.png")
    if not os.path.exists(template_path):
        print(f"Star bonus template not found: {template_path}")
        return False

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load star bonus template: {template_path}")
        return False

    # Get template dimensions
    template_height, template_width = template.shape[:2]
    print(f"[SBARB FARM] Star bonus template size: {template_width}x{template_height}")

    # Define search region (top-middle portion of screen)
    # Make sure region is larger than template
    star_bonus_region = (600, 50, 1900, 700)

    # Capture the search region
    screen_img = ImageGrab.grab(bbox=star_bonus_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Get search region dimensions
    region_height, region_width = screen_cv.shape[:2]
    print(f"[SBARB FARM] Search region size: {region_width}x{region_height}")

    # Verify template is smaller than search region
    if template_width > region_width or template_height > region_height:
        print(f"[SBARB FARM] Template ({template_width}x{template_height}) is larger than search region ({region_width}x{region_height}), using full screen")
        # Fall back to full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Perform template matching
    try:
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.70:  # 70% confidence threshold
            print(f"Star bonus screen detected with confidence {max_val:.2f}")
            send_discord_debug_log(f"Star bonus screen detected (confidence: {max_val:.2f})")
            return True
        else:
            print(f"Star bonus screen not detected (best match confidence: {max_val:.2f})")
            return False
    except cv2.error as e:
        print(f"[SBARB FARM] Error during template matching: {e}")
        send_discord_debug_log(f"SBarb Farm: Star bonus detection error - {e}", "WARNING")
        return False


def detect_two_stars():
    """
    Detect 2 stars on screen during Builder Base attack using template matching.
    Returns True if 2 stars detected, False otherwise.
    Searches bottom-right region of screen where stars appear.
    """
    # Search bottom-right region where stars appear
    search_region = (1500, 1000, 2560, 1440)  # Bottom-right corner
    screen_img = ImageGrab.grab(bbox=search_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    stars_template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(stars_template_dir):
        print(f"2 stars templates directory not found: {stars_template_dir}")
        send_discord_debug_log(f"2 stars templates directory not found: {stars_template_dir}", "WARNING")
        return False

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get('2_stars')
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(stars_template_dir, "2_stars.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load 2 stars template: {template_path}")
        send_discord_debug_log(f"Failed to load 2 stars template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.85:  # 85% confidence threshold (higher to avoid false positives)
        print(f"2 stars detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"2 stars detected with confidence {max_val:.2f}")
        return True
    else:
        return False


def detect_three_stars():
    """
    Detect 3 stars on screen during Builder Base attack using template matching.
    Returns True if 3 stars detected, False otherwise.
    Searches bottom-right region of screen where stars appear.
    This happens when Builder Hall is destroyed last (goes from 1 star to 3 stars directly).
    """
    # Search bottom-right region where stars appear
    search_region = (1500, 1000, 2560, 1440)  # Bottom-right corner
    screen_img = ImageGrab.grab(bbox=search_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    stars_template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(stars_template_dir):
        print(f"3 stars templates directory not found: {stars_template_dir}")
        send_discord_debug_log(f"3 stars templates directory not found: {stars_template_dir}", "WARNING")
        return False

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get('3_stars')
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(stars_template_dir, "3_stars.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load 3 stars template: {template_path}")
        send_discord_debug_log(f"Failed to load 3 stars template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.85:  # 70% confidence threshold
        print(f"3 stars detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"3 stars detected with confidence {max_val:.2f}")
        return True
    else:
        return False


def detect_star_bonus():
    """
    Detect star bonus screen in Builder Base using template matching.
    Returns True if star bonus screen detected, False otherwise.
    Searches center region of screen where the bonus screen appears.
    """
    # Search center region where star bonus screen appears (it's quite big)
    screen_img = ImageGrab.grab()  # Full screen capture
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(template_dir):
        print(f"Star bonus templates directory not found: {template_dir}")
        send_discord_debug_log(f"Star bonus templates directory not found: {template_dir}", "WARNING")
        return False

    # Load the star bonus template
    template_path = os.path.join(template_dir, "star_bonus.png")
    if not os.path.exists(template_path):
        print(f"Star bonus template not found: {template_path}")
        send_discord_debug_log(f"Star bonus template not found: {template_path}", "WARNING")
        return False

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load star bonus template: {template_path}")
        send_discord_debug_log(f"Failed to load star bonus template: {template_path}", "WARNING")
        return False

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        print(f"Star bonus screen detected with confidence {max_val:.2f}")
        send_discord_debug_log(f"Star bonus screen detected with confidence {max_val:.2f}")
        return True
    else:
        return False


# ============================================================================
# BB GOLD TEMPLATE CACHING
# ============================================================================

def load_bb_gold_templates():
    """
    Pre-load all BB Gold templates into memory to eliminate disk I/O during attacks.
    Called once at bot startup. Provides 20-40% speedup by caching frequently used templates.
    """
    global _bb_gold_template_cache

    templates = {
        '2_stars': 'screenshots/reference/builder_base/2_stars.png',
        '3_stars': 'screenshots/reference/builder_base/3_stars.png',
        'surrender': 'screenshots/reference/attack/surrender.png',  # Fixed: attack/ not builder_base/
        'end_battle': 'screenshots/reference/attack/end_battle.png',
        'return_home': 'screenshots/reference/builder_base/return_home.png',
        'army_button': 'screenshots/reference/reinforcements/army_button.png',
        'connection_lost': 'screenshots/reference/general/connection_lost.png',
        'try_again': 'screenshots/reference/general/try_again.png'
    }

    for name, path in templates.items():
        if os.path.exists(path):
            template = cv2.imread(path)
            if template is not None:
                _bb_gold_template_cache[name] = template
                print(f"[CACHE] Loaded BB Gold template: {name}")
        else:
            print(f"[CACHE] Warning: Template not found: {path}")

    print(f"[CACHE] BB Gold templates loaded: {len(_bb_gold_template_cache)}/8")


# ============================================================================
# BB GOLD STATE MACHINE - STATE DETECTION FUNCTIONS
# ============================================================================

def detect_in_base_state():
    """
    Detect if bot is at home base using army_button.png template matching.

    Returns:
        bool: True if army button detected (in base), False otherwise

    Template: screenshots/reference/reinforcements/army_button.png
    Region: Full screen (config.ARMY_BUTTON_SEARCH_REGION)
    Threshold: 0.8 (config.ARMY_BUTTON_DETECTION_THRESHOLD)
    """
    try:
        # Use full screen if region not specified
        search_region = getattr(config, 'ARMY_BUTTON_SEARCH_REGION', None)
        if search_region:
            screenshot = ImageGrab.grab(bbox=search_region)
        else:
            screenshot = ImageGrab.grab()  # Full screen

        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Load from cache (or fallback to disk)
        template = _bb_gold_template_cache.get('army_button')
        if template is None:
            # Cache miss - load from disk as fallback
            template_dir = getattr(config, 'ARMY_BUTTON_TEMPLATE_DIR', 'screenshots/reference/reinforcements')
            template_path = os.path.join(template_dir, "army_button.png")
            if os.path.exists(template_path):
                template = cv2.imread(template_path)

        if template is None:
            return False

        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        threshold = getattr(config, 'ARMY_BUTTON_DETECTION_THRESHOLD', 0.8)
        detected = max_val >= threshold

        if detected:
            print(f"[BASE DETECT] Army button detected (confidence: {max_val:.2f})")

        return detected

    except Exception as e:
        print(f"[BASE DETECT] Error detecting base: {e}")
        return False


# ============================================================================
# CONNECTION LOST DETECTION AND RECOVERY
# ============================================================================

# Global flag to track if connection monitor is running
_connection_monitor_running = False
_connection_monitor_paused = False

def detect_connection_lost():
    """
    Detect if "Connection lost" popup is showing using template matching.
    First detects the popup, then finds the "TRY AGAIN" button.

    Returns:
        tuple: (x, y) coordinates of "TRY AGAIN" button center if found, None otherwise

    Templates:
        - screenshots/reference/general/connection_lost.png (popup detection)
        - screenshots/reference/general/try_again.png (button detection)
    """
    try:
        screenshot = ImageGrab.grab()
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Step 1: Detect the connection lost popup
        popup_template = _bb_gold_template_cache.get('connection_lost')
        if popup_template is None:
            template_path = 'screenshots/reference/general/connection_lost.png'
            if os.path.exists(template_path):
                popup_template = cv2.imread(template_path)

        if popup_template is None:
            return None

        result = cv2.matchTemplate(screenshot_cv, popup_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        threshold = 0.75  # 75% confidence threshold
        if max_val < threshold:
            return None  # Popup not found

        print(f"[CONNECTION] Connection lost popup detected (confidence: {max_val:.2f})")

        # Step 2: Find the "TRY AGAIN" button using template matching
        try_again_template = _bb_gold_template_cache.get('try_again')
        if try_again_template is None:
            template_path = 'screenshots/reference/general/try_again.png'
            if os.path.exists(template_path):
                try_again_template = cv2.imread(template_path)

        if try_again_template is None:
            print("[CONNECTION] Warning: try_again.png template not found, using fallback position")
            # Fallback: estimate position based on popup location
            popup_height = popup_template.shape[0]
            return (max_loc[0] + 60, max_loc[1] + popup_height - 20)

        # Search for TRY AGAIN button on the full screen
        btn_result = cv2.matchTemplate(screenshot_cv, try_again_template, cv2.TM_CCOEFF_NORMED)
        btn_min_val, btn_max_val, btn_min_loc, btn_max_loc = cv2.minMaxLoc(btn_result)

        if btn_max_val >= 0.7:  # 70% threshold for button
            # Calculate center of the button
            btn_height, btn_width = try_again_template.shape[:2]
            try_again_x = btn_max_loc[0] + btn_width // 2
            try_again_y = btn_max_loc[1] + btn_height // 2

            print(f"[CONNECTION] TRY AGAIN button found at ({try_again_x}, {try_again_y}) (confidence: {btn_max_val:.2f})")
            return (try_again_x, try_again_y)
        else:
            print(f"[CONNECTION] TRY AGAIN button not found (best: {btn_max_val:.2f}), using fallback")
            # Fallback position
            popup_height = popup_template.shape[0]
            return (max_loc[0] + 60, max_loc[1] + popup_height - 20)

    except Exception as e:
        print(f"[CONNECTION] Error detecting connection lost: {e}")
        return None


def handle_connection_lost():
    """
    Handle connection lost by clicking "TRY AGAIN" and waiting for reconnection.
    After reconnect, detects current screen state.

    Returns:
        bool: True if reconnection successful, False otherwise
    """
    global _connection_monitor_paused

    try_again_pos = detect_connection_lost()
    if try_again_pos is None:
        return False

    # Pause the monitor while handling reconnection
    _connection_monitor_paused = True

    print("[CONNECTION] *** CONNECTION LOST - Attempting reconnect ***")
    gui.log_message("Connection lost! Clicking Try Again...")
    send_discord_debug_log("Connection lost detected - attempting reconnect", "WARNING")

    # Click "TRY AGAIN" button
    fast_click(try_again_pos[0], try_again_pos[1])
    time.sleep(2)  # Wait for reconnection attempt

    # Wait for reconnection (check if popup disappears and base loads)
    max_wait = 30  # seconds
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Check if still showing connection lost
        if detect_connection_lost() is not None:
            # Still showing popup - click again
            print("[CONNECTION] Still disconnected, clicking Try Again...")
            fast_click(try_again_pos[0], try_again_pos[1])
            time.sleep(3)
            continue

        # Popup gone - wait a moment for screen to settle
        time.sleep(1)

        # Try to detect where we are
        if detect_in_base_state():
            print("[CONNECTION] ✓ Reconnected - at home base")
            gui.log_message("Reconnected successfully - at home base")
            send_discord_debug_log("Reconnected successfully - at home base", "INFO")
            _connection_monitor_paused = False
            return True

        # Could be in attack screen or elsewhere - just continue
        print("[CONNECTION] ✓ Reconnected - determining screen state...")
        gui.log_message("Reconnected - screen state unknown, continuing...")
        send_discord_debug_log("Reconnected - screen state unknown", "INFO")
        _connection_monitor_paused = False
        return True

    print("[CONNECTION] ✗ Failed to reconnect after 30 seconds")
    gui.log_message("Failed to reconnect after 30 seconds")
    send_discord_debug_log("Failed to reconnect after 30 seconds", "ERROR")
    _connection_monitor_paused = False
    return False


def connection_monitor_loop():
    """
    Background thread that checks for connection lost every 5 seconds.
    Runs continuously while the bot is active.
    """
    global _connection_monitor_running, _connection_monitor_paused

    print("[CONNECTION MONITOR] Started - checking every 5 seconds")

    while _connection_monitor_running:
        try:
            # Skip check if paused or handling reconnection
            if not _connection_monitor_paused:
                try_again_pos = detect_connection_lost()
                if try_again_pos is not None:
                    handle_connection_lost()

            # Wait 5 seconds before next check
            time.sleep(5)

        except Exception as e:
            print(f"[CONNECTION MONITOR] Error: {e}")
            time.sleep(5)

    print("[CONNECTION MONITOR] Stopped")


def start_connection_monitor():
    """Start the connection monitor background thread."""
    global _connection_monitor_running

    if _connection_monitor_running:
        print("[CONNECTION MONITOR] Already running")
        return

    _connection_monitor_running = True
    monitor_thread = threading.Thread(target=connection_monitor_loop, daemon=True)
    monitor_thread.start()
    print("[CONNECTION MONITOR] Thread started")


def stop_connection_monitor():
    """Stop the connection monitor background thread."""
    global _connection_monitor_running
    _connection_monitor_running = False
    print("[CONNECTION MONITOR] Stop requested")


def wait_for_base_screen(timeout=15):
    """
    Wait for home base screen to load using army_button.png template matching.
    Used after returning home to ensure base is fully loaded before OCR.

    Args:
        timeout: Maximum wait time in seconds (default 15)

    Returns:
        bool: True if base detected within timeout, False otherwise
    """
    print(f"[BASE DETECT] Waiting for base screen (timeout: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if detect_in_base_state():
            elapsed = time.time() - start_time
            print(f"[BASE DETECT] ✓ Base screen loaded ({elapsed:.1f}s)")
            return True
        time.sleep(0.3)

    print(f"[BASE DETECT] ✗ Timeout - base not detected after {timeout}s")
    return False


def detect_battle_active_state():
    """
    Detect if battle is currently active (troops deployed, not yet ended).
    Battle is active if:
    - Surrender button IS visible (attack started)
    - End battle button NOT visible (battle hasn't ended)
    - Star bonus NOT visible (battle hasn't ended)

    Returns:
        bool: True if battle active, False otherwise
    """
    try:
        surrender_visible = detect_surrender_button() is not None
        end_battle_visible = detect_end_battle_button() is not None
        star_bonus_visible = detect_star_bonus()

        # Battle active = surrender exists but end screens don't
        is_active = surrender_visible and not end_battle_visible and not star_bonus_visible

        if is_active:
            print("[BB STATE] BATTLE_ACTIVE confirmed (surrender visible, no end screens)")

        return is_active

    except Exception as e:
        print(f"[BB STATE] Error detecting BATTLE_ACTIVE: {e}")
        return False


def detect_end_screen_state():
    """
    Detect if battle ended and end screen is displayed (post-battle screen with resources).
    End screen indicators:
    - Return home button visible (primary indicator), OR
    - Battle UI elements are GONE (no surrender button, no end_battle button) as fallback

    NOTE: This detects the post-battle screen AFTER clicking surrender/end battle,
    showing the resources earned screen with the return home button.

    Returns:
        dict: {'detected': bool, 'stars': int, 'star_bonus': bool, 'return_button_visible': bool}
                stars = 0/1/2/3, star_bonus = True if bonus screen present
    """
    try:
        result = {
            'detected': False,
            'stars': 0,
            'star_bonus': False,
            'return_button_visible': False,
            'return_button_pos': None
        }

        # Primary indicator: Return home button (appears on post-battle screen)
        return_button = detect_return_home_button()
        if return_button:
            result['detected'] = True
            result['return_button_visible'] = True
            result['return_button_pos'] = return_button
            print(f"[BB STATE] END_SCREEN confirmed (return home button at {return_button})")

        # Fallback: Check if battle UI elements are gone (if template doesn't exist yet)
        if not result['detected']:
            surrender_visible = detect_surrender_button() is not None
            end_battle_visible = detect_end_battle_button() is not None

            # If battle UI is gone, we're likely at end screen
            if not surrender_visible and not end_battle_visible:
                result['detected'] = True
                print("[BB STATE] END_SCREEN confirmed (battle UI elements gone - fallback method)")

        # Check for star bonus (appears AFTER end screen when user clicks through)
        if detect_star_bonus():
            result['star_bonus'] = True
            print("[BB STATE] END_SCREEN: Star bonus visible")

        # Check star count (may still be visible on end screen)
        if detect_three_stars():
            result['stars'] = 3
            print("[BB STATE] END_SCREEN: 3 stars detected")
        elif detect_two_stars():
            result['stars'] = 2
            print("[BB STATE] END_SCREEN: 2 stars detected")

        return result

    except Exception as e:
        print(f"[BB STATE] Error detecting END_SCREEN: {e}")
        return {'detected': False, 'stars': 0, 'star_bonus': False, 'return_button_visible': False}


def detect_ghost_attack():
    """
    Detect ghost attack state - search initiated but no base loaded.
    Ghost attack occurs when:
    - Not in base (army button NOT visible)
    - Not in attack ready (no "Attacker" text)
    - Not in battle (no surrender button)
    - Not at end screen (no end battle button)

    Returns:
        bool: True if ghost attack detected, False otherwise
    """
    try:
        in_base = detect_in_base_state()
        attack_ready = check_bb_attacker_text()
        surrender_exists = detect_surrender_button() is not None
        end_button_exists = detect_end_battle_button() is not None

        # Ghost = not in any known valid state
        is_ghost = not (in_base or attack_ready or surrender_exists or end_button_exists)

        if is_ghost:
            print("[BB STATE] GHOST ATTACK detected (no valid state indicators)")
            send_discord_debug_log("BB Gold: Ghost attack detected - no valid state", "WARNING")

        return is_ghost

    except Exception as e:
        print(f"[BB STATE] Error detecting ghost attack: {e}")
        return False


def detect_bb_confirm_button():
    """
    Detect the green confirmation button in Builder Base surrender dialog.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    Searches only in center dialog area to avoid matching other buttons.
    """
    # Search only in center region where dialog appears (avoid bottom corners with other buttons)
    # Dialog appears roughly in center: X=640-1920, Y=600-1000
    search_region = (640, 600, 1920, 1000)
    screen_img = ImageGrab.grab(bbox=search_region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(template_dir):
        print(f"BB confirm button templates directory not found: {template_dir}")
        send_discord_debug_log(f"BB confirm button templates directory not found: {template_dir}", "WARNING")
        return None

    # Load the confirm button template
    template_path = os.path.join(template_dir, "confirm.png")
    if not os.path.exists(template_path):
        print(f"BB confirm button template not found: {template_path}")
        send_discord_debug_log(f"BB confirm button template not found: {template_path}", "WARNING")
        return None

    template = cv2.imread(template_path)
    if template is None:
        print(f"Failed to load BB confirm button template: {template_path}")
        send_discord_debug_log(f"Failed to load BB confirm button template: {template_path}", "WARNING")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.75:  # 75% confidence threshold (higher to avoid false positives)
        # Calculate center of the button (convert to global coordinates)
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + search_region[0]
        center_y = max_loc[1] + template_height // 2 + search_region[1]

        # Additional sanity check: confirm button should be in center area, not at bottom corners
        if center_y > 1100:  # Too low on screen (near return button at y=1225)
            print(f"BB confirm button rejected - too low on screen (y={center_y}), likely matched wrong button")
            send_discord_debug_log(f"BB confirm rejected - matched button at y={center_y} (too low)", "WARNING")
            return None

        print(f"BB confirm button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"BB confirm button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"BB confirm button not detected (best match confidence: {max_val:.2f})")
        return None


def detect_return_home_button(quiet=False):
    """
    Detect return home button on post-battle screen using template matching.
    This button appears after battle ends (on the screen showing resources earned).

    Args:
        quiet (bool): If True, suppress "not detected" log messages (useful for continuous monitoring)

    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Search in bottom-center area where return home button appears
    # Button location: X=1070-1496, Y=1116-1328
    region = (1000, 1050, 1550, 1400)
    screen_img = ImageGrab.grab(bbox=region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/builder_base/"
    if not os.path.exists(template_dir):
        print(f"Return home button templates directory not found: {template_dir}")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get('return_home')
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(template_dir, "return_home.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"[BB STATE] Failed to load return home button template: {template_path}")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        # Calculate center of the button (convert to global coordinates)
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + region[0]
        center_y = max_loc[1] + template_height // 2 + region[1]

        print(f"[BB STATE] ✓ Return home button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        if not quiet:
            print(f"[BB STATE] ✗ Return home button not detected (best match: {max_val:.2f}, threshold: 0.70)")
        return None


def detect_end_battle_button():
    """
    Detect end battle button on screen using template matching.
    Returns (x, y) coordinates of the button center if found, None otherwise.
    """
    # Search in bottom-left area where end_battle button appears
    region = (0, 1000, 600, 1440)
    screen_img = ImageGrab.grab(bbox=region)
    screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

    # Check if templates directory exists
    template_dir = "screenshots/reference/attack/"
    if not os.path.exists(template_dir):
        print(f"End battle button templates directory not found: {template_dir}")
        return None

    # Load from cache (or fallback to disk)
    template = _bb_gold_template_cache.get('end_battle')
    if template is None:
        # Cache miss - load from disk as fallback
        template_path = os.path.join(template_dir, "end_battle.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path)

    if template is None:
        print(f"Failed to load end battle button template: {template_path}")
        return None

    # Perform template matching
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if max_val >= 0.7:  # 70% confidence threshold
        # Calculate center of the button (convert to global coordinates)
        template_height, template_width = template.shape[:2]
        center_x = max_loc[0] + template_width // 2 + region[0]
        center_y = max_loc[1] + template_height // 2 + region[1]

        print(f"End battle button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        send_discord_debug_log(f"End battle button detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"End battle button not detected (best match confidence: {max_val:.2f})")
        return None


def detect_surrender_or_end_battle():
    """
    Detect either surrender button OR end battle button on screen.
    Returns tuple (button_type, x, y) where button_type is 'surrender' or 'end_battle',
    or (None, None, None) if neither found.
    """
    # First try to detect surrender button
    surrender_pos = detect_surrender_button()
    if surrender_pos:
        return ('surrender', surrender_pos[0], surrender_pos[1])

    # If surrender not found, try end battle button
    end_battle_pos = detect_end_battle_button()
    if end_battle_pos:
        return ('end_battle', end_battle_pos[0], end_battle_pos[1])

    # Neither found
    return (None, None, None)


def detect_current_game_state():
    """
    Detect current game state when uncertain (for error recovery and fallback handling).

    Returns:
        str: One of 'in_base', 'battle_active', 'end_screen', 'unknown'

    Detection order:
    1. Check if at base (army button visible)
    2. Check if at end screen (return home button visible)
    3. Check if in active battle (surrender button visible)
    4. Unknown state if none match
    """
    print("[STATE DETECT] Attempting to detect current game state...")

    # 1. Check if we're at base
    if detect_in_base_state():
        print("[STATE DETECT] ✓ Detected: IN_BASE (army button visible)")
        return 'in_base'

    # 2. Check if we're at end screen
    if detect_return_home_button():
        print("[STATE DETECT] ✓ Detected: END_SCREEN (return home button visible)")
        return 'end_screen'

    # 3. Check if we're in active battle
    button_type, x, y = detect_surrender_or_end_battle()
    if button_type == 'surrender':
        print("[STATE DETECT] ✓ Detected: BATTLE_ACTIVE (surrender button visible)")
        return 'battle_active'
    elif button_type == 'end_battle':
        print("[STATE DETECT] ✓ Detected: BATTLE_ENDING (end battle button visible)")
        return 'battle_ending'

    # 4. Unknown state
    print("[STATE DETECT] ✗ Could not determine state (no recognizable UI elements)")
    return 'unknown'


def calculate_deployment_step(troop_count, coord_count):
    """
    Calculate optimal step size for even troop distribution across coordinates.

    Args:
        troop_count: Number of troops to deploy
        coord_count: Number of available deployment coordinates

    Returns:
        Step size (int) - how many coordinates to skip between deployments
    """
    if troop_count == 0 or coord_count == 0:
        return 1

    # Calculate raw step based on troop density
    raw_step = coord_count // troop_count

    # Clamp between 1 and 10 for balance of coverage vs speed
    # - step=1: use every coordinate (dense, slower)
    # - step=10: skip 10 coords each (sparse, faster)
    step = max(1, min(raw_step, 10))

    return step


def get_opposite_side(side):
    """Get the opposite side for camera movement"""
    opposite_map = {
        'left': 'right',
        'right': 'left',
        'up': 'down',
        'down': 'up'
    }
    return opposite_map.get(side, 'right')  # Default to right if unknown


def move_camera_to_opposite_side(current_side, fast_mode=False):
    """Move camera to the opposite side of the base"""
    opposite_side = get_opposite_side(current_side)

    print(f"Moving camera from {current_side} to {opposite_side}")
    send_discord_debug_log(f"Moving camera from {current_side} to {opposite_side}")

    # Define camera drag directions
    # Drag from center outward in the direction we want to move
    center_x, center_y = 1280, 720  # Screen center (adjust if needed)
    drag_distance = 800  # pixels to drag - increased for more reliable camera movement

    if opposite_side == 'left':
        # Drag from center to right (moves camera left)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x + drag_distance, center_y
    elif opposite_side == 'right':
        # Drag from center to left (moves camera right)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x - drag_distance, center_y
    elif opposite_side == 'up':
        # Drag from center down (moves camera up)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x, center_y + drag_distance
    elif opposite_side == 'down':
        # Drag from center up (moves camera down)
        start_x, start_y = center_x, center_y
        end_x, end_y = center_x, center_y - drag_distance

    # Perform the drag
    pyautogui.moveTo(start_x, start_y)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.1)
    pyautogui.moveTo(end_x, end_y, duration=0.5)  # Slower drag for more reliable movement
    time.sleep(0.1)
    pyautogui.mouseUp()

    # Fast mode for SGoblin Farm - minimal delay
    if fast_mode:
        pass  # time.sleep(0.3)  # COMMENTED OUT - no delay for maximum speed
    else:
        time.sleep(0.5)  # Wait for camera to settle

    print(f"Camera moved to {opposite_side}")
    send_discord_debug_log(f"Camera moved to {opposite_side}")


def get_lightning_spell_targets(air_defenses):
    """
    Get air defense positions for lightning spell targeting.
    Returns list of (x, y) coordinates sorted by priority (highest level first).
    """
    if not air_defenses:
        return []
    
    # Sort by level (highest first) and return positions
    sorted_defenses = sorted(air_defenses, key=lambda x: x[2], reverse=True)
    return [(x, y) for x, y, _, _ in sorted_defenses]


def thin_digits(img):
    """
    Thin bold/thick digits using morphological erosion (OpenCV).
    """
    try:
        import cv2
        img_np = np.array(img)
        kernel = np.ones((2, 2), np.uint8)
        eroded = cv2.erode(img_np, kernel, iterations=1)
        return Image.fromarray(eroded)
    except ImportError:
        return img  # Fallback: return original if OpenCV not available


def ocr_resources(region, debug=False):
    """
    OCR a single resource region with preprocessing and return integer value,
    correctly handling spaced digits and ensuring minimum length.
    Uses adaptive thresholding and erosion for best results on mixed backgrounds.
    If debug=True, shows the processed image and prints the raw OCR result.
    """
    img = ImageGrab.grab(bbox=region).convert('L')
    try:
        import cv2
        img_np = np.array(img)
        # Adaptive thresholding for variable backgrounds
        bin_img = cv2.adaptiveThreshold(
            img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        # Erode to thin digits
        kernel = np.ones((2, 2), np.uint8)
        bin_img = cv2.erode(bin_img, kernel, iterations=1)
        bin_img = Image.fromarray(bin_img)
    except ImportError:
        # Fallback: simple threshold and no erosion
        thresh = 200
        img_array = np.array(img)
        bin_img = Image.fromarray(np.where(img_array > thresh, 255, 0).astype(np.uint8))

    text = pytesseract.image_to_string(bin_img, config='--psm 7 -c tessedit_char_whitelist=0123456789')
    if debug:
        bin_img.show(title="Processed OCR Image")
        print(f"Raw OCR result: '{text}'")
    cleaned = ''.join(ch for ch in text if ch.isdigit())
    if len(cleaned) < 3:
        raw_text = pytesseract.image_to_string(img, config='--psm 7 digits')
        cleaned = ''.join(ch for ch in raw_text if ch.isdigit())
    try:
        value = int(cleaned)
        send_discord_ocr_log(f"OCR: {value} (ocr_resources)")
        gui.ocr_log("Resources", value, raw_value=cleaned)
        return value
    except ValueError:
        send_discord_ocr_log(f"OCR: ValueError (ocr_resources)")
        gui.ocr_log("Resources", "ERROR", raw_value=cleaned)
        return 0


def ocr_loot():
    """
    OCR loot values after battle (gold, elixir, dark elixir).
    Returns dictionary with loot values.
    If any value is > 4 million after retry, set it to 0 and log a warning.
    """
    loot = {
        'gold': 0,
        'elixir': 0,
        'dark_elixir': 0
    }
    try:
        # OCR each loot type using multi-engine system
        gold_img = ImageGrab.grab(bbox=config.LOOT_GOLD_REGION)
        # Add separator for loot OCR to distinguish between attacks
        send_discord_ocr_log("━━━━━━ **LOOT OCR** ━━━━━━")

        loot['gold'] = ocr_attack_resource_template_digits(gold_img, debug=False, context='loot_screen', resource_type='gold')

        elixir_img = ImageGrab.grab(bbox=config.LOOT_ELIXIR_REGION)
        loot['elixir'] = ocr_attack_resource_template_digits(elixir_img, debug=False, context='loot_screen', resource_type='elixir')

        dark_elixir_img = ImageGrab.grab(bbox=config.LOOT_DARK_ELIXIR_REGION)
        loot['dark_elixir'] = ocr_attack_resource_template_digits(dark_elixir_img, debug=False, context='loot_screen', resource_type='dark_elixir')

        # Failsafe: if any value > 4 million, set to 0 and log
        for k in ['gold', 'elixir', 'dark_elixir']:
            if loot[k] > 4_000_000:
                print(f"[OCR FAILSAFE] Loot {k} value {loot[k]} > 4 million. Ignoring this value.")
                gui.log_message(f"[OCR FAILSAFE] Loot {k} value {loot[k]} > 4 million. Ignoring this value.")
                send_discord_debug_log(f"OCR failsafe: Loot {k} value {loot[k]} > 4 million, ignoring", "WARNING")
                send_discord_ocr_log(f"OCR: {loot[k]} (loot_{k}, loot_screen) > 4 million, set to 0")
                loot[k] = 0
        print(f"Loot captured - Gold: {loot['gold']:,}, Elixir: {loot['elixir']:,}, Dark Elixir: {loot['dark_elixir']:,}")
        gui.log_message(f"Loot: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}")
        send_discord_debug_log(f"Loot captured: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}")
        debug_save_loot_ocr_regions()  # Automatically save loot OCR regions after battle
        return loot
    except Exception as e:
        print(f"Error capturing loot: {e}")
        gui.log_message(f"Error capturing loot: {e}")
        send_discord_debug_log(f"Error capturing loot: {e}", "ERROR")
        send_discord_ocr_log(f"OCR: Exception {e} (ocr_loot)")
        return loot


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
    current_profile = gui.current_profile
    all_profiles = gui.profiles

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
            current_profile = gui.current_profile

            if dark_elixir is not None:
                resource_str = f"Gold: {gold:,}, Elixir: {elixir:,}, Dark: {dark_elixir:,}"
            else:
                resource_str = f"Gold: {gold:,}, Elixir: {elixir:,}"

            print(f"⚠️ AUTO-SWITCH: Resources ({resource_str}) suggest profile '{profile_name}'")
            print(f"   Current: {current_profile} → Switching to: {profile_name}")
            print(f"   Reason: {reason}")
            gui.log_message(f"⚠️ Auto-switching profile: {current_profile} → {profile_name}")
            gui.log_message(f"   Reason: {reason}")
            send_discord_debug_log(f"Auto-switching profile: {current_profile} → {profile_name} ({reason})", "WARNING")

            # Switch profile
            gui.profile_var.set(profile_name)
            gui.apply_profile(silent=True)

            return True
        return False
    except Exception as e:
        print(f"Error in auto_switch_profile_if_needed: {e}")
        return False


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
    global last_3_resources, paused

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
        print(f"⚠️ STORAGES FULL - NO LOOT GAINED")
        print(f"{'='*60}")
        print(f"Same resources detected for 3 consecutive attacks:")
        print(f"  {resource_str}")
        print(f"Likely max storage values are outdated or storages are full.")
        print(f"AUTO-PAUSING BOT - Please update profile storage maximums!")
        print(f"{'='*60}\n")

        gui.log_message("⚠️ STORAGES FULL - Pausing bot")
        gui.log_message(f"Same resources: {resource_str}")
        gui.log_message("Update profile storage maximums!")

        send_discord_debug_log(
            f"🛑 Storages Full - Auto-pausing bot\n"
            f"Same resources for 3 attacks: {resource_str}\n"
            f"Update profile storage maximums!",
            "WARNING"
        )

        # Pause the bot
        paused = True
        gui.toggle_pause()  # Update GUI state

        # Clear tracking to avoid repeated pauses
        last_3_resources[base_type] = []

        return True

    return False


def ocr_remaining_troop_count():
    """
    OCR the remaining troop count during attack from the troop count region.
    Format: "xN" where N is the number of remaining troops (e.g., "x2", "x50", "x0")

    Returns:
        int: Number of remaining troops (0-64), or -1 if OCR fails
    """
    try:
        # Capture the troop count region
        screenshot = ImageGrab.grab(bbox=config.TROOP_COUNT_REGION)

        # Convert to grayscale and apply thresholding for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 150, 255, cv2.THRESH_BINARY)

        # OCR the text (expect format "xN" where N is 0-64)
        text = pytesseract.image_to_string(screenshot_cv, config='--psm 7')
        text = text.strip().replace(' ', '').replace('O', '0')  # Fix common OCR mistakes

        # Remove 'x' prefix if present
        if text.startswith('x'):
            text = text[1:]

        # Try to parse the number
        if text.isdigit():
            count = int(text)
            if 0 <= count <= 64:  # Validate range
                print(f"[TROOP COUNT OCR] Remaining troops: {count}")
                return count
            else:
                print(f"[TROOP COUNT OCR] Invalid count {count} (out of range 0-64)")
                return -1
        else:
            print(f"[TROOP COUNT OCR] Failed to parse: '{text}'")
            return -1

    except Exception as e:
        print(f"[TROOP COUNT OCR] Exception: {e}")
        return -1


def check_bb_attacker_text():
    """
    Check if 'Attacker' text is visible on screen to confirm BB base has loaded.
    Returns True if text detected, False otherwise.
    """
    try:
        # Capture the attacker text region
        screenshot = ImageGrab.grab(bbox=config.BB_ATTACKER_TEXT_REGION)

        # Convert to grayscale for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)

        # Apply thresholding (white text on dark background)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 150, 255, cv2.THRESH_BINARY)

        # OCR the text
        text = pytesseract.image_to_string(screenshot_cv, config='--psm 7')
        text = text.strip().lower()

        # Check if "attacker" is in the text
        if 'attacker' in text:
            return True
        return False
    except Exception as e:
        print(f"[BB] Error checking Attacker text: {e}")
        send_discord_debug_log(f"BB: Error checking Attacker text: {e}", "WARNING")
        return False


def save_loot_data(loot_data, loop_count):
    """
    Save loot data to a CSV file for tracking.
    """
    import csv
    from datetime import datetime

    filename = 'data/loot_tracking.csv'
    file_exists = os.path.exists(filename)

    try:
        with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'attack_number', 'gold', 'elixir', 'dark_elixir', 'total_loot']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header if file is new
            if not file_exists:
                writer.writeheader()

            # Calculate total loot value
            total_loot = loot_data['gold'] + loot_data['elixir'] + (loot_data['dark_elixir'] * 100)  # Dark elixir worth more

            # Write loot data
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'attack_number': loop_count,
                'gold': loot_data['gold'],
                'elixir': loot_data['elixir'],
                'dark_elixir': loot_data['dark_elixir'],
                'total_loot': total_loot
            })

        print(f"Loot data saved to {filename}")
        gui.log_message(f"Loot data saved to {filename}")

    except Exception as e:
        print(f"Error saving loot data: {e}")
        gui.log_message(f"Error saving loot data: {e}")

# Control callbacks

def update_status():
    """Update GUI status from bot state (both main status and quick status indicator)"""
    if gui.bot_running:
        if gui.bot_paused:
            gui.status_label.config(text='PAUSED', foreground='orange')
            gui.quick_status_label.config(text='● Paused', foreground='orange')
        else:
            gui.status_label.config(text='RUNNING', foreground='green')
            gui.quick_status_label.config(text='● Running', foreground='green')
    else:
        gui.status_label.config(text='STOPPED', foreground='red')
        gui.quick_status_label.config(text='● Stopped', foreground='red')


def toggle_pause():
    global paused
    paused = not paused
    gui.bot_paused = paused
    print(f"Paused set to {paused}")
    gui.log_message(f"Bot {'paused' if paused else 'resumed'}")
    root.after(0, update_status)


def stop_bot():
    """Stop the bot immediately without closing the GUI"""
    global running, paused
    running = False
    paused = True

    # Release all held keys immediately
    try:
        pyautogui.keyUp('shift')
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('alt')
        # Release mouse buttons if held
        try:
            pyautogui.mouseUp()
        except:
            pass
    except Exception as e:
        print(f"Error releasing keys: {e}")

    # Stop any ongoing PyAutoGUI operations
    pyautogui.PAUSE = 0

    print("Bot stopped immediately by user (F2)")
    send_discord_debug_log("Bot stopped immediately by user hotkey (F2)", "INFO")

    # Update GUI on main thread (handles button states and status labels)
    root.after(0, gui.stop_bot)


def exit_app():
    """Stop the bot and close the entire program"""
    global running
    running = False
    gui.bot_running = False
    gui.log_message("Bot stopped - closing program")

    # Stop connection monitor
    stop_connection_monitor()

    # Unhook all keyboard hotkeys to prevent clicks after exit
    try:
        keyboard.unhook_all()
        print("Keyboard hotkeys cleaned up")
    except Exception as e:
        print(f"Error unhooking keyboard: {e}")

    # Stop any PyAutoGUI operations
    pyautogui.PAUSE = 0  # Disable pause between actions for faster shutdown

    root.quit()


def debug_save_ocr_regions():
    """Save screenshots of the OCR regions for debugging bounding boxes."""
    try:
        folder = "debug_ocr_regions"
        os.makedirs(folder, exist_ok=True)
        # Count images in folder
        images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if len(images) >= 500:
            #gui.log_message("Debug OCR region folder full (500+ images), not saving new images.")
            return
        gold_img = ImageGrab.grab(bbox=config.GOLD_REGION)
        gold_img.save(os.path.join(folder, "debug_gold_region_{:03d}.png".format(len(images)+1)))
        elixir_img = ImageGrab.grab(bbox=config.ELIXIR_REGION)
        elixir_img.save(os.path.join(folder, "debug_elixir_region_{:03d}.png".format(len(images)+1)))
        if hasattr(config, "DARK_ELIXIR_REGION"):
            dark_region = getattr(config, "DARK_ELIXIR_REGION")
            dark_img = ImageGrab.grab(bbox=dark_region)
            dark_img.save(os.path.join(folder, "debug_dark_elixir_region_{:03d}.png".format(len(images)+1)))
        gui.log_message("OCR region screenshots saved for debugging.")
    except Exception as e:
        print(f"Error saving OCR region screenshots: {e}")
        gui.log_message(f"Error saving OCR region screenshots: {e}")

def debug_save_loot_ocr_regions():
    """Save screenshots of the loot OCR regions after battle for debugging bounding boxes."""
    try:
        folder = "debug_ocr_regions"
        os.makedirs(folder, exist_ok=True)
        # Count images in folder
        images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if len(images) >= 500:
            return
        gold_img = ImageGrab.grab(bbox=config.LOOT_GOLD_REGION)
        gold_img.save(os.path.join(folder, "debug_loot_gold_region_{:03d}.png".format(len(images)+1)))
        elixir_img = ImageGrab.grab(bbox=config.LOOT_ELIXIR_REGION)
        elixir_img.save(os.path.join(folder, "debug_loot_elixir_region_{:03d}.png".format(len(images)+1)))
        if hasattr(config, "LOOT_DARK_ELIXIR_REGION"):
            dark_region = getattr(config, "LOOT_DARK_ELIXIR_REGION")
            dark_img = ImageGrab.grab(bbox=dark_region)
            dark_img.save(os.path.join(folder, "debug_loot_dark_elixir_region_{:03d}.png".format(len(images)+1)))
        gui.log_message("Loot OCR region screenshots saved for debugging.")
    except Exception as e:
        print(f"Error saving loot OCR region screenshots: {e}")
        gui.log_message(f"Error saving loot OCR region screenshots: {e}")

def send_discord_notification(message):
    """
    Send a notification to a Discord channel using a webhook URL with robust error handling.
    Set your webhook URL in DISCORD_WEBHOOK_URL in config.py.
    Bot continues running even if Discord is unreachable.
    """
    import config

    # Check if Discord logging is enabled
    if not getattr(config, 'DEBUG_LOG_ENABLED', True):
        return

    webhook_url = getattr(config, 'DISCORD_WEBHOOK_URL', None)
    if not webhook_url:
        return  # Silently skip if no webhook configured

    data = {"content": message}

    try:
        # Add 5-second timeout to prevent hanging
        response = requests.post(webhook_url, json=data, timeout=5)
        if response.status_code != 204:
            print(f"[Discord] Warning: Message failed with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        # Catch all network errors: DNS failures, timeouts, connection errors
        print(f"[Discord] Warning: Could not send message - {type(e).__name__}")
        # Bot continues running - Discord failure doesn't stop execution
    except Exception as e:
        # Catch any other unexpected errors
        print(f"[Discord] Warning: Unexpected error - {e}")

def send_discord_debug_log(message, level="INFO"):
    """
    Send debug log to Discord channel.
    Levels: DEBUG, INFO, WARNING, ERROR
    """
    global debug_log_buffer, last_debug_log
    
    if not DEBUG_LOG_ENABLED:
        return
    
    # Check if level meets minimum threshold
    level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_priority = level_priority.get(DEBUG_LOG_LEVEL, 1)
    current_priority = level_priority.get(level, 1)
    
    if current_priority < min_priority:
        return
    
    # Add timestamp and format message
    timestamp = time.strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    # Add to buffer
    debug_log_buffer.append(formatted_message)
    
    # Send immediately for errors and warnings
    if level in ["ERROR", "WARNING"]:
        send_discord_notification(f"🚨 **{level}**: {message}")
        return
    
    # Send buffered logs periodically
    current_time = time.time()
    if current_time - last_debug_log >= DEBUG_LOG_INTERVAL and debug_log_buffer:
        # Combine multiple messages
        combined_message = "📊 **Debug Log Update:**\n" + "\n".join(debug_log_buffer[-10:])  # Last 10 messages
        send_discord_notification(combined_message)
        debug_log_buffer.clear()
        last_debug_log = current_time

# Bind hotkeys
keyboard.add_hotkey('f1', toggle_pause)
keyboard.add_hotkey('f2', stop_bot)
keyboard.add_hotkey('esc', exit_app)
keyboard.add_hotkey('f6', debug_save_ocr_regions)

def clear_overlay_hotkey():
    """Clear all overlay drawings (F7 hotkey)."""
    if gui.overlay and gui.overlay_enabled:
        gui.overlay.clear()
        gui.overlay.update()
        print("[OVERLAY] Cleared via F7 hotkey")

keyboard.add_hotkey('f7', clear_overlay_hotkey)

def save_overlay_screenshot_hotkey():
    """Save overlay screenshot with black background (F8 hotkey)."""
    if gui.overlay and gui.overlay_enabled:
        gui.overlay.save_screenshot()
    else:
        print("[OVERLAY] Cannot save - overlay not enabled")

keyboard.add_hotkey('f8', save_overlay_screenshot_hotkey)

def ocr_attack_resource(img, debug=False):
    """
    Robust OCR for attack resource numbers (white digits, dark background).
    Tries adaptive thresholding, simple threshold, and raw grayscale.
    """
    import numpy as np
    try:
        import cv2
        img = img.convert('L')
        img_np = np.array(img)
        # Try adaptive thresholding
        bin_img = cv2.adaptiveThreshold(
            img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        bin_img_pil = Image.fromarray(bin_img)
        if debug:
            bin_img_pil.show(title="Adaptive Threshold")
        text = pytesseract.image_to_string(bin_img_pil, config='--psm 7 -c tessedit_char_whitelist=0123456789')
        cleaned = ''.join(ch for ch in text if ch.isdigit())
        if cleaned:
            return int(cleaned)
        # Fallback: simple threshold
        _, bin_img2 = cv2.threshold(img_np, 180, 255, cv2.THRESH_BINARY)
        bin_img2_pil = Image.fromarray(bin_img2)
        if debug:
            bin_img2_pil.show(title="Simple Threshold 180")
        text2 = pytesseract.image_to_string(bin_img2_pil, config='--psm 7 -c tessedit_char_whitelist=0123456789')
        cleaned2 = ''.join(ch for ch in text2 if ch.isdigit())
        if cleaned2:
            return int(cleaned2)
        # Fallback: raw grayscale
        text3 = pytesseract.image_to_string(img, config='--psm 7 -c tessedit_char_whitelist=0123456789')
        cleaned3 = ''.join(ch for ch in text3 if ch.isdigit())
        if cleaned3:
            return int(cleaned3)
        return 0
    except ImportError:
        # Fallback: PIL only
        img = img.convert('L')
        text = pytesseract.image_to_string(img, config='--psm 7 -c tessedit_char_whitelist=0123456789')
        cleaned = ''.join(ch for ch in text if ch.isdigit())
        return int(cleaned) if cleaned else 0
    except Exception as e:
        if debug:
            print(f"[OCR Error] {e}")
        return 0
def plot_statistics():
    """
    Plot loot and loops completed over the past day, week, and month from loot_tracking.csv.
    """
    import pandas as pd
    try:
        df = pd.read_csv('data/loot_tracking.csv', parse_dates=['timestamp'])
    except Exception as e:
        print(f"Error reading loot_tracking.csv: {e}")
        return
    if df.empty:
        print("No data to plot.")
        return
    now = datetime.now()
    periods = {
        'Day': now - timedelta(days=1),
        'Week': now - timedelta(weeks=1),
        'Month': now - timedelta(days=30)
    }
    plt.figure(figsize=(15, 10))
    for i, (label, start_time) in enumerate(periods.items(), 1):
        plt.subplot(2, 2, i)
        mask = df['timestamp'] >= start_time.strftime('%Y-%m-%d %H:%M:%S')
        sub = df[mask]
        if sub.empty:
            plt.title(f"No data for last {label.lower()}")
            continue
        plt.plot(sub['timestamp'], sub['total_loot'], marker='o', label='Total Loot')
        plt.xlabel('Time')
        plt.ylabel('Total Loot')
        plt.title(f'Total Loot in the last {label.lower()}')
        plt.xticks(rotation=45)
        plt.legend()
    # Plot loops completed (attack_number)
    plt.subplot(2, 2, 4)
    plt.plot(df['timestamp'], df['attack_number'], marker='x', color='orange', label='Loops Completed')
    plt.xlabel('Time')
    plt.ylabel('Loop #')
    plt.title('Loops Completed Over Time')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()
# def ocr_attack_resource_easyocr(img, debug=False):
#     """
#     OCR for attack resource numbers using EasyOCR, mimicking the simple usage pattern.
#     Accepts a PIL image, converts to BGR numpy array, and restricts to digits only.
#     """
#     import numpy as np
#     import cv2
#     # Convert PIL image to BGR numpy array
#     img_np = np.array(img.convert('RGB'))
#     img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
#     if debug:
#         cv2.imshow('Attack Resource OCR Input', img_bgr)
#         cv2.waitKey(500)
#         cv2.destroyAllWindows()
#     # Use EasyOCR to extract only digits
#     results = easyocr_reader.readtext(
#         img_bgr,
#         detail=0,
#         allowlist='0123456789'
#     )
#     digits = ''.join(str(r) for r in results)
#     if debug:
#         print("EasyOCR result:", digits)
#     return int(digits) if digits.isdigit() else 0

def ocr_attack_resource_template_digits(img, debug=False, context=None, resource_type=None):
    """
    OCR for attack resource numbers using digit template matching.
    Loads digit templates from screenshots/reference/digits/ based on context.
    Context must be specified: 'attack_screen', 'base_screen', 'loot_screen', 'base_dark_elixir', etc.
    resource_type: optional 'gold', 'elixir', or 'dark_elixir' for better Discord logging.
    Accepts a PIL image, returns the detected integer.
    """
    try:
        # Require context to be specified
        if context is None:
            raise ValueError("Context must be specified for ocr_attack_resource_template_digits (e.g., 'attack_screen', 'base_screen', 'loot_screen', 'base_dark_elixir')")
        # 1. Load & binarize templates for the specific context
        templates = {}
        digits_dir = os.path.join('screenshots/reference', 'digits', context)
        if not os.path.exists(digits_dir):
            if debug:
                print(f"[Template OCR] Context directory not found: {digits_dir}")
            # Fallback to base context if specific context not found
            digits_dir = os.path.join('screenshots/reference', 'digits', 'base_screen')
            if not os.path.exists(digits_dir):
                if debug:
                    print(f"[Template OCR] Fallback directory not found: {digits_dir}")
                return 0
        for digit in range(10):
            tpl_path = os.path.join(digits_dir, f'{digit}.png')
            tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                if debug:
                    print(f"[Template OCR] Cannot load template: {tpl_path}")
                continue
            _, tpl_bin = cv2.threshold(
                tpl, 0, 255,
                cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
            )
            templates[digit] = tpl_bin
        if not templates:
            if debug:
                print(f"[Template OCR] No templates loaded for context: {context}")
            return 0
        # 2. Convert input PIL image to OpenCV BGR, then gray + binary-invert
        img_np = np.array(img.convert('RGB'))
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
        )
        # 3. Template matching for each digit
        detections = []
        # Balanced threshold for thick-outlined storage numbers
        # Use lenient threshold for storage/loot screens (thicker outlined digits)
        if context in ('base_screen', 'base_dark_elixir', 'bb_base_screen', 'loot_screen'):
            base_threshold = 0.68  # Middle ground: not too strict, not too lenient
        else:
            base_threshold = 0.72  # Stricter for attack screen previews

        for digit, tpl in templates.items():
            # Slightly lower for commonly missed digits (0, 4, 7)
            if digit in (0, 4, 7):
                match_threshold = base_threshold - 0.03  # Small adjustment, not too aggressive
            else:
                match_threshold = base_threshold

            tpl_h, tpl_w = tpl.shape
            score_map = cv2.matchTemplate(thresh, tpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(score_map >= match_threshold)
            for (y, x) in zip(ys, xs):
                score = float(score_map[y, x])
                x1, y1 = x, y
                x2, y2 = x + tpl_w, y + tpl_h
                detections.append((x1, y1, x2, y2, score, digit))
        if not detections:
            if debug:
                print(f"[Template OCR] No digit matches found for context: {context}")
            resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '❌')
            resource_label = resource_type.upper() if resource_type else context
            send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: No matches found")
            return 0
        # 4. Non-Max Suppression tuned for thick-outlined digits with grouping
        # Overlap threshold of 0.2 (20%) - filters false positives while keeping adjacent digits
        boxes  = np.array([d[:4] for d in detections])
        scores = np.array([d[4]  for d in detections])
        keep_boxes = non_max_suppression(boxes, probs=scores, overlapThresh=0.2)

        if len(keep_boxes) == 0:
            if debug:
                print(f"[Template OCR] No digit matches found after NMS for context: {context}")
            resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '❌')
            resource_label = resource_type.upper() if resource_type else context
            send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: No matches after NMS")
            return 0

        # 5. Pick best digit per kept box (store confidence for logging)
        final = []
        for (x1, y1, x2, y2) in keep_boxes:
            cands = [
                (scr, dig) for (bx1,by1,bx2,by2,scr,dig) in detections
                if bx1==x1 and by1==y1 and bx2==x2 and by2==y2
            ]
            if not cands:
                continue
            best_score, best_digit = max(cands, key=lambda x: x[0])
            final.append((x1, best_digit, best_score))

        # 6. Sort left-to-right
        final = sorted(final, key=lambda x: x[0])
        result = ''.join(str(d) for _, d, _ in final)
        if debug:
            print(f"[Template OCR] Template matching result: {result} (context: {context})")

        if result.isdigit():
            value = int(result)

            # Validation: If result seems unreasonably small for storage context, try Tesseract fallback
            # Storage values should typically be > 1000 unless truly empty
            if context in ('base_screen', 'bb_base_screen') and value > 0 and value < 10000 and len(result) < 5:
                if debug:
                    print(f"[Template OCR] Result {value} seems small for storage, trying Tesseract fallback...")

                # Try Tesseract OCR as fallback
                try:
                    # Prepare image for Tesseract (white text on black background)
                    tesseract_result = pytesseract.image_to_string(
                        Image.fromarray(thresh),
                        config='--psm 7 -c tessedit_char_whitelist=0123456789'
                    )
                    tesseract_cleaned = ''.join(ch for ch in tesseract_result if ch.isdigit())

                    if tesseract_cleaned and tesseract_cleaned.isdigit():
                        tesseract_value = int(tesseract_cleaned)
                        # Use Tesseract result if it's significantly larger
                        if tesseract_value > value * 10:
                            if debug:
                                print(f"[Template OCR] Using Tesseract result: {tesseract_value} (was {value})")
                            resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '🔄')
                            resource_label = resource_type.upper() if resource_type else context
                            send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: {tesseract_value} (Tesseract fallback, template was {value})")
                            gui.ocr_log(resource_label, tesseract_value, raw_value=f"template:{value}")
                            return tesseract_value
                except Exception as e:
                    if debug:
                        print(f"[Template OCR] Tesseract fallback failed: {e}")

            # Build detailed Discord log with resource type and digit confidences
            resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '📊')
            resource_label = resource_type.upper() if resource_type else context
            digit_conf = ' '.join(f"{d}({s*100:.0f}%)" for _, d, s in final)
            avg_conf = sum(s for _, _, s in final) / len(final) * 100 if final else 0
            send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: {result}  [{digit_conf}]")
            gui.ocr_log(resource_label, value, raw_value=result, confidence=avg_conf)
            return value
        else:
            resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '❌')
            resource_label = resource_type.upper() if resource_type else context
            send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: Non-digit '{result}'")
            return 0
    except Exception as e:
        if debug:
            print(f"[Template OCR] Error: {e}")
        resource_emoji = {'gold': '🪙', 'elixir': '💧', 'dark_elixir': '⚫'}.get(resource_type, '❌')
        resource_label = resource_type.upper() if resource_type else context
        send_discord_ocr_log(f"{resource_emoji} **{resource_label}**: Exception {e}")
        return 0

def ocr_base_resource(img, debug=False):
    """
    Specialized OCR for base resource numbers (white digits, dark background).
    Uses a high threshold and erosion. If debug=True, shows processed image and prints raw OCR.
    """
    import numpy as np
    try:
        import cv2
        img = img.convert('L')
        img_np = np.array(img)
        # Use a high threshold to isolate white digits (tune if needed)
        _, bin_img = cv2.threshold(img_np, 235, 255, cv2.THRESH_BINARY)
        kernel = np.ones((2, 2), np.uint8)
        bin_img = cv2.erode(bin_img, kernel, iterations=1)
        bin_img_pil = Image.fromarray(bin_img)
    except ImportError:
        img = img.convert('L')
        bin_img_pil = img.point(lambda x: 255 if x > 235 else 0, '1')
    if debug:
        bin_img_pil.show()
    text = pytesseract.image_to_string(bin_img_pil, config='--psm 7 -c tessedit_char_whitelist=0123456789')
    if debug:
        print(f"Raw OCR: '{text}'")
    cleaned = ''.join(ch for ch in text if ch.isdigit())
    return int(cleaned) if cleaned else 0




def detect_air_sweepers():
    """
    Detect air sweepers in the base using template matching for all 8 directions.
    Returns a list of (x, y, direction, confidence) tuples.
    """
    sweepers = []
    templates_dir = "screenshots/reference/air_sweepers"
    if not os.path.exists(templates_dir):
        print(f"Air sweeper templates directory not found: {templates_dir}")
        return sweepers
    # Capture the base view region
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    # For each template (direction)
    for template_path in glob.glob(os.path.join(templates_dir, "air_sweeper_*.png")):
        direction = os.path.splitext(os.path.basename(template_path))[0].replace("air_sweeper_", "")
        template = cv2.imread(template_path)
        if template is None:
            continue
        result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= 0.7)  # Threshold can be adjusted
        for pt in zip(*locations[::-1]):
            x, y = pt
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]
            confidence = result[y, x]
            sweepers.append((global_x, global_y, direction, confidence))
    # Remove duplicates (positions too close)
    filtered = []
    for sw in sweepers:
        x, y, direction, conf = sw
        is_dup = False
        for ex in filtered:
            ex_x, ex_y, _, _ = ex
            if ((x - ex_x) ** 2 + (y - ex_y) ** 2) ** 0.5 < 50:
                is_dup = True
                break
        if not is_dup:
            filtered.append(sw)
    # Sort by confidence
    filtered.sort(key=lambda x: x[3], reverse=True)
    # Return up to 2 sweepers
    return filtered[:2]

def get_air_defense_proximity_sorter(side):
    if side == 'left':
        return lambda ad: ad[0]  # x coordinate, smaller is closer to left
    elif side == 'right':
        return lambda ad: -ad[0] # x coordinate, larger is closer to right
    elif side == 'up':
        return lambda ad: ad[1]  # y coordinate, smaller is closer to top
    elif side == 'down':
        return lambda ad: -ad[1] # y coordinate, larger is closer to bottom
    else:
        return lambda ad: 0


def calculate_lightning_spells_needed(air_defense_level, lightning_damage):
    """
    Calculate how many lightning spells are needed to destroy an air defense.
    Returns the number of spells needed.
    """
    hp = config.AIR_DEFENSE_HP.get(air_defense_level, 1000)  # Default to 1000 if level not found
    spells_needed = (hp + lightning_damage - 1) // lightning_damage  # Ceiling division
    return max(1, spells_needed)  # Minimum 1 spell





def collect_resources():
    """
    Click resource collection coordinates to collect resources from generators.
    """
    print("Collecting resources from generators...")
    gui.log_message("Collecting resources from generators...")
    
    for i, (x, y) in enumerate(config.RESOURCE_COLLECTION_COORDS):
        human_like_move_click(x, y)
        # Use humanized sleep for natural timing
        humanized_sleep(0.2, variance=0.3)
        print(f"  Collected from coordinate {i+1}: ({x}, {y})")
    
    time.sleep(1)  # Wait for collection animation
    print("Resource collection completed")
    gui.log_message("Resource collection completed")





def check_discord_commands():
    """
    Check for Discord commands by monitoring bot_settings.json file.
    This allows the main bot to respond to Discord controller commands.
    """
    global paused, running, last_settings_check
    current_time = time.time()
    if current_time - last_settings_check < settings_check_interval:
        return
    last_settings_check = current_time
    try:
        # Check if bot_settings.json exists and has been modified
        if not os.path.exists('bot_settings.json'):
            return
        # Load current settings from file
        with open('bot_settings.json', 'r', encoding='utf-8') as f:
            file_settings = json.load(f)
        # Check for Discord control flags
        discord_running = file_settings.get('discord_running', None)
        discord_paused = file_settings.get('discord_paused', None)
        # Only apply Discord commands if the flags actually exist in the file
        if discord_running is not None and discord_paused is not None:
            # Apply Discord commands
            if discord_running and not gui.bot_running:
                gui.bot_running = True
                gui.bot_paused = False
                paused = False
                running = True
                gui.log_message("Bot started via Discord command")
                print("Bot started via Discord command")
                root.after(0, update_status)
            elif not discord_running and gui.bot_running:
                gui.bot_running = False
                gui.bot_paused = True
                paused = True
                running = False
                gui.log_message("Bot stopped via Discord command")
                print("Bot stopped via Discord command")
                root.after(0, update_status)
            elif discord_running and gui.bot_running:
                if discord_paused and not gui.bot_paused:
                    gui.bot_paused = True
                    paused = True
                    gui.log_message("Bot paused via Discord command")
                    print("Bot paused via Discord command")
                    root.after(0, update_status)
                elif not discord_paused and gui.bot_paused:
                    gui.bot_paused = False
                    paused = False
                    gui.log_message("Bot resumed via Discord command")
                    print("Bot resumed via Discord command")
                    root.after(0, update_status)
        # --- Commented out: Discord settings update functionality ---
        # gui_settings = gui.get_settings()
        # settings_changed = False
        # for key, value in file_settings.items():
        #     if key not in ['discord_running', 'discord_paused'] and key in gui_settings:
        #         if gui_settings[key] != value:
        #             settings_changed = True
        #             gui.log_message(f"Setting updated via Discord: {key} = {value}")
        #             print(f"Setting updated via Discord: {key} = {value}")
        # if settings_changed:
        #     root.after(0, gui.update_settings_from_file)
    except Exception as e:
        print(f"Error checking Discord commands: {e}")





# Main action loop
# Setup automatic break timing
def schedule_next_break():
    # Get settings from GUI
    settings = gui.get_settings()
    break_interval = settings.get('break_interval', 45)  # minutes
    auto_pause_enabled = settings.get('auto_pause_enabled', True)
    
    if not auto_pause_enabled:
        return None  # No break scheduled
    
    # Add some randomization (±5 minutes)
    interval_seconds = (break_interval + random.uniform(-5, 5)) * 60
    return time.time() + interval_seconds

break_time = schedule_next_break()

def is_base_search_ready():
    """Check if base search screen is ready by detecting end_battle button"""
    template_path = 'screenshots/reference/attack/end_battle.png'
    # Search in bottom-left area where end_battle button appears
    region = (0, 1100, 600, 1440)
    threshold = 0.75
    try:
        template = cv2.imread(template_path)
        if template is None:
            print(f"Warning: Could not load template at {template_path}")
            return False

        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            print(f"Base search screen detected (confidence: {max_val:.2f})")
            return True
        return False
    except Exception as e:
        print(f"Error in is_base_search_ready: {e}")
        return False

def is_attack_screen_ready():
    # Use the alt hotkey template and region as the cue
    template_path = 'assets/alt_hotkey_template.png'
    region = (522, 1273, 664, 1412)
    try:
        template = cv2.imread(template_path)
        if template is None:
            return False
        h, w, _ = template.shape
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        if screenshot_cv.shape[0] == h and screenshot_cv.shape[1] == w:
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            return max_val >= 0.8
        else:
            return False
    except Exception as e:
        print(f"[DERANK] Error in is_attack_screen_ready: {e}")
        return False

def detect_main_base_boat():
    """
    Detect boat on Main Base using template matching.
    Returns (x, y) coordinates of the boat center if found, None otherwise.
    """
    try:
        # Full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load the boat template
        template_path = "screenshots/reference/main_base/boat.png"
        if not os.path.exists(template_path):
            print(f"[MAIN BOAT] Boat template not found: {template_path}")
            send_discord_debug_log(f"Main Base boat template not found: {template_path}", "WARNING")
            return None

        template = cv2.imread(template_path)
        if template is None:
            print(f"[MAIN BOAT] Failed to load boat template: {template_path}")
            send_discord_debug_log(f"Failed to load boat template: {template_path}", "WARNING")
            return None

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            # Calculate center of the boat
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2
            center_y = max_loc[1] + template_height // 2

            print(f"[MAIN BOAT] Boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            send_discord_debug_log(f"Main Base boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            return (center_x, center_y)
        else:
            print(f"[MAIN BOAT] Boat not detected (best match confidence: {max_val:.2f})")
            send_discord_debug_log(f"Main Base boat not detected (best match confidence: {max_val:.2f})", "WARNING")
            return None
    except Exception as e:
        print(f"[MAIN BOAT] Error detecting boat: {e}")
        send_discord_debug_log(f"Main Base boat detection error: {e}", "ERROR")
        return None

def detect_bb_boat():
    """
    Detect Builder Base boat using template matching.
    Returns (x, y, is_cart_fallback) tuple if found, None otherwise.
    is_cart_fallback is True when using trees fallback (returns elixir cart position).
    """
    try:
        # Full screen search
        screen_img = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)

        # Load the boat template
        template_path = "screenshots/reference/builder_base/boat.png"
        if not os.path.exists(template_path):
            print(f"[BB BOAT] Boat template not found: {template_path}")
            send_discord_debug_log(f"BB boat template not found: {template_path}", "WARNING")
            return None

        template = cv2.imread(template_path)
        if template is None:
            print(f"[BB BOAT] Failed to load boat template: {template_path}")
            send_discord_debug_log(f"Failed to load boat template: {template_path}", "WARNING")
            return None

        # Perform template matching
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.7:  # 70% confidence threshold
            # Calculate center of the boat
            template_height, template_width = template.shape[:2]
            center_x = max_loc[0] + template_width // 2
            center_y = max_loc[1] + template_height // 2

            print(f"[BB BOAT] Boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            send_discord_debug_log(f"BB boat detected at ({center_x}, {center_y}) with confidence {max_val:.2f}")
            return (center_x, center_y, False)

        # Boat not found - try trees fallback to find elixir cart
        print(f"[BB BOAT] Boat not detected (best match confidence: {max_val:.2f}), trying trees fallback...")
        trees_template_path = "screenshots/reference/builder_base/trees.png"
        if os.path.exists(trees_template_path):
            trees_template = cv2.imread(trees_template_path)
            if trees_template is not None:
                trees_result = cv2.matchTemplate(screen_cv, trees_template, cv2.TM_CCOEFF_NORMED)
                _, trees_max_val, _, trees_max_loc = cv2.minMaxLoc(trees_result)

                if trees_max_val >= 0.7:
                    trees_h, trees_w = trees_template.shape[:2]
                    trees_center_x = trees_max_loc[0] + trees_w // 2
                    trees_center_y = trees_max_loc[1] + trees_h // 2

                    # Calculate elixir cart position from trees (offset +248, +200)
                    cart_x = trees_center_x + 248
                    cart_y = trees_center_y + 200

                    print(f"[BB BOAT] Trees detected at ({trees_center_x}, {trees_center_y}), using elixir cart at ({cart_x}, {cart_y})")
                    send_discord_debug_log(f"BB boat fallback: trees at ({trees_center_x}, {trees_center_y}), elixir cart at ({cart_x}, {cart_y})")
                    return (cart_x, cart_y, True)
                else:
                    print(f"[BB BOAT] Trees fallback failed (confidence: {trees_max_val:.2f})")

        send_discord_debug_log(f"BB boat not detected, trees fallback also failed", "WARNING")
        return None
    except Exception as e:
        print(f"[BB BOAT] Error detecting boat: {e}")
        send_discord_debug_log(f"BB boat detection error: {e}", "ERROR")
        return None

def switch_village(target_village):
    """
    Switch between Main Base and Builder Base.

    Args:
        target_village: 'main' or 'builder_base'

    Returns:
        True if switch successful, False otherwise
    """
    print(f"[VILLAGE SWITCH] Switching to {target_village}...")
    send_discord_debug_log(f"Switching to {target_village}")

    try:
        # Determine which boat to look for based on target village
        if target_village == 'builder_base':
            # Currently on Main Base, need to find Main Base boat
            print("[VILLAGE SWITCH] Preparing to detect boat on Main Base...")

            # Zoom out to see more of the base
            print("[VILLAGE SWITCH] Zooming out...")
            pyautogui.scroll(-3)  # Scroll down to zoom out
            time.sleep(0.5)

            # Drag camera to left-bottom to make boat visible
            # To see LEFT-BOTTOM area: drag RIGHT and UP
            print("[VILLAGE SWITCH] Dragging camera to left-bottom area...")
            start_x, start_y = 1280, 720  # Screen center
            end_x, end_y = start_x + 600, start_y - 400  # Drag right and up
            pyautogui.moveTo(start_x, start_y, duration=0.3)
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=0.5, button='left')
            time.sleep(1)

            # Now detect boat
            print("[VILLAGE SWITCH] Looking for boat on Main Base...")
            boat_pos = detect_main_base_boat()

            if not boat_pos:
                print("[VILLAGE SWITCH] Failed to find boat on Main Base")
                send_discord_debug_log("Failed to find boat on Main Base", "ERROR")
                return False

        else:  # target_village == 'main'
            # Currently on Builder Base, need to find BB boat
            print("[VILLAGE SWITCH] Looking for boat on Builder Base...")
            boat_pos = detect_bb_boat()

            if not boat_pos:
                # Boat not visible, try camera drag
                print("[VILLAGE SWITCH] Boat not found, dragging camera...")
                # Drag camera to see right side
                start_x, start_y = 1280, 720
                end_x, end_y = start_x - 800, start_y + 800
                pyautogui.moveTo(start_x, start_y, duration=0.3)
                pyautogui.drag(end_x - start_x, end_y - start_y, duration=0.5, button='left')
                time.sleep(1)

                # Try detection again
                boat_pos = detect_bb_boat()

                if not boat_pos:
                    print("[VILLAGE SWITCH] Failed to find boat on Builder Base")
                    send_discord_debug_log("Failed to find boat on Builder Base", "ERROR")
                    return False

        # Click the boat (or cart position if using trees fallback)
        click_x, click_y = boat_pos[0], boat_pos[1]
        is_cart = boat_pos[2] if len(boat_pos) > 2 else False
        if is_cart:
            print(f"[VILLAGE SWITCH] Clicking elixir cart area at ({click_x}, {click_y})")
        else:
            print(f"[VILLAGE SWITCH] Clicking boat at ({click_x}, {click_y})")
        human_like_move_click(click_x, click_y)
        time.sleep(0.5)

        # Wait for village transition (animation takes ~3-4 seconds)
        print("[VILLAGE SWITCH] Waiting for village transition...")
        time.sleep(4)

        # Verify we're in the correct village
        print(f"[VILLAGE SWITCH] Successfully switched to {target_village}")
        send_discord_debug_log(f"Successfully switched to {target_village}")
        return True

    except Exception as e:
        print(f"[VILLAGE SWITCH] Error switching village: {e}")
        send_discord_debug_log(f"Village switch error: {e}", "ERROR")
        return False

def collect_bb_loot():
    """
    Collect loot from Builder Base by finding the boat and clicking the relative position.
    """
    print("[BB LOOT] Starting loot collection...")
    send_discord_debug_log("BB Elixir: Starting loot collection")
    gui.log_message("BB Elixir: Collecting loot...")

    # Drag camera to see right side and slightly up
    # To see RIGHT: drag LEFT. To see UP: drag DOWN.
    print("[BB LOOT] Dragging camera to boat area...")
    start_x, start_y = 1280, 720  # Screen center
    end_x, end_y = start_x - 800, start_y + 800  # Drag left 100px, down 50px

    pyautogui.moveTo(start_x, start_y, duration=0.1)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.1)
    pyautogui.moveTo(end_x, end_y, duration=0.5)
    time.sleep(0.1)
    pyautogui.mouseUp()
    time.sleep(1)  # Wait for camera to settle

    # Try to detect boat (retry up to 3 times)
    boat_pos = None
    for attempt in range(3):
        boat_pos = detect_bb_boat()
        if boat_pos:
            break
        else:
            print(f"[BB LOOT] Boat not found, retry {attempt + 1}/3...")
            time.sleep(0.5)

    if boat_pos:
        pos_x, pos_y, is_cart = boat_pos

        if is_cart:
            # Trees fallback - click elixir cart directly
            click_x = pos_x
            click_y = pos_y
            print(f"[BB LOOT] Clicking elixir cart directly at ({click_x}, {click_y})")
        else:
            # Boat detected - click at offset position
            click_x = pos_x - 450
            click_y = pos_y + 150
            print(f"[BB LOOT] Clicking loot at ({click_x}, {click_y}) (relative to boat)")
        send_discord_debug_log(f"BB Elixir: Clicking loot at ({click_x}, {click_y})")
        human_like_move_click(click_x, click_y)
        time.sleep(2)

        # Click second position
        print("[BB LOOT] Clicking confirmation at (1857, 1215)")
        send_discord_debug_log("BB Elixir: Clicking loot confirmation (1857, 1215)")
        human_like_move_click(1857, 1215)
        time.sleep(1.5)

        # Click third position
        print("[BB LOOT] Clicking final button at (211, 900)")
        send_discord_debug_log("BB Elixir: Clicking final loot button (211, 900)")
        human_like_move_click(211, 900)
        time.sleep(2)

        print("[BB LOOT] Loot collection completed")
        gui.log_message("BB Elixir: Loot collected successfully")
        send_discord_debug_log("BB Elixir: Loot collection completed")
    else:
        print("[BB LOOT] WARNING: Boat not found after 3 attempts, skipping loot collection")
        gui.log_message("BB Elixir: Boat not found - skipping loot")
        send_discord_debug_log("BB Elixir: Boat not found - skipping loot collection", "WARNING")

def filter_out_unit_bar(coordinates):
    """
    Filter out coordinates that fall within the unit bar area and surrender button area.
    Unit bar area: x=1, y=1209 to x=2553, y=1431 (non-clickable for unit placement)
    Surrender button area: x=4, y=1006 to x=301, y=1151 (expanded by 20px for mouse variance)
    """
    UNIT_BAR_X1 = 1
    UNIT_BAR_Y1 = 1209
    UNIT_BAR_X2 = 2553
    UNIT_BAR_Y2 = 1431

    # Surrender button with 20px padding for mouse movement variance
    SURRENDER_BTN_X1 = 4    # was 24
    SURRENDER_BTN_Y1 = 1006  # was 1026
    SURRENDER_BTN_X2 = 301   # was 281
    SURRENDER_BTN_Y2 = 1151  # was 1131

    filtered_coords = []
    excluded_count_unit_bar = 0
    excluded_count_surrender = 0

    for x, y in coordinates:
        # Check if coordinate is within unit bar bounds
        if UNIT_BAR_X1 <= x <= UNIT_BAR_X2 and UNIT_BAR_Y1 <= y <= UNIT_BAR_Y2:
            excluded_count_unit_bar += 1
            continue
        # Check if coordinate is within surrender button bounds
        if SURRENDER_BTN_X1 <= x <= SURRENDER_BTN_X2 and SURRENDER_BTN_Y1 <= y <= SURRENDER_BTN_Y2:
            excluded_count_surrender += 1
            continue
        filtered_coords.append((x, y))

    if excluded_count_unit_bar > 0:
        print(f"[BB] Filtered out {excluded_count_unit_bar} coordinates within unit bar area")
        send_discord_debug_log(f"BB: Excluded {excluded_count_unit_bar} coords in unit bar")
    if excluded_count_surrender > 0:
        print(f"[BB] Filtered out {excluded_count_surrender} coordinates within surrender button area")
        send_discord_debug_log(f"BB: Excluded {excluded_count_surrender} coords in surrender button area")

    return filtered_coords

def detect_bb_deployment_zone():
    """
    Detect Builder Base deployment zone by finding red boundary lines.
    Returns list of valid deployment coordinates outside the red lines.
    """
    try:
        # Capture the game screen area
        screen_region = (200, 100, 2360, 1200)  # Adjust based on your resolution
        screenshot = ImageGrab.grab(bbox=screen_region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Define red color range in HSV (for the red deployment boundary lines)
        # Red has two ranges in HSV
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])

        # Create masks for red color
        mask1 = cv2.inRange(screenshot_hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(screenshot_hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Find contours of red lines
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("[BB] No red deployment lines detected, using default coordinates")
            # Fallback to corners if detection fails
            return [
                (300, 300), (300, 1000), (2200, 300), (2200, 1000),
                (300, 650), (2200, 650), (1250, 300), (1250, 1000)
            ]

        # Find the bounding box of all red line contours
        all_points = np.concatenate(contours)
        x, y, w, h = cv2.boundingRect(all_points)

        # Convert back to screen coordinates
        x_offset, y_offset = screen_region[0], screen_region[1]
        boundary_left = x + x_offset
        boundary_top = y + y_offset
        boundary_right = x + w + x_offset
        boundary_bottom = y + h + y_offset

        print(f"[BB] Detected red boundary: left={boundary_left}, top={boundary_top}, right={boundary_right}, bottom={boundary_bottom}")
        send_discord_debug_log(f"BB deployment zone detected: {boundary_left}, {boundary_top}, {boundary_right}, {boundary_bottom}")

        # Generate valid deployment coordinates OUTSIDE the red boundary
        # Top, bottom, left, and right sides
        valid_coords = []

        # Top side (above red line)
        if boundary_top > 200:
            for x_pos in range(boundary_left, boundary_right, 100):
                valid_coords.append((x_pos, boundary_top - 50))

        # Bottom side (below red line)
        if boundary_bottom < 1200:
            for x_pos in range(boundary_left, boundary_right, 100):
                valid_coords.append((x_pos, boundary_bottom + 50))

        # Left side (left of red line)
        if boundary_left > 200:
            for y_pos in range(boundary_top, boundary_bottom, 100):
                valid_coords.append((boundary_left - 50, y_pos))

        # Right side (right of red line)
        if boundary_right < 2360:
            for y_pos in range(boundary_top, boundary_bottom, 100):
                valid_coords.append((boundary_right + 50, y_pos))

        if not valid_coords:
            print("[BB] No valid coordinates generated, using fallback")
            return [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

        print(f"[BB] Generated {len(valid_coords)} valid deployment coordinates")
        return valid_coords

    except Exception as e:
        print(f"[BB] Error detecting deployment zone: {e}")
        send_discord_debug_log(f"BB deployment zone detection error: {e}", "ERROR")
        # Fallback coordinates
        return [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]


# Baby Dragon deployment constants
BB_DRAGON_SCREEN_REGION = (200, 100, 2360, 1200)
BB_DRAGON_BOUNDARY_OFFSET = 25  # pixels from red line
BB_DRAGON_SAMPLE_INTERVAL = 50  # pixels between samples
BB_DRAGON_CIRCULARITY_THRESHOLD = 0.4  # max circularity for line-like contours (increased from 0.15)

# HSV red color ranges for deployment boundary detection
# Widened ranges to catch more red variations (lighting, shadows, base skins)
BB_DRAGON_LOWER_RED1 = np.array([0, 70, 80])
BB_DRAGON_UPPER_RED1 = np.array([12, 255, 255])
BB_DRAGON_LOWER_RED2 = np.array([158, 70, 80])
BB_DRAGON_UPPER_RED2 = np.array([180, 255, 255])

# Hough Line detection parameters
BB_DRAGON_HOUGH_MIN_LINE_LENGTH = 60   # Minimum line length in pixels
BB_DRAGON_HOUGH_MAX_LINE_GAP = 50      # Maximum gap to connect segments
BB_DRAGON_HOUGH_THRESHOLD = 40         # Votes threshold for Hough
BB_DRAGON_LINE_MERGE_ANGLE = 15        # Degrees - max angle diff for collinear
BB_DRAGON_LINE_MERGE_DIST = 40         # Pixels - max perpendicular distance
BB_DRAGON_LINE_MERGE_GAP = 100         # Pixels - max endpoint gap to merge


def detect_hough_lines(red_mask):
    """
    Detect straight line segments in the red mask using Hough Transform.

    Args:
        red_mask: Binary mask of detected red pixels

    Returns:
        List of line segments as (x1, y1, x2, y2) tuples
    """
    # Apply Canny edge detection for cleaner lines
    edges = cv2.Canny(red_mask, 50, 150, apertureSize=3)

    # Dilate edges slightly to ensure connectivity
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)

    # Detect lines using Probabilistic Hough Transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=BB_DRAGON_HOUGH_THRESHOLD,
        minLineLength=BB_DRAGON_HOUGH_MIN_LINE_LENGTH,
        maxLineGap=BB_DRAGON_HOUGH_MAX_LINE_GAP
    )

    if lines is None:
        return []

    return [tuple(line[0]) for line in lines]


def filter_lines_by_length(lines, min_length=50):
    """Filter lines to keep only those above minimum length."""
    filtered = []
    for line in lines:
        x1, y1, x2, y2 = line
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        if length >= min_length:
            filtered.append({
                'line': line,
                'length': length,
                'angle': np.arctan2(y2 - y1, x2 - x1)
            })
    return filtered


def are_lines_collinear(line1_data, line2_data):
    """
    Check if two line segments are approximately collinear.
    Uses angle similarity and perpendicular distance.
    """
    # Check angle similarity
    angle_diff = abs(line1_data['angle'] - line2_data['angle'])
    angle_diff = min(angle_diff, np.pi - angle_diff)  # Handle wraparound

    if np.degrees(angle_diff) > BB_DRAGON_LINE_MERGE_ANGLE:
        return False

    # Check perpendicular distance
    x1, y1, x2, y2 = line1_data['line']
    x3, y3, x4, y4 = line2_data['line']

    # Midpoint of line2
    mid_x = (x3 + x4) / 2
    mid_y = (y3 + y4) / 2

    # Distance from midpoint to line1 (extended)
    A = y2 - y1
    B = -(x2 - x1)
    C = (x2 - x1) * y1 - (y2 - y1) * x1

    denom = np.sqrt(A**2 + B**2)
    if denom < 1e-10:
        return False

    dist = abs(A * mid_x + B * mid_y + C) / denom
    return dist < BB_DRAGON_LINE_MERGE_DIST


def get_endpoint_distance(line1, line2):
    """Get minimum distance between any endpoints of two lines."""
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2

    endpoints1 = [(x1, y1), (x2, y2)]
    endpoints2 = [(x3, y3), (x4, y4)]

    min_dist = float('inf')
    for p1 in endpoints1:
        for p2 in endpoints2:
            dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
            min_dist = min(min_dist, dist)

    return min_dist


def merge_collinear_lines(line_data_list):
    """
    Merge line segments that are collinear and close together.
    Returns list of merged line segments.
    """
    if not line_data_list:
        return []

    merged = []
    used = set()

    for i, line1 in enumerate(line_data_list):
        if i in used:
            continue

        # Find all collinear lines close enough to merge
        group = [line1]
        used.add(i)

        for j, line2 in enumerate(line_data_list):
            if j in used:
                continue

            if are_lines_collinear(line1, line2):
                endpoint_dist = get_endpoint_distance(line1['line'], line2['line'])
                if endpoint_dist < BB_DRAGON_LINE_MERGE_GAP:
                    group.append(line2)
                    used.add(j)

        # Merge group into single line using extreme endpoints
        all_points = []
        for line_data in group:
            x1, y1, x2, y2 = line_data['line']
            all_points.extend([(x1, y1), (x2, y2)])

        # Find the two most distant points
        max_dist = 0
        best_pair = (all_points[0], all_points[-1])

        for k, p1 in enumerate(all_points):
            for p2 in all_points[k+1:]:
                dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                if dist > max_dist:
                    max_dist = dist
                    best_pair = (p1, p2)

        merged_line = (int(best_pair[0][0]), int(best_pair[0][1]),
                      int(best_pair[1][0]), int(best_pair[1][1]))
        merged.append(merged_line)

    return merged


def create_line_mask(lines, shape):
    """
    Create a mask image with the detected lines drawn on it.
    Used to filter the original red mask to only keep line regions.
    """
    line_mask = np.zeros(shape, dtype=np.uint8)
    for x1, y1, x2, y2 in lines:
        cv2.line(line_mask, (x1, y1), (x2, y2), 255, thickness=25)
    return line_mask


def sample_points_along_hull(hull_approx, base_center_x, base_center_y, red_mask):
    """
    Sample deployment coordinates evenly along a convex hull's edges.
    Applies radial offset and filters out invalid regions.

    Args:
        hull_approx: Approximated convex hull from cv2.approxPolyDP
        base_center_x: X coordinate of base center (in region coords)
        base_center_y: Y coordinate of base center (in region coords)
        red_mask: Original red mask for no-go zone filtering

    Returns:
        List of (screen_x, screen_y) deployment coordinates
    """
    # Extract hull vertices and close the loop
    hull_points = [hull_approx[i][0] for i in range(len(hull_approx))]
    hull_points.append(hull_points[0])  # Close the loop

    # Calculate cumulative distances along perimeter
    cumulative_distances = [0]
    for i in range(1, len(hull_points)):
        edge_dist = np.sqrt((hull_points[i][0] - hull_points[i-1][0])**2 +
                           (hull_points[i][1] - hull_points[i-1][1])**2)
        cumulative_distances.append(cumulative_distances[-1] + edge_dist)

    total_perimeter = cumulative_distances[-1]
    num_samples = max(int(total_perimeter / BB_DRAGON_SAMPLE_INTERVAL), 8)
    sample_spacing = total_perimeter / num_samples

    print(f"[BB DRAGONS] Perimeter: {total_perimeter:.0f}px, sampling {num_samples} points")

    # Sample at equal intervals along perimeter
    valid_coords = []
    for i in range(num_samples):
        target_dist = i * sample_spacing

        # Find which edge this distance falls on
        for j in range(1, len(cumulative_distances)):
            if cumulative_distances[j] >= target_dist:
                # Interpolate between vertices j-1 and j
                edge_start = cumulative_distances[j-1]
                edge_length = cumulative_distances[j] - edge_start
                t = (target_dist - edge_start) / edge_length if edge_length > 0 else 0

                # Interpolated point on hull edge
                point_x = hull_points[j-1][0] + t * (hull_points[j][0] - hull_points[j-1][0])
                point_y = hull_points[j-1][1] + t * (hull_points[j][1] - hull_points[j-1][1])

                # Vector from base center to interpolated point
                dx = point_x - base_center_x
                dy = point_y - base_center_y

                # Normalize and scale by offset distance
                length = np.sqrt(dx * dx + dy * dy)
                if length > 0:
                    offset_x = int(point_x + (dx / length) * BB_DRAGON_BOUNDARY_OFFSET)
                    offset_y = int(point_y + (dy / length) * BB_DRAGON_BOUNDARY_OFFSET)

                    # Convert to screen coordinates
                    screen_x = offset_x + BB_DRAGON_SCREEN_REGION[0]
                    screen_y = offset_y + BB_DRAGON_SCREEN_REGION[1]

                    valid_coords.append((screen_x, screen_y))
                break

    # Filter out coordinates inside the red boundary
    no_go_zone = cv2.dilate(red_mask, np.ones((15, 15), np.uint8), iterations=1)

    final_coords = []
    for screen_x, screen_y in valid_coords:
        region_x = screen_x - BB_DRAGON_SCREEN_REGION[0]
        region_y = screen_y - BB_DRAGON_SCREEN_REGION[1]

        if 0 <= region_x < no_go_zone.shape[1] and 0 <= region_y < no_go_zone.shape[0]:
            if no_go_zone[region_y, region_x] > 0:
                continue

        final_coords.append((screen_x, screen_y))

    # Filter out unit bar area
    final_coords = filter_out_unit_bar(final_coords)

    # Clamp all coordinates to valid screen bounds
    clamped_coords = []
    for x, y in final_coords:
        clamped_x = max(250, min(x, 2300))
        clamped_y = max(150, min(y, 1150))
        clamped_coords.append((clamped_x, clamped_y))
    final_coords = clamped_coords

    print(f"[BB DRAGONS] Final valid coordinates: {len(final_coords)}")

    if len(final_coords) < 6:
        print("[BB DRAGONS] Not enough coordinates, adding ring fallback")
        ring_coords = generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
        final_coords.extend(ring_coords)

    return final_coords


def generate_ring_fallback_coords(center_x=None, center_y=None, radius=400, num_points=8):
    """
    Generate deployment positions in a ring around base center.
    Used as intermediate fallback before corner positions.

    Args:
        center_x: X coordinate of ring center (in region coords, or None for default)
        center_y: Y coordinate of ring center (in region coords, or None for default)
        radius: Radius of the ring in pixels
        num_points: Number of points to generate around the ring

    Returns:
        List of (screen_x, screen_y) coordinates
    """
    # Default to center of screen region if no center provided
    region_width = BB_DRAGON_SCREEN_REGION[2] - BB_DRAGON_SCREEN_REGION[0]
    region_height = BB_DRAGON_SCREEN_REGION[3] - BB_DRAGON_SCREEN_REGION[1]

    if center_x is None:
        center_x = region_width // 2
    if center_y is None:
        center_y = region_height // 2

    coords = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        x = int(center_x + radius * np.cos(angle))
        y = int(center_y + radius * np.sin(angle))

        # Convert to screen coordinates
        screen_x = x + BB_DRAGON_SCREEN_REGION[0]
        screen_y = y + BB_DRAGON_SCREEN_REGION[1]

        # Clamp to valid screen area (with margin from edges)
        screen_x = max(250, min(screen_x, 2300))
        screen_y = max(150, min(screen_y, 1150))

        coords.append((screen_x, screen_y))

    return coords


def detect_bb_deployment_zone_advanced():
    """
    Detect BB deployment zone using Hough Line Transform + convex hull.
    Uses straight line detection to filter out building blobs, then creates
    a convex hull from the detected boundary lines.
    Returns list of valid deployment coordinates along the boundary.
    """
    try:
        # Capture the game screen area
        screenshot = ImageGrab.grab(bbox=BB_DRAGON_SCREEN_REGION)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Create masks for red color
        mask1 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED1, BB_DRAGON_UPPER_RED1)
        mask2 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED2, BB_DRAGON_UPPER_RED2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Calculate base center for reference
        height, width = screenshot_cv.shape[:2]
        base_center_x = width // 2
        base_center_y = height // 2

        # === HOUGH LINE DETECTION ===
        # Detect straight lines to filter out building blobs
        raw_lines = detect_hough_lines(red_mask)
        print(f"[BB DRAGONS] Hough detected {len(raw_lines)} raw lines")

        if len(raw_lines) >= 4:
            # Filter and merge collinear line segments
            filtered_lines = filter_lines_by_length(raw_lines, min_length=50)
            print(f"[BB DRAGONS] Filtered to {len(filtered_lines)} lines by length")

            if len(filtered_lines) >= 4:
                merged_lines = merge_collinear_lines(filtered_lines)
                print(f"[BB DRAGONS] Merged into {len(merged_lines)} line segments")

                if len(merged_lines) >= 4:
                    # Create a mask from detected lines to filter out building blobs
                    line_mask = create_line_mask(merged_lines, red_mask.shape)

                    # Dilate line mask to capture nearby red pixels
                    line_mask = cv2.dilate(line_mask, np.ones((10, 10), np.uint8), iterations=2)

                    # Keep only red pixels that are near detected straight lines
                    filtered_red_mask = cv2.bitwise_and(red_mask, line_mask)

                    # Dilate the filtered mask to connect fragments
                    kernel = np.ones((5, 5), np.uint8)
                    dilated_mask = cv2.dilate(filtered_red_mask, kernel, iterations=2)

                    # Find contours on the filtered mask
                    contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    if contours:
                        # Combine all line-filtered contours into one hull
                        all_points = np.vstack(contours)
                        print(f"[BB DRAGONS] HOUGH MODE: Using {len(contours)} line-filtered contours")

                        # Skip to hull creation with all_points as contour_to_use
                        contour_to_use = all_points

                        # Jump to hull creation (skip the old tier logic)
                        hull = cv2.convexHull(contour_to_use)
                        epsilon = 0.01 * cv2.arcLength(hull, True)
                        hull_approx = cv2.approxPolyDP(hull, epsilon, True)
                        print(f"[BB DRAGONS] Using convex hull with {len(hull_approx)} vertices")

                        # Sample points along hull edges
                        return sample_points_along_hull(hull_approx, base_center_x, base_center_y, red_mask)

        # === FALLBACK: Original contour-based detection ===
        print("[BB DRAGONS] Hough detection insufficient, falling back to contour method")

        # Dilate to connect fragmented contours
        kernel = np.ones((5, 5), np.uint8)
        dilated_mask = cv2.dilate(red_mask, kernel, iterations=2)

        # Find contours of red lines
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            print("[BB DRAGONS] No red deployment lines detected, using ring fallback")
            return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)

        print(f"[BB DRAGONS] Found {len(contours)} contours")

        # Sort contours by perimeter (largest first)
        contours_with_perimeter = [(cv2.arcLength(c, True), c) for c in contours]
        contours_with_perimeter.sort(reverse=True, key=lambda x: x[0])

        largest_perimeter, largest_contour = contours_with_perimeter[0]
        print(f"[BB DRAGONS] Largest contour perimeter: {largest_perimeter:.0f}px")

        # Minimum perimeter threshold - deployment boundary should be at least 1200px
        MIN_BOUNDARY_PERIMETER = 1200

        # TIER 1: Use largest contour if big enough
        if largest_perimeter >= MIN_BOUNDARY_PERIMETER:
            contour_to_use = largest_contour
            print("[BB DRAGONS] TIER 1: Using largest contour")
        else:
            # TIER 2: Try combining top contours if largest is too small
            print(f"[BB DRAGONS] Largest contour too small ({largest_perimeter:.0f}px), trying multi-contour combination...")

            # Combine top N contours with perimeter > 300px
            significant_contours = [c for perim, c in contours_with_perimeter if perim > 300]

            if len(significant_contours) >= 2:
                # Take up to 5 largest contours and combine their points
                contours_to_combine = significant_contours[:5]
                all_points = np.vstack(contours_to_combine)
                combined_perimeter = sum(cv2.arcLength(c, True) for c in contours_to_combine)
                print(f"[BB DRAGONS] TIER 2: Combining {len(contours_to_combine)} contours (total perimeter: {combined_perimeter:.0f}px)")

                if combined_perimeter >= MIN_BOUNDARY_PERIMETER:
                    contour_to_use = all_points
                else:
                    # TIER 3: Use ring fallback around red mask centroid
                    print("[BB DRAGONS] TIER 3: Combined perimeter still too small, using ring fallback around red centroid")
                    # Calculate centroid of red mask
                    red_points = cv2.findNonZero(red_mask)
                    if red_points is not None and len(red_points) > 0:
                        centroid = np.mean(red_points, axis=0)[0]
                        return generate_ring_fallback_coords(int(centroid[0]), int(centroid[1]), radius=350, num_points=8)
                    else:
                        return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
            else:
                # TIER 3: Not enough contours to combine, use ring fallback
                print("[BB DRAGONS] TIER 3: Not enough contours to combine, using ring fallback")
                red_points = cv2.findNonZero(red_mask)
                if red_points is not None and len(red_points) > 0:
                    centroid = np.mean(red_points, axis=0)[0]
                    return generate_ring_fallback_coords(int(centroid[0]), int(centroid[1]), radius=350, num_points=8)
                else:
                    return generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)

        # Use CONVEX HULL on the selected contour(s)
        hull = cv2.convexHull(contour_to_use)

        # Approximate the hull to reduce points while maintaining shape
        epsilon = 0.01 * cv2.arcLength(hull, True)
        hull_approx = cv2.approxPolyDP(hull, epsilon, True)

        print(f"[BB DRAGONS] Using convex hull with {len(hull_approx)} vertices")

        # Sample points ALONG hull edges (not just at vertices)
        # This ensures even distribution around the perimeter
        valid_coords = []

        # Extract hull vertices and close the loop
        hull_points = [hull_approx[i][0] for i in range(len(hull_approx))]
        hull_points.append(hull_points[0])  # Close the loop

        # Calculate cumulative distances along perimeter
        cumulative_distances = [0]
        for i in range(1, len(hull_points)):
            edge_dist = np.sqrt((hull_points[i][0] - hull_points[i-1][0])**2 +
                               (hull_points[i][1] - hull_points[i-1][1])**2)
            cumulative_distances.append(cumulative_distances[-1] + edge_dist)

        total_perimeter = cumulative_distances[-1]
        num_samples = max(int(total_perimeter / BB_DRAGON_SAMPLE_INTERVAL), 8)
        sample_spacing = total_perimeter / num_samples

        print(f"[BB DRAGONS] Perimeter: {total_perimeter:.0f}px, sampling {num_samples} points at {sample_spacing:.0f}px intervals")

        # Sample at equal intervals along perimeter (interpolating between vertices)
        for i in range(num_samples):
            target_dist = i * sample_spacing

            # Find which edge this distance falls on
            for j in range(1, len(cumulative_distances)):
                if cumulative_distances[j] >= target_dist:
                    # Interpolate between vertices j-1 and j
                    edge_start = cumulative_distances[j-1]
                    edge_length = cumulative_distances[j] - edge_start
                    t = (target_dist - edge_start) / edge_length if edge_length > 0 else 0

                    # Interpolated point on hull edge
                    point_x = hull_points[j-1][0] + t * (hull_points[j][0] - hull_points[j-1][0])
                    point_y = hull_points[j-1][1] + t * (hull_points[j][1] - hull_points[j-1][1])

                    # Vector from base center to interpolated point
                    dx = point_x - base_center_x
                    dy = point_y - base_center_y

                    # Normalize and scale by offset distance
                    length = np.sqrt(dx * dx + dy * dy)
                    if length > 0:
                        offset_x = int(point_x + (dx / length) * BB_DRAGON_BOUNDARY_OFFSET)
                        offset_y = int(point_y + (dy / length) * BB_DRAGON_BOUNDARY_OFFSET)

                        # Convert to screen coordinates
                        screen_x = offset_x + BB_DRAGON_SCREEN_REGION[0]
                        screen_y = offset_y + BB_DRAGON_SCREEN_REGION[1]

                        valid_coords.append((screen_x, screen_y))
                    break

        print(f"[BB DRAGONS] Generated {len(valid_coords)} coordinates before filtering")

        # Final filter: remove coordinates inside the red boundary
        no_go_zone = cv2.dilate(red_mask, np.ones((15, 15), np.uint8), iterations=1)

        final_coords = []
        for screen_x, screen_y in valid_coords:
            region_x = screen_x - BB_DRAGON_SCREEN_REGION[0]
            region_y = screen_y - BB_DRAGON_SCREEN_REGION[1]

            if 0 <= region_x < no_go_zone.shape[1] and 0 <= region_y < no_go_zone.shape[0]:
                if no_go_zone[region_y, region_x] > 0:
                    continue

            final_coords.append((screen_x, screen_y))

        # Also filter out unit bar area
        final_coords = filter_out_unit_bar(final_coords)

        # Clamp all coordinates to valid screen bounds (with safety margins)
        clamped_coords = []
        for x, y in final_coords:
            clamped_x = max(250, min(x, 2300))
            clamped_y = max(150, min(y, 1150))
            clamped_coords.append((clamped_x, clamped_y))
        final_coords = clamped_coords

        print(f"[BB DRAGONS] Final valid coordinates: {len(final_coords)}")

        if len(final_coords) < 6:
            print("[BB DRAGONS] Not enough coordinates after filtering, adding ring fallback positions")
            # Use ring fallback around base center
            ring_coords = generate_ring_fallback_coords(base_center_x, base_center_y, radius=400, num_points=8)
            final_coords.extend(ring_coords)

        return final_coords

    except Exception as e:
        print(f"[BB DRAGONS] Error in advanced deployment zone detection: {e}")
        send_discord_debug_log(f"BB Dragons deployment zone error: {e}", "ERROR")
        # Use ring fallback around screen center on error
        return generate_ring_fallback_coords(radius=400, num_points=8)


def select_equally_spaced_coords(coords, num_points=6, min_distance=150):
    """
    Select N points equally spaced around the boundary with minimum distance enforcement.
    Sorts coordinates by angle from center and picks points ensuring minimum pixel distance.

    Args:
        coords: List of (x, y) coordinates
        num_points: Number of points to select (default 6)
        min_distance: Minimum pixel distance between selected points (default 250)
    """
    import math

    if len(coords) <= num_points:
        return coords

    # Calculate center of all coordinates
    center_x = sum(c[0] for c in coords) / len(coords)
    center_y = sum(c[1] for c in coords) / len(coords)

    # Sort by angle from center (clockwise)
    def angle_from_center(coord):
        return math.atan2(coord[1] - center_y, coord[0] - center_x)

    sorted_coords = sorted(coords, key=angle_from_center)

    def distance(p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def is_far_enough(candidate, selected_points, min_dist):
        """Check if candidate is at least min_dist away from all selected points."""
        for p in selected_points:
            if distance(candidate, p) < min_dist:
                return False
        return True

    # Pick points with minimum distance enforcement
    selected = []
    step = len(sorted_coords) // num_points

    # Start with evenly spaced candidates, but enforce minimum distance
    for i in range(len(sorted_coords)):
        if len(selected) >= num_points:
            break

        # Prefer evenly spaced starting points
        idx = (i * step) % len(sorted_coords)
        candidate = sorted_coords[idx]

        if is_far_enough(candidate, selected, min_distance):
            selected.append(candidate)

    # If we didn't get enough points with strict distance, relax and try again
    if len(selected) < num_points:
        print(f"[BB DRAGONS] Only found {len(selected)} points with {min_distance}px spacing, relaxing constraint...")
        selected = []
        relaxed_distance = 90  # Relaxed minimum distance

        for i in range(len(sorted_coords)):
            if len(selected) >= num_points:
                break
            idx = (i * step) % len(sorted_coords)
            candidate = sorted_coords[idx]

            if is_far_enough(candidate, selected, relaxed_distance):
                selected.append(candidate)

    # Final fallback: just take evenly spaced points regardless of distance
    if len(selected) < num_points:
        print(f"[BB DRAGONS] Still only {len(selected)} points, using basic spacing")
        selected = [sorted_coords[i * step] for i in range(num_points)]

    return selected


def save_bb_dragon_debug_visualization(all_coords, dragon_coords, bm_coord):
    """
    Save debug visualization of BB Gold Baby Dragons deployment detection.
    Creates a 3-panel image: Raw Mask | Mask Overlay | Deployment Positions

    Args:
        all_coords: List of all valid deployment coordinates
        dragon_coords: List of 6 dragon deployment positions
        bm_coord: Battle Machine deployment position (x, y)
    """
    try:
        from datetime import datetime
        import os

        # Ensure output directory exists
        output_dir = "screenshots/debug/bb_deployment_zone"
        os.makedirs(output_dir, exist_ok=True)

        # Capture current screen
        screenshot = ImageGrab.grab(bbox=BB_DRAGON_SCREEN_REGION)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)

        # Detect red boundary (same logic as detect_bb_deployment_zone_advanced)
        mask1 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED1, BB_DRAGON_UPPER_RED1)
        mask2 = cv2.inRange(screenshot_hsv, BB_DRAGON_LOWER_RED2, BB_DRAGON_UPPER_RED2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((5, 5), np.uint8)
        dilated_mask = cv2.dilate(red_mask, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # === PANEL 1: Raw Mask (white on black) ===
        panel1 = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)

        # === PANEL 2: Hough Lines Detection ===
        panel2 = screenshot_cv.copy()

        # Detect and draw Hough lines
        raw_lines = detect_hough_lines(red_mask)
        filtered_lines = filter_lines_by_length(raw_lines, min_length=50) if raw_lines else []
        merged_lines = merge_collinear_lines(filtered_lines) if len(filtered_lines) >= 4 else []

        # Draw raw detected lines in blue (thin)
        for line in raw_lines:
            x1, y1, x2, y2 = line
            cv2.line(panel2, (x1, y1), (x2, y2), (255, 100, 100), 1)

        # Draw merged lines in green (thick)
        for line in merged_lines:
            x1, y1, x2, y2 = line
            cv2.line(panel2, (x1, y1), (x2, y2), (0, 255, 0), 3)

        # === PANEL 3: Deployment positions with hull ===
        panel3 = screenshot_cv.copy()

        # Draw hull if contours found
        hull = None
        largest_perimeter = 0
        if contours:
            contours_with_perimeter = [(cv2.arcLength(c, True), c) for c in contours]
            contours_with_perimeter.sort(reverse=True, key=lambda x: x[0])
            largest_perimeter, largest_contour = contours_with_perimeter[0]

            MIN_BOUNDARY_PERIMETER = 1200
            if largest_perimeter >= MIN_BOUNDARY_PERIMETER:
                hull = cv2.convexHull(largest_contour)
                epsilon = 0.01 * cv2.arcLength(hull, True)
                hull = cv2.approxPolyDP(hull, epsilon, True)
                cv2.drawContours(panel3, [hull], -1, (255, 255, 0), 3)

        # Draw all valid coordinates as small gray circles
        for x, y in all_coords:
            region_x = x - BB_DRAGON_SCREEN_REGION[0]
            region_y = y - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (region_x, region_y), 5, (128, 128, 128), -1)

        # Draw dragon positions as numbered green circles
        for i, (x, y) in enumerate(dragon_coords):
            region_x = x - BB_DRAGON_SCREEN_REGION[0]
            region_y = y - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (region_x, region_y), 15, (0, 255, 0), -1)
            cv2.circle(panel3, (region_x, region_y), 17, (255, 255, 255), 2)
            text = str(i + 1)
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(panel3, text, (region_x - text_w // 2, region_y + text_h // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # Draw Battle Machine position
        if bm_coord:
            bm_region_x = bm_coord[0] - BB_DRAGON_SCREEN_REGION[0]
            bm_region_y = bm_coord[1] - BB_DRAGON_SCREEN_REGION[1]
            cv2.circle(panel3, (bm_region_x, bm_region_y), 15, (0, 165, 255), -1)
            cv2.circle(panel3, (bm_region_x, bm_region_y), 17, (255, 255, 255), 2)
            (text_w, text_h), _ = cv2.getTextSize("BM", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.putText(panel3, "BM", (bm_region_x - text_w // 2, bm_region_y + text_h // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        # === Add labels to each panel ===
        label_y = 30
        cv2.putText(panel1, "1. Raw Mask", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(panel2, "2. Hough Lines", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(panel3, "3. Positions", (10, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Add stats to panel 2 (Hough lines info)
        hough_stats = [
            f"Raw lines: {len(raw_lines)}",
            f"Filtered: {len(filtered_lines)}",
            f"Merged: {len(merged_lines)}",
        ]
        for i, stat in enumerate(hough_stats):
            y_pos = 60 + i * 25
            (text_w, text_h), _ = cv2.getTextSize(stat, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(panel2, (8, y_pos - text_h - 2), (12 + text_w, y_pos + 2), (0, 0, 0), -1)
            cv2.putText(panel2, stat, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Add stats to panel 3
        stats = [
            f"Contours: {len(contours)}",
            f"Largest: {largest_perimeter:.0f}px",
            f"Coords: {len(all_coords)}",
        ]
        for i, stat in enumerate(stats):
            y_pos = 60 + i * 25
            (text_w, text_h), _ = cv2.getTextSize(stat, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(panel3, (8, y_pos - text_h - 2), (12 + text_w, y_pos + 2), (0, 0, 0), -1)
            cv2.putText(panel3, stat, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # === Combine all 3 panels side by side ===
        combined = np.hstack([panel1, panel2, panel3])

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bb_debug_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, combined)

        print(f"[BB DRAGONS DEBUG] Visualization saved to: {filepath}")
        send_discord_debug_log(f"BB Dragons debug visualization saved: {filename}")

    except Exception as e:
        print(f"[BB DRAGONS DEBUG] Error saving visualization: {e}")
        send_discord_debug_log(f"BB Dragons debug visualization error: {e}", "ERROR")


def handle_bb_elixir_mode():
    """Handle BB Elixir mode - detect deployment zone, place one unit, and surrender immediately"""
    send_discord_debug_log("BB Elixir mode: attacking any base")
    gui.log_message("BB Elixir mode: attacking any base")

    # Detect valid deployment zone (outside red lines)
    valid_coords = detect_bb_deployment_zone()

    # Filter out unit bar area (x=1-2553, y=1209-1431)
    valid_coords = filter_out_unit_bar(valid_coords)

    # Safety check: if all coords were filtered out, use fallback
    if not valid_coords:
        print("[BB ELIXIR] WARNING: All coordinates filtered out, using fallback positions")
        send_discord_debug_log("BB Elixir: All coords filtered - using fallback", "WARNING")
        valid_coords = [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

    # Use first troop slot (Builder Base troops)
    KEYS = config.KEYS

    # Try deploying at different coordinates until surrender button appears
    surrender_pos = None
    deployment_attempt = 0

    print("[BB ELIXIR] Starting deployment with surrender button validation...")
    send_discord_debug_log("BB Elixir: Starting deployment loop")

    # Phase 1: Try valid coordinates first (up to 10 attempts)
    while not surrender_pos and deployment_attempt < 10:
        deployment_attempt += 1

        # Choose a random coordinate from valid coordinates
        chosen_coord = random.choice(valid_coords)

        print(f"[BB ELIXIR] Deployment attempt {deployment_attempt}/10 at {chosen_coord}")
        send_discord_debug_log(f"BB Elixir: Attempt {deployment_attempt} at {chosen_coord}")

        # Select troop and try to deploy
        keyboard.send(KEYS['troop1'])
        time.sleep(0.1)
        human_like_move_click(chosen_coord[0], chosen_coord[1])
        time.sleep(0.3)  # Wait briefly for troop to deploy

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)  # Store for later use
            print(f"[BB ELIXIR] {button_type.replace('_', ' ').title()} button detected! Troop successfully deployed at {chosen_coord}")
            send_discord_debug_log(f"BB Elixir: Success - {button_type} button found at ({button_x}, {button_y})")
            break
        else:
            print(f"[BB ELIXIR] Surrender/end battle button not found - invalid placement, trying different location...")

    # Phase 2: If still no success, try random coordinates across entire screen until success
    if not surrender_pos:
        print("[BB ELIXIR] Valid coords failed - trying random screen coordinates until success...")
        send_discord_debug_log("BB Elixir: Switching to random coordinate mode", "WARNING")

        max_random_attempts = 50  # Safety limit
        while not surrender_pos and deployment_attempt < 60:  # 10 + 50 = 60 total max
            deployment_attempt += 1

            # Generate random coordinate (avoid edges and unit bar)
            random_x = random.randint(300, 2200)
            random_y = random.randint(200, 1100)  # Avoid unit bar at bottom

            print(f"[BB ELIXIR] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})")

            # Select troop and try to deploy
            keyboard.send(KEYS['troop1'])
            time.sleep(0.1)
            human_like_move_click(random_x, random_y)
            time.sleep(0.3)

            # Check if surrender or end battle button appeared (deployment successful)
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                print(f"[BB ELIXIR] SUCCESS! Troop deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected")
                send_discord_debug_log(f"BB Elixir: Success with random coords - {button_type} button found")
                surrender_pos = (button_x, button_y)  # Store position for use below
                break

    # Click surrender/end battle button - FAST CLICK for speed
    if surrender_pos:
        print(f"[BB ELIXIR] Clicking battle end button at {surrender_pos}")
        send_discord_debug_log(f"BB Elixir: Clicking battle end button at {surrender_pos}")
        fast_click(*surrender_pos)  # Ultra-fast click
        time.sleep(0.3)  # Reduced from 1s to 0.3s

        # Click confirm button (fixed coordinate) - FAST CLICK for speed
        print("[BB ELIXIR] Clicking confirmation...")
        send_discord_debug_log("BB Elixir: Clicking confirmation")
        fast_click(1483, 898)  # Ultra-fast click
        time.sleep(0.3)  # Reduced from 2s to 0.3s
    else:
        # NO FALLBACK - Detect actual state and handle appropriately
        print("[BB ELIXIR] CRITICAL: Surrender button not found - detecting state...")
        send_discord_debug_log("BB Elixir: Surrender not found - detecting state", "ERROR")

        detected_state = detect_current_game_state()

        if detected_state == 'in_base':
            print("[BB ELIXIR] Already at base - no surrender needed")
            send_discord_debug_log("BB Elixir: Already at base")
        elif detected_state == 'battle_ending' or detected_state == 'end_screen':
            print(f"[BB ELIXIR] Battle already ending ({detected_state}) - no surrender needed")
            send_discord_debug_log(f"BB Elixir: Battle ending - {detected_state}")
        else:
            # Still in battle but can't find surrender - try deploying troop to enable it
            print("[BB ELIXIR] Deploying troop to enable surrender...")
            fast_click(1282, 720)
            time.sleep(2.0)

            # Try finding surrender again
            button_type, x, y = detect_surrender_or_end_battle()
            if button_type == 'surrender':
                print(f"[BB ELIXIR] Surrender now available at {x}, {y}")
                fast_click(x, y)
                time.sleep(0.3)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.3)
            elif button_type == 'end_battle':
                print(f"[BB ELIXIR] Battle ended - clicking end battle")
                fast_click(x, y)
                time.sleep(0.3)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.3)
            else:
                print("[BB ELIXIR] ERROR: Could not find surrender/end battle - waiting for timeout")
                send_discord_debug_log("BB Elixir: No surrender/end battle found - waiting", "ERROR")
                time.sleep(5)  # Wait for potential auto-end

    send_discord_debug_log("BB Elixir: surrendered attack")
    gui.log_message("BB Elixir: surrendered attack")

    # Return home - FAST CLICK for speed
    fast_click(*config.RETURN_BUTTON)  # Ultra-fast click
    time.sleep(1.5)  # Reduced delay (was config.RETURN_DELAY which is 7s)

    # Note: Skip full storage check for BB Elixir - quick surrenders gain minimal loot,
    # so same readings are normal behavior, not an indication of full storages

    # Increment BB Elixir attack counter
    global bb_elixir_attack_count
    settings = gui.get_settings()
    collect_interval = settings.get('bb_collect_interval', 12)
    bb_elixir_attack_count += 1
    print(f"[BB ELIXIR] Attack count: {bb_elixir_attack_count}/{collect_interval}")
    send_discord_debug_log(f"BB Elixir: Attack {bb_elixir_attack_count}/{collect_interval} completed")

    # Collect loot every N attacks (configurable)
    if bb_elixir_attack_count >= collect_interval:
        print(f"[BB ELIXIR] {collect_interval} attacks completed - collecting loot!")
        gui.log_message(f"BB Elixir: {collect_interval} attacks done - collecting loot")
        send_discord_debug_log(f"BB Elixir: {collect_interval} attacks completed - starting loot collection")

        collect_bb_loot()

        # Reset counter
        bb_elixir_attack_count = 0
        print("[BB ELIXIR] Counter reset - starting new cycle")
        send_discord_debug_log("BB Elixir: Loot collected, counter reset to 0")

    return True  # Attack completed


# ============================================================================
# BB GOLD STATE MACHINE - HELPER FUNCTIONS
# ============================================================================

def deploy_bb_gold_baby_dragons(context):
    """
    Deploy 6 Baby Dragons equally spaced around the boundary + Battle Machine.
    Uses advanced deployment zone detection for close-to-boundary placement.

    Args:
        context (dict): State machine context

    Returns:
        bool: True if deployment successful, False otherwise
    """
    print("[BB DRAGONS] Starting Baby Dragons deployment...")
    send_discord_debug_log("BB Gold Baby Dragons: Starting deployment")

    # Zoom out before detecting deployment zone to see full base
    print("[BB DRAGONS] Zooming out for better detection...")
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.15)  # Brief wait for zoom animation

    # Detect valid deployment zone using advanced detection
    all_coords = detect_bb_deployment_zone_advanced()

    if not all_coords or len(all_coords) < 6:
        print("[BB DRAGONS] Not enough deployment coordinates, using ring fallback")
        send_discord_debug_log("BB Dragons: Using ring fallback coordinates", "WARNING")
        # Use ring fallback around screen center
        all_coords = generate_ring_fallback_coords(radius=400, num_points=8)

    # Select 6 equally-spaced coordinates for Baby Dragons
    dragon_coords = select_equally_spaced_coords(all_coords, num_points=6)
    print(f"[BB DRAGONS] Selected {len(dragon_coords)} equally-spaced positions")

    # Pre-calculate Battle Machine position for potential debug visualization
    remaining_coords = [c for c in all_coords if c not in dragon_coords]
    if remaining_coords:
        bm_coord = random.choice(remaining_coords)
    else:
        bm_coord = (1250, 650)  # Center fallback

    # Save debug visualization if enabled
    if gui.get_settings().get('bb_gold_dragon_debug_positions', False):
        print("[BB DRAGONS] Debug mode enabled - saving position visualization...")
        save_bb_dragon_debug_visualization(all_coords, dragon_coords, bm_coord)

    KEYS = config.KEYS
    surrender_pos = None

    # === DEPLOY BATTLE MACHINE FIRST ===
    print(f"[BB DRAGONS] Deploying Battle Machine first at {bm_coord}...")
    keyboard.send(KEYS['queen'])  # 'q' key
    time.sleep(0.02)
    turbo_move_cursor(bm_coord[0], bm_coord[1])
    turbo_fast_click()
    time.sleep(0.3)  # Brief wait to check for surrender button

    # Check if surrender button appeared (deployment successful)
    button_type, button_x, button_y = detect_surrender_or_end_battle()

    if button_type:
        surrender_pos = (button_x, button_y)
        context['surrender_button_cached'] = True
        context['surrender_button_pos'] = surrender_pos
        context['surrender_button_type'] = button_type
        print(f"[BB DRAGONS] Battle Machine deployed successfully - {button_type} button detected")
        gui.update_bb_gold_state('BATTLE_ACTIVE')
    else:
        # Try fallback position for BM
        print("[BB DRAGONS] BM position failed, trying fallback...")
        fallback_coord = (1250, 200)  # Top center
        keyboard.send(KEYS['queen'])
        time.sleep(0.02)
        turbo_move_cursor(fallback_coord[0], fallback_coord[1])
        turbo_fast_click()
        time.sleep(0.3)

        button_type, button_x, button_y = detect_surrender_or_end_battle()
        if button_type:
            surrender_pos = (button_x, button_y)
            context['surrender_button_cached'] = True
            context['surrender_button_pos'] = surrender_pos
            context['surrender_button_type'] = button_type
            bm_coord = fallback_coord
            print(f"[BB DRAGONS] BM fallback deployment successful")
            gui.update_bb_gold_state('BATTLE_ACTIVE')
        else:
            print("[BB DRAGONS] CRITICAL: Failed to deploy Battle Machine!")
            send_discord_debug_log("BB Dragons: CRITICAL - Failed to deploy BM", "ERROR")
            return False

    # Activate Battle Machine ability immediately
    print("[BB DRAGONS] Activating Battle Machine ability...")
    keyboard.send('q')
    context['battle_machine_ability_time'] = time.time()

    # === DEPLOY ALL 6 BABY DRAGONS AT ONCE ===
    print("[BB DRAGONS] Deploying all 6 Baby Dragons (turbo mode)...")
    for i in range(6):
        dragon_num = i + 1
        coord = dragon_coords[i] if i < len(dragon_coords) else random.choice(all_coords)

        keyboard.send(str(dragon_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay for key registration
        turbo_move_cursor(coord[0], coord[1])
        turbo_fast_click()
        time.sleep(0.02)  # Minimal delay between dragons

    print("[BB DRAGONS] All 6 Baby Dragons deployed")
    send_discord_debug_log("BB Dragons: All 6 dragons deployed")

    # Wait before casting abilities (dragons need time to spread out)
    print("[BB DRAGONS] Waiting before casting abilities...")
    time.sleep(4.3)

    # Cast all 6 Baby Dragon abilities (rapid fire)
    for ability_num in range(1, 7):
        keyboard.send(str(ability_num))
        time.sleep(0.02)

    print("[BB DRAGONS] All abilities cast")
    send_discord_debug_log("BB Dragons: All abilities cast")

    print("[BB DRAGONS] Deployment complete!")
    send_discord_debug_log("BB Dragons: Deployment complete - BM ability activated")

    return True


def deploy_bb_gold_troops(context):
    """
    Deploy troops for BB Gold mode based on selected troop mode.

    Args:
        context (dict): State machine context

    Returns:
        bool: True if deployment successful (surrender button appeared), False otherwise

    Supports three modes:
    - night_witches: Battle Machine + 6 Night Witches (default)
    - bomber_night_witches: Bomber + Battle Machine + Night Witches (22s ability recast)
    - baby_dragons: 6 Baby Dragons spread out + Battle Machine (14s ability recast)
    """
    # Check troop mode setting
    troop_mode = gui.get_settings().get('bb_gold_troop_mode', 'night_witches')
    print(f"[BB GOLD DEPLOY] Troop mode: {troop_mode}")

    # Route to appropriate deployment function based on mode
    if troop_mode == 'baby_dragons':
        return deploy_bb_gold_baby_dragons(context)

    # For night_witches and bomber_night_witches, use the standard deployment below
    # (bomber mode uses same deployment, just tracks bomber ability separately)

    # Detect valid deployment zone (outside red lines)
    valid_coords = detect_bb_deployment_zone()

    # Filter out unit bar area (x=1-2553, y=1209-1431)
    valid_coords = filter_out_unit_bar(valid_coords)

    # Safety check: if all coords were filtered out, use fallback
    if not valid_coords:
        print("[BB GOLD DEPLOY] WARNING: All coordinates filtered out, using fallback positions")
        send_discord_debug_log("BB Gold: All coords filtered - using fallback", "WARNING")
        valid_coords = [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

    # Randomly choose deployment position from valid coordinates
    if valid_coords:
        deployment_coord = random.choice(valid_coords)
        print(f"[BB GOLD DEPLOY] Using deployment position: {deployment_coord} (randomly selected from {len(valid_coords)} options)")
        send_discord_debug_log(f"BB Gold: Deploying at randomly selected position {deployment_coord}")
    else:
        deployment_coord = (300, 300)  # Fallback to top-left corner
        print("[BB GOLD DEPLOY] WARNING: No valid coords detected, using fallback corner")
        send_discord_debug_log("BB Gold: Using fallback corner position", "WARNING")

    KEYS = config.KEYS

    # Try deploying at the chosen coordinate until surrender button appears
    surrender_pos = None
    deployment_attempt = 0

    print("[BB GOLD DEPLOY] Deploying Battle Machine...")
    send_discord_debug_log("BB Gold: Deploying Battle Machine")

    # Phase 1: Try valid coordinates first (up to 10 attempts)
    while not surrender_pos and deployment_attempt < 10:
        deployment_attempt += 1
        print(f"[BB GOLD DEPLOY] Deployment attempt {deployment_attempt}/10 at {deployment_coord}")

        # Deploy Battle Machine (q)
        keyboard.send(KEYS['queen'])  # 'q' key for Battle Machine
        time.sleep(0.2)
        human_like_move_click(deployment_coord[0], deployment_coord[1])
        time.sleep(0.5)

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)
            # CACHE surrender button position for fast clicking later (2-star path)
            context['surrender_button_cached'] = True
            context['surrender_button_pos'] = surrender_pos
            context['surrender_button_type'] = button_type
            print(f"[BB GOLD DEPLOY] Battle Machine deployed successfully at {deployment_coord} ({button_type} button detected)")
            print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
            send_discord_debug_log(f"BB Gold: Battle Machine deployed - {button_type} button cached at {surrender_pos}")
            # Update GUI to show BATTLE_ACTIVE immediately
            gui.update_bb_gold_state('BATTLE_ACTIVE')
            break
        else:
            print(f"[BB GOLD DEPLOY] Surrender/end battle button not found - invalid placement, trying again...")
            # Try a different random valid coordinate for next attempt
            if valid_coords:
                deployment_coord = random.choice(valid_coords)

    # Phase 2: If still no success, try random coordinates across entire screen until success
    if not surrender_pos:
        print("[BB GOLD DEPLOY] Valid coords failed - trying random screen coordinates until success...")
        send_discord_debug_log("BB Gold: Switching to random coordinate mode", "WARNING")

        max_random_attempts = 20  # Safety limit
        while not surrender_pos and deployment_attempt < 30:  # 10 + 20 = 30 total max
            deployment_attempt += 1

            # Generate random coordinate (avoid edges and unit bar)
            random_x = random.randint(300, 2200)
            random_y = random.randint(200, 1100)  # Avoid unit bar at bottom

            print(f"[BB GOLD DEPLOY] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})")

            # Deploy Battle Machine
            keyboard.send(KEYS['queen'])
            time.sleep(0.2)
            human_like_move_click(random_x, random_y)
            time.sleep(0.5)

            # Check if surrender or end battle button appeared
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                surrender_pos = (button_x, button_y)
                # CACHE surrender button position for fast clicking later (2-star path)
                context['surrender_button_cached'] = True
                context['surrender_button_pos'] = surrender_pos
                context['surrender_button_type'] = button_type
                print(f"[BB GOLD DEPLOY] SUCCESS! Battle Machine deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected")
                print(f"[BB GOLD DEPLOY] ✓ Cached {button_type} button at {surrender_pos} for instant surrender")
                send_discord_debug_log(f"BB Gold: Success with random coords - {button_type} button cached at {surrender_pos}")
                # Update GUI to show BATTLE_ACTIVE immediately
                gui.update_bb_gold_state('BATTLE_ACTIVE')
                deployment_coord = (random_x, random_y)  # Update deployment coord for Night Witches
                break

    if not surrender_pos:
        print("[BB GOLD DEPLOY] CRITICAL: Failed to deploy Battle Machine after 30 attempts!")
        send_discord_debug_log("BB Gold: CRITICAL - Failed to deploy after 30 attempts", "ERROR")
        return False

    # Activate Battle Machine ability immediately after deployment
    print("[BB GOLD DEPLOY] Activating Battle Machine ability...")
    send_discord_debug_log("BB Gold: Activating Battle Machine ability")
    keyboard.send('q')  # Battle Machine ability key
    context['battle_machine_ability_time'] = time.time()  # Track when ability was used
    time.sleep(0.2)

    # Deploy all 6 Night Witches at the same position - FAST DEPLOYMENT
    print("[BB GOLD DEPLOY] Deploying 6 Night Witches...")
    send_discord_debug_log("BB Gold: Deploying 6 Night Witches")

    for witch_num in range(1, 7):
        keyboard.send(str(witch_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay
        fast_click(deployment_coord[0], deployment_coord[1])  # Ultra-fast click
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD DEPLOY] All Night Witches deployed")
    send_discord_debug_log("BB Gold: All 6 Night Witches deployed")

    # Wait 3 seconds before casting abilities
    print("[BB GOLD DEPLOY] Waiting 3 seconds before casting abilities...")
    time.sleep(3)

    # Cast abilities for all 6 Night Witches - FAST CASTING
    print("[BB GOLD DEPLOY] Casting Night Witch abilities...")
    send_discord_debug_log("BB Gold: Casting abilities")

    for ability_num in range(1, 7):
        keyboard.send(str(ability_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD DEPLOY] All abilities cast - troops deployed successfully")
    send_discord_debug_log("BB Gold: All abilities cast - deployment complete")

    # Set bomber ability timer after casting (bomber ability was cast when key '1' was pressed)
    if troop_mode == 'bomber_night_witches':
        context['bomber_ability_time'] = time.time()
        print("[BB GOLD DEPLOY] Bomber ability timer started (22s recast)")

    return True


def monitor_bb_gold_battle(context):
    """
    Monitor BB Gold battle for 2/3 stars or Return Home button (battle ended).

    Args:
        context (dict): State machine context with attack_start_time, battle_machine_ability_time

    Returns:
        dict: {'stars': int, 'timeout_without_stars': bool, 'return_home_pos': tuple or None}

    Uses Return Home button detection instead of fixed timeout for immediate
    battle end detection. This is more responsive and works for all end scenarios.
    """
    max_wait_time = 180  # Maximum 3 minutes to get stars
    start_time = time.time()
    battle_machine_ability_time = context.get('battle_machine_ability_time')
    last_return_home_check = 0  # Track last Return Home check time
    return_home_check_interval = 2.0  # Check every 2 seconds to reduce overhead

    result = {
        'stars': 0,
        'timeout_without_stars': False,
        'return_home_pos': None
    }

    print("[BB GOLD MONITOR] Monitoring for 2/3 stars or battle end...")
    gui.log_message("BB Gold: Monitoring for 2/3 stars...")

    while (time.time() - start_time) < max_wait_time:
        current_time = time.time()

        # Check for Return Home button (battle ended without 2+ stars)
        # This replaces the fixed 80-second timeout with immediate detection
        if current_time - last_return_home_check >= return_home_check_interval:
            last_return_home_check = current_time
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                result['timeout_without_stars'] = True
                result['return_home_pos'] = return_home_pos
                print(f"[BB GOLD MONITOR] Return Home button detected at {return_home_pos} - battle ended without stars")
                gui.log_message("BB Gold: Battle ended - returning home")
                send_discord_debug_log("BB Gold: Return Home detected - battle ended without stars")
                break

        # Re-activate Battle Machine ability every 14 seconds if battle is still ongoing
        if (battle_machine_ability_time is not None and
            current_time - battle_machine_ability_time >= 14):
            print("[BB GOLD MONITOR] 14 seconds elapsed - re-activating Battle Machine ability...")
            send_discord_debug_log("BB Gold: Re-activating Battle Machine ability after 14 seconds")
            keyboard.send('q')  # Re-activate Battle Machine ability
            battle_machine_ability_time = current_time  # Reset timer for next activation
            context['battle_machine_ability_time'] = current_time
            time.sleep(0.2)

        # Re-activate Bomber ability every 22 seconds if enabled and battle is still ongoing
        bomber_ability_time = context.get('bomber_ability_time')
        if (bomber_ability_time is not None and
            current_time - bomber_ability_time >= 22):
            print("[BB GOLD MONITOR] 22 seconds elapsed - re-activating Bomber ability...")
            send_discord_debug_log("BB Gold: Re-activating Bomber ability after 22 seconds")
            keyboard.send('1')  # Re-activate Bomber ability (slot 1)
            context['bomber_ability_time'] = current_time
            time.sleep(0.2)

        # Check for 2 stars first (most common case) with double verification (optimized from 3x)
        two_star_verification = sum(1 for _ in range(2) if detect_two_stars())

        if two_star_verification >= 2:  # If both checks passed
            # Check if "try for 3 stars" is enabled for Baby Dragons
            try_3_stars = gui.get_settings().get('bb_gold_try_3_stars', False)
            troop_mode = gui.get_settings().get('bb_gold_troop_mode', 'night_witches')

            if try_3_stars and troop_mode == 'baby_dragons':
                # Skip 2-star exit, continue monitoring for 3 stars
                if result['stars'] < 2:  # Only log once when first reaching 2 stars
                    result['stars'] = 2
                    print("[BB GOLD MONITOR] 2 STARS DETECTED! Continuing for 3 stars...")
                    gui.log_message("BB Gold: 2 stars - trying for 3...")
                    send_discord_debug_log("BB Gold: 2 stars detected - continuing for 3 stars")
                # Don't break - continue monitoring for 3 stars or Return Home
            else:
                result['stars'] = 2
                print("[BB GOLD MONITOR] 2 STARS DETECTED! Surrendering immediately...")
                gui.log_message("BB Gold: 2 stars detected - surrendering")
                send_discord_debug_log("BB Gold: 2 stars detected - surrendering immediately")
                break

        # Check for 3 stars (rare edge case - Builder Hall destroyed last before 2nd star appears)
        three_star_verification = sum(1 for _ in range(2) if detect_three_stars())

        if three_star_verification >= 2:  # If both checks passed
            result['stars'] = 3
            print("[BB GOLD MONITOR] 3 STARS DETECTED! (Builder Hall was last building)")
            gui.log_message("BB Gold: 3 stars detected!")
            send_discord_debug_log("BB Gold: 3 stars detected - waiting 7 seconds before ending")

            # Wait 7 seconds as requested for 3 stars
            print("[BB GOLD MONITOR] Waiting 7 seconds...")
            time.sleep(7)
            break

        time.sleep(0.5)  # Check every ~0.5 seconds

    if result['stars'] == 0 and not result['timeout_without_stars']:
        print("[BB GOLD MONITOR] WARNING: 2/3 stars not detected after 3 minutes, ending battle anyway")
        gui.log_message("BB Gold: Timeout - ending battle")
        send_discord_debug_log("BB Gold: Timeout waiting for stars - ending battle anyway", "WARNING")

    return result


def end_bb_gold_battle(stars_detected, context=None):
    """
    End BB Gold battle by clicking surrender (2 stars) or end battle (3 stars).

    Args:
        stars_detected (int): Number of stars detected (0, 1, 2, or 3)
        context (dict, optional): State machine context with cached surrender button position

    Returns:
        dict: {'success': bool, 'final_stars': int}

    Extracts end battle logic from original handle_bb_gold_mode()
    """
    result = {'success': False, 'final_stars': stars_detected}

    # Check if we have a cached surrender button position (from deployment)
    cached_available = context and context.get('surrender_button_cached', False)
    if cached_available:
        cached_pos = context.get('surrender_button_pos')
        cached_type = context.get('surrender_button_type', 'surrender')
        print(f"[BB GOLD END] ✓ Using cached {cached_type} button at {cached_pos}")
        send_discord_debug_log(f"BB Gold: Using cached {cached_type} button from deployment")

    if stars_detected == 3:
        # 3 STAR PATH - use end battle button (surrender not available with 3 stars)
        print("[BB GOLD END] 3 stars achieved - detecting end battle button...")
        send_discord_debug_log("BB Gold: 3 stars - using end battle button")

        end_battle_pos = detect_end_battle_button()

        if end_battle_pos:
            print(f"[BB GOLD END] Clicking end battle button at {end_battle_pos}")
            send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
            fast_click(*end_battle_pos)

            # Click confirm button
            print("[BB GOLD END] Clicking end battle confirmation...")
            send_discord_debug_log("BB Gold: Clicking end battle confirmation")
            fast_click(1483, 898)
            time.sleep(0.8)  # Optimized: reduced from 1.5s

            print("[BB GOLD END] 3-star battle ended successfully")
            send_discord_debug_log("BB Gold: 3-star battle ended")
            result['success'] = True
            return result
        else:
            # NO FALLBACK - Return failure so state machine can handle it
            print("[BB GOLD END] ERROR: End battle button not detected - cannot proceed")
            send_discord_debug_log("BB Gold: End battle button not found - returning failure", "ERROR")
            result['success'] = False
            return result

    elif stars_detected == 2:
        # 2 STAR PATH - use cached position if available, otherwise detect
        if cached_available:
            # Use cached position from deployment (INSTANT - no detection delay)
            button_type = cached_type
            button_x, button_y = cached_pos
            print(f"[BB GOLD END] 2 stars achieved - using CACHED {button_type} button")
            send_discord_debug_log(f"BB Gold: 2 stars - using cached {button_type} button (instant)")
        else:
            # No cache - detect button (slower)
            print("[BB GOLD END] 2 stars achieved - detecting surrender/end battle button...")
            send_discord_debug_log("BB Gold: 2 stars - detecting surrender/end battle button")
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            # Click surrender/end battle button - FAST CLICK for speed
            if not button_type:
                # NO FALLBACK - Return failure so state machine can handle it
                print("[BB GOLD END] ERROR: Surrender button not detected - cannot proceed")
                send_discord_debug_log("BB Gold: Surrender button not found - returning failure", "ERROR")
                result['success'] = False
                return result

        print(f"[BB GOLD END] Clicking {button_type} button at ({button_x}, {button_y})")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} at ({button_x}, {button_y})")
        fast_click(button_x, button_y)

        # Click confirm button
        print(f"[BB GOLD END] Clicking {button_type} confirmation...")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} confirmation")
        fast_click(1483, 898)
        time.sleep(0.8)  # Optimized: reduced from 1.5s

        # After surrender attempt, check if 3 stars appeared (Builder Hall destroyed during surrender)
        print("[BB GOLD END] Checking if 3 stars appeared after surrender attempt...")
        three_star_check = sum(1 for _ in range(3) if detect_three_stars())

        if three_star_check >= 2:
            # Edge case: Builder Hall was destroyed while clicking surrender
            # Surrender is NEGATED by 3 stars - must click end battle button instead
            result['final_stars'] = 3
            print("[BB GOLD END] 3 STARS DETECTED after surrender attempt! (Builder Hall destroyed during surrender)")
            gui.log_message("BB Gold: 3 stars appeared during surrender")
            send_discord_debug_log("BB Gold: 3 stars appeared after surrender - clicking end battle")

            # Must click end battle button since surrender was negated
            print("[BB GOLD END] Detecting end battle button (surrender negated by 3 stars)...")
            end_battle_pos = detect_end_battle_button()

            if not end_battle_pos:
                # NO FALLBACK - Return failure so state machine can handle it
                print("[BB GOLD END] ERROR: End battle button not detected (post-surrender 3 stars) - cannot proceed")
                send_discord_debug_log("BB Gold: End battle button not found (post-surrender) - returning failure", "ERROR")
                result['success'] = False
                return result

            print(f"[BB GOLD END] Clicking end battle button at {end_battle_pos}")
            send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
            time.sleep(2.5)  # Wait for game to process 3-star state after surrender was negated
            fast_click(*end_battle_pos)

            # Click confirm button
            print("[BB GOLD END] Clicking end battle confirmation...")
            send_discord_debug_log("BB Gold: Clicking end battle confirmation")
            fast_click(1483, 898)
            time.sleep(0.8)  # Optimized: reduced from 1.5s

            print("[BB GOLD END] Post-surrender 3-star battle ended successfully")
            send_discord_debug_log("BB Gold: Post-surrender 3-star battle ended")
        else:
            print("[BB GOLD END] Surrender successful (2 stars)")
            send_discord_debug_log("BB Gold: surrendered successfully with 2 stars")

        result['success'] = True
        return result

    else:
        # 0/1 STAR PATH - use cached position if available, otherwise detect
        if cached_available:
            # Use cached position from deployment (INSTANT - no detection delay)
            button_type = cached_type
            button_x, button_y = cached_pos
            print(f"[BB GOLD END] {stars_detected} stars - using CACHED {button_type} button")
            send_discord_debug_log(f"BB Gold: {stars_detected} stars - using cached {button_type} button (instant)")
        else:
            # No cache - detect button (slower)
            print(f"[BB GOLD END] {stars_detected} stars - detecting surrender/end battle button...")
            send_discord_debug_log(f"BB Gold: {stars_detected} stars - detecting surrender/end battle button")
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if not button_type:
                # NO FALLBACK - Return failure so state machine can handle it
                print(f"[BB GOLD END] ERROR: No surrender/end battle button found ({stars_detected} stars)")
                send_discord_debug_log(f"BB Gold: No button found ({stars_detected} stars) - returning failure", "ERROR")
                result['success'] = False
                return result

        print(f"[BB GOLD END] Clicking {button_type} button at ({button_x}, {button_y})")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} at ({button_x}, {button_y})")
        fast_click(button_x, button_y)

        # Click confirm button
        print(f"[BB GOLD END] Clicking {button_type} confirmation...")
        send_discord_debug_log(f"BB Gold: Clicking {button_type} confirmation")
        fast_click(1483, 898)
        time.sleep(0.8)

        print(f"[BB GOLD END] Battle ended successfully ({stars_detected} stars)")
        send_discord_debug_log(f"BB Gold: Battle ended with {stars_detected} stars")
        result['success'] = True
        return result


def increment_bb_gold_counter():
    """
    Increment BB Gold attack counter and collect loot if interval reached.
    Extracts counter logic from original handle_bb_gold_mode().
    """
    global bb_gold_attack_count
    settings = gui.get_settings()
    collect_interval = settings.get('bb_collect_interval', 12)
    bb_gold_attack_count += 1

    print(f"[BB GOLD] Attack count: {bb_gold_attack_count}/{collect_interval}")
    send_discord_debug_log(f"BB Gold: Attack {bb_gold_attack_count}/{collect_interval} completed")

    # Collect loot every N attacks (configurable)
    if bb_gold_attack_count >= collect_interval:
        print(f"[BB GOLD] {collect_interval} attacks completed - collecting loot!")
        gui.log_message(f"BB Gold: {collect_interval} attacks done - collecting loot")
        send_discord_debug_log(f"BB Gold: {collect_interval} attacks completed - starting loot collection")

        collect_bb_loot()

        # Reset counter
        bb_gold_attack_count = 0
        print("[BB GOLD] Counter reset - starting new cycle")
        send_discord_debug_log("BB Gold: Loot collected, counter reset to 0")


def handle_bb_gold_mode_legacy():
    """
    Handle BB Gold mode - deploy Battle Machine + Night Witches far from red lines,
    wait for 2 stars, then surrender immediately.

    LEGACY VERSION - Kept as backup. Use handle_bb_gold_mode_stateful() instead.
    """
    send_discord_debug_log("BB Gold mode: starting attack")
    gui.log_message("BB Gold mode: starting attack")

    # Detect valid deployment zone (outside red lines)
    valid_coords = detect_bb_deployment_zone()

    # Filter out unit bar area (x=1-2553, y=1209-1431)
    valid_coords = filter_out_unit_bar(valid_coords)

    # Safety check: if all coords were filtered out, use fallback
    if not valid_coords:
        print("[BB GOLD] WARNING: All coordinates filtered out, using fallback positions")
        send_discord_debug_log("BB Gold: All coords filtered - using fallback", "WARNING")
        valid_coords = [(300, 300), (300, 1000), (2200, 300), (2200, 1000)]

    # Randomly choose deployment position from valid coordinates
    if valid_coords:
        deployment_coord = random.choice(valid_coords)  # Random position each attack
        print(f"[BB GOLD] Using deployment position: {deployment_coord} (randomly selected from {len(valid_coords)} options)")
        send_discord_debug_log(f"BB Gold: Deploying at randomly selected position {deployment_coord}")
    else:
        deployment_coord = (300, 300)  # Fallback to top-left corner
        print("[BB GOLD] WARNING: No valid coords detected, using fallback corner")
        send_discord_debug_log("BB Gold: Using fallback corner position", "WARNING")

    KEYS = config.KEYS

    # Try deploying at the chosen coordinate until surrender button appears
    surrender_pos = None
    deployment_attempt = 0

    print("[BB GOLD] Deploying Battle Machine...")
    send_discord_debug_log("BB Gold: Deploying Battle Machine")

    # Phase 1: Try valid coordinates first (up to 10 attempts)
    while not surrender_pos and deployment_attempt < 10:
        deployment_attempt += 1
        print(f"[BB GOLD] Deployment attempt {deployment_attempt}/10 at {deployment_coord}")

        # Deploy Battle Machine (q)
        keyboard.send(KEYS['queen'])  # 'q' key for Battle Machine
        time.sleep(0.2)
        human_like_move_click(deployment_coord[0], deployment_coord[1])
        time.sleep(0.5)

        # Check if surrender or end battle button appeared (meaning troop was successfully placed)
        button_type, button_x, button_y = detect_surrender_or_end_battle()

        if button_type:
            surrender_pos = (button_x, button_y)
            print(f"[BB GOLD] Battle Machine deployed successfully at {deployment_coord} ({button_type} button detected)")
            send_discord_debug_log(f"BB Gold: Battle Machine deployed - {button_type} button found")
            break
        else:
            print(f"[BB GOLD] Surrender/end battle button not found - invalid placement, trying again...")
            # Try a different random valid coordinate for next attempt
            if valid_coords:
                deployment_coord = random.choice(valid_coords)

    # Phase 2: If still no success, try random coordinates across entire screen until success
    if not surrender_pos:
        print("[BB GOLD] Valid coords failed - trying random screen coordinates until success...")
        send_discord_debug_log("BB Gold: Switching to random coordinate mode", "WARNING")

        max_random_attempts = 20  # Safety limit (reduced from 50)
        while not surrender_pos and deployment_attempt < 30:  # 10 + 20 = 30 total max
            deployment_attempt += 1

            # Generate random coordinate (avoid edges and unit bar)
            random_x = random.randint(300, 2200)
            random_y = random.randint(200, 1100)  # Avoid unit bar at bottom

            print(f"[BB GOLD] Random attempt {deployment_attempt - 10}/{max_random_attempts} at ({random_x}, {random_y})")

            # Deploy Battle Machine
            keyboard.send(KEYS['queen'])
            time.sleep(0.2)
            human_like_move_click(random_x, random_y)
            time.sleep(0.5)

            # Check if surrender or end battle button appeared
            button_type, button_x, button_y = detect_surrender_or_end_battle()

            if button_type:
                surrender_pos = (button_x, button_y)
                print(f"[BB GOLD] SUCCESS! Battle Machine deployed at random coordinate ({random_x}, {random_y}), {button_type} button detected")
                send_discord_debug_log(f"BB Gold: Success with random coords - {button_type} button found")
                deployment_coord = (random_x, random_y)  # Update deployment coord for Night Witches
                break

    # Track Battle Machine ability activation time
    battle_machine_ability_time = None
    last_return_home_check = 0  # Track last Return Home button check time

    if not surrender_pos:
        print("[BB GOLD] CRITICAL: Failed to deploy Battle Machine after 30 attempts!")
        print("[BB GOLD] Likely still at base - restarting attack sequence...")
        send_discord_debug_log("BB Gold: CRITICAL - Failed to deploy after 30 attempts, restarting sequence", "ERROR")
        gui.log_message("BB Gold: Deployment failed - restarting")
        return False  # Signal to restart attack sequence
    else:
        # Activate Battle Machine ability immediately after deployment
        print("[BB GOLD] Activating Battle Machine ability...")
        send_discord_debug_log("BB Gold: Activating Battle Machine ability")
        keyboard.send('q')  # Battle Machine ability key
        battle_machine_ability_time = time.time()  # Track when ability was used
        time.sleep(0.2)

    # Deploy all 6 Night Witches at the same position - FAST DEPLOYMENT
    print("[BB GOLD] Deploying 6 Night Witches...")
    send_discord_debug_log("BB Gold: Deploying 6 Night Witches")

    for witch_num in range(1, 7):
        keyboard.send(str(witch_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay
        fast_click(deployment_coord[0], deployment_coord[1])  # Ultra-fast click
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD] All Night Witches deployed")
    send_discord_debug_log("BB Gold: All 6 Night Witches deployed")

    # Wait 3 seconds before casting abilities
    print("[BB GOLD] Waiting 3 seconds before casting abilities...")
    time.sleep(3)

    # Cast abilities for all 6 Night Witches - FAST CASTING
    print("[BB GOLD] Casting Night Witch abilities...")
    send_discord_debug_log("BB Gold: Casting abilities")

    for ability_num in range(1, 7):
        keyboard.send(str(ability_num))  # Keys 1-6
        time.sleep(0.02)  # Minimal delay

    print("[BB GOLD] All abilities cast")
    send_discord_debug_log("BB Gold: All abilities cast - monitoring for 2/3 stars")

    # Monitor for 2 or 3 stars with verification
    max_wait_time = 180  # Maximum 3 minutes to get stars
    start_time = time.time()
    stars_detected = False
    three_stars_detected = False
    battle_lost = False  # Flag for battle ended (Return Home button detected)
    return_home_check_interval = 2.0  # Check every 2 seconds to reduce overhead
    cached_return_home_pos = None  # Cache detected Return Home button position

    print("[BB GOLD] Monitoring for 2/3 stars or battle end...")
    gui.log_message("BB Gold: Monitoring for 2/3 stars...")

    while not stars_detected and (time.time() - start_time) < max_wait_time:
        current_time = time.time()

        # Check for Return Home button (battle ended without 2+ stars)
        # This replaces the fixed 80-second timeout with immediate detection
        if current_time - last_return_home_check >= return_home_check_interval:
            last_return_home_check = current_time
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                battle_lost = True
                cached_return_home_pos = return_home_pos
                print(f"[BB GOLD] Return Home button detected at {return_home_pos} - battle ended without stars")
                gui.log_message("BB Gold: Battle ended - returning home")
                send_discord_debug_log("BB Gold: Return Home detected - battle ended without stars")
                break

        # Re-activate Battle Machine ability every 15 seconds if battle is still ongoing
        if (battle_machine_ability_time is not None and
            current_time - battle_machine_ability_time >= 15):
            print("[BB GOLD] 15 seconds elapsed - re-activating Battle Machine ability...")
            send_discord_debug_log("BB Gold: Re-activating Battle Machine ability after 15 seconds")
            keyboard.send('q')  # Re-activate Battle Machine ability
            battle_machine_ability_time = current_time  # Reset timer for next activation
            time.sleep(0.2)

        # Check for 2 stars first (most common case) with triple verification
        two_star_verification = 0
        for _ in range(3):
            if detect_two_stars():
                two_star_verification += 1
            # time.sleep(0.2)

        if two_star_verification >= 2:  # If 2 out of 3 checks passed
            stars_detected = True
            print("[BB GOLD] 2 STARS DETECTED! Surrendering immediately...")
            gui.log_message("BB Gold: 2 stars detected - surrendering")
            send_discord_debug_log("BB Gold: 2 stars detected - surrendering immediately")
            break

        # Check for 3 stars (rare edge case - Builder Hall destroyed last before 2nd star appears)
        three_star_verification = 0
        for _ in range(3):
            if detect_three_stars():
                three_star_verification += 1
            # time.sleep(0.2)

        if three_star_verification >= 2:  # If 2 out of 3 checks passed
            stars_detected = True
            three_stars_detected = True
            print("[BB GOLD] 3 STARS DETECTED! (Builder Hall was last building)")
            gui.log_message("BB Gold: 3 stars detected!")
            send_discord_debug_log("BB Gold: 3 stars detected - waiting 7 seconds before ending")

            # Wait 7 seconds as requested for 3 stars
            print("[BB GOLD] Waiting 7 seconds...")
            time.sleep(7)
            break

        time.sleep(0.5)  # Check every ~0.5 seconds

    if not stars_detected and not battle_lost:
        print("[BB GOLD] WARNING: 2/3 stars not detected after 3 minutes, ending battle anyway")
        gui.log_message("BB Gold: Timeout - ending battle")
        send_discord_debug_log("BB Gold: Timeout waiting for stars - ending battle anyway", "WARNING")

    # Skip surrender/end battle if battle ended (Return Home detected) - battle already over, go straight to return home
    if not battle_lost:
        # Separate handling for 3 stars vs 2 stars
        if three_stars_detected:
            # 3 STAR PATH - use end battle button (surrender not available with 3 stars)
            print("[BB GOLD] 3 stars achieved - detecting end battle button...")
            send_discord_debug_log("BB Gold: 3 stars - using end battle button")

            end_battle_pos = detect_end_battle_button()

            if end_battle_pos:
                print(f"[BB GOLD] Clicking end battle button at {end_battle_pos}")
                send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
                fast_click(*end_battle_pos)
            else:
                print("[BB GOLD] WARNING: End battle button not detected! Using fallback...")
                send_discord_debug_log("BB Gold: No end battle detected, using fallback", "WARNING")
                fast_click(144, 1080)  # Fallback BB end battle position

            # Click confirm button
            print("[BB GOLD] Clicking end battle confirmation...")
            send_discord_debug_log("BB Gold: Clicking end battle confirmation")
            fast_click(1483, 898)
            time.sleep(1.5)

            print("[BB GOLD] 3-star battle ended successfully")
            send_discord_debug_log("BB Gold: 3-star battle ended")

        else:
            # 2 STAR PATH - use surrender or end battle button
            print("[BB GOLD] 2 stars achieved - detecting surrender/end battle button...")
            send_discord_debug_log("BB Gold: 2 stars - detecting surrender/end battle button")

            button_type, button_x, button_y = detect_surrender_or_end_battle()

            # Click surrender/end battle button - FAST CLICK for speed
            if button_type:
                print(f"[BB GOLD] Clicking {button_type} button at ({button_x}, {button_y})")
                send_discord_debug_log(f"BB Gold: Clicking {button_type} at ({button_x}, {button_y})")
                fast_click(button_x, button_y)

                # Click confirm button
                print(f"[BB GOLD] Clicking {button_type} confirmation...")
                send_discord_debug_log(f"BB Gold: Clicking {button_type} confirmation")
                fast_click(1483, 898)
                time.sleep(1.5)
            else:
                # NO FALLBACK - Log error and continue (legacy code path)
                print("[BB GOLD] ERROR: Surrender/end battle button not detected - continuing anyway")
                send_discord_debug_log("BB Gold: No surrender/end battle button found", "ERROR")
                time.sleep(2)  # Wait for potential auto-end

            # After surrender attempt, check if 3 stars appeared (Builder Hall destroyed during surrender)
            print("[BB GOLD] Checking if 3 stars appeared after surrender attempt...")
            three_star_check = 0
            for _ in range(3):
                if detect_three_stars():
                    three_star_check += 1

            if three_star_check >= 2:
                # Edge case: Builder Hall was destroyed while clicking surrender
                # Surrender is NEGATED by 3 stars - must click end battle button instead
                three_stars_detected = True
                print("[BB GOLD] 3 STARS DETECTED after surrender attempt! (Builder Hall destroyed during surrender)")
                gui.log_message("BB Gold: 3 stars appeared during surrender")
                send_discord_debug_log("BB Gold: 3 stars appeared after surrender - clicking end battle")

                # Must click end battle button since surrender was negated
                print("[BB GOLD] Detecting end battle button (surrender negated by 3 stars)...")
                end_battle_pos = detect_end_battle_button()

                if end_battle_pos:
                    print(f"[BB GOLD] Clicking end battle button at {end_battle_pos}")
                    send_discord_debug_log(f"BB Gold: Clicking end battle at {end_battle_pos}")
                    fast_click(*end_battle_pos)
                else:
                    print("[BB GOLD] WARNING: End battle button not detected! Using fallback...")
                    send_discord_debug_log("BB Gold: No end battle detected, using fallback", "WARNING")
                    fast_click(144, 1080)  # Fallback BB end battle position

                # Click confirm button
                print("[BB GOLD] Clicking end battle confirmation...")
                send_discord_debug_log("BB Gold: Clicking end battle confirmation")
                fast_click(1483, 898)
                time.sleep(1.5)

                print("[BB GOLD] Post-surrender 3-star battle ended successfully")
                send_discord_debug_log("BB Gold: Post-surrender 3-star battle ended")
            else:
                print("[BB GOLD] Surrender successful (2 stars)")
                send_discord_debug_log("BB Gold: surrendered successfully with 2 stars")

    gui.log_message("BB Gold: attack completed")

    # Return home - FAST CLICK for speed
    fast_click(*config.RETURN_BUTTON)  # Ultra-fast click
    time.sleep(1.5)  # Reduced delay (was config.RETURN_DELAY which is 7s)

    # Check for star bonus screen with retry loop
    print("[BB GOLD] Checking for star bonus screen...")
    star_bonus_found = False
    max_retries = 4
    for attempt in range(max_retries):
        if detect_star_bonus():
            print(f"[BB GOLD] Star bonus screen detected on attempt {attempt + 1}! Clicking to close at (1282, 1101)...")
            gui.log_message("BB Gold: Closing star bonus screen")
            send_discord_debug_log(f"BB Gold: Star bonus screen detected (attempt {attempt + 1}) - closing")
            fast_click(1282, 1101)
            time.sleep(1.0)  # Wait for screen to close
            print("[BB GOLD] Star bonus screen closed")
            send_discord_debug_log("BB Gold: Star bonus screen closed")
            star_bonus_found = True
            break
        else:
            if attempt < max_retries - 1:
                print(f"[BB GOLD] Star bonus not found (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(0.8)  # Wait before retry

    if not star_bonus_found:
        print("[BB GOLD] No star bonus screen detected after all attempts")

    # Read BB storages for full storage detection
    # Note: track_resources and check_and_pause_if_storages_full are called internally
    bb_storages = read_bb_base_storages()

    # Increment BB Gold attack counter (similar to BB Elixir)
    global bb_gold_attack_count
    settings = gui.get_settings()
    collect_interval = settings.get('bb_collect_interval', 12)
    bb_gold_attack_count += 1
    print(f"[BB GOLD] Attack count: {bb_gold_attack_count}/{collect_interval}")
    send_discord_debug_log(f"BB Gold: Attack {bb_gold_attack_count}/{collect_interval} completed")

    # Collect loot every N attacks (configurable)
    if bb_gold_attack_count >= collect_interval:
        print(f"[BB GOLD] {collect_interval} attacks completed - collecting loot!")
        gui.log_message(f"BB Gold: {collect_interval} attacks done - collecting loot")
        send_discord_debug_log(f"BB Gold: {collect_interval} attacks completed - starting loot collection")

        collect_bb_loot()

        # Reset counter
        bb_gold_attack_count = 0
        print("[BB GOLD] Counter reset - starting new cycle")
        send_discord_debug_log("BB Gold: Loot collected, counter reset to 0")

    return True  # Attack completed


def save_bb_gold_attack_duration(context):
    """
    Save BB Gold attack duration to CSV file.

    Args:
        context: Attack context dict containing 'attack_start_time' and 'stars_detected'
    """
    attack_start_time = context.get('attack_start_time')
    if attack_start_time is None:
        print("[BB GOLD] No attack start time recorded - skipping duration logging")
        return

    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time
    stars = context.get('final_stars', context.get('stars_detected', 0))

    # Get the troop mode used for this attack
    troop_mode = gui.get_settings().get('bb_gold_troop_mode', 'night_witches')
    # Map internal names to display names
    troop_mode_display = {
        'night_witches': 'Night Witches',
        'bomber_night_witches': 'Bomber + Night Witches',
        'baby_dragons': 'Baby Dragons'
    }.get(troop_mode, troop_mode)

    csv_file = "data/bb_gold_time.csv"
    file_exists = os.path.exists(csv_file)

    try:
        import csv
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Loop #', 'Duration (seconds)', 'Stars', 'Troop Mode', 'Timestamp'])
            writer.writerow([
                bb_gold_attack_count + 1,
                f'{attack_duration:.2f}',
                stars,
                troop_mode_display,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        print(f"[BB GOLD] Attack duration: {attack_duration:.2f}s, {stars} stars, mode: {troop_mode_display} (saved to {csv_file})")
        send_discord_debug_log(f"BB Gold: Attack completed in {attack_duration:.2f}s with {stars} stars ({troop_mode_display})")
    except Exception as e:
        print(f"[BB GOLD] Error saving timing to CSV: {e}")
        send_discord_debug_log(f"BB Gold: Error saving timing - {e}", "WARNING")


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
        'retry_count': 0,
        'troops_deployed': False,
        'stars_detected': 0,
        'attack_start_time': None,
        'battle_machine_ability_time': None,
        'battle_lost': False
    }

    state_timeout = getattr(config, 'BB_STATE_DETECTION_TIMEOUT', 30)
    max_retries = getattr(config, 'BB_LOAD_MAX_RETRIES', 3)

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
            last_universal_check = context.get('last_return_home_universal_check', 0)
            current_time = time.time()
            if current_time - last_universal_check >= 0.5:
                context['last_return_home_universal_check'] = current_time
                return_home_pos = detect_return_home_button(quiet=True)
                if return_home_pos:
                    print(f"[BB GOLD STATE] !! Return Home detected in {current_state.name} - transitioning to END_SCREEN")
                    context['return_home_button_pos'] = return_home_pos
                    current_state = BBGoldState.END_SCREEN
                    gui.update_bb_gold_state(current_state.name)
                    continue  # Skip to END_SCREEN handling

        # STATE 1: IN_BASE -> SEARCHING
        if current_state == BBGoldState.IN_BASE and context['retry_count'] == 0:
            print("[BB GOLD STATE] IN_BASE: Initiating search")
            gui.log_message("BB Gold: Starting search")

            # NEW: If queue is active, wait for storage UI to stabilize before checking
            try:
                if 'queue_manager' in globals() and queue_manager and queue_manager.queue_active:
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
            context['search_start_time'] = time.time()
            gui.update_bb_gold_state(current_state.name)

            # Sleep removed - state transitions are now instant
            continue

        # STATE 2: SEARCHING -> ATTACK_READY
        if current_state == BBGoldState.SEARCHING:
            print("[BB GOLD STATE] SEARCHING: Waiting for match...")

            # Wait for either attack ready or timeout
            timeout_start = time.time()
            while time.time() - timeout_start < state_timeout:

                # Check if attack ready
                if check_bb_attacker_text():
                    print("[BB GOLD STATE] SEARCHING -> ATTACK_READY: Attacker text detected")
                    current_state = BBGoldState.ATTACK_READY
                    gui.update_bb_gold_state(current_state.name)
                    break

                # Check for ghost attack after 10 seconds
                if time.time() - timeout_start > 10:
                    if detect_ghost_attack():
                        print("[BB GOLD STATE] SEARCHING -> ERROR_RECOVERY: Ghost attack")
                        current_state = BBGoldState.ERROR_RECOVERY
                        gui.update_bb_gold_state(current_state.name)
                        break

                time.sleep(config.BB_LOAD_CHECK_INTERVAL)

            # Timeout handling
            if current_state == BBGoldState.SEARCHING:
                print("[BB GOLD STATE] SEARCHING timeout - assuming ghost attack")
                current_state = BBGoldState.ERROR_RECOVERY
                gui.update_bb_gold_state(current_state.name)
            continue

        # STATE 3: ATTACK_READY -> BATTLE_ACTIVE
        if current_state == BBGoldState.ATTACK_READY:
            print("[BB GOLD STATE] ATTACK_READY: Deploying troops")
            gui.log_message("BB Gold: Deploying troops")

            # Set attack start time
            context['attack_start_time'] = time.time()

            # Deploy troops using helper function
            deployment_success = deploy_bb_gold_troops(context)

            if deployment_success:
                context['troops_deployed'] = True
                current_state = BBGoldState.BATTLE_ACTIVE
                gui.update_bb_gold_state(current_state.name)
                print("[BB GOLD STATE] ATTACK_READY -> BATTLE_ACTIVE: Troops deployed")
            else:
                print("[BB GOLD STATE] ATTACK_READY -> ERROR_RECOVERY: Deployment failed")
                current_state = BBGoldState.ERROR_RECOVERY
                gui.update_bb_gold_state(current_state.name)
            continue

        # STATE 4: BATTLE_ACTIVE -> BATTLE_ENDING
        if current_state == BBGoldState.BATTLE_ACTIVE:
            print("[BB GOLD STATE] BATTLE_ACTIVE: Monitoring for stars")
            gui.log_message("BB Gold: Monitoring battle...")

            # Monitor for stars or Return Home button (battle ended)
            battle_result = monitor_bb_gold_battle(context)

            context['stars_detected'] = battle_result['stars']
            context['battle_lost'] = battle_result['timeout_without_stars']

            # Cache Return Home button position if detected (for faster END_SCREEN handling)
            if battle_result.get('return_home_pos'):
                context['return_home_button_pos'] = battle_result['return_home_pos']

            current_state = BBGoldState.BATTLE_ENDING
            gui.update_bb_gold_state(current_state.name)
            print(f"[BB GOLD STATE] BATTLE_ACTIVE -> BATTLE_ENDING: {battle_result['stars']} stars, lost={battle_result['timeout_without_stars']}")
            continue

        # STATE 5: BATTLE_ENDING -> END_SCREEN
        if current_state == BBGoldState.BATTLE_ENDING:
            print("[BB GOLD STATE] BATTLE_ENDING: Clicking surrender/end battle")

            # Skip if battle ended (Return Home button detected without stars)
            if not context.get('battle_lost', False):
                end_result = end_bb_gold_battle(context['stars_detected'], context)

                if not end_result['success']:
                    print("[BB GOLD STATE] BATTLE_ENDING: End button click failed, retrying")
                    time.sleep(1)
                    continue

                # Update final stars from end result
                context['final_stars'] = end_result['final_stars']
            else:
                print("[BB GOLD STATE] BATTLE_ENDING: Battle ended (Return Home detected), skipping surrender")
                context['final_stars'] = 0
                # Return Home button position already cached from monitor_bb_gold_battle()

            # Special handling for 3 stars - FORCE return home button detection
            if context.get('final_stars', 0) == 3:
                print("[BB GOLD STATE] BATTLE_ENDING: 3 stars - forcing return home button detection (no fallback)")
                send_discord_debug_log("BB Gold: 3 stars - waiting for return home button confirmation")

                max_attempts = 5
                attempt = 0

                while attempt < max_attempts:
                    attempt += 1
                    print(f"[BB GOLD STATE] BATTLE_ENDING: Checking for return home button (attempt {attempt}/{max_attempts})...")

                    # Wait up to 5 seconds for return home button to appear
                    timeout_start = time.time()
                    return_home_found = False

                    while time.time() - timeout_start < 5:
                        return_home_pos = detect_return_home_button()
                        if return_home_pos:
                            print(f"[BB GOLD STATE] BATTLE_ENDING: ✓ Return home button confirmed at {return_home_pos}")
                            send_discord_debug_log(f"BB Gold: Return home button confirmed (3 stars)")
                            # Cache position for END_SCREEN state
                            context['return_home_button_pos'] = return_home_pos
                            return_home_found = True
                            break
                        time.sleep(0.3)  # Optimized: reduced from 0.5s

                    if return_home_found:
                        # Success - transition to END_SCREEN
                        print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed (return home visible)")
                        current_state = BBGoldState.END_SCREEN
                        gui.update_bb_gold_state(current_state.name)
                        break
                    else:
                        # Return home button not visible - end battle/surrender didn't work
                        print(f"[BB GOLD STATE] BATTLE_ENDING: ✗ Return home button not visible (attempt {attempt}/{max_attempts})")
                        send_discord_debug_log(f"BB Gold: Return home not visible - clicking end battle again (attempt {attempt})", "WARNING")

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
                    gui.update_bb_gold_state(current_state.name)

            else:
                # 0/1/2 stars - use standard end screen detection with fallback
                print("[BB GOLD STATE] BATTLE_ENDING: 0/1/2 stars - standard end screen detection")
                end_screen_timeout = getattr(config, 'BB_END_SCREEN_TIMEOUT', 10)
                timeout_start = time.time()
                while time.time() - timeout_start < end_screen_timeout:
                    end_screen = detect_end_screen_state()
                    if end_screen['detected']:
                        print("[BB GOLD STATE] BATTLE_ENDING -> END_SCREEN: End screen confirmed")
                        current_state = BBGoldState.END_SCREEN
                        gui.update_bb_gold_state(current_state.name)
                        context['star_bonus'] = end_screen['star_bonus']
                        # Cache return home button position if detected
                        if end_screen.get('return_button_pos'):
                            context['return_home_button_pos'] = end_screen['return_button_pos']
                        break
                    time.sleep(0.3)  # Optimized: reduced from 0.5s

                if current_state != BBGoldState.END_SCREEN:
                    print("[BB GOLD STATE] BATTLE_ENDING: End screen not detected, assuming present")
                    current_state = BBGoldState.END_SCREEN
                    gui.update_bb_gold_state(current_state.name)

            continue

        # STATE 6: END_SCREEN -> RETURNING_HOME
        if current_state == BBGoldState.END_SCREEN:
            print("[BB GOLD STATE] END_SCREEN: Detecting and clicking return button")
            gui.log_message("BB Gold: Returning home")

            # Use cached position if available (from BATTLE_ENDING state for 3 stars)
            cached_pos = context.get('return_home_button_pos')
            clicked = False  # Initialize clicked variable

            if cached_pos:
                # Use cached position - no need to detect again
                print(f"[BB GOLD STATE] END_SCREEN: Using cached return home position {cached_pos} - clicking instantly")
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
                        print(f"[BB GOLD STATE] END_SCREEN: ✓ Return home button detected at {return_home_pos} - clicking instantly")
                        send_discord_debug_log(f"BB Gold: Clicking return home at {return_home_pos}")
                        fast_click(*return_home_pos)
                        clicked = True
                        break
                    time.sleep(interval)  # Exponential backoff

                if not clicked:
                    # NO FALLBACK - Detect actual state and handle appropriately
                    print("[BB GOLD STATE] END_SCREEN: Return home button not detected after 10s - detecting actual state")
                    send_discord_debug_log("BB Gold: Return home button not found - detecting state", "WARNING")

                    detected_state = detect_current_game_state()

                    if detected_state == 'in_base':
                        # Already at base - skip to IN_BASE state
                        print("[BB GOLD STATE] END_SCREEN: Already at base - transitioning to IN_BASE")
                        send_discord_debug_log("BB Gold: Already at base (return button not needed)")
                        current_state = BBGoldState.IN_BASE
                        gui.update_bb_gold_state(current_state.name)
                        save_bb_gold_attack_duration(context)
                        increment_bb_gold_counter()
                        return True

                    elif detected_state == 'battle_active':
                        # Still in battle - need to surrender
                        print("[BB GOLD STATE] END_SCREEN: Still in active battle - attempting surrender")
                        send_discord_debug_log("BB Gold: Stuck in battle - surrendering", "WARNING")
                        button_type, x, y = detect_surrender_or_end_battle()
                        if button_type == 'surrender':
                            fast_click(x, y)
                            time.sleep(0.5)
                            # Click confirmation
                            fast_click(1483, 898)
                            time.sleep(2.0)
                        current_state = BBGoldState.BATTLE_ENDING
                        gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == 'battle_ending':
                        # Battle ending - transition to BATTLE_ENDING state
                        print("[BB GOLD STATE] END_SCREEN: Battle still ending - transitioning to BATTLE_ENDING")
                        current_state = BBGoldState.BATTLE_ENDING
                        gui.update_bb_gold_state(current_state.name)
                        continue

                    elif detected_state == 'end_screen':
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
                            gui.update_bb_gold_state(current_state.name)
                            continue

                    else:  # 'unknown'
                        # Unknown state - enter error recovery
                        print("[BB GOLD STATE] END_SCREEN: Unknown state detected - entering ERROR_RECOVERY")
                        send_discord_debug_log("BB Gold: Unknown state - entering error recovery", "ERROR")
                        current_state = BBGoldState.ERROR_RECOVERY
                        gui.update_bb_gold_state(current_state.name)
                        continue

            # Only proceed to RETURNING_HOME if return button was actually clicked
            if clicked:
                time.sleep(1.0)  # Brief wait for transition
                current_state = BBGoldState.RETURNING_HOME
                gui.update_bb_gold_state(current_state.name)
                print("[BB GOLD STATE] END_SCREEN -> RETURNING_HOME: Return clicked")
            continue

        # STATE 7: RETURNING_HOME -> IN_BASE
        if current_state == BBGoldState.RETURNING_HOME:
            print("[BB GOLD STATE] RETURNING_HOME: Waiting for base arrival")

            # Wait for IN_BASE confirmation
            return_timeout = getattr(config, 'BB_RETURN_HOME_TIMEOUT', 15)
            timeout_start = time.time()
            while time.time() - timeout_start < return_timeout:
                if detect_in_base_state():
                    print("[BB GOLD STATE] RETURNING_HOME -> IN_BASE: Army button detected")
                    gui.update_bb_gold_state("IN_BASE")

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
            gui.log_message("BB Gold: Error recovery")
            send_discord_debug_log("BB Gold: Entering error recovery", "WARNING")

            # Quick check: Return Home button means we're on end screen (cache position for fast click)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                print("[BB GOLD STATE] ERROR_RECOVERY: Return Home detected - on end screen")
                context['return_home_button_pos'] = return_home_pos
                current_state = BBGoldState.END_SCREEN
                gui.update_bb_gold_state(current_state.name)
                continue

            # If not on end screen, detect what state we're actually in
            detected_state = detect_current_game_state()

            if detected_state == 'in_base':
                # Already recovered - return to IN_BASE
                print("[BB GOLD STATE] ERROR_RECOVERY: Already at base - recovery successful")
                send_discord_debug_log("BB Gold: Error recovery successful (already at base)")
                context['retry_count'] += 1
                if context['retry_count'] < max_retries:
                    print(f"[BB GOLD STATE] ERROR_RECOVERY -> IN_BASE: Retry {context['retry_count']}/{max_retries}")
                    current_state = BBGoldState.IN_BASE
                    gui.update_bb_gold_state(current_state.name)
                else:
                    print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                    send_discord_debug_log("BB Gold: Max retries exceeded, aborting", "ERROR")
                    return False

            elif detected_state == 'battle_active':
                # Stuck in battle - surrender to exit
                print("[BB GOLD STATE] ERROR_RECOVERY: In active battle - surrendering")
                send_discord_debug_log("BB Gold: Error recovery - surrendering from battle", "WARNING")
                button_type, x, y = detect_surrender_or_end_battle()
                if button_type == 'surrender':
                    fast_click(x, y)
                    time.sleep(0.5)
                    # Click confirmation
                    fast_click(1483, 898)
                    time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    gui.update_bb_gold_state(current_state.name)
                else:
                    # Can't find surrender - try minimal troop deployment to enable it
                    print("[BB GOLD STATE] ERROR_RECOVERY: Surrender not found - deploying troop")
                    fast_click(1282, 720)  # Deploy one troop
                    time.sleep(3.0)
                    # Try surrender again
                    button_type, x, y = detect_surrender_or_end_battle()
                    if button_type == 'surrender':
                        fast_click(x, y)
                        time.sleep(0.5)
                        fast_click(1483, 898)
                        time.sleep(2.0)
                    current_state = BBGoldState.BATTLE_ENDING
                    gui.update_bb_gold_state(current_state.name)

            elif detected_state == 'battle_ending' or detected_state == 'end_screen':
                # Battle ending or end screen - transition appropriately
                print(f"[BB GOLD STATE] ERROR_RECOVERY: Detected {detected_state} - transitioning")
                if detected_state == 'battle_ending':
                    current_state = BBGoldState.BATTLE_ENDING
                else:
                    current_state = BBGoldState.END_SCREEN
                gui.update_bb_gold_state(current_state.name)

            else:  # 'unknown'
                # Unknown state - try clicking return button and retry
                print("[BB GOLD STATE] ERROR_RECOVERY: Unknown state - clicking return button")
                send_discord_debug_log("BB Gold: Unknown state in error recovery - clicking return", "WARNING")
                click_in_square(config.BB_RETURN_BUTTON_GHOST)
                time.sleep(config.BB_RETRY_WAIT_TIME)

                # Check again if we're at base now
                if detect_in_base_state():
                    print("[BB GOLD STATE] ERROR_RECOVERY: Return click worked - at base now")
                    context['retry_count'] += 1
                    if context['retry_count'] < max_retries:
                        current_state = BBGoldState.IN_BASE
                        gui.update_bb_gold_state(current_state.name)
                    else:
                        print("[BB GOLD STATE] ERROR_RECOVERY: Max retries exceeded")
                        return False
                else:
                    # Still stuck - increment retry and continue looping
                    context['retry_count'] += 1
                    if context['retry_count'] >= max_retries:
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


def detect_destruction_percentage(save_debug_screenshots=True):
    """
    Detect current destruction percentage during attack using OCR.
    Returns percentage as integer (0-100), or None if detection fails.
    Reads from bottom-right destruction percentage box.
    Includes jump detection to reject impossible increases (>25% in 0.5s).

    Args:
        save_debug_screenshots: If True, saves debug screenshots on abnormal jumps. Set to False for SBarb Farm mode.
    """
    try:
        # Destruction percentage region (bottom-right box)
        # Format: "XX%" where XX is the percentage
        destruction_region = (2404, 1111, 2534, 1170)
        screenshot = ImageGrab.grab(bbox=destruction_region)

        # Convert to grayscale and apply thresholding for better OCR
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        _, screenshot_cv = cv2.threshold(screenshot_cv, 200, 255, cv2.THRESH_BINARY)

        # OCR the percentage text
        text = pytesseract.image_to_string(screenshot_cv, config='--psm 7 digits')
        text = text.strip().replace('%', '').replace(' ', '').replace('O', '0')  # Fix common OCR mistakes

        # Extract first 2 digits only (percentages are 0-99 for this use case)
        import re
        digits = re.findall(r'\d', text)  # Extract all digits
        if len(digits) >= 1:
            # Take first 2 digits (or 1 if only one digit found)
            percentage_str = ''.join(digits[:2])
            percentage = int(percentage_str)

            if 0 <= percentage <= 99:  # Valid range for our use case
                # Jump detection: reject impossible increases (>25% in 0.5s check interval)
                if hasattr(detect_destruction_percentage, 'last_valid') and detect_destruction_percentage.last_valid is not None:
                    jump = percentage - detect_destruction_percentage.last_valid
                    if jump > 25:
                        # Abnormal jump detected - save debug screenshots (if enabled)
                        if save_debug_screenshots:
                            os.makedirs("debug_screenshots", exist_ok=True)
                            timestamp = int(time.time())
                            screenshot.save(f"debug_screenshots/destruction_abnormal_raw_{timestamp}_{percentage}pct.png")
                            cv2.imwrite(f"debug_screenshots/destruction_abnormal_threshold_{timestamp}_{percentage}pct.png", screenshot_cv)
                            print(f"[DESTRUCTION DEBUG] REJECTED {percentage}% - impossible jump of +{jump}% from {detect_destruction_percentage.last_valid}% (screenshots saved to debug_screenshots/)")
                        else:
                            print(f"[DESTRUCTION DEBUG] REJECTED {percentage}% - impossible jump of +{jump}% from {detect_destruction_percentage.last_valid}%")
                        return None
                    elif jump < -5:
                        # Percentage shouldn't decrease (except small OCR errors)
                        if save_debug_screenshots:
                            os.makedirs("debug_screenshots", exist_ok=True)
                            timestamp = int(time.time())
                            screenshot.save(f"debug_screenshots/destruction_abnormal_raw_{timestamp}_{percentage}pct.png")
                            cv2.imwrite(f"debug_screenshots/destruction_abnormal_threshold_{timestamp}_{percentage}pct.png", screenshot_cv)
                            print(f"[DESTRUCTION DEBUG] REJECTED {percentage}% - negative jump of {jump}% from {detect_destruction_percentage.last_valid}% (screenshots saved to debug_screenshots/)")
                        else:
                            print(f"[DESTRUCTION DEBUG] REJECTED {percentage}% - negative jump of {jump}% from {detect_destruction_percentage.last_valid}%")
                        return None

                # Valid percentage - store and return
                detect_destruction_percentage.last_valid = percentage
                if config.DEBUG_DESTRUCTION_PERCENTAGE:
                    if text != percentage_str:
                        print(f"[DESTRUCTION DEBUG] Detected: {percentage}% (extracted from '{text}')")
                    else:
                        print(f"[DESTRUCTION DEBUG] Detected: {percentage}%")
                return percentage

        if config.DEBUG_DESTRUCTION_PERCENTAGE:
            print(f"[DESTRUCTION DEBUG] Failed to parse: raw_text='{text}' | extracted_digits={digits if 'digits' in locals() else 'none'}")
        return None
    except Exception as e:
        print(f"[DESTRUCTION] Error detecting percentage: {e}")
        return None

def detect_queen_arrow_projectile():
    """
    Detect the Queen's Giant Arrow by tracking its bright cyan/green glow trail.
    Uses color-based detection (HSV) to find the distinctive arrow trail across multiple frames.

    Returns:
        List of (x, y) coordinates along arrow path for spell casting, or None if detection failed
    """
    try:
        print(f"[QUEEN ARROW] Starting glow trail detection...")

        # Arrow glow trail color range (bright cyan/green beam)
        # CALIBRATED VALUES - tuned to reduce false positives
        lower_cyan = np.array([77, 0, 194])     # H=77-95 (cyan), S=0+ (any saturation), V=194+ (very bright only)
        upper_cyan = np.array([95, 255, 255])   # High brightness threshold filters out dark objects

        # Capture multiple frames to track arrow movement
        frame_count = config.QUEEN_ARROW_FRAME_COUNT
        frame_interval = config.QUEEN_ARROW_FRAME_INTERVAL
        glow_detections = []  # List of (frame_num, points_along_trail)

        print(f"[QUEEN ARROW] Capturing {frame_count} frames at {frame_interval}s intervals...")

        for frame_num in range(frame_count):
            # Capture screenshot of base region only
            base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
            img = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Find cyan/green glow pixels
            mask = cv2.inRange(hsv, lower_cyan, upper_cyan)

            # Find contours of glow trail
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            frame_glow_points = []

            for contour in contours:
                area = cv2.contourArea(contour)

                # Filter by size: glow trail segments should be reasonably sized
                # Not tiny noise pixels, but also not huge water/terrain reflections
                if area < 100:  # Minimum 100 pixels for glow trail segment
                    continue
                if area > 1000:  # Maximum 1000 pixels - filters out large false positives (water, terrain)
                    continue

                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by width/height: arrow glow is THICK, not thin lines
                # Thin wall lines are 2-5px wide, arrow glow is 10-30px wide
                min_thickness = 8  # pixels - minimum width or height
                if w < min_thickness and h < min_thickness:
                    # Both dimensions too thin - it's a line, not arrow glow
                    continue

                # Filter by position: exclude UI areas
                if x < 200 or x > 2100 or y < 200 or y > 1000:
                    continue

                # Calculate center of this glow segment
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert to global screen coordinates
                    global_x = cx + config.BASE_VIEW_REGION[0]
                    global_y = cy + config.BASE_VIEW_REGION[1]

                    frame_glow_points.append((global_x, global_y, area))

            if frame_glow_points:
                glow_detections.append((frame_num, frame_glow_points))
                print(f"[QUEEN ARROW] Frame {frame_num}: Detected {len(frame_glow_points)} glow segments")

            # Wait before next frame
            if frame_num < frame_count - 1:
                time.sleep(frame_interval)

        print(f"[QUEEN ARROW] Glow detected in {len(glow_detections)} frames")

        # Need glow in at least 2 frames to determine path
        if len(glow_detections) < 2:
            print(f"[QUEEN ARROW] Insufficient glow detections ({len(glow_detections)} frames) - need at least 2")
            return None

        # Collect all glow points from all frames
        all_glow_points = []
        for frame_num, points in glow_detections:
            all_glow_points.extend([(p[0], p[1]) for p in points])  # (x, y) only

        if len(all_glow_points) < 2:
            print(f"[QUEEN ARROW] Not enough glow points detected ({len(all_glow_points)})")
            return None

        print(f"[QUEEN ARROW] Total glow points across all frames: {len(all_glow_points)}")

        # IMPROVED: Find the densest cluster of points (main arrow trail)
        # Strategy: Use pairwise distances to find the largest group of nearby points
        x_coords_all = np.array([p[0] for p in all_glow_points])
        y_coords_all = np.array([p[1] for p in all_glow_points])

        if len(x_coords_all) < 3:
            print(f"[QUEEN ARROW] Not enough points for clustering")
            return None

        # IMPROVED: Find the densest LINE segment by starting from the densest point
        # and including only connected neighbors - prevents scattered points from skewing the line
        cluster_radius = 200  # pixels - connection radius
        min_neighbors = 2  # Reduced - we'll filter more later

        # Step 1: Count neighbors for each point
        neighbor_counts = []
        for i, (x1, y1) in enumerate(zip(x_coords_all, y_coords_all)):
            neighbor_count = 0
            for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                if i != j:
                    dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if dist <= cluster_radius:
                        neighbor_count += 1
            neighbor_counts.append(neighbor_count)

        # Step 2: Find ALL connected components, then choose the most LINEAR one
        # (Arrow paths are straight lines, not scattered clusters)
        if len(neighbor_counts) == 0 or max(neighbor_counts) == 0:
            print(f"[QUEEN ARROW] No clustered points found")
            clustered_indices = list(range(len(all_glow_points)))
        else:
            # Find all connected components
            visited = set()
            components = []

            for start_idx in range(len(x_coords_all)):
                if start_idx in visited:
                    continue

                # Build connected component from this point
                component = set([start_idx])
                queue = [start_idx]
                visited.add(start_idx)

                while queue:
                    current_idx = queue.pop(0)
                    x1, y1 = x_coords_all[current_idx], y_coords_all[current_idx]

                    for j, (x2, y2) in enumerate(zip(x_coords_all, y_coords_all)):
                        if j not in visited:
                            dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                            if dist <= cluster_radius:
                                component.add(j)
                                queue.append(j)
                                visited.add(j)

                if len(component) >= 3:  # Only keep components with 3+ points
                    components.append(sorted(list(component)))

            print(f"[QUEEN ARROW] Found {len(components)} connected components")

            # Score each component by linearity (how well points form a straight line)
            best_component = None
            best_score = -1

            for comp_indices in components:
                comp_x = x_coords_all[comp_indices]
                comp_y = y_coords_all[comp_indices]

                # Fit a line through this component
                x_range = np.max(comp_x) - np.min(comp_x)
                y_range = np.max(comp_y) - np.min(comp_y)

                if x_range > y_range and x_range > 0:
                    coeffs = np.polyfit(comp_x, comp_y, 1)
                    m, b = coeffs
                    distances = np.abs(m * comp_x - comp_y + b) / np.sqrt(m**2 + 1)
                elif y_range > 0:
                    coeffs = np.polyfit(comp_y, comp_x, 1)
                    m, b = coeffs
                    distances = np.abs(m * comp_y - comp_x + b) / np.sqrt(m**2 + 1)
                else:
                    continue  # Skip degenerate components

                # Calculate linearity score: favor more points with lower deviation from line
                avg_distance = np.mean(distances)
                num_points = len(comp_indices)
                linearity_score = (num_points ** 2) / (avg_distance + 1)  # +1 to avoid division by zero

                print(f"[QUEEN ARROW] Component with {num_points} points: avg deviation={avg_distance:.1f}px, score={linearity_score:.1f}")

                if linearity_score > best_score:
                    best_score = linearity_score
                    best_component = comp_indices

            if best_component is None or len(best_component) < 3:
                print(f"[QUEEN ARROW] No good linear component found, using all points")
                clustered_indices = list(range(len(all_glow_points)))
            else:
                clustered_indices = best_component
                print(f"[QUEEN ARROW] Selected best linear component: {len(clustered_indices)} points")

        # Use only the connected component points for line fitting
        x_coords = x_coords_all[clustered_indices]
        y_coords = y_coords_all[clustered_indices]

        print(f"[QUEEN ARROW] Using {len(x_coords)} connected points (filtered {len(all_glow_points) - len(x_coords)} scattered points)")

        # IMPROVED: Iterative outlier removal based on perpendicular distance from line
        # Fit initial line, remove points far from it, refit - focuses on the main straight line
        max_iterations = 3
        max_perpendicular_distance = 50  # pixels - max distance from line

        for iteration in range(max_iterations):
            if len(x_coords) < 3:
                break

            # Check if line is more vertical than horizontal
            x_range = np.max(x_coords) - np.min(x_coords)
            y_range = np.max(y_coords) - np.min(y_coords)

            if x_range > y_range:
                # Horizontal-ish line: fit y = mx + b
                coeffs = np.polyfit(x_coords, y_coords, 1)
                m, b = coeffs

                # Calculate perpendicular distance for each point
                # For line y = mx + b, perpendicular distance = |mx - y + b| / sqrt(m^2 + 1)
                distances = np.abs(m * x_coords - y_coords + b) / np.sqrt(m**2 + 1)

            else:
                # Vertical-ish line: fit x = my + b
                coeffs = np.polyfit(y_coords, x_coords, 1)
                m, b = coeffs

                # For line x = my + b, perpendicular distance = |my - x + b| / sqrt(m^2 + 1)
                distances = np.abs(m * y_coords - x_coords + b) / np.sqrt(m**2 + 1)

            # Keep only points within max distance
            inlier_mask = distances <= max_perpendicular_distance
            inliers_before = len(x_coords)
            x_coords = x_coords[inlier_mask]
            y_coords = y_coords[inlier_mask]
            inliers_after = len(x_coords)

            if inliers_before == inliers_after:
                # No points removed, we're done
                break

            print(f"[QUEEN ARROW] Iteration {iteration+1}: Removed {inliers_before - inliers_after} points far from line")

        # Safety check: ensure we still have enough points after outlier removal
        if len(x_coords) < 2:
            print(f"[QUEEN ARROW] All points removed as outliers! Only {len(x_coords)} points remain.")
            print(f"[QUEEN ARROW] No clear arrow glow detected - detection failed")
            return None

        # Final line fit with refined points
        x_range = np.max(x_coords) - np.min(x_coords)
        y_range = np.max(y_coords) - np.min(y_coords)

        if x_range > y_range:
            # Horizontal-ish line: fit y = mx + b
            coeffs = np.polyfit(x_coords, y_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            x_min, x_max = np.min(x_coords), np.max(x_coords)
            start_point = (int(x_min), int(m * x_min + b))
            end_point = (int(x_max), int(m * x_max + b))

            print(f"[QUEEN ARROW] Final line: y = {m:.3f}x + {b:.1f} ({len(x_coords)} inliers)")
        else:
            # Vertical-ish line: fit x = my + b
            coeffs = np.polyfit(y_coords, x_coords, 1)
            m, b = coeffs

            # Find start/end by projecting points onto the fitted line
            y_min, y_max = np.min(y_coords), np.max(y_coords)
            start_point = (int(m * y_min + b), int(y_min))
            end_point = (int(m * y_max + b), int(y_max))

            print(f"[QUEEN ARROW] Final line: x = {m:.3f}y + {b:.1f} ({len(x_coords)} inliers)")

        start_x, start_y = start_point
        end_x, end_y = end_point

        # Calculate trail length along the fitted line
        trail_length = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5

        # Validate that we have a reasonable arrow path
        min_trail_length = 200  # pixels - arrow trail should be at least this long
        if trail_length < min_trail_length:
            print(f"[QUEEN ARROW] Glow trail too short ({trail_length:.1f}px < {min_trail_length}px)")
            return None

        print(f"[QUEEN ARROW] Arrow trail detected: ({start_x},{start_y}) -> ({end_x},{end_y})")
        print(f"[QUEEN ARROW] Trail length: {trail_length:.1f}px")

        # Extrapolate path by 30% for better coverage
        dx = end_x - start_x
        dy = end_y - start_y
        extension_factor = 1.3
        extrapolated_end_x = int(start_x + dx * extension_factor)
        extrapolated_end_y = int(start_y + dy * extension_factor)

        print(f"[QUEEN ARROW] Extrapolated path end: ({extrapolated_end_x},{extrapolated_end_y})")
        send_discord_debug_log(f"Queen arrow: Glow trail detected ({len(all_glow_points)} points, {max_distance:.0f}px trail)")

        return [(start_x, start_y), (extrapolated_end_x, extrapolated_end_y)]

    except Exception as e:
        print(f"[QUEEN ARROW] Error in glow trail detection: {e}")
        send_discord_debug_log(f"Queen arrow glow detection failed: {e}", "WARNING")
        import traceback
        traceback.print_exc()
        return None

def detect_queen_arrow_path_and_cast_spells(queen_side, queen_ability_timing, spell_casting_flag):
    """
    Detect the Queen's Giant Arrow path and cast 11 Earthquakes along it.
    Uses glow trail detection (primary) with purple HP bar detection as fallback.

    Args:
        queen_side: 'up' or 'down' - which side Queen was deployed on
        queen_ability_timing: seconds to wait for Queen ability to activate (from settings)
        spell_casting_flag: shared flag dict to track spell casting phase (for hero ability re-selection)

    Returns True if successful, False otherwise.
    """
    try:
        print(f"[QUEEN ARROW] Waiting for Queen ability (deployed on {queen_side}, timing: {queen_ability_timing}s)...")

        # Wait for Queen ability to activate (already triggered by hero ability thread)
        time.sleep(queen_ability_timing)
        print(f"[QUEEN ARROW] Ability activated after {queen_ability_timing}s - starting detection...")

        # ===== PRIMARY METHOD: GLOW TRAIL DETECTION =====
        print(f"[QUEEN ARROW] Attempting glow trail detection...")
        arrow_path = detect_queen_arrow_projectile()

        if arrow_path is not None and len(arrow_path) == 2:
            # Successfully detected arrow glow trail - use these coordinates
            start, end = arrow_path
            print(f"[QUEEN ARROW] ✓ Glow trail detection successful: {start} -> {end}")
            send_discord_debug_log(f"SBarb Farm: Queen arrow glow trail detected")
            detection_method = "glow_trail"
        else:
            # ===== FALLBACK METHOD: PURPLE HP BAR DETECTION =====
            print(f"[QUEEN ARROW] Glow trail detection failed, using HP bar fallback...")
            time.sleep(0.5)  # Wait a bit more for damage to show

            # Capture screenshot
            screenshot = pyautogui.screenshot()
            img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Purple HP bar HSV range (magenta/purple color)
            lower_purple = np.array([140, 80, 80])   # Purple hue
            upper_purple = np.array([170, 255, 255])

            # Find purple HP bars
            mask = cv2.inRange(hsv, lower_purple, upper_purple)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Get centers of all HP bars with strict filtering
            hp_bar_centers = []
            for contour in contours:
                area = cv2.contourArea(contour)

                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by size: HP bars are small rectangles (50-500 pixels area typical)
                if area < 50 or area > 800:
                    continue

                # Filter by aspect ratio: HP bars are horizontal (wider than tall)
                if h == 0 or w / h < 1.5:  # Must be at least 1.5x wider than tall
                    continue

                # Filter by position: exclude UI areas (top/bottom edges, far left/right)
                # Game area is roughly (200, 200) to (2300, 1200)
                if x < 200 or x > 2300 or y < 200 or y > 1200:
                    continue

                # Calculate center
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    hp_bar_centers.append((cx, cy, area))
                    print(f"[QUEEN ARROW] HP bar detected: pos=({cx},{cy}), area={area}, size={w}x{h}, ratio={w/h:.2f}")

            print(f"[QUEEN ARROW] Detected {len(hp_bar_centers)} purple HP bars")

            # Exclude Queen's target based on deployment side
            if len(hp_bar_centers) >= 2:
                if queen_side == 'down':
                    # Queen at bottom - exclude bottom-most (highest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=True)  # Sort by Y (bottom to top)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed BOTTOM - excluded target at {queen_target[:2]}")
                elif queen_side == 'up':
                    # Queen at top - exclude top-most (lowest Y)
                    hp_bar_centers.sort(key=lambda p: p[1], reverse=False)  # Sort by Y (top to bottom)
                    queen_target = hp_bar_centers[0]
                    hp_bar_centers = hp_bar_centers[1:]
                    print(f"[QUEEN ARROW] Queen deployed TOP - excluded target at {queen_target[:2]}")

                print(f"[QUEEN ARROW] {len(hp_bar_centers)} damaged buildings remain after exclusion")

            # If we have at least 2 damaged buildings from arrow (early detection)
            if len(hp_bar_centers) >= 2:
                # Extract coordinates (without area)
                coords = [(p[0], p[1]) for p in hp_bar_centers]

                # Arrow flies in a straight line - use first and last detected building to extrapolate
                # Even with just 2-3 buildings detected, we can extrapolate the full path
                start = coords[0]
                end = coords[-1]

                # Calculate arrow direction vector
                dx = end[0] - start[0]
                dy = end[1] - start[1]

                # Extrapolate further along the arrow path for better coverage
                # Extend the line by 30% beyond the last detected building
                extension_factor = 1.3
                extended_end_x = int(start[0] + dx * extension_factor)
                extended_end_y = int(start[1] + dy * extension_factor)

                # Use extended end point for spell distribution
                end = (extended_end_x, extended_end_y)

                print(f"[QUEEN ARROW] ✓ HP bar fallback successful: {start} -> {end}")
                print(f"[QUEEN ARROW] Arrow path extrapolated from {len(coords)} buildings")
                send_discord_debug_log(f"SBarb Farm: Queen arrow HP bar fallback used ({len(coords)} buildings)")
                detection_method = "hp_bar"
            else:
                print(f"[QUEEN ARROW] ✗ Both detection methods failed ({len(hp_bar_centers)} HP bars)")
                send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed completely", "WARNING")
                return False

        # ===== SPELL CASTING (COMMON TO BOTH METHODS) =====
        print(f"[QUEEN ARROW] Casting 11 Earthquake spells along detected path ({detection_method})...")

        # Set flag to indicate spell casting is active (for hero ability re-selection)
        spell_casting_flag['value'] = True

        # Cast 11 Earthquake spells evenly distributed along the path - ULTRA FAST
        keyboard.send('a')  # Select Earthquake spell
        time.sleep(0.03)

        for i in range(11):
            # Calculate position along the line (0 to 1)
            t = i / 10  # 0%, 10%, 20%, ... 100%
            x = int(start[0] + t * (end[0] - start[0]))
            y = int(start[1] + t * (end[1] - start[1]))

            # Re-select spell every 4 casts to maintain selection
            if i % 4 == 0 and i > 0:
                keyboard.send('a')
                time.sleep(0.01)

            fast_click(x, y)
            time.sleep(0.02)  # Ultra-fast casting

        print(f"[QUEEN ARROW] Successfully cast 11 Earthquake spells on arrow path ({detection_method})")
        send_discord_debug_log(f"SBarb Farm: Cast 11 Earthquakes on Queen arrow path using {detection_method} detection")

        # Clear flag - spell casting complete
        spell_casting_flag['value'] = False

        # Wait for spells to finish casting animation
        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"[QUEEN ARROW] Error detecting arrow path: {e}")
        send_discord_debug_log(f"SBarb Farm: Queen arrow detection failed - {e}", "WARNING")
        return False

def handle_sbarb_farm_mode():
    """
    Handle SBarb Farm mode - deploy Super Barbarians on two sides, throw 11 earthquake spells randomly,
    surrender when 50% destruction reached (or 60s timeout).
    Optimized for speed and efficiency - no base evaluation, no defense/TH detection, attacks first base immediately.
    """
    send_discord_debug_log("SBarb Farm mode: starting attack")
    gui.log_message("SBarb Farm: starting attack")

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[SBARB FARM] Attack screen not ready - skipping base")
        send_discord_debug_log("SBarb Farm: Attack screen timeout - skipping", "WARNING")
        gui.log_message("SBarb Farm: Attack screen timeout - skipping")
        skip_base()
        return False

    # Zoom out NOW that we're in attack screen (BEFORE any camera movement)
    print("[SBARB FARM] Zooming out...")
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    # Zoom out aggressively - 5 scrolls of -300
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.1)  # Reduced wait for zoom animation (optimized for speed)
    print("[SBARB FARM] Zoom complete")

    # Get settings for deployment
    settings = gui.get_settings()
    KEYS = config.KEYS
    heroes_first = settings.get('sbarb_heroes_first', False)
    turbo_deployment = settings.get('sbarb_turbo_deployment', False)

    # Achievement building destruction tracking for CSV
    building_destroyed = "None"  # Type of building destroyed (or "None")
    spells_completed = False  # True if all 10 lightning spells were cast

    # Choose two opposite sides for split deployment (only vertical - up/down)
    # Left/right has coordinate issues, restrict to top-bottom or bottom-top only
    sides = ['up', 'down']
    first_side = random.choice(sides)
    opposite_side = get_opposite_side(first_side)

    deployment_order = "Heroes First" if heroes_first else "Army First"
    print(f"[SBARB FARM] Deploying on {first_side} and {opposite_side} ({deployment_order})")
    send_discord_debug_log(f"SBarb Farm: Deploying on {first_side} and {opposite_side} ({deployment_order})")

    # Draw overlay for SBarb Farm attack (no side arrow - too cluttered)
    overlay_clear()
    if gui.overlay and gui.overlay_enabled:
        gui.overlay.draw_text(100, 80, f"SBarb Farm: {first_side.upper()} then {opposite_side.upper()}", '#FFFF00')
        gui.overlay.draw_text(100, 110, f"Mode: {deployment_order}", '#FFFF00')
        gui.overlay.update()

    # Move camera to first side - ULTRA FAST for SBarb Farm (skip camera movement delays)
    # Ensure zoom is complete before dragging (don't drag during zoom - it blocks zoom)
    time.sleep(0.1)  # Extra buffer to ensure zoom fully complete before camera drag
    drag_map = {
        'left': ((600, 700), (1500, 700)),
        'right': ((2000, 700), (1000, 700)),
        'up': ((1280, 300), (1280, 900)),
        'down': ((1280, 1100), (1280, 700)),
    }
    drag_start, drag_end = drag_map[first_side]
    pyautogui.moveTo(*drag_start, duration=0)
    pyautogui.mouseDown()
    pyautogui.moveTo(*drag_end, duration=0.1)  # Fast drag
    pyautogui.mouseUp()
    time.sleep(0.1)  # Minimal delay

    # Get deployment coordinates
    first_side_coords = config.SIDE_DEPLOYMENT_COORDS[first_side]['units']
    second_side_coords = config.SIDE_DEPLOYMENT_COORDS[opposite_side]['units']

    # Randomize deployment direction (sometimes reverse coordinates for variety)
    if random.random() < 0.5:
        first_side_coords = list(reversed(first_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {first_side}")
    if random.random() < 0.5:
        second_side_coords = list(reversed(second_side_coords))
        print(f"[SBARB FARM] Reversed deployment direction on {opposite_side}")

    # Get actual troop count from settings
    troop_counts = settings.get('troop_counts', [64, 0, 0, 0, 0, 0, 0])

    # Find which slot has Super Barbarians (first non-zero count)
    sbarb_slot_index = None
    total_troops = 0
    for i, count in enumerate(troop_counts):
        if count > 0:
            sbarb_slot_index = i
            total_troops = count
            break

    # If no troops found, default to slot 0
    if sbarb_slot_index is None:
        sbarb_slot_index = 0
        total_troops = troop_counts[0]

    # Get the hotkey for this slot
    sbarb_hotkey = KEYS[f'troop{sbarb_slot_index + 1}']

    print(f"[SBARB FARM] Detected Super Barbarians in slot {sbarb_slot_index + 1}, using hotkey '{sbarb_hotkey}', count: {total_troops}")

    first_half = total_troops // 2

    # Calculate deployment step for even distribution across coordinates
    first_side_step = calculate_deployment_step(first_half, len(first_side_coords))
    second_side_step = calculate_deployment_step(first_half, len(second_side_coords))

    print(f"[SBARB FARM] Deploying {total_troops} troops ({first_half} per side)")
    print(f"[SBARB FARM] Step size: {first_side_step} (first), {second_side_step} (second)")

    # Start timer for attack duration tracking (before any deployments)
    attack_start_time = time.time()

    # Get hero ability timings from GUI settings
    queen_timing = settings.get('queen_ability_timing', 1)
    king_timing = settings.get('king_ability_timing', 1)
    warden_timing = settings.get('warden_ability_timing', 1)
    rc_timing = settings.get('rc_ability_timing', 1)

    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }

    import threading

    # Shared flag for 50% destruction monitoring
    target_destruction = 50
    destruction_reached = {'value': False, 'percentage': 0}
    max_wait_time = 60
    attack_failed_early = False  # True if Return Home detected before 50% (troops died)

    # Reset destruction percentage tracking for new attack
    detect_destruction_percentage.last_valid = None

    # Shared flag for spell casting phase (to handle hero ability re-selection)
    spell_casting_active = {'value': False}

    # Shared dict for achievement building scan results
    achievement_scan_result = {'found': False, 'building': None, 'type': None, 'scanning': False, 'completed': False}

    # Shared dict for cached surrender button position
    surrender_button_cache = {'position': None, 'detected': False}

    def scan_achievement_buildings_background():
        """Background thread to scan for achievement buildings in parallel with deployment"""
        achievement_scan_result['scanning'] = True
        print("[SBARB FARM] Background achievement building scan started...")
        send_discord_debug_log("SBarb Farm: Background achievement building scan started")

        # Get settings from GUI
        settings = gui.get_settings()

        # Check if 50% already reached before scanning
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached before scan - skipping")
            achievement_scan_result['completed'] = True
            achievement_scan_result['scanning'] = False
            return

        # Get targeting mode from settings (default: clumps for backward compatibility)
        target_mode = settings.get('sbarb_cast_spells_target_mode', 'clumps')
        print(f"[SBARB FARM] Targeting mode: {target_mode.replace('_', ' ').title()}")

        if target_mode == 'clumps':
            # CLUMPS MODE: Scan all enabled buildings and look for clusters
            print("[SBARB FARM] Scanning all buildings for clusters...")

            # Build list of enabled buildings from checkboxes
            enabled_buildings = []
            building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                              'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
            for bt in building_types:
                if settings.get(f'achievement_scan_{bt}', True):
                    enabled_buildings.append(bt)

            if not enabled_buildings:
                print("[SBARB FARM] No buildings enabled for scanning")
                achievement_scan_result['completed'] = True
                achievement_scan_result['scanning'] = False
                return

            # Detect all enabled buildings
            all_buildings = detect_all_achievement_buildings(enabled_buildings)

            if not all_buildings:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log("SBarb Farm: No buildings found (clumps mode)")
                achievement_scan_result['completed'] = True
                achievement_scan_result['scanning'] = False
                return

            # Combine all buildings into single list with type labels
            combined_buildings = []
            for building_type, buildings in all_buildings.items():
                for bx, by, conf in buildings:
                    combined_buildings.append((bx, by, conf, building_type))

            print(f"[SBARB FARM] Found {len(combined_buildings)} total building(s)")

            # Look for clusters (2+ buildings within 125px)
            clusters = find_building_clusters(combined_buildings, max_distance=125)

            if len(clusters) > 0 and len(clusters[0]) >= 2:
                # Attack the biggest cluster center
                biggest_cluster = clusters[0]
                x, y = get_cluster_center(biggest_cluster)
                # Count building types in cluster for detailed logging
                cluster_type_counts = {}
                for cx, cy, cconf, ctype in biggest_cluster:
                    cluster_type_counts[ctype] = cluster_type_counts.get(ctype, 0) + 1
                cluster_types_summary = ", ".join([f"{count} {btype.replace('_', ' ')}" for btype, count in cluster_type_counts.items()])
                print(f"  [BACKGROUND SCAN] ✓ CLUSTER of {len(biggest_cluster)} buildings at ({x}, {y})")
                print(f"    Types: {cluster_types_summary}")
                achievement_scan_result['found'] = True
                achievement_scan_result['building'] = (x, y, 1.0)
                achievement_scan_result['type'] = f"cluster_{len(biggest_cluster)}"
                achievement_scan_result['cluster_types'] = cluster_types_summary  # Store for CSV logging
                send_discord_debug_log(f"SBarb Farm: Cluster of {len(biggest_cluster)} buildings ({cluster_types_summary}) at ({x}, {y})")
            else:
                # No cluster found, use priority building
                priority_list = settings.get('achievement_priority_list', building_types)
                priority_enabled = [b for b in priority_list if b in enabled_buildings]

                for building_type in priority_enabled:
                    if building_type in all_buildings and all_buildings[building_type]:
                        bx, by, conf = all_buildings[building_type][0]
                        # Calculate center
                        bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                        x = bx + bw // 2
                        y = by + bh // 2
                        print(f"  [BACKGROUND SCAN] ✓ No cluster - using priority {building_type.replace('_', ' ')} at ({x}, {y})")
                        achievement_scan_result['found'] = True
                        achievement_scan_result['building'] = (x, y, conf)
                        achievement_scan_result['type'] = building_type
                        send_discord_debug_log(f"SBarb Farm: {building_type} at ({x}, {y}) (no cluster)")
                        break
                else:
                    print("[BACKGROUND SCAN] No priority buildings found")
                    send_discord_debug_log("SBarb Farm: No priority buildings found")

        else:  # target_mode in ['target', 'first_detected']
            # TARGET/FIRST_DETECTED MODE: Scan in priority order, return first match
            result = scan_achievement_buildings_parallel_priority(settings)

            if result is not None:
                x, y, confidence, building_type = result
                # Convert top-left to center coordinates
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                achievement_scan_result['found'] = True
                achievement_scan_result['building'] = (center_x, center_y, confidence)
                achievement_scan_result['type'] = building_type
                print(f"  [BACKGROUND SCAN] ✓ {building_type.replace('_', ' ')} FOUND at center ({center_x}, {center_y})! ({target_mode.replace('_', ' ')} mode)")
                send_discord_debug_log(f"SBarb Farm: {building_type} found at ({center_x}, {center_y}) ({target_mode} mode)")
            else:
                print("[BACKGROUND SCAN] No achievement buildings found")
                send_discord_debug_log(f"SBarb Farm: No buildings found ({target_mode} mode)")

        achievement_scan_result['completed'] = True
        achievement_scan_result['scanning'] = False

    def detect_surrender_button_early():
        """Detect and cache surrender or end battle button position early during attack"""
        if not surrender_button_cache['detected']:
            print("[SBARB FARM] Pre-detecting surrender/end battle button position...")
            button_type, button_x, button_y = detect_surrender_or_end_battle()
            if button_type:
                surrender_button_cache['position'] = (button_x, button_y)
                surrender_button_cache['detected'] = True
                print(f"[SBARB FARM] {button_type.replace('_', ' ').title()} button cached at ({button_x}, {button_y})")
                send_discord_debug_log(f"SBarb Farm: {button_type} button pre-cached at ({button_x}, {button_y})")
            else:
                print("[SBARB FARM] Surrender/end battle button not detected yet")

    def monitor_destruction_continuous():
        """Background thread to continuously monitor destruction percentage and Return Home button"""
        nonlocal attack_failed_early

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached['value']:
                break

            # Check for Return Home button (battle ended early - troops died before 50%)
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                elapsed = time.time() - attack_start_time
                current_pct = destruction_reached.get('percentage', 0)
                print(f"[SBARB FARM] Return Home detected after {elapsed:.1f}s - attack failed (troops died at {current_pct}%, before {target_destruction}%)")
                gui.log_message(f"SBarb Farm: Attack failed - troops died at {current_pct}%")
                send_discord_debug_log(f"SBarb Farm: Attack failed after {elapsed:.1f}s - Return Home detected at {current_pct}%", "WARNING")
                destruction_reached['value'] = True  # Signal main loop to stop waiting
                destruction_reached['return_home_pos'] = return_home_pos  # Cache position for faster click
                attack_failed_early = True
                break

            current_destruction = detect_destruction_percentage(save_debug_screenshots=False)
            if current_destruction is not None:
                destruction_reached['percentage'] = current_destruction
                if current_destruction >= target_destruction:
                    elapsed = time.time() - attack_start_time
                    destruction_reached['value'] = True
                    print(f"[SBARB FARM] {target_destruction}% REACHED! ({current_destruction}% after {elapsed:.1f}s)")
                    gui.log_message(f"SBarb Farm: {current_destruction}% reached - stopping deployment!")
                    send_discord_debug_log(f"SBarb Farm: {current_destruction}% destruction reached after {elapsed:.1f}s")
                    break

            time.sleep(0.2)  # Check every 0.2 seconds (faster polling for quicker detection)

    # Start destruction monitoring thread
    monitor_thread = threading.Thread(target=monitor_destruction_continuous, daemon=True)
    monitor_thread.start()
    print(f"[SBARB FARM] Started background monitoring for {target_destruction}% destruction")

    # ============================================================
    # TURBO DEPLOYMENT MODE (Windows API fast-click)
    # ============================================================
    if turbo_deployment:
        print(f"[SBARB FARM] *** TURBO DEPLOYMENT MODE ENABLED ***")
        send_discord_debug_log("SBarb Farm: Turbo deployment mode active (~16 CPS)")

        # Get turbo corners for both sides
        first_corners = TURBO_SIDE_CORNERS[first_side].copy()
        second_corners = TURBO_SIDE_CORNERS[opposite_side].copy()

        # Randomly reverse direction sometimes
        if random.random() < 0.5:
            first_corners = list(reversed(first_corners))
            print(f"[TURBO DEPLOY] Reversed direction on {first_side}")
        if random.random() < 0.5:
            second_corners = list(reversed(second_corners))
            print(f"[TURBO DEPLOY] Reversed direction on {opposite_side}")

        # ===== PHASE 1: Deploy first half on first side =====
        print(f"[TURBO DEPLOY] Deploying {first_half} troops on {first_side}...")
        turbo_deploy_along_path(first_corners, first_half, TURBO_CLICK_DELAY_MS, sbarb_hotkey, destruction_reached)

        # ===== PHASE 2: Deploy heroes and siege on FIRST side (right after troops) =====
        if not destruction_reached['value']:
            print(f"[TURBO DEPLOY] Deploying heroes and siege on {first_side}...")
            turbo_deploy_heroes(first_side, hero_timings, destruction_reached)
            turbo_deploy_siege(first_side, destruction_reached)
        else:
            print(f"[TURBO DEPLOY] 50% reached after first wave - skipping heroes/siege")

        # Get spell casting setting
        sbarb_cast_spells = settings.get('sbarb_cast_spells', False)

        # ===== PHASE 3-5: Camera, abilities, and second wave (skip if 50% reached) =====
        if not destruction_reached['value']:
            # ===== PHASE 3: Camera to opposite side =====
            print(f"[TURBO DEPLOY] Moving camera to {opposite_side}...")

            # Click neutral area first to deselect
            pyautogui.click(1280, 400)
            time.sleep(0.1)

            # Extended drag for opposite side
            if opposite_side == 'up':
                drag_start_opp, drag_end_opp = (1280, 200), (1280, 1100)
            else:  # down
                drag_start_opp, drag_end_opp = (1280, 1200), (1280, 400)

            pyautogui.moveTo(*drag_start_opp, duration=0.05)
            time.sleep(0.05)
            pyautogui.mouseDown()
            time.sleep(0.05)
            pyautogui.moveTo(*drag_end_opp, duration=0.15)
            time.sleep(0.05)
            pyautogui.mouseUp()

            # ===== PHASE 4: Activate ALL hero abilities immediately (during camera settle) =====
            if not destruction_reached['value']:
                print(f"[TURBO DEPLOY] Activating all hero abilities...")
                for hero_key in ['queen', 'king', 'warden', 'rc']:
                    timing = hero_timings.get(hero_key, -1)
                    if timing >= 0:  # Only activate if not disabled (-1)
                        keyboard.send(KEYS[hero_key])
                        print(f"[TURBO DEPLOY] {hero_key.title()} ability activated")
                        time.sleep(0.08)  # Small delay between ability activations
                send_discord_debug_log("SBarb Farm: All hero abilities activated (turbo mode)")

            # ===== Start background achievement scan (after camera settled) =====
            if sbarb_cast_spells and not destruction_reached['value']:
                scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
                scan_thread.start()
                print("[TURBO DEPLOY] Started background achievement building scan")

            # ===== PHASE 5: Deploy second half on opposite side =====
            if not destruction_reached['value']:
                print(f"[TURBO DEPLOY] Deploying {first_half} troops on {opposite_side}...")
                turbo_deploy_along_path(second_corners, first_half, TURBO_CLICK_DELAY_MS, sbarb_hotkey, destruction_reached)
            else:
                print(f"[TURBO DEPLOY] 50% reached - skipping second wave")
        else:
            print(f"[TURBO DEPLOY] 50% reached - skipping phases 3-5")

        # ===== PHASE 6: Spell casting (only if 50% not reached) =====
        achievement_spells_deployed = False

        if not destruction_reached['value'] and sbarb_cast_spells:
            # Wait for background scan to complete (with timeout)
            scan_start = time.time()
            while not achievement_scan_result['completed'] and (time.time() - scan_start) < 6:
                if destruction_reached['value']:
                    break
                time.sleep(0.1)

            if achievement_scan_result['found'] and not destruction_reached['value']:
                found_building = achievement_scan_result['building']
                found_type = achievement_scan_result['type']
                x, y, confidence = found_building

                print(f"[TURBO DEPLOY] CASTING SPELLS ON: {found_type.replace('_', ' ')} at ({x}, {y})")
                gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
                send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type} (turbo mode)")

                # Deploy 1 Earthquake + 10 Lightning using turbo clicks (~11 CPS)
                SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting
                spell_start = time.perf_counter()

                keyboard.send('a')
                time.sleep(0.05)
                turbo_move_cursor(x, y)
                turbo_fast_click()
                time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                keyboard.send('s')
                time.sleep(0.05)
                spells_cast = 0
                for _ in range(10):
                    if destruction_reached['value']:
                        break
                    spell_x = x + random.randint(-3, 3)
                    spell_y = y + random.randint(-3, 3)
                    turbo_move_cursor(spell_x, spell_y)
                    turbo_fast_click()
                    spells_cast += 1
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                spell_elapsed = time.perf_counter() - spell_start
                print(f"[TURBO DEPLOY] Cast {spells_cast + 1} spells in {spell_elapsed*1000:.0f}ms (~{(spells_cast + 1)/spell_elapsed:.0f} CPS)")

                # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
                if found_type.startswith('cluster_') and 'cluster_types' in achievement_scan_result:
                    building_destroyed = achievement_scan_result['cluster_types']
                else:
                    building_destroyed = found_type
                spells_completed = True
                achievement_spells_deployed = True
                print(f"[TURBO DEPLOY] Spells deployed on {found_type}")

            # Fallback: random spells if no achievement building found
            if not achievement_spells_deployed and not destruction_reached['value']:
                print("[TURBO DEPLOY] Deploying random spells...")
                spell_casting_active['value'] = True
                SPELL_CLICK_DELAY_MS = 90  # ~11 CPS for spell casting

                keyboard.send('a')
                time.sleep(0.05)
                for _ in range(2):
                    if destruction_reached['value']:
                        break
                    x, y = random.randint(700, 1800), random.randint(400, 1000)
                    turbo_move_cursor(x, y)
                    turbo_fast_click()
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                keyboard.send('s')
                time.sleep(0.05)
                for _ in range(9):
                    if destruction_reached['value']:
                        break
                    x, y = random.randint(700, 1800), random.randint(400, 1000)
                    turbo_move_cursor(x, y)
                    turbo_fast_click()
                    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

                spell_casting_active['value'] = False
                print("[TURBO DEPLOY] Random spells deployed")
        elif destruction_reached['value']:
            print(f"[TURBO DEPLOY] 50% reached - skipping spell casting")

        # ===== Start background surrender button detection for fast surrender =====
        if not surrender_button_cache['detected']:
            surrender_detect_thread = threading.Thread(target=detect_surrender_button_early, daemon=True)
            surrender_detect_thread.start()
            print("[TURBO DEPLOY] Started background surrender button detection")

        print(f"[TURBO DEPLOY] All deployment phases complete")
        print(f"[TURBO DEPLOY] *** TURBO MODE FINISHED - skipping standard deployment ***")
        send_discord_debug_log("SBarb Farm: Turbo deployment complete")

    # Helper function for hero ability activation (used by both turbo and standard modes)
    def activate_sbarb_hero_ability(hero_role, timing):
        """Activate hero ability after specified timing, then re-select spell or troops"""
        if timing >= 0:
            if timing > 0:
                time.sleep(timing)
            keyboard.send(KEYS[hero_role])
            print(f"[SBARB FARM] {hero_role.title()} ability activated at {timing}s")
            send_discord_debug_log(f"SBarb Farm: {hero_role.title()} ability activated at {timing}s")
            # Re-select spells or troops depending on current phase
            time.sleep(0.05)
            if spell_casting_active['value']:
                keyboard.send('a')  # Re-select Earthquake spell
                print(f"[SBARB FARM] Re-selected Earthquake spell after {hero_role.title()} ability")
            else:
                keyboard.send(sbarb_hotkey)  # Re-select troops (dynamic slot)
                print(f"[SBARB FARM] Re-selected troops after {hero_role.title()} ability")

    # ============================================================
    # STANDARD DEPLOYMENT MODE (hold-and-drag)
    # Skip this entire section if turbo deployment was used
    # ============================================================
    if not turbo_deployment:
        print(f"[SBARB FARM] Using STANDARD deployment mode (hold-and-drag)")

        # CONDITIONAL DEPLOYMENT ORDER BASED ON SETTING
        if heroes_first:
            # ===== HEROES FIRST ORDER =====
            print(f"[SBARB FARM] Deploying heroes first on {first_side}...")
            hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]['hero']

            # Deploy each hero and start their ability timer immediately
            for hero_key in ['queen', 'king', 'warden', 'rc']:
                # Deploy hero
                keyboard.send(KEYS[hero_key])
                time.sleep(0.01)
                pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
                pyautogui.click()
                time.sleep(0.01)

                # Start ability timer RIGHT AFTER deploying this hero
                timing = hero_timings[hero_key]
                if timing != -1:
                    ability_thread = threading.Thread(
                        target=activate_sbarb_hero_ability,
                        args=(hero_key, timing),
                        daemon=True
                    )
                    ability_thread.start()
                    print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

            print("[SBARB FARM] All heroes deployed, ability timers started")

            # Deploy siege machine
            keyboard.send(KEYS['siege'])
        time.sleep(0.01)
        pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
        pyautogui.click()
        time.sleep(0.3)

        # Check if Queen arrow spell targeting is enabled
        queen_arrow_spells = settings.get('sbarb_queen_arrow_spells', False)

        if queen_arrow_spells:
            # ===== QUEEN ARROW PATH DETECTION (BEFORE TROOPS) =====
            print("[SBARB FARM] Using Queen arrow path detection (before troop deployment)...")
            send_discord_debug_log("SBarb Farm: Detecting Queen arrow path before troops")

            # Wait for Queen ability to activate and arrow to hit
            success = detect_queen_arrow_path_and_cast_spells(first_side, queen_timing, spell_casting_active)

            if success:
                print("[SBARB FARM] Queen arrow spells deployed successfully")
                # Spells have been cast, skip normal spell deployment later
                # Extra delay to ensure all spell animations complete
                time.sleep(0.3)
            else:
                # Detection failed - will use fallback spells later
                print("[SBARB FARM] Queen arrow detection failed, will use fallback spells later")
                queen_arrow_spells = False

        # Click neutral area to ensure we're not in drag mode (after spells)
        pyautogui.click(1280, 400)  # Click top-center (safe area)
        # time.sleep(0.3)  # Increased delay to ensure spell mode is fully exited - COMMENTED OUT FOR SPEED

        # Now deploy first half of troops
        print(f"[SBARB FARM] Deploying first half ({first_half} troops) on {first_side}...")
        keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
        # time.sleep(0.4)  # Increased delay for troop selection to register after spells - COMMENTED OUT FOR SPEED

        # Hold-and-drag deployment - much faster and better spread
        if first_half > 0:
            first_coord = first_side_coords[0]
            pyautogui.moveTo(*first_coord, duration=0)
            pyautogui.mouseDown()
            time.sleep(0.5)  # Hold at first position to activate deployment mode

            # Drag through coordinates quickly - dynamic step based on troop count
            for i in range(1, len(first_side_coords), first_side_step):
                coord = first_side_coords[i]
                pyautogui.moveTo(coord[0], coord[1], duration=0.01)
                time.sleep(0.003)  # Brief pause at each position

            pyautogui.mouseUp()
            time.sleep(0.05)

        # Check if 50% reached during first wave deployment
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
            pass  # Will check again before next phase

    elif not turbo_deployment:
        # ===== ARMY FIRST ORDER (ORIGINAL) =====
        # (Only runs when turbo deployment is disabled AND heroes_first is False)
        # Deploy first half - HOLD-AND-DRAG for maximum spread
        print(f"[SBARB FARM] Deploying first half ({first_half} troops) on {first_side}...")
        keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
        time.sleep(0.05)

        # Hold-and-drag deployment - much faster and better spread
        if first_half > 0:
            first_coord = first_side_coords[0]
            pyautogui.moveTo(*first_coord, duration=0)
            pyautogui.mouseDown()
            time.sleep(0.5)  # Hold at first position to activate deployment mode

            # Drag through coordinates quickly - dynamic step based on troop count
            for i in range(1, len(first_side_coords), first_side_step):
                coord = first_side_coords[i]
                pyautogui.moveTo(coord[0], coord[1], duration=0.01)
                time.sleep(0.003)  # Brief pause at each position

            pyautogui.mouseUp()
            time.sleep(0.05)

        # Deploy heroes at first side position - ULTRA FAST
        print("[SBARB FARM] Deploying heroes on first side...")
        hero_pos = config.SIDE_DEPLOYMENT_COORDS[first_side]['hero']

        # Deploy each hero and start their ability timer immediately
        for hero_key in ['queen', 'king', 'warden', 'rc']:
            # Deploy hero
            keyboard.send(KEYS[hero_key])
            time.sleep(0.01)
            pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
            pyautogui.click()
            time.sleep(0.01)

            # Start ability timer RIGHT AFTER deploying this hero
            timing = hero_timings[hero_key]
            if timing != -1:
                ability_thread = threading.Thread(
                    target=activate_sbarb_hero_ability,
                    args=(hero_key, timing),
                    daemon=True
                )
                ability_thread.start()
                print(f"[SBARB FARM] Started {hero_key.title()} ability timer ({timing}s)")

        print("[SBARB FARM] All heroes deployed, ability timers started")

        # Deploy siege machine - ULTRA FAST
        keyboard.send(KEYS['siege'])
        time.sleep(0.01)
        pyautogui.moveTo(hero_pos[0], hero_pos[1], duration=0)  # INSTANT
        pyautogui.click()
        time.sleep(0.2)  # Brief pause after siege

        # Check if 50% reached during first wave deployment
        if destruction_reached['value']:
            print(f"[SBARB FARM] 50% reached during first wave - skipping remaining deployment")
            pass  # Will check again before next phase

    # Check if 50% reached before moving camera for second wave
    # Skip if turbo deployment was used (already handled above)
    if not destruction_reached['value'] and not turbo_deployment:
        # Move camera to opposite side - ULTRA FAST (skip camera movement delays)
        print(f"[SBARB FARM] Moving camera to opposite side ({opposite_side})...")
        send_discord_debug_log(f"SBarb Farm: Moving camera to {opposite_side}")
        # Instant drag to opposite side - INCREASED DRAG DISTANCE
        drag_start_opposite, drag_end_opposite = drag_map[opposite_side]
        # Double the drag distance for better camera movement
        if opposite_side == 'up':
            drag_end_opposite = (1280, 1100)  # Increased from 900 to 1100
        elif opposite_side == 'down':
            drag_end_opposite = (1280, 500)  # Increased from 700 to 500

        pyautogui.moveTo(*drag_start_opposite, duration=0)
        pyautogui.mouseDown()
        pyautogui.moveTo(*drag_end_opposite, duration=0.15)  # Slightly slower for longer drag
        pyautogui.mouseUp()
        time.sleep(0.1)  # Reduced delay to exit camera drag mode (optimized for speed)

        # Start background achievement building scan if spell casting is enabled
        if settings.get('sbarb_cast_spells', False) and not achievement_scan_result['scanning']:
            scan_thread = threading.Thread(target=scan_achievement_buildings_background, daemon=True)
            scan_thread.start()
            print("[SBARB FARM] Started background achievement building scan during deployment")
            send_discord_debug_log("SBarb Farm: Background scan started during 2nd wave deployment")

        # Start background surrender button detection
        if not surrender_button_cache['detected']:
            surrender_detect_thread = threading.Thread(target=detect_surrender_button_early, daemon=True)
            surrender_detect_thread.start()

        # Deploy second half on opposite side - HOLD-AND-DRAG for maximum spread
        print(f"[SBARB FARM] Deploying second half on {opposite_side}...")

        # Click somewhere neutral to ensure we're not in drag mode
        pyautogui.click(1280, 400)  # Click top-center (safe area)
        time.sleep(0.1)

        keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
        time.sleep(0.1)  # Reduced delay for troop selection (optimized for speed)

        # Calculate how many troops remain
        remaining_troops = first_half  # Should be roughly the same or slightly more

        # Hold-and-drag deployment
        if remaining_troops > 0 and len(second_side_coords) > 0:
            first_coord = second_side_coords[0]
            pyautogui.moveTo(*first_coord, duration=0)
            pyautogui.mouseDown()
            time.sleep(0.5)  # Hold at first position to activate deployment mode

            # Drag through coordinates quickly - dynamic step based on troop count
            for i in range(1, len(second_side_coords), second_side_step):
                coord = second_side_coords[i]
                pyautogui.moveTo(coord[0], coord[1], duration=0.01)
                time.sleep(0.003)  # Brief pause at each position

            pyautogui.mouseUp()
            time.sleep(0.05)

        print("[SBARB FARM] All troops deployed")
        send_discord_debug_log("SBarb Farm: All troops deployed")

        # SMART CLEANUP: OCR remaining troops and deploy with individual clicks
        if not destruction_reached['value']:
            print("[SBARB FARM] Checking remaining troop count via OCR...")
            send_discord_debug_log("SBarb Farm: OCR cleanup check started")

            # OCR the remaining troop count
            remaining_count = ocr_remaining_troop_count()

            if remaining_count == 0:
                # No troops left - skip cleanup entirely (avoids "no units" message)
                print("[SBARB FARM] No troops remaining - skipping cleanup")
                send_discord_debug_log("SBarb Farm: 0 troops remaining, cleanup skipped")
            elif remaining_count > 0:
                # Deploy remaining troops with individual clicks
                print(f"[SBARB FARM] {remaining_count} troops remaining - deploying with clicks")
                send_discord_debug_log(f"SBarb Farm: {remaining_count} troops remaining, starting click deployment")

                keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
                time.sleep(0.05)

                # Choose 6 evenly spaced positions from last deployed side
                cleanup_coords = second_side_coords
                num_coords = len(cleanup_coords)
                num_clicks = min(8, num_coords)  # Up to 8 clicks

                # Calculate indices for even spacing
                if num_coords > 0:
                    step = max(1, num_coords // num_clicks)
                    click_positions = [cleanup_coords[i * step] for i in range(num_clicks)]

                    # Deploy with individual clicks
                    for i, pos in enumerate(click_positions):
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during cleanup - stopping")
                            break

                        fast_click(*pos)
                        time.sleep(0.08)  # Brief delay between clicks
                        print(f"  Cleanup click {i+1}/{num_clicks}")

                    print(f"[SBARB FARM] Cleanup complete - {num_clicks} clicks deployed")
                    send_discord_debug_log(f"SBarb Farm: Cleanup complete ({num_clicks} clicks)")
            else:
                # OCR failed - fallback to 3 safety clicks
                print("[SBARB FARM] OCR failed - fallback to 3 safety clicks")
                send_discord_debug_log("SBarb Farm: OCR failed, using fallback clicks")

                keyboard.send(sbarb_hotkey)  # Select Super Barbarians (dynamic slot)
                time.sleep(0.05)

                cleanup_coords = second_side_coords
                if len(cleanup_coords) >= 3:
                    # Click at start, middle, end
                    for pos in [cleanup_coords[0], cleanup_coords[len(cleanup_coords)//2], cleanup_coords[-1]]:
                        if destruction_reached['value']:
                            break
                        fast_click(*pos)
                        time.sleep(0.08)

                print("[SBARB FARM] Fallback cleanup complete")
                send_discord_debug_log("SBarb Farm: Fallback cleanup complete")
    else:
        print("[SBARB FARM] 50% reached - skipping second wave deployment")

    # Check if 50% reached before deploying spells
    # Note: In heroes-first mode with queen arrow spells, spells are already deployed before troops
    # Skip if turbo deployment was used (spells already handled in turbo mode)
    if not destruction_reached['value'] and not turbo_deployment:
        # Check if Queen arrow spells were enabled and if they've been deployed already
        queen_arrow_setting = settings.get('sbarb_queen_arrow_spells', False)

        # In heroes-first mode, queen_arrow_spells variable indicates if spells were deployed successfully
        # In army-first mode, we always need to deploy spells here
        if heroes_first and queen_arrow_setting and queen_arrow_spells:
            # Spells already deployed before troops via Queen arrow detection
            print("[SBARB FARM] Spells already deployed via Queen arrow detection, skipping")
        elif not heroes_first and queen_arrow_setting:
            # Army-first mode with queen arrow enabled - not supported
            print("[SBARB FARM] WARNING: Queen arrow spells require heroes-first mode, using random spells")
            send_discord_debug_log("SBarb Farm: Queen arrow requires heroes-first mode", "WARNING")
            # Deploy random spells as fallback
            queen_arrow_use_fallback = True
        else:
            # Need to deploy spells: either army-first mode, or heroes-first with no queen arrow, or detection failed
            queen_arrow_use_fallback = True

        # Deploy spells if needed
        if not (heroes_first and queen_arrow_setting and queen_arrow_spells):
            # Check if achievement building spell casting is enabled
            cast_spells_on_achievement = settings.get('sbarb_cast_spells', False)
            achievement_spells_deployed = False

            if cast_spells_on_achievement:
                # Use cached scan results from background thread
                print("[SBARB FARM] Checking background scan results...")

                # Wait for background scan to complete (max 2 seconds)
                scan_wait_start = time.time()
                while achievement_scan_result['scanning'] and (time.time() - scan_wait_start) < 2.0:
                    if destruction_reached['value']:
                        print("[SBARB FARM] 50% reached while waiting for scan - skipping")
                        break
                    time.sleep(0.1)

                if achievement_scan_result['found']:
                    # Background scan found a building - use cached result!
                    found_building = achievement_scan_result['building']
                    found_type = achievement_scan_result['type']
                    print(f"[SBARB FARM] ✓ Using cached scan result: {found_type.replace('_', ' ')}")
                    send_discord_debug_log(f"SBarb Farm: Using cached building ({found_type})")
                elif achievement_scan_result['completed']:
                    # Scan completed but found nothing
                    print("[SBARB FARM] Background scan completed - no buildings found")
                    send_discord_debug_log("SBarb Farm: Background scan found no buildings")
                    found_building = None
                    found_type = None
                else:
                    # Scan timed out or 50% reached - no result available
                    print("[SBARB FARM] Background scan incomplete - no result available")
                    send_discord_debug_log("SBarb Farm: Background scan incomplete")
                    found_building = None
                    found_type = None

                if found_building:
                    # Set flag to indicate spell casting is active
                    spell_casting_active['value'] = True

                    x, y, confidence = found_building
                    print(f"[SBARB FARM] CASTING SPELLS ON: {found_type.replace('_', ' ').title()} at ({x}, {y}) - Confidence: {confidence:.3f}")
                    gui.log_message(f"Casting spells on {found_type.replace('_', ' ')}")
                    send_discord_debug_log(f"SBarb Farm: Casting spells on {found_type.replace('_', ' ')} at ({x}, {y})")

                    # Deploy 1 Earthquake spell
                    print("Deploying Earthquake spell...")
                    keyboard.send('a')  # Earthquake hotkey
                    time.sleep(0.02)
                    fast_click(x, y)
                    time.sleep(0.05)

                    # Deploy 10 Lightning spells
                    print("Deploying Lightning spells...")
                    lightning_spells_cast = 0
                    for i in range(10):
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during spell deployment - stopping")
                            break
                        keyboard.send('s')  # Lightning hotkey
                        time.sleep(0.01)
                        # Add slight variation to position (±3px like Achievement Farm)
                        spell_x = x + random.randint(-3, 3)
                        spell_y = y + random.randint(-3, 3)
                        fast_click(spell_x, spell_y)
                        time.sleep(0.03)
                        lightning_spells_cast += 1
                        print(f"  Lightning {i+1}/10 deployed")

                    # Check if all 10 lightning spells were successfully cast
                    if lightning_spells_cast == 10:
                        print("[SBARB FARM] All spells deployed (1 Earthquake + 10 Lightning)!")
                        gui.log_message("Spells deployed successfully")
                        send_discord_debug_log("SBarb Farm: All spells deployed (1 Earthquake + 10 Lightning)")

                        # Track building destruction for CSV
                        # Use cluster_types for CSV if available (Clumps mode), otherwise use found_type
                        if found_type.startswith('cluster_') and 'cluster_types' in achievement_scan_result:
                            building_destroyed = achievement_scan_result['cluster_types']
                        else:
                            building_destroyed = found_type
                        spells_completed = True
                        print(f"[SBARB FARM] ✓ Achievement building destroyed: {found_type.replace('_', ' ').title()}")
                        send_discord_debug_log(f"SBarb Farm: {found_type.replace('_', ' ').title()} destroyed")
                    else:
                        print(f"[SBARB FARM] Spell deployment interrupted ({lightning_spells_cast}/10 lightning spells cast)")
                        send_discord_debug_log(f"SBarb Farm: Spell deployment interrupted ({lightning_spells_cast}/10)")

                    achievement_spells_deployed = True

                    # Clear flag - spell casting complete
                    spell_casting_active['value'] = False
                else:
                    print("[SBARB FARM] No achievement buildings found - falling back to random spells")
                    gui.log_message("No achievement buildings found")
                    send_discord_debug_log("SBarb Farm: No achievement buildings found, using random spells")

            # If achievement spells not enabled or no buildings found, deploy random spells
            if not achievement_spells_deployed:
                # Deploy 2 Earthquake + 9 Lightning spells at random base locations - FAST (ORIGINAL METHOD)
                print("[SBARB FARM] Deploying 2 Earthquake + 9 Lightning spells randomly...")
                send_discord_debug_log("SBarb Farm: Deploying 2 Earthquake + 9 Lightning spells")

                # Set flag to indicate spell casting is active (for hero ability re-selection)
                spell_casting_active['value'] = True

                # Spell region (center of base for maximum damage)
                spell_region = (982, 554, 1548, 871)

                # Deploy 2 Earthquake spells first
                keyboard.send('a')  # Select Earthquake spell
                time.sleep(0.05)

                for spell_num in range(2):
                    # Check during spell deployment
                    if destruction_reached['value']:
                        print("[SBARB FARM] 50% reached during spell deployment - stopping")
                        break
                    # Random location within spell region
                    random_x = random.randint(spell_region[0], spell_region[2])
                    random_y = random.randint(spell_region[1], spell_region[3])
                    fast_click(random_x, random_y)
                    time.sleep(0.05)

                if not destruction_reached['value']:
                    print("[SBARB FARM] 2 Earthquake spells deployed")

                    # Deploy 9 Lightning spells
                    keyboard.send('s')  # Select Lightning spell
                    time.sleep(0.05)

                    for spell_num in range(9):
                        # Check during spell deployment
                        if destruction_reached['value']:
                            print("[SBARB FARM] 50% reached during spell deployment - stopping")
                            break

                        # Random location within spell region
                        random_x = random.randint(spell_region[0], spell_region[2])
                        random_y = random.randint(spell_region[1], spell_region[3])

                        if spell_num % 4 == 0 and spell_num > 0:  # Re-select spell every 4 casts
                            keyboard.send('s')
                            time.sleep(0.02)

                        fast_click(random_x, random_y)
                        time.sleep(0.05)  # Very fast spell casting

                    if not destruction_reached['value']:
                        print("[SBARB FARM] All spells deployed (2 Earthquake + 9 Lightning)")
                        send_discord_debug_log("SBarb Farm: All spells deployed (2 Earthquake + 9 Lightning)")

                # Clear flag - spell casting complete
                spell_casting_active['value'] = False
    else:
        print("[SBARB FARM] 50% reached - skipping spell deployment")

    # Wait for 50% if not reached yet (background thread still monitoring)
    if not destruction_reached['value']:
        print(f"[SBARB FARM] Waiting for {target_destruction}% destruction (60s timeout)...")
        gui.log_message(f"SBarb Farm: Waiting for {target_destruction}%...")

        while (time.time() - attack_start_time) < max_wait_time:
            if destruction_reached['value']:
                break
            time.sleep(0.2)  # Check every 0.2 seconds (faster polling)

        if not destruction_reached['value']:
            elapsed = time.time() - attack_start_time
            print(f"[SBARB FARM] 60s timeout reached (failsafe triggered after {elapsed:.1f}s)")
            gui.log_message("SBarb Farm: 60s timeout - surrendering")
            send_discord_debug_log("SBarb Farm: 60s timeout failsafe triggered", "WARNING")

    # Skip surrender if Return Home was already detected (battle ended early - troops died)
    if attack_failed_early and destruction_reached.get('return_home_pos'):
        print("[SBARB FARM] Skipping surrender - Return Home already detected (battle ended)")
        send_discord_debug_log("SBarb Farm: Skipping surrender - already at end screen")
    # OPTIMIZED surrender sequence - use cached position for instant surrender
    elif surrender_button_cache['detected']:
        # Use cached surrender button position (FAST - no template matching delay)
        surrender_pos = surrender_button_cache['position']
        print(f"[SBARB FARM] Using cached surrender button at {surrender_pos}")
        send_discord_debug_log(f"SBarb Farm: Using cached surrender position at {surrender_pos}")
        fast_click(*surrender_pos)
        time.sleep(0.1)  # Minimal delay (reduced from 0.3s)

        # Click confirm surrender button - FAST
        print("[SBARB FARM] Clicking surrender confirmation...")
        send_discord_debug_log("SBarb Farm: Clicking surrender confirmation")
        fast_click(1483, 898)
        time.sleep(0.1)  # Minimal delay
    else:
        # Detect surrender OR end battle button (both end the battle)
        print("[SBARB FARM] Detecting surrender/end battle button...")
        button_type, x, y = detect_surrender_or_end_battle()

        if button_type:
            print(f"[SBARB FARM] Clicking {button_type} button at ({x}, {y})")
            send_discord_debug_log(f"SBarb Farm: Clicking {button_type} at ({x}, {y})")
            fast_click(x, y)
            time.sleep(0.1)

            # Click confirm button - FAST
            print(f"[SBARB FARM] Clicking {button_type} confirmation...")
            send_discord_debug_log(f"SBarb Farm: Clicking {button_type} confirmation")
            fast_click(1483, 898)
            time.sleep(0.1)  # Minimal delay (reduced from 0.3s)
        else:
            # NO FALLBACK - Detect actual state and handle appropriately
            print("[SBARB FARM] WARNING: Surrender button not detected - detecting state...")
            send_discord_debug_log("SBarb Farm: Surrender not found - detecting state", "WARNING")

            # Check if battle already ended or we're already at base
            button_type, x, y = detect_surrender_or_end_battle()
            if button_type == 'end_battle':
                print("[SBARB FARM] Battle already ended - clicking end battle button")
                send_discord_debug_log("SBarb Farm: Battle ended - clicking end battle")
                fast_click(x, y)
                time.sleep(0.1)
                fast_click(1483, 898)  # Confirmation
                time.sleep(0.1)
            elif detect_return_home_button():
                print("[SBARB FARM] Already at end screen - surrender not needed")
                send_discord_debug_log("SBarb Farm: Already at end screen")
            else:
                # Still in battle but can't find surrender - try deploying troop to enable it
                print("[SBARB FARM] Deploying troop to enable surrender...")
                send_discord_debug_log("SBarb Farm: Deploying troop to enable surrender", "WARNING")
                fast_click(1282, 720)  # Deploy one troop
                time.sleep(2.0)

                # Try finding surrender again
                for retry in range(2):
                    button_type, x, y = detect_surrender_or_end_battle()
                    if button_type == 'surrender':
                        print(f"[SBARB FARM] Surrender now available at {x}, {y}")
                        fast_click(x, y)
                        time.sleep(0.1)
                        fast_click(1483, 898)
                        time.sleep(0.1)
                        break
                    elif button_type == 'end_battle':
                        print("[SBARB FARM] Battle ended - clicking end battle")
                        fast_click(x, y)
                        time.sleep(0.1)
                        fast_click(1483, 898)
                        time.sleep(0.1)
                        break
                    time.sleep(1.0)
                else:
                    # Still can't find - log error but continue
                    print("[SBARB FARM] ERROR: Could not find surrender/end battle - continuing anyway")
                    send_discord_debug_log("SBarb Farm: Failed to surrender - button not found", "ERROR")
                    time.sleep(3)  # Wait for potential auto-end

    # End timer and save attack duration to CSV
    attack_end_time = time.time()
    attack_duration = attack_end_time - attack_start_time

    # Save to data/sbarb_time.csv with achievement building destruction tracking
    csv_file = "data/sbarb_time.csv"
    file_exists = os.path.exists(csv_file)

    # Format building name for CSV (only if all spells completed, otherwise blank)
    building_name_display = building_destroyed.replace('_', ' ').title() if spells_completed else ""

    # Determine attack outcome
    if destruction_reached.get('percentage', 0) >= target_destruction:
        attack_outcome = "Success"
    elif attack_failed_early:
        attack_outcome = "Failed (early end)"
    else:
        attack_outcome = "Failed (timeout)"

    try:
        import csv
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Loop #', 'Duration (seconds)', 'Timestamp', 'Building Destroyed', 'Outcome'])
            writer.writerow([
                loop_count + 1,
                f'{attack_duration:.2f}',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                building_name_display,
                attack_outcome
            ])
    except Exception as e:
        print(f"[SBARB FARM] Error saving timing to CSV: {e}")
        send_discord_debug_log(f"SBarb Farm: Error saving timing - {e}", "WARNING")

    destruction_info = f", {building_name_display} destroyed" if spells_completed else ""
    print(f"[SBARB FARM] Attack duration: {attack_duration:.2f}s{destruction_info} (saved to {csv_file})")
    send_discord_debug_log(f"SBarb Farm: Attack completed in {attack_duration:.2f}s{destruction_info}")

    if attack_failed_early:
        send_discord_debug_log(f"SBarb Farm: attack failed ({attack_outcome})")
        gui.log_message(f"SBarb Farm: attack failed ({attack_outcome})")
    else:
        send_discord_debug_log("SBarb Farm: surrendered attack")
        gui.log_message("SBarb Farm: surrendered attack")

    # Return home - use cached position if available (faster when detected during battle)
    if destruction_reached.get('return_home_pos'):
        print(f"[SBARB FARM] Using cached Return Home position: {destruction_reached['return_home_pos']}")
        fast_click(*destruction_reached['return_home_pos'])
    else:
        fast_click(*config.RETURN_BUTTON)
    time.sleep(1.5)

    # Additional delay before star bonus check
    time.sleep(0.5)

    # Check for star bonus screen
    print("[SBARB FARM] Checking for star bonus screen...")
    if detect_star_bonus_screen():
        print("[SBARB FARM] Star bonus detected! Clicking close button...")
        gui.log_message("SBarb Farm: Star bonus collected")
        send_discord_debug_log("SBarb Farm: Star bonus screen detected and closed")

        # Click the close button (X button)
        fast_click(102, 824)
        time.sleep(0.5)

        # Click return button again to go home
        fast_click(*config.RETURN_BUTTON)
        time.sleep(1.5)
    else:
        print("[SBARB FARM] No star bonus screen detected, continuing...")

    return True  # Attack completed


# ============================================================================
# STORAGE READING FUNCTIONS (for Queue System)
# ============================================================================

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
        max_retries = 3

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
        settings = gui.get_settings()
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
        max_retries = 3

        # Read BB Gold with template matching OCR
        bb_gold_img = ImageGrab.grab(bbox=config.BB_BASE_GOLD_REGION)
        gold_absolute = ocr_attack_resource_template_digits(bb_gold_img, context='bb_base_screen', debug=False, resource_type='gold')

        # Read BB Elixir with template matching OCR
        bb_elixir_img = ImageGrab.grab(bbox=config.BB_BASE_ELIXIR_REGION)
        elixir_absolute = ocr_attack_resource_template_digits(bb_elixir_img, context='bb_base_screen', debug=False, resource_type='elixir')

        # Get BB max storage values from settings
        settings = gui.get_settings()
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


# ============================================================================
# ATTACK MODE HANDLERS
# ============================================================================

def handle_derank_mode():
    """Handle derank mode attack - place one unit using normal deployment strategy and surrender immediately"""
    send_discord_debug_log("Derank mode: attacking any base")
    gui.log_message("Derank mode: attacking any base")
    # Wait for attack screen to be ready (alt hotkey region visible)
    for _ in range(30):  # Wait up to ~6 seconds
        if is_attack_screen_ready():
            print("[DERANK] Attack screen ready (hotkey region visible)")
            break
        time.sleep(0.2)
    else:
        print("[DERANK] Timeout waiting for attack screen, proceeding anyway")
    # Use normal deployment strategy: pick a random side and a valid coordinate
    settings = gui.get_settings()
    chosen_side, side_coords = choose_attack_side(settings)
    print(f"[DERANK] Chosen side: {chosen_side}")
    send_discord_debug_log(f"Derank: chosen side {chosen_side}")
    # Detect alternate hotkeys and prepare KEYS
    alt_hotkeys = detect_alt_hotkeys()
    KEYS = prepare_hotkeys(alt_hotkeys)
    # Move camera to the chosen side
    move_camera_to_side(chosen_side)
    # Pick a random valid deployment coordinate from side_coords['units']
    if side_coords['units']:
        chosen_coord = random.choice(side_coords['units'])
    else:
        # Fallback to a corner if for some reason units list is empty
        chosen_coord = (400, 400)
    troop_key = getattr(config, 'KEYS', {}).get('eDragon', '1') if hasattr(config, 'KEYS') else '1'
    keyboard.send(troop_key)
    time.sleep(0.3)
    human_like_move_click(chosen_coord[0], chosen_coord[1])
    print(f"[DERANK] Clicked at {chosen_coord}")
    send_discord_debug_log(f"Derank: placed unit at {chosen_coord} (side {chosen_side})")
    # Wait 1 second before surrendering
    time.sleep(1)
    # Click surrender button (x=145, y=1132)
    human_like_move_click(145, 1132)
    time.sleep(1)
    # Click confirm surrender button (x=1507, y=901)
    human_like_move_click(1507, 901)
    time.sleep(2)
    send_discord_debug_log("Derank: surrendered attack")
    gui.log_message("Derank: surrendered attack")
    # Return home
    human_like_move_click(*config.RETURN_BUTTON)
    time.sleep(config.RETURN_DELAY)
    return True

def evaluate_base_resources():
    """OCR and evaluate base resources, return (gold, elixir) tuple"""
    send_discord_ocr_log("━━━━━━ **BASE SEARCH** ━━━━━━")

    # Clear overlay for new base scan
    overlay_clear()

    gold_img = ImageGrab.grab(bbox=config.GOLD_REGION)
    gold = ocr_attack_resource_template_digits(gold_img, context='attack_screen', debug=ATTACK_OCR_DEBUG, resource_type='gold')

    # Draw gold OCR region on overlay (confidence based on whether value is reasonable)
    gold_conf = 85 if 0 < gold < 5000000 else 40
    overlay_draw_ocr(config.GOLD_REGION, f"{gold:,}", gold_conf, "GOLD")

    elixir_img = ImageGrab.grab(bbox=config.ELIXIR_REGION)
    elixir = ocr_attack_resource_template_digits(elixir_img, context='attack_screen', debug=ATTACK_OCR_DEBUG, resource_type='elixir')

    # Draw elixir OCR region on overlay
    elixir_conf = 85 if 0 < elixir < 5000000 else 40
    overlay_draw_ocr(config.ELIXIR_REGION, f"{elixir:,}", elixir_conf, "ELIXIR")

    print(f"OCR -> Gold: {gold}, Elixir: {elixir}")
    send_discord_debug_log(f"Resource OCR: Gold {gold:,}, Elixir {elixir:,}")
    # debug_save_ocr_regions()  # DISABLED - causes significant delays (screenshot + disk I/O)

    # Auto-switch profile if resources suggest wrong account (main base - no dark elixir on preview)
    auto_switch_profile_if_needed(gold, elixir, dark_elixir=None)

    return gold, elixir

def should_skip_base(gold, elixir, air_defenses, settings):
    """Determine if base should be skipped based on resources and air defenses"""
    min_amount = settings.get('min_resources', config.MIN_AMOUNT)
    reinforcements_enabled = get_global_reinforcements_enabled()
    
    # Check resources
    if gold + elixir < min_amount:
        send_discord_debug_log(f"Insufficient resources: {gold + elixir:,} < {min_amount:,}, skipping base")
        return True, "insufficient_resources"
    
    # Check air defenses
    if reinforcements_enabled and len(air_defenses) < 4:
        print(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base.")
        gui.log_message(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base.")
        send_discord_debug_log(f"Only {len(air_defenses)} air defenses detected (need 4 for reinforcements), skipping base", "WARNING")
        return True, "insufficient_air_defenses"
    
    if not reinforcements_enabled and len(air_defenses) < 3:
        print(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        gui.log_message(f"Only {len(air_defenses)} air defenses detected, skipping base.")
        send_discord_debug_log(f"Only {len(air_defenses)} air defenses detected, skipping base", "WARNING")
        return True, "insufficient_air_defenses"
    
    return False, None

def skip_base():
    """Skip the current base"""
    x, y = config.SKIP_BUTTON
    jitter = 24
    click_in_square((x - jitter, y - jitter, x + jitter, y + jitter))
    # No delay - detection loop in main_loop() handles waiting for next base

def choose_attack_side(settings, town_hall=None):
    """Choose attack side based on settings and town hall position"""
    attack_side_mode = settings.get('attack_side_mode', 'random')
    sides = list(config.SIDE_DEPLOYMENT_COORDS.keys())
    
    if attack_side_mode == 'th_side' and town_hall:
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
                chosen_side = 'right'
            else:
                chosen_side = 'left'
        else:
            # Town hall is more vertically offset
            if y_diff > 0:
                chosen_side = 'down'
            else:
                chosen_side = 'up'
        
        # Debug information
        debug_info = f"TH at ({th_x}, {th_y}), center at ({BASE_CENTER_X}, {BASE_CENTER_Y})"
        debug_info += f", x_diff={x_diff:.1f}, y_diff={y_diff:.1f}"
        gui.debug_message(debug_info)
        
        side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
        gui.log_message(f"Chosen attack side: {chosen_side} (TH on {chosen_side} side of base center)")
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
        gui.log_message(f"Chosen attack side: {chosen_side} (random)")
        print(f"Chosen attack side: {chosen_side} (random)")
        send_discord_debug_log(f"Attack side chosen: {chosen_side} (random)")
        # Draw attack side indicator on overlay
        overlay_draw_side(chosen_side)
        overlay_update()
        return chosen_side, side_coords

def detect_alt_hotkeys():
    """Detect if alternate hotkeys should be used based on template matching"""
    template_path = 'assets/alt_hotkey_template.png'
    region = (522, 1273, 664, 1412)
    
    try:
        template = cv2.imread(template_path)
        if template is None:
            print(f"[DEBUG] Failed to load template: {template_path}")
            return False
        
        h, w, _ = template.shape
        screenshot = ImageGrab.grab(bbox=region)
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Ensure screenshot and template are the same size
        if screenshot_cv.shape[0] == h and screenshot_cv.shape[1] == w:
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= 0.8:
                gui.log_message('Alternate hotkeys enabled (template matched in region 522,1273,664,1412)')
                gui.debug_message('USING ALTERNATE HOTKEY SETUP (template matched)')
                print('Alternate hotkeys enabled (template matched in region 522,1273,664,1412)')
                send_discord_debug_log('Alternate hotkeys enabled (template matched)')
                return True
            else:
                gui.log_message('Default hotkeys enabled (template not matched in region 522,1273,664,1412)')
                gui.debug_message('USING DEFAULT HOTKEY SETUP (template not matched)')
                print('Default hotkeys enabled (template not matched in region 522,1273,664,1412)')
                send_discord_debug_log('Default hotkeys enabled (template not matched)')
                return False
        else:
            gui.log_message('Default hotkeys enabled (screenshot/template size mismatch)')
            gui.debug_message('USING DEFAULT HOTKEY SETUP (screenshot/template size mismatch)')
            print('Default hotkeys enabled (screenshot/template size mismatch)')
            send_discord_debug_log('Default hotkeys enabled (screenshot/template size mismatch)')
            return False
            
    except Exception as e:
        gui.log_message(f'Default hotkeys enabled (template matching error: {e})')
        gui.debug_message(f'USING DEFAULT HOTKEY SETUP (template matching error: {e})')
        print(f'Default hotkeys enabled (template matching error: {e})')
        send_discord_debug_log(f'Default hotkeys enabled (template matching error: {e})', "WARNING")
        return False

def prepare_hotkeys(alt_hotkeys):
    """Prepare hotkeys based on whether alternate hotkeys are detected"""
    KEYS = dict(config.KEYS)
    if alt_hotkeys:
        # Swap troop1 and troop2 if alternate hotkeys detected
        KEYS['troop1'], KEYS['troop2'] = KEYS['troop2'], KEYS['troop1']
        KEYS['queen'], KEYS['warden'] = KEYS['warden'], KEYS['queen']
    return KEYS

def check_town_hall_level(town_hall, settings):
    """Check if town hall level is acceptable, return True if should skip"""
    if town_hall:
        x, y, level, conf = town_hall
        print(f"Detected Town Hall Level {level} at ({x}, {y}) - Confidence: {conf:.2f}")
        gui.log_message(f"Town Hall Level {level} detected")
        
        # Check max Town Hall level from settings
        max_th_level = settings.get('max_th_level', 15)
        if level > max_th_level:
            print(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            gui.log_message(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base.")
            send_discord_debug_log(f"Town Hall level {level} exceeds max allowed ({max_th_level}), skipping base", "WARNING")
            return True
    else:
        print("Town Hall not detected")
        gui.log_message("Town Hall not detected")
        
        # Check if we should skip when town hall detection fails
        skip_on_th_fail = get_global_skip_on_th_fail()
        if skip_on_th_fail:
            print("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base.")
            gui.log_message("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base.")
            send_discord_debug_log("Town Hall detection failed and 'Skip on TH Detection Fail' is enabled - skipping base", "WARNING")
            return True
    
    return False

def deploy_lightning_spells(air_defenses, lightning_targets, chosen_side, settings, KEYS):
    """Deploy lightning spells on air defenses"""
    if not lightning_targets:
        print("No air defenses detected - skipping lightning spells")
        gui.log_message("No air defenses detected - skipping lightning spells")
        send_discord_debug_log("No air defenses detected - skipping lightning spells", "WARNING")
        return
    
    reinforcements_enabled = get_global_reinforcements_enabled()
    
    if reinforcements_enabled:
        print(f"Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        gui.log_message(f"Deploying 13 lightning spells on 4 air defenses (Reinforcements mode)")
        send_discord_debug_log("Deploying 13 lightning spells (Reinforcements mode)")
        
        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level
        
        spells_used = 0
        lightning_damage = settings.get('lightning_damage', 300)
        
        # Use 12 spells (3 per AD) on 4 air defenses
        for idx, (x, y, level, _) in enumerate(air_defenses[:4]):
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            for i in range(spell_count):
                if spells_used < 11:
                    keyboard.send(KEYS['lightning'])
                else:
                    keyboard.send('s')  # Use 'S' for the last 2 spells
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/13 at ({x}, {y}) (AD {idx+1})")
                spells_used += 1
        
        # 13th spell at random location
        random_x = random.randint(1003, 1495)
        random_y = random.randint(471, 853)
        keyboard.send('s')
        time.sleep(0.02)
        jitter = random.randint(-5, 5)
        pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
        pyautogui.click()
        print(f"    13th Lightning spell at random location ({random_x}, {random_y})")
        spells_used += 1
        
        gui.log_message("Lightning spell deployment completed (Reinforcements mode)")
        send_discord_debug_log("Lightning spell deployment completed (Reinforcements mode)")
    else:
        print(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        gui.log_message(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        send_discord_debug_log(f"Deploying lightning spells on top 3 air defenses (non-reinforcements mode)")
        
        position_to_level = {}
        for x, y, level, _ in air_defenses:
            position_to_level[(x, y)] = level
        
        spells_used = 0
        lightning_damage = settings.get('lightning_damage', 300)
        
        # Target exactly 3 air defenses (9 spells total)
        for idx, (x, y) in enumerate(lightning_targets[:3]):  # Only first 3 air defenses
            level = position_to_level.get((x, y), 1)
            spell_count = calculate_lightning_spells_needed(level, lightning_damage)
            hp = config.AIR_DEFENSE_HP.get(level, 1000)
            print(f"  Air Defense {idx+1} (Level {level}) has {hp} HP, using {spell_count} lightning spells ({lightning_damage} damage each)")
            
            for i in range(spell_count):
                keyboard.send(KEYS['lightning'])
                time.sleep(0.02)
                jitter = random.randint(-3, 3)
                pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Lightning spell {spells_used + 1}/9 at ({x}, {y}) (AD {idx+1})")
                spells_used += 1
        
        print(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining for air sweepers")
        gui.log_message(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")
        send_discord_debug_log(f"Used {spells_used}/9 spells on 3 air defenses, {11 - spells_used} spells remaining")
        
        # Handle remaining spells (should be 2 for air sweepers)
        handle_remaining_lightning_spells(spells_used, chosen_side, KEYS)
        
        gui.log_message("Lightning spell deployment completed (non-reinforcements mode)")
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
            gui.log_message(f"Detected {len(sweepers)} air sweepers for lightning targeting.")
            send_discord_debug_log(f"Detected {len(sweepers)} air sweepers for lightning targeting")
            
            # Map attack side to directions
            side_to_dirs = {
                'left': ['left', 'up_left', 'down_left'],
                'right': ['right', 'up_right', 'down_right'],
                'up': ['up', 'up_left', 'up_right'],
                'down': ['down', 'down_left', 'down_right']
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
                    keyboard.send(KEYS['lightning'])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(x + 20 + jitter, y + 20 + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Lightning spell {spells_used + i + 1}/11 at Air Sweeper ({x}, {y}) facing {direction}")
                print("Air sweeper lightning spells deployed successfully")
                gui.log_message("Air sweeper lightning spells deployed successfully")
                send_discord_debug_log("Air sweeper lightning spells deployed successfully")
            else:
                print("No air sweeper found for remaining lightning spells.")
                gui.log_message("No air sweeper found for remaining lightning spells.")
                send_discord_debug_log("No air sweeper found for remaining lightning spells", "WARNING")
                # Use the 2 spells at random coordinates as fallback
                random_coords = [
                    (1003, 471),  # Point 1
                    (1495, 853)   # Point 2
                ]
                for i in range(2):
                    x1, y1 = random_coords[0]
                    x2, y2 = random_coords[1]
                    random_x = random.randint(min(x1, x2), max(x1, x2))
                    random_y = random.randint(min(y1, y2), max(y1, y2))
                    keyboard.send(KEYS['lightning'])
                    time.sleep(0.02)
                    jitter = random.randint(-5, 5)
                    pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                    pyautogui.click()
                    print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")
        else:
            # Failsafe: Use remaining lightning spells at random coordinates
            print(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            gui.log_message(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            send_discord_debug_log(f"Using {remaining_spells} remaining lightning spells at random coordinates")
            
            random_coords = [
                (1003, 471),  # Point 1
                (1495, 853)   # Point 2
            ]
            for i in range(remaining_spells):
                x1, y1 = random_coords[0]
                x2, y2 = random_coords[1]
                random_x = random.randint(min(x1, x2), max(x1, x2))
                random_y = random.randint(min(y1, y2), max(y1, y2))
                keyboard.send(KEYS['lightning'])
                time.sleep(0.02)
                jitter = random.randint(-5, 5)
                pyautogui.moveTo(random_x + jitter, random_y + jitter, duration=0.01)
                pyautogui.click()
                print(f"    Failsafe lightning spell {spells_used + i + 1}/11 at ({random_x}, {random_y})")

def move_camera_to_side(chosen_side, fast_mode=False):
    """Move camera to the chosen attack side"""
    send_discord_debug_log(f"Moving camera to {chosen_side} side")
    drag_map = {
        'left': ((600, 700), (1500, 700)),    # Drag right to see left
        'right': ((2000, 700), (1000, 700)),  # Drag left to see right
        'up': ((1280, 300), (1280, 900)),     # Drag down to see up (top)
        'down': ((1280, 1100), (1280, 700)),  # Drag up to see down (bottom)
    }
    drag_start, drag_end = drag_map[chosen_side]
    pyautogui.moveTo(*drag_start, duration=config.DRAG_DURATION_START)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseDown()
    time.sleep(config.DRAG_DELAY)
    pyautogui.moveTo(*drag_end, duration=config.DRAG_DURATION_END)
    time.sleep(config.DRAG_DELAY)
    pyautogui.mouseUp()
    # Fast mode for SGoblin Farm - minimal delay
    if fast_mode:
        time.sleep(0.3)
    else:
        time.sleep(config.DRAG_POST_DELAY)

def deploy_troops(side_coords, settings, KEYS):
    """Deploy all troops (generic troop slots 1-7, Siege, Heroes)"""
    # Get troop counts from settings
    troop_counts = settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])

    # Deploy each troop type that has count > 0
    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'

            # Get deployment coordinates
            troop_coords = random.sample(side_coords['units'], min(troop_count, len(side_coords['units'])))

            # Select troop
            keyboard.send(KEYS[troop_key])
            time.sleep(0.1)

            # Deploy troops
            for x, y in troop_coords:
                random_sleep(config.SLEEP_MIN, config.SLEEP_MAX)
                pyautogui.moveTo(x, y, duration=random.uniform(0.03, 0.07))
                pyautogui.click()

            send_discord_debug_log(f"Deployed {troop_count} troops from slot {i+1}")
            print(f"Deployed {troop_count} troops from slot {i+1}")
    
    # Deploy Siege Machine and Heroes
    print("Deploying siege machine and heroes...")
    send_discord_debug_log("Deploying siege machine and heroes")
    hero_pos = side_coords['hero']
    
    # Get individual hero ability timing from settings
    settings = gui.get_settings()
    queen_timing = settings.get('queen_ability_timing', 15)
    king_timing = settings.get('king_ability_timing', 15)
    warden_timing = settings.get('warden_ability_timing', 15)
    rc_timing = settings.get('rc_ability_timing', 15)
    
    # Deploy siege machine
    keyboard.send(KEYS['siege'])
    time.sleep(config.HERO_DELAY)
    human_like_move_click(*hero_pos)
    time.sleep(config.POST_DEPLOY_DELAY)
    
    # Deploy heroes and start their ability timers individually
    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }
    
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
    for role in ['queen', 'king', 'warden', 'rc']:
        # Deploy the hero
        keyboard.send(KEYS[role])
        time.sleep(config.HERO_DELAY)
        human_like_move_click(*hero_pos)
        time.sleep(config.POST_DEPLOY_DELAY)
        
        # Start ability timer for this specific hero
        timing = hero_timings[role]
        if timing != -1:  # Only start thread if ability is not disabled
            ability_thread = threading.Thread(
                target=activate_hero_ability, 
                args=(role, timing), 
                daemon=True
            )
            ability_thread.start()
            send_discord_debug_log(f"Started {role.title()} ability timer ({timing} seconds)")

def wait_for_battle_end():
    """Wait until battle ends by detecting black bar region"""
    send_discord_debug_log("Waiting for battle to end...")
    check_count = 0
    while running:
        img = ImageGrab.grab(bbox=config.BLACK_BAR_REGION)
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
    gui.log_message("Battle ended, capturing loot...")
    send_discord_debug_log("Battle ended, capturing loot")
    time.sleep(config.LOOT_CAPTURE_DELAY)
    
    loot_data = ocr_loot()
    save_loot_data(loot_data, loop_count + 1)
    
    # Update GUI loot statistics
    root.after(0, lambda: gui.update_loot_stats(loot_data))
    
    # Return home
    human_like_move_click(*config.RETURN_BUTTON)

    # Wait for base screen to load (template matching army button)
    if not wait_for_base_screen(timeout=15):
        print("[WARNING] Base screen not detected after return - OCR may be inaccurate")
        send_discord_debug_log("Base screen not detected after return - OCR may fail", "WARNING")

    # Wait for resources to stabilize before reading
    time.sleep(0.3)

    # Check base resources after returning home (template matching OCR with retry)
    max_retries = 3

    # Read Gold with retry
    base_gold = 0
    for attempt in range(max_retries):
        base_gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
        base_gold = ocr_attack_resource_template_digits(base_gold_img, context='base_screen', debug=False, resource_type='gold')
        if base_gold > 0:
            break
        if attempt < max_retries - 1:
            print(f"[STORAGE] Gold OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
            time.sleep(0.2)

    # Read Elixir with retry
    base_elixir = 0
    for attempt in range(max_retries):
        base_elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
        base_elixir = ocr_attack_resource_template_digits(base_elixir_img, context='base_screen', debug=False, resource_type='elixir')
        if base_elixir > 0:
            break
        if attempt < max_retries - 1:
            print(f"[STORAGE] Elixir OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
            time.sleep(0.2)

    # Read Dark Elixir with retry
    base_dark_elixir = 0
    if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
        for attempt in range(max_retries):
            base_dark_elixir_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
            base_dark_elixir = ocr_attack_resource_template_digits(base_dark_elixir_img, context='base_dark_elixir', debug=False)
            if base_dark_elixir > 0:
                break
            if attempt < max_retries - 1:
                print(f"[STORAGE] DE OCR returned 0, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(0.2)
    print(f"Base resources after attack: Gold={base_gold}, Elixir={base_elixir}, Dark Elixir={base_dark_elixir}")
    send_discord_debug_log(f"Base resources after attack: Gold={base_gold:,}, Elixir={base_elixir:,}, Dark Elixir={base_dark_elixir:,}")

    # Track resources and check for full storages (no loot gained over 3 attacks)
    track_resources(base_gold, base_elixir, base_dark_elixir, base_type='main_base')
    check_and_pause_if_storages_full(base_type='main_base')

    # Check if storages are full (Farming profile, at least 2 of 3 full)
    settings = gui.get_settings()
    current_profile = settings.get('current_profile', '')
    if current_profile == 'Farming':
        # Get max values from settings (fall back to defaults if missing)
        try:
            import json
            with open('bot_settings.json', 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            max_gold = int(file_data.get('max_gold_storage', 14000000))
            max_elixir = int(file_data.get('max_elixir_storage', 14000000))
            max_dark = int(file_data.get('max_dark_elixir_storage', 240000))
        except Exception:
            max_gold = 14000000
            max_elixir = 14000000
            max_dark = 240000
        full_count = 0
        if base_gold == max_gold:
            full_count += 1
        if base_elixir == max_elixir:
            full_count += 1
        if base_dark_elixir == max_dark:
            full_count += 1
        if full_count >= 2:
            msg = f"<@everyone> Storages are full! Gold: {base_gold:,}/{max_gold:,}, Elixir: {base_elixir:,}/{max_elixir:,}, Dark Elixir: {base_dark_elixir:,}/{max_dark:,}. Bot paused."
            send_discord_notification(msg)
            gui.log_message("At least 2 storages are full. Bot paused.")
            return True  # Signal to pause bot
    
    # Check if storages are full (legacy logic)
    if base_gold == 11_000_000 or base_elixir == 14_000_000:
        msg = f"<@everyone> Storages are full! Gold: {base_gold:,}, Elixir: {base_elixir:,}. Bot paused."
        send_discord_notification(msg)
        return True  # Signal to pause bot
    
    # Handle reinforcements
    reinforcements_enabled = get_global_reinforcements_enabled()
    if reinforcements_enabled:
        print("Requesting reinforcements...")
        gui.log_message("Requesting reinforcements...")
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
            gui.log_message("Reinforcements requested successfully")
            send_discord_debug_log("Reinforcements requested successfully")
        else:
            print("Failed to detect army button - skipping reinforcements")
            gui.log_message("Failed to detect army button - skipping reinforcements")
            send_discord_debug_log("Failed to detect army button - skipping reinforcements", "WARNING")

    return False  # No need to pause

def detect_all_achievement_buildings(enabled_buildings=None):
    """
    Detect achievement building types on the base using PARALLEL template matching.
    All building types are scanned simultaneously for maximum speed.

    Args:
        enabled_buildings: List of building types to scan. If None, scans all types.

    Returns:
        Dictionary with building type as key and list of (x, y, confidence) tuples as value
    """
    if enabled_buildings is None:
        enabled_buildings = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot', 'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    print(f"[PARALLEL SCAN] Scanning {len(enabled_buildings)} building types simultaneously...")
    start_time = time.time()

    # Capture base screenshot ONCE (shared by all threads)
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    results = {}
    total_found = 0

    # Use ThreadPoolExecutor to scan all building types in parallel (max 5 workers to reduce CPU usage)
    with ThreadPoolExecutor(max_workers=min(5, len(enabled_buildings))) as executor:
        # Submit all detection tasks
        future_to_building = {
            executor.submit(detect_achievement_building_from_image, building_type, base_cv): building_type
            for building_type in enabled_buildings
        }

        # Collect results as they complete
        for future in as_completed(future_to_building):
            building_type = future_to_building[future]
            try:
                buildings = future.result()
                if buildings:
                    results[building_type] = buildings
                    total_found += len(buildings)
                    print(f"  ✓ {building_type.replace('_', ' ')}: {len(buildings)} found")
                else:
                    print(f"  - {building_type.replace('_', ' ')}: none found")
            except Exception as e:
                print(f"  ✗ {building_type.replace('_', ' ')}: ERROR - {str(e)}")
                send_discord_debug_log(f"Error detecting {building_type}: {str(e)}", "ERROR")

    elapsed_time = time.time() - start_time
    print(f"[PARALLEL SCAN] Complete in {elapsed_time:.2f}s - Total found: {total_found}")
    send_discord_debug_log(f"Parallel scan complete: {total_found} buildings in {elapsed_time:.2f}s")

    return results


def _scan_achievement_buildings_parallel_internal(settings):
    """
    INTERNAL: Scan achievement buildings in parallel and return highest-priority match.

    This is the internal parallel implementation used when user enables parallel scanning.
    Scans all enabled achievement building types simultaneously using ThreadPoolExecutor.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for highest-priority building found,
        or None if no buildings detected
    """
    # 1. Extract enabled buildings from checkboxes
    enabled_buildings = []
    all_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower',
                 'scattershot', 'spell_tower', 'multi_archer_tower',
                 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    for building_type in all_types:
        checkbox_key = f'achievement_scan_{building_type}'
        if settings.get(checkbox_key, True):  # Default enabled if not found
            enabled_buildings.append(building_type)

    if not enabled_buildings:
        print("[PARALLEL SCAN] No achievement buildings enabled in settings")
        return None

    print(f"[PARALLEL SCAN] Scanning {len(enabled_buildings)} enabled building types in parallel...")

    # 2. Get priority list from settings
    priority_list = settings.get('achievement_priority_list', all_types)

    # 3. Filter to only enabled buildings in priority order
    priority_enabled = [b for b in priority_list if b in enabled_buildings]

    # 4. Parallel scan using existing function (scans all types simultaneously)
    all_buildings = detect_all_achievement_buildings(enabled_buildings)

    if not all_buildings:
        print("[PARALLEL SCAN] No achievement buildings detected on base")
        return None

    # 5. Select highest-priority building from results
    for building_type in priority_enabled:
        if building_type in all_buildings and all_buildings[building_type]:
            # Get highest confidence match of this type
            best_match = max(all_buildings[building_type], key=lambda x: x[2])
            x, y, confidence = best_match
            print(f"[PARALLEL SCAN] Selected: {building_type.replace('_', ' ').title()} (Priority #{priority_enabled.index(building_type)+1}, Confidence: {confidence:.3f})")
            return (x, y, confidence, building_type)

    # Fallback: return highest confidence overall (shouldn't happen if priority list is complete)
    best_overall = None
    best_conf = 0
    best_type = None
    for btype, matches in all_buildings.items():
        for match in matches:
            if match[2] > best_conf:
                best_overall = match
                best_conf = match[2]
                best_type = btype

    if best_overall:
        print(f"[PARALLEL SCAN] Fallback: Selected {best_type.replace('_', ' ').title()} (highest confidence: {best_conf:.3f})")
        return (best_overall[0], best_overall[1], best_overall[2], best_type)

    return None


def scan_achievement_buildings_parallel_priority(settings):
    """
    Scan achievement buildings using user's preferred method (parallel or sequential).

    Checks GUI setting 'achievement_parallel_scan' to decide:
    - True: Use parallel scanning (faster, higher CPU usage, may cause spikes/crashes)
    - False: Use sequential scanning (slower, minimal CPU usage, stable) [DEFAULT]

    This function acts as a dispatcher based on user preference.

    Used by: SBarb Farm, SGoblin Farm modes.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_parallel_scan: Boolean (default False)
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for highest-priority building found,
        or None if no buildings detected
    """
    # Check if user enabled parallel scanning (default: False for stability)
    use_parallel = settings.get('achievement_parallel_scan', False)

    if use_parallel:
        print("[SCAN MODE] Using parallel scanning (fast, higher CPU)")
        send_discord_debug_log("Achievement scan: Parallel mode (fast, higher CPU)")
        return _scan_achievement_buildings_parallel_internal(settings)
    else:
        print("[SCAN MODE] Using sequential scanning (slower, low CPU)")
        send_discord_debug_log("Achievement scan: Sequential mode (slower, low CPU)")
        return scan_achievement_buildings_sequential(settings)


def scan_achievement_buildings_sequential(settings):
    """
    Scan achievement buildings sequentially (one at a time) in priority order.

    This is slower than parallel scanning but uses minimal CPU and won't cause spikes.
    Stops at FIRST priority match found for efficiency.

    Used by: SBarb Farm, SGoblin Farm when parallel scanning is disabled.

    Args:
        settings: Dictionary from gui.get_settings() containing:
            - achievement_priority_list: List of building types in priority order
            - achievement_scan_<building>: Boolean checkboxes for each building type

    Returns:
        Tuple (x, y, confidence, building_type) for first priority building found,
        or None if no buildings detected
    """
    # 1. Extract enabled buildings from checkboxes
    enabled_buildings = []
    all_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower',
                 'scattershot', 'spell_tower', 'multi_archer_tower',
                 'ricochet_cannon', 'firespitter', 'multi_gear_tower']

    for building_type in all_types:
        checkbox_key = f'achievement_scan_{building_type}'
        if settings.get(checkbox_key, True):
            enabled_buildings.append(building_type)

    if not enabled_buildings:
        print("[SEQUENTIAL SCAN] No achievement buildings enabled in settings")
        return None

    # 2. Get priority list from settings
    priority_list = settings.get('achievement_priority_list', all_types)

    # 3. Filter to only enabled buildings in priority order
    priority_enabled = [b for b in priority_list if b in enabled_buildings]

    print(f"[SEQUENTIAL SCAN] Scanning {len(priority_enabled)} enabled buildings in priority order...")
    send_discord_debug_log(f"Sequential scan: checking {len(priority_enabled)} building types")

    # 4. Capture screenshot ONCE (shared for all detections)
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # 5. Scan each building type sequentially (one at a time)
    for i, building_type in enumerate(priority_enabled):
        print(f"  [{i+1}/{len(priority_enabled)}] Checking {building_type.replace('_', ' ')}...")

        # Call detection function with shared screenshot
        buildings = detect_achievement_building_from_image(building_type, base_cv)

        if buildings:
            # FOUND! Return first match immediately (early exit)
            best_match = max(buildings, key=lambda x: x[2])  # Highest confidence
            x, y, confidence = best_match
            print(f"  ✓ FOUND! {building_type.replace('_', ' ').title()} (Priority #{i+1}, Confidence: {confidence:.3f})")
            send_discord_debug_log(f"Sequential scan found: {building_type} (priority #{i+1})")
            return (x, y, confidence, building_type)
        else:
            print(f"  ✗ Not found, continuing...")

    print("[SEQUENTIAL SCAN] No achievement buildings detected")
    send_discord_debug_log("Sequential scan: no buildings found")
    return None


def perform_achievement_farm_attack():
    """Perform Achievement Farm attack with 3 targeting modes: Target, Clumps, First Detected"""
    print("=== ENTERING ACHIEVEMENT FARM MODE ===")
    send_discord_debug_log("=== ENTERING ACHIEVEMENT FARM MODE ===")
    gui.log_message("Achievement Farm mode activated")

    # Get current settings from GUI
    settings = gui.get_settings()

    # Get priority building type, targeting mode, and priority list from settings
    priority_building = settings.get('achievement_target_building', 'eagle_artillery')
    target_mode = settings.get('achievement_farm_target_mode', 'clumps')
    priority_list = settings.get('achievement_priority_list', [
        'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
        'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
    ])

    # Build list of enabled buildings from checkboxes
    # Uses full key names: achievement_scan_eagle_artillery, achievement_scan_inferno_tower, etc.
    enabled_buildings = []
    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                      'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
    for bt in building_types:
        if settings.get(f'achievement_scan_{bt}', True):
            enabled_buildings.append(bt)

    if not enabled_buildings:
        print("[ACH FARM] ERROR: No buildings enabled for scanning! Please enable at least one building type.")
        gui.log_message("No buildings enabled - aborting")
        send_discord_debug_log("Achievement Farm: No buildings enabled for scanning", "ERROR")
        return False

    print(f"Targeting Mode: {target_mode.replace('_', ' ').title()}")
    print(f"Priority target: {priority_building.replace('_', ' ').title()}")
    print(f"Enabled buildings: {', '.join([b.replace('_', ' ').title() for b in enabled_buildings])}")
    gui.log_message(f"Mode: {target_mode.replace('_', ' ').title()}")
    send_discord_debug_log(f"Achievement Farm: Mode={target_mode}, Target={priority_building.replace('_', ' ')}, Enabled={len(enabled_buildings)}")

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[ACH FARM] Attack screen not ready - skipping base")
        send_discord_debug_log("Achievement Farm: Attack screen timeout - skipping", "WARNING")
        gui.log_message("Achievement Farm: Attack screen timeout - skipping")
        skip_base()
        return False

    # Attack screen verified ready, preparing to scan...
    print("[ACH FARM] Attack screen ready, preparing to scan...")
    time.sleep(0.1)  # Short delay before zoom

    # Zoom out BEFORE template matching for better detection and speed
    print("[ACH FARM] Zooming out before template matching...")
    pyautogui.moveTo(1280, 700, duration=0)
    time.sleep(0.1)
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.01)
    time.sleep(0.2)
    print("[ACH FARM] Zoom complete, starting template matching...")

    # Determine attack target based on targeting mode
    x, y = None, None
    global skipped_bases

    if target_mode == 'target':
        # MODE 1: Target - Try buildings in priority order until one is found
        print(f"[TARGET MODE] Trying buildings in priority order...")

        # Filter priority list to only include enabled buildings
        priority_enabled = [b for b in priority_list if b in enabled_buildings]

        if not priority_enabled:
            print(f"[TARGET MODE] No enabled buildings in priority list!")
            gui.log_message(f"No enabled buildings - surrendering")
            send_discord_debug_log(f"Achievement Farm [TARGET]: No enabled buildings", "WARNING")
            # Surrender immediately
            fast_click(152, 1136)
            time.sleep(0.3)
            fast_click(1483, 898)
            time.sleep(0.3)
            fast_click(*config.RETURN_BUTTON)
            time.sleep(1.5)
            skipped_bases += 1
            return False

        # Try each building in priority order
        overlay_clear()  # Clear overlay before scanning
        found = False
        for building_type in priority_enabled:
            print(f"  Trying: {building_type.replace('_', ' ').title()}...", end=" ")
            buildings = detect_achievement_building(building_type)
            if buildings:
                x, y, confidence = buildings[0]
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                x = x + bw // 2
                y = y + bh // 2
                print(f"FOUND at center ({x}, {y})")
                gui.log_message(f"Target {building_type.replace('_', ' ')} found - attacking!")
                send_discord_debug_log(f"Achievement Farm [TARGET]: {building_type.replace('_', ' ')} at ({x}, {y})")
                # Draw spell target on overlay at building center
                overlay_draw_spell_target(x, y, f"TARGET: {building_type.replace('_', ' ')}")
                found = True
                break
            else:
                print("not found")

        if not found:
            print(f"[TARGET MODE] No buildings detected in priority list - skipping base")
            gui.log_message(f"No targets found - skipping base")
            send_discord_debug_log(f"Achievement Farm [TARGET]: No buildings found - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            skipped_bases += 1
            return False  # Continue to next base

    elif target_mode == 'first_detected':
        # MODE 3: First Detected - FAST MODE: Stop scanning as soon as ANY building is found (PRIORITY ORDER)
        print(f"[FIRST DETECTED MODE] Scanning in priority order for first match...")
        overlay_clear()  # Clear overlay before scanning

        # Filter priority list to only include enabled buildings
        priority_enabled = [b for b in priority_list if b in enabled_buildings]

        # Scan in PRIORITY ORDER and stop at first match
        found_building = None
        found_type = None

        for building_type in priority_enabled:
            buildings = detect_achievement_building(building_type)
            if buildings:
                # FOUND! Stop scanning immediately
                found_building = buildings[0]
                found_type = building_type
                break

        if found_building:
            x, y, confidence = found_building
            # Calculate building center using actual template size
            bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(found_type, (70, 70))
            x = x + bw // 2
            y = y + bh // 2
            print(f"FIRST DETECTED: {found_type.replace('_', ' ').title()} at center ({x}, {y}) - Confidence: {confidence:.3f}")
            gui.log_message(f"First detected: {found_type.replace('_', ' ')} - attacking!")
            send_discord_debug_log(f"Achievement Farm [FIRST]: {found_type.replace('_', ' ')} at ({x}, {y})")
            # Draw spell target on overlay at building center
            overlay_draw_spell_target(x, y, f"FIRST: {found_type.replace('_', ' ')}")
        else:
            print(f"No buildings detected after scanning priority list - skipping base")
            gui.log_message(f"No buildings detected - skipping base")
            send_discord_debug_log(f"Achievement Farm [FIRST]: No buildings detected - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            skipped_bases += 1
            return False

    else:  # target_mode == 'clumps'
        # MODE 2: Clumps - Look for clusters, prefer priority building if no cluster
        print(f"[CLUMPS MODE] Scanning enabled building types for clusters...")
        overlay_clear()  # Clear overlay before scanning
        if gui.overlay and gui.overlay_enabled:
            gui.overlay.draw_text(100, 50, "CLUMPS MODE: Scanning all building types...", '#FFFF00')
            gui.overlay.update()
        all_buildings = detect_all_achievement_buildings(enabled_buildings)

        if not all_buildings:
            print(f"No achievement buildings found - skipping base")
            gui.log_message(f"No achievement buildings found - skipping base")
            send_discord_debug_log(f"Achievement Farm [CLUMPS]: No buildings found - skipping base")
            # Skip base and continue searching
            fast_click(*config.SKIP_BUTTON)
            time.sleep(config.SKIP_DELAY)
            skipped_bases += 1
            return False  # Continue to next base

        # Combine all buildings into single list with type labels
        combined_buildings = []
        for building_type, buildings in all_buildings.items():
            for bx, by, conf in buildings:
                combined_buildings.append((bx, by, conf, building_type))

        print(f"Found {len(combined_buildings)} total building(s)")

        # Look for clusters (pass buildings with types for accurate center-to-center distance)
        clusters = find_building_clusters(combined_buildings, max_distance=125)

        if len(clusters) > 0 and len(clusters[0]) >= 2:
            # Attack the biggest cluster
            biggest_cluster = clusters[0]
            x, y = get_cluster_center(biggest_cluster)

            # Identify building types in cluster (now directly available in cluster data)
            cluster_types = {}
            for cx, cy, cconf, ctype in biggest_cluster:
                cluster_types[ctype] = cluster_types.get(ctype, 0) + 1

            type_summary = ", ".join([f"{count} {btype.replace('_', ' ')}" for btype, count in cluster_types.items()])

            print(f"CLUSTER FOUND: {len(biggest_cluster)} buildings clustered together!")
            print(f"  Cluster contains: {type_summary}")
            print(f"  Attack center: ({x}, {y})")
            gui.log_message(f"Cluster: {type_summary} - attacking all!")
            send_discord_debug_log(f"Achievement Farm [CLUMPS]: {type_summary} at ({x}, {y})")
            # Draw cluster center on overlay
            overlay_draw_spell_target(x, y, f"CLUSTER ({len(biggest_cluster)})")
        else:
            # No cluster - select building based on priority list order
            print(f"No cluster found, selecting highest priority building...")

            # Filter priority list to only buildings that were actually found
            found_building_types = list(all_buildings.keys())
            priority_enabled = [b for b in priority_list if b in found_building_types]

            # Attack the highest priority building that was found
            target_building = None
            target_type = None

            if priority_enabled:
                target_type = priority_enabled[0]  # Highest priority
                target_building = all_buildings[target_type][0]  # Highest confidence of that type
                x, y, confidence = target_building
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(target_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                print(f"PRIORITY TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
                gui.log_message(f"Single {target_type.replace('_', ' ')} (priority #{priority_list.index(target_type)+1}) - attacking")
                send_discord_debug_log(f"Achievement Farm [CLUMPS-PRIORITY]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})")
                # Draw priority target on overlay at building center
                overlay_draw_spell_target(center_x, center_y, f"PRIORITY: {target_type.replace('_', ' ')}")
                # Update x, y to center for spell casting
                x, y = center_x, center_y
            else:
                # Fallback: attack any found building (shouldn't happen)
                target_type = list(all_buildings.keys())[0]
                x, y, confidence = all_buildings[target_type][0]
                # Calculate building center using actual template size
                bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(target_type, (70, 70))
                center_x = x + bw // 2
                center_y = y + bh // 2
                print(f"FALLBACK TARGET: {target_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
                gui.log_message(f"Single {target_type.replace('_', ' ')} (fallback) - attacking")
                send_discord_debug_log(f"Achievement Farm [CLUMPS-FALLBACK]: {target_type.replace('_', ' ')} at ({center_x}, {center_y})")
                # Draw fallback target on overlay at building center
                overlay_draw_spell_target(center_x, center_y, f"FALLBACK: {target_type.replace('_', ' ')}")
                # Update x, y to center for spell casting
                x, y = center_x, center_y

    # Update overlay to show all detections and target before attacking
    overlay_update()

    # Deploy spells on target - ULTRA FAST using Windows API (~12 CPS)
    # 1 Earthquake spell (hotkey A) + 10 Lightning spells (hotkey S)
    SPELL_CLICK_DELAY_MS = 83  # ~12 CPS for spell casting

    print(f"[ACH FARM] Deploying 1 Earthquake + 10 Lightning spells at ({x}, {y}) using Windows API (~12 CPS)...")
    spell_start = time.time()

    # Earthquake spell
    keyboard.send('a')
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)
    turbo_move_cursor(x, y)
    turbo_fast_click()
    time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    # Lightning spells - Windows API fast clicks (tight spread)
    for i in range(10):
        keyboard.send('s')
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)
        spell_x = x + random.randint(-3, 3)
        spell_y = y + random.randint(-3, 3)
        turbo_move_cursor(spell_x, spell_y)
        turbo_fast_click()
        time.sleep(SPELL_CLICK_DELAY_MS / 1000)

    spell_elapsed = time.time() - spell_start
    print(f"[ACH FARM] Cast 11 spells in {spell_elapsed*1000:.0f}ms (~{11/spell_elapsed:.0f} CPS)")

    print("[ACH FARM] All spells deployed - surrendering...")
    gui.log_message("Spells deployed - surrendering")
    send_discord_debug_log("Achievement Farm: All spells deployed - surrendering")

    time.sleep(0.3)  # Reduced wait time

    # Surrender - ULTRA FAST
    fast_click(152, 1136)
    time.sleep(0.2)
    fast_click(1483, 898)
    time.sleep(0.2)

    send_discord_debug_log("Achievement Farm: Surrendered attack")
    gui.log_message("Achievement Farm: Attack surrendered")

    # Return home
    fast_click(*config.RETURN_BUTTON)
    time.sleep(1.5)

    return False  # Attack completed successfully


def perform_normal_attack():
    """Perform a normal attack (non-derank mode)"""
    # SANITY CHECK: Verify we should be here
    settings = gui.get_settings()
    current_profile = settings.get('current_profile', 'Unknown')
    sbarb_mode_check = settings.get('sbarb_farm_mode', False)

    if sbarb_mode_check:
        print(f"\n{'!'*70}")
        print(f"[ERROR] ❌ CRITICAL: perform_normal_attack() called with sbarb_farm_mode=True!")
        print(f"[ERROR] Profile: {current_profile}")
        print(f"[ERROR] This should NEVER happen - SBarb Farm should skip evaluation!")
        print(f"[ERROR] Check that bot was restarted after code changes!")
        print(f"{'!'*70}\n")
        send_discord_debug_log(f"ERROR: perform_normal_attack() called with sbarb_farm_mode=True! Profile: {current_profile}", "ERROR")

    # Get current settings from GUI
    settings = gui.get_settings()

    # OCR resources
    gold, elixir = evaluate_base_resources()

    # Human-like pause to "read" the loot values
    reading_pause(0.4)  # Quick glance at loot

    # Detect air defenses
    air_defenses = detect_air_defenses()
    print(f"Air defenses detected (count): {len(air_defenses)}")
    for i, ad in enumerate(air_defenses):
        x, y, level, conf = ad
        print(f"  AD {i+1}: ({x}, {y}), Level: {level}, Confidence: {conf:.2f}")

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
    ad_target_mode = settings.get('ad_target_mode', 'level')
    if ad_target_mode == 'proximity':
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

def deploy_wall_breaker(position):
    """Deploy a single Super Wall Breaker at the specified position"""
    keyboard.send('2')  # Wall Breaker hotkey
    time.sleep(0.05)
    pyautogui.moveTo(*position, duration=0.02)
    pyautogui.click()
    time.sleep(0.05)

def perform_sgoblin_farm_attack():
    """Perform SGoblin Farm attack - split army on opposite sides and surrender after 10s"""
    print("=== ENTERING SGOBLIN FARM MODE ===")
    send_discord_debug_log("=== ENTERING SGOBLIN FARM MODE ===")
    gui.log_message("SGoblin Farm mode activated")

    # Get current settings from GUI
    settings = gui.get_settings()

    # Wait for attack screen to load by detecting End Battle button
    if not wait_for_attack_screen_ready(timeout=10):
        print("[SGOBLIN] Attack screen not ready - skipping base")
        send_discord_debug_log("SGoblin Farm: Attack screen timeout - skipping", "WARNING")
        gui.log_message("SGoblin Farm: Attack screen timeout - skipping")
        skip_base()
        return "skipped"

    # OCR resources with retry if 0 detected - keep retrying until both values > 0
    retry_attempt = 0
    while True:
        gold, elixir = evaluate_base_resources()

        # If either value is 0, retry after 0.2 seconds (give more time for screen to load)
        if gold == 0 or elixir == 0:
            retry_attempt += 1
            print(f"[SGOBLIN] OCR returned 0 (gold={gold}, elixir={elixir}), retrying in 0.2s... (attempt {retry_attempt})")
            send_discord_debug_log(f"SGoblin Farm: OCR retry {retry_attempt} - gold={gold}, elixir={elixir}")
            time.sleep(0.2)
            continue

        # Success - both values are non-zero
        print(f"[SGOBLIN] OCR successful: gold={gold:,}, elixir={elixir:,}")
        break

    # Check if resources meet minimum threshold (no TH or AD check for SGoblin Farm)
    min_resources = settings.get('min_resources', 800000)
    total_resources = gold + elixir

    if total_resources < min_resources:
        print(f"Resources too low: {total_resources:,} < {min_resources:,}, skipping base")
        skip_base()
        return "skipped"  # Base was skipped, not attacked

    send_discord_debug_log(f"Base selected for SGoblin Farm: {total_resources:,} resources")

    # Attack screen already loaded by main_loop - proceed with deployment
    print("[SGOBLIN FARM] Starting SGoblin Farm attack...")

    # Get troop counts from settings
    troop_counts = settings.get('troop_counts', [0, 0, 0, 0, 0, 0, 0])

    # Choose initial attack side randomly (only up/down for SGoblin Farm)
    sides = ['up', 'down']
    chosen_side = random.choice(sides)
    side_coords = config.SIDE_DEPLOYMENT_COORDS[chosen_side]
    opposite_side = get_opposite_side(chosen_side)
    opposite_coords = config.SIDE_DEPLOYMENT_COORDS[opposite_side]

    print(f"SGoblin Farm: Deploying on {chosen_side} and {opposite_side}")
    send_discord_debug_log(f"SGoblin Farm: Deploying on {chosen_side} and {opposite_side}")
    gui.log_message(f"SGoblin Farm: Attacking from {chosen_side} and {opposite_side}")

    # Use standard hotkeys (no alternate hotkey detection for SGoblin Farm speed)
    KEYS = config.KEYS

    # Move camera to first side (fast mode for SGoblin Farm)
    move_camera_to_side(chosen_side, fast_mode=True)

    # Zoom out before deploying troops (ensure camera movement has finished)
    time.sleep(0.1)  # Wait for camera drag to complete
    pyautogui.moveTo(1280, 700, duration=0)  # Move to center of screen
    time.sleep(0.1)
    # Zoom out aggressively - 5 scrolls of -300
    for _ in range(5):
        pyautogui.scroll(-300)
        time.sleep(0.1)
    # time.sleep(0.5)  # Wait for zoom animation to complete
    print("Zoomed out for SGoblin Farm deployment")
    send_discord_debug_log("Zoomed out for SGoblin Farm deployment")

    # Deploy first half of troops FIRST
    print("Deploying first wave of troops...")
    send_discord_debug_log("Deploying first wave of troops")

    # Check if wall breakers should be deployed
    use_wallbreakers = settings.get('sgoblin_use_wallbreakers', False)

    if use_wallbreakers:
        # NEW MODE: Deploy with wall breakers interspersed
        print("Using wall breaker deployment mode")
        send_discord_debug_log("Using wall breaker deployment mode")
        wb_positions = config.WALL_BREAKER_POSITIONS[chosen_side]

    # NEW DEPLOYMENT STRATEGY: 4 fast passes (2 per side) through entire coordinate path
    # Each pass deploys ~1/4 of troops by moving quickly through all coordinates
    print("[SGOBLIN FARM] Using 4-pass deployment strategy (2 per side)")
    send_discord_debug_log("SGoblin Farm: 4-pass deployment - 2 per side")

    # Deploy wall breakers FIRST on first side if enabled (before goblins)
    if use_wallbreakers:
        print(f"[SGOBLIN FARM] Deploying 2 Super Wall Breakers on {chosen_side}...")
        send_discord_debug_log(f"SGoblin Farm: Deploying wall breakers on {chosen_side}")
        deploy_wall_breaker(wb_positions[0])
        deploy_wall_breaker(wb_positions[1])
        print(f"[SGOBLIN FARM] Wall breakers deployed on {chosen_side}")
        send_discord_debug_log(f"2 Wall Breakers deployed on {chosen_side}")
        time.sleep(0.5)  # Wait for walls to start breaking

    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'
            # Get all available coordinates for this side
            available_coords = side_coords['units']

            # Calculate deployment step for even distribution (4 passes total, 2 per side)
            troops_per_pass = troop_count // 4  # Divided across 4 total passes
            deployment_step = calculate_deployment_step(troops_per_pass, len(available_coords))

            print(f"[SGOBLIN FARM] Deploying {troop_count} {troop_key} troops (2 passes on {chosen_side})")
            print(f"[SGOBLIN FARM] Step size: {deployment_step} (~{troops_per_pass} troops per pass)")

            # PASS 1 & 2: Deploy on first side (chosen_side)
            for pass_num in range(1, 3):
                print(f"  Pass {pass_num}/2 on {chosen_side}...")
                keyboard.send(KEYS[troop_key])
                time.sleep(0.05)

                # Start at first coordinate
                first_coord = available_coords[0]
                pyautogui.moveTo(*first_coord, duration=0.02)
                pyautogui.mouseDown()
                time.sleep(0.3)  # Short hold to start deployment

                # Fast drag through coordinates - dynamic step based on troop count
                for i in range(1, len(available_coords), deployment_step):
                    coord = available_coords[i]
                    pyautogui.moveTo(*coord, duration=0.003)  # VERY FAST movement
                    time.sleep(0.001)

                pyautogui.mouseUp()
                time.sleep(0.1)
                print(f"  Pass {pass_num} complete")

            # First side complete - 2 passes done
            send_discord_debug_log(f"First side ({chosen_side}) complete: 2 passes with {troop_count//2} troops")
            print(f"[SGOBLIN FARM] First side complete: ~{troop_count//2} {troop_key} deployed on {chosen_side}")

    # Deploy heroes AFTER first wave
    import threading

    def activate_hero_ability_sgoblin(hero_role):
        """Activate hero ability after 1 second for SGoblin Farm"""
        time.sleep(1)
        keyboard.send(KEYS[hero_role])
        print(f"[SGOBLIN FARM] {hero_role.title()} ability activated at 1s")
        send_discord_debug_log(f"{hero_role.title()} ability activated after 1 second")
        # No troop reselection needed - first wave already deployed, second wave hasn't started yet

    print("Deploying heroes...")
    send_discord_debug_log("Deploying heroes")
    hero_pos = side_coords['hero']

    # Get hero ability timings from settings
    queen_timing = settings.get('queen_ability_timing', -1)
    king_timing = settings.get('king_ability_timing', -1)
    warden_timing = settings.get('warden_ability_timing', -1)
    rc_timing = settings.get('rc_ability_timing', -1)

    hero_timings = {
        'queen': queen_timing,
        'king': king_timing,
        'warden': warden_timing,
        'rc': rc_timing
    }

    for role in ['queen', 'king', 'warden', 'rc']:
        # Deploy the hero
        keyboard.send(KEYS[role])
        time.sleep(0.05)
        pyautogui.moveTo(*hero_pos, duration=0.02)
        pyautogui.click()
        time.sleep(0.02)

        # Start ability timer only if not disabled (-1)
        timing = hero_timings[role]
        if timing != -1:
            ability_thread = threading.Thread(
                target=activate_hero_ability_sgoblin,
                args=(role,),
                daemon=True
            )
            ability_thread.start()
            send_discord_debug_log(f"{role.title()} ability timer started ({timing}s)")
        else:
            send_discord_debug_log(f"{role.title()} ability disabled")
        print(f"Deployed {role.title()}")

    print("All 4 heroes deployed")
    send_discord_debug_log("All 4 heroes deployed")

    # Deploy siege machine IMMEDIATELY after heroes (before abilities trigger at 1s)
    print("Deploying siege machine...")
    send_discord_debug_log("Deploying siege machine")
    keyboard.send('z')  # Siege machine hotkey
    time.sleep(0.05)
    pyautogui.moveTo(*hero_pos, duration=0.02)  # Same position as heroes
    pyautogui.click()
    time.sleep(0.02)
    print("Siege machine deployed")
    send_discord_debug_log("Siege machine deployed (before abilities trigger)")

    # Move camera to opposite side (fast mode for SGoblin Farm)
    print(f"Moving camera to opposite side ({opposite_side})...")
    send_discord_debug_log(f"Moving camera to opposite side ({opposite_side})")
    move_camera_to_opposite_side(chosen_side, fast_mode=True)

    # PASS 3 & 4: Deploy second half on opposite side
    print(f"[SGOBLIN FARM] Deploying second half on opposite side ({opposite_side})...")
    send_discord_debug_log(f"SGoblin Farm: Deploying on {opposite_side}")

    # Deploy wall breakers FIRST on opposite side if enabled (before goblins)
    if use_wallbreakers:
        wb_positions_opposite = config.WALL_BREAKER_POSITIONS[opposite_side]
        print(f"[SGOBLIN FARM] Deploying 2 Super Wall Breakers on {opposite_side}...")
        send_discord_debug_log(f"SGoblin Farm: Deploying wall breakers on {opposite_side}")
        deploy_wall_breaker(wb_positions_opposite[0])
        deploy_wall_breaker(wb_positions_opposite[1])
        print(f"[SGOBLIN FARM] Wall breakers deployed on {opposite_side}")
        send_discord_debug_log(f"2 Wall Breakers deployed on {opposite_side}")
        time.sleep(0.5)  # Wait for walls to start breaking

    for i in range(7):
        troop_count = troop_counts[i]
        if troop_count > 0:
            troop_key = f'troop{i+1}'
            # Get all available coordinates for opposite side
            available_coords = opposite_coords['units']

            # Calculate deployment step for even distribution (same as first side)
            troops_per_pass = troop_count // 4  # Divided across 4 total passes
            deployment_step = calculate_deployment_step(troops_per_pass, len(available_coords))

            print(f"[SGOBLIN FARM] Deploying {troop_count} {troop_key} troops (2 passes on {opposite_side})")
            print(f"[SGOBLIN FARM] Step size: {deployment_step} (~{troops_per_pass} troops per pass)")

            # PASS 3 & 4: Deploy on opposite side
            for pass_num in range(3, 5):
                print(f"  Pass {pass_num}/4 on {opposite_side}...")
                keyboard.send(KEYS[troop_key])
                time.sleep(0.05)

                # Start at first coordinate
                first_coord = available_coords[0]
                pyautogui.moveTo(*first_coord, duration=0.02)
                pyautogui.mouseDown()
                time.sleep(0.3)  # Short hold to start deployment

                # Fast drag through coordinates - dynamic step based on troop count
                for i in range(1, len(available_coords), deployment_step):
                    coord = available_coords[i]
                    pyautogui.moveTo(*coord, duration=0.003)  # VERY FAST movement
                    time.sleep(0.001)

                pyautogui.mouseUp()
                time.sleep(0.1)
                print(f"  Pass {pass_num} complete")

            # Second side complete - 4 passes total done
            send_discord_debug_log(f"Second side ({opposite_side}) complete: 2 passes with {troop_count//2} troops")
            print(f"[SGOBLIN FARM] Second side complete: ~{troop_count//2} {troop_key} deployed on {opposite_side}")

    print("[SGOBLIN FARM] All 4 passes complete - all troops deployed!")
    send_discord_debug_log("SGoblin Farm: All 4 passes complete")

    # CLEANUP PHASE: Deploy any remaining units by dragging backwards for 3 seconds (REMOVED - no longer needed with 4-pass strategy)
    print("Starting cleanup deployment phase (3 seconds)...")
    send_discord_debug_log("SGoblin: Cleanup phase - deploying remaining units")

    # Find first troop slot that has units
    cleanup_troop_key = None
    for i in range(7):
        if troop_counts[i] > 0:
            cleanup_troop_key = f'troop{i+1}'
            break

    if cleanup_troop_key:
        # Select the troop
        keyboard.send(KEYS[cleanup_troop_key])
        time.sleep(0.05)

        # Get coordinates from the opposite side (last deployed side)
        cleanup_coords = opposite_coords['units']
        num_cleanup_coords = len(cleanup_coords)

        # Start dragging backwards through coordinates for 3 seconds
        cleanup_start = time.time()
        cleanup_duration = 3.0  # 3 seconds

        # Start at first position
        pyautogui.moveTo(*cleanup_coords[0], duration=0.02)
        pyautogui.mouseDown()
        time.sleep(0.5)  # Hold in place to activate deployment mode (not camera drag)

        coord_idx = 0
        direction = 1  # 1 for forward, -1 for backward

        while (time.time() - cleanup_start) < cleanup_duration:
            coord_idx += direction

            # Reverse direction at boundaries
            if coord_idx >= num_cleanup_coords:
                coord_idx = num_cleanup_coords - 2
                direction = -1
            elif coord_idx < 0:
                coord_idx = 1
                direction = 1

            x, y = cleanup_coords[coord_idx]
            pyautogui.moveTo(x, y, duration=0.05)
            time.sleep(0.05)

        pyautogui.mouseUp()
        print("Cleanup deployment phase complete")
        send_discord_debug_log("SGoblin: Cleanup phase complete")

    # All troops deployed - START 10 second timer before surrender
    print("All troops deployed, starting 10 second timer...")
    send_discord_debug_log("SGoblin: All troops deployed, 10 second timer started")
    timer_start = time.time()

    # Check if spell casting on achievement buildings is enabled
    cast_spells_enabled = settings.get('sgoblin_cast_spells', False)

    if cast_spells_enabled:
        # Scan for achievement buildings using parallel priority scan
        print("[PRIORITY SCAN] Scanning for achievement buildings...")
        send_discord_debug_log("SGoblin: Scanning achievement buildings")
        gui.log_message("Scanning for achievement buildings...")

        # PARALLEL SCAN using GUI priority list (3-5x faster than sequential)
        result = scan_achievement_buildings_parallel_priority(settings)

        if result is not None:
            x, y, confidence, building_type = result
            # Convert top-left to center coordinates
            bw, bh = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
            center_x = x + bw // 2
            center_y = y + bh // 2
            print(f"CASTING SPELLS ON: {building_type.replace('_', ' ').title()} at ({center_x}, {center_y}) - Confidence: {confidence:.3f}")
            gui.log_message(f"Casting spells on {building_type.replace('_', ' ')}")
            send_discord_debug_log(f"SGoblin: Casting on {building_type} at ({center_x}, {center_y})")

            # Deploy 1 Earthquake spell
            print("Deploying Earthquake spell...")
            keyboard.send('a')  # Earthquake hotkey
            time.sleep(0.02)
            fast_click(center_x, center_y)
            time.sleep(0.05)

            # Deploy 10 Lightning spells
            print("Deploying Lightning spells...")
            for i in range(10):
                keyboard.send('s')  # Lightning hotkey
                time.sleep(0.01)
                # Add slight variation to position (±3px like Achievement Farm)
                spell_x = center_x + random.randint(-3, 3)
                spell_y = center_y + random.randint(-3, 3)
                fast_click(spell_x, spell_y)
                time.sleep(0.03)
                print(f"  Lightning {i+1}/10 deployed")

            print(f"Spell casting complete on {building_type.replace('_', ' ')}")
            gui.log_message("Spells deployed successfully")
            send_discord_debug_log(f"SGoblin: 1 EQ + 10 Lightning on {building_type}")
        else:
            print("[PRIORITY SCAN] No achievement buildings found")
            gui.log_message("No achievement buildings detected")
            send_discord_debug_log("SGoblin: No buildings found")

    # Calculate remaining time to reach 10 seconds total
    elapsed = time.time() - timer_start
    remaining = max(0, 10 - elapsed)

    if remaining > 0:
        print(f"Waiting {remaining:.1f} more seconds (total 10s from deployment)...")
        send_discord_debug_log(f"SGoblin: Waiting {remaining:.1f}s more (scan/cast took {elapsed:.1f}s)")
        time.sleep(remaining)
    else:
        print("10 seconds already elapsed during scanning/casting")
        send_discord_debug_log("SGoblin: 10 seconds already elapsed")

    # Detect and click surrender OR end battle button (retry up to 3 times)
    print("Looking for surrender/end battle button...")
    send_discord_debug_log("Looking for surrender/end battle button")
    button_type = None
    button_x = None
    button_y = None

    for attempt in range(3):
        button_type, button_x, button_y = detect_surrender_or_end_battle()
        if button_type:
            break
        else:
            print(f"Surrender/end battle button not found, retry {attempt + 1}/3...")
            time.sleep(0.5)

    if button_type:
        print(f"{button_type.replace('_', ' ').title()} button found at ({button_x}, {button_y}), clicking...")
        send_discord_debug_log(f"SGoblin: {button_type} button found at ({button_x}, {button_y})")
        human_like_move_click(button_x, button_y)
        time.sleep(0.5)

        # Click confirmation
        print(f"Clicking {button_type} confirmation...")
        send_discord_debug_log(f"SGoblin: Clicking {button_type} confirmation")
        human_like_move_click(1483, 898)
        time.sleep(2)
    else:
        # NO FALLBACK - Detect actual state and handle appropriately
        print("Warning: Surrender button not found after 3 attempts! Detecting actual state...")
        send_discord_debug_log("SGoblin: Surrender button not found - detecting state", "WARNING")

        # Check if battle already ended (end battle button or return home button visible)
        button_type, x, y = detect_surrender_or_end_battle()
        if button_type == 'end_battle':
            print("Battle already ended - clicking end battle button")
            send_discord_debug_log("SGoblin: Battle ended before surrender - clicking end battle")
            human_like_move_click(x, y)
            time.sleep(1.5)
        elif detect_return_home_button():
            print("Already at end screen - surrender not needed")
            send_discord_debug_log("SGoblin: Already at end screen - skipping surrender")
        else:
            # Still in battle but can't find surrender - try deploying a troop to enable it
            print("Surrender not available - attempting troop deployment to enable surrender")
            send_discord_debug_log("SGoblin: Deploying troop to enable surrender", "WARNING")
            human_like_move_click(1282, 720)  # Deploy one troop
            time.sleep(2.0)

            # Try finding surrender again
            for retry in range(2):
                button_type, x, y = detect_surrender_or_end_battle()
                if button_type == 'surrender':
                    print(f"Surrender button now available at {x}, {y} - clicking")
                    human_like_move_click(x, y)
                    time.sleep(0.5)
                    human_like_move_click(1483, 898)
                    time.sleep(2)
                    break
                elif button_type == 'end_battle':
                    print("Battle ended - clicking end battle button")
                    human_like_move_click(x, y)
                    time.sleep(1.5)
                    break
                time.sleep(1.0)
            else:
                # Still can't find surrender after troop deployment - log error but continue
                print("ERROR: Could not find surrender or end battle button - continuing anyway")
                send_discord_debug_log("SGoblin: Failed to surrender - button not found after retries", "ERROR")
                time.sleep(3)  # Wait a bit for battle to potentially end on its own

    # Wait for battle to end
    wait_for_battle_end()

    # Check if fast return (skip loot logging) is enabled
    skip_logging = settings.get('sgoblin_skip_logging', False)

    if skip_logging:
        # Fast return - skip loot capture and logging
        print("Fast return enabled - skipping loot logging")
        send_discord_debug_log("SGoblin: Fast return - skipping loot logging")
        fast_click(*config.RETURN_BUTTON)
        time.sleep(1.5)  # Reduced return delay
        return False  # Attack completed successfully
    else:
        # Normal post-battle handling with loot tracking
        should_pause = handle_post_battle()
        if should_pause:
            return True  # Signal to pause bot
        return False  # Attack completed successfully

def check_auto_pause():
    """Check if auto-pause condition is met and pause bot if needed"""
    global paused, loop_count

    settings = gui.get_settings()
    auto_pause_mode = settings.get('auto_pause_mode', 'manual')
    auto_pause_value = settings.get('auto_pause_value', 50)

    # Debug: Log auto-pause mode
    print(f"[AUTO-PAUSE] Mode: {auto_pause_mode}")

    should_pause = False
    pause_reason = ""

    if auto_pause_mode == 'loops':
        # Check if loop count reached target
        if loop_count >= auto_pause_value:
            should_pause = True
            pause_reason = f"Auto-pause: {auto_pause_value} attacks completed"

    elif auto_pause_mode == 'time':
        # Check if time limit reached (read from GUI to avoid circular import)
        if hasattr(gui, 'auto_pause_start_time') and gui.auto_pause_start_time is not None:
            elapsed_minutes = (time.time() - gui.auto_pause_start_time) / 60
            if elapsed_minutes >= auto_pause_value:
                should_pause = True
                pause_reason = f"Auto-pause: {auto_pause_value} minutes elapsed"

    elif auto_pause_mode == 'storage_full':
        # Check if storages are full based on current profile and user-selected resources
        current_profile = gui.current_profile
        settings = gui.get_settings()
        check_gold = settings.get('storage_full_gold', True)
        check_elixir = settings.get('storage_full_elixir', True)
        check_de = settings.get('storage_full_de', False)
        print(f"[AUTO-PAUSE] Storage Full check - Gold:{check_gold}, Elixir:{check_elixir}, DE:{check_de}")

        # Get the selected preset's max values for storage full check
        storage_full_preset = settings.get('storage_full_preset', 'main')
        storage_presets = settings.get('storage_presets', {})
        preset_values = storage_presets.get(storage_full_preset, {})

        # Use preset values if available, otherwise fall back to global settings
        max_gold = preset_values.get('max_gold_storage', settings.get('max_gold_storage', 18000000))
        max_elixir = preset_values.get('max_elixir_storage', settings.get('max_elixir_storage', 14000000))
        max_de = preset_values.get('max_dark_elixir_storage', settings.get('max_dark_elixir_storage', 240000))
        max_bb_gold = preset_values.get('max_bb_gold_storage', settings.get('max_bb_gold_storage', 5000000))
        max_bb_elixir = preset_values.get('max_bb_elixir_storage', settings.get('max_bb_elixir_storage', 5000000))

        if current_profile in ["BB Gold", "BB Elixir"]:
            # Check Builder Base storages (DE is ignored for BB)
            # Note: track_resources is called internally by read_bb_base_storages()
            bb_storages = read_bb_base_storages()
            if bb_storages['success']:
                # Check if 3-consecutive-same-readings triggered a pause
                if check_and_pause_if_storages_full(base_type='builder_base'):
                    return True  # Already paused by consecutive readings check

                # Calculate percentages using preset's max values
                bb_gold_percent = min(100, int((bb_storages['gold_absolute'] / max_bb_gold) * 100)) if max_bb_gold > 0 else 0
                bb_elixir_percent = min(100, int((bb_storages['elixir_absolute'] / max_bb_elixir) * 100)) if max_bb_elixir > 0 else 0
                bb_gold_full = bb_gold_percent >= 99
                bb_elixir_full = bb_elixir_percent >= 99

                # Check only the resources the user selected (DE ignored for BB)
                resources_to_check = []
                full_status = []
                if check_gold:
                    resources_to_check.append('Gold')
                    full_status.append(bb_gold_full)
                if check_elixir:
                    resources_to_check.append('Elixir')
                    full_status.append(bb_elixir_full)

                # Pause if ALL selected resources are full
                if resources_to_check and all(full_status):
                    should_pause = True
                    pause_reason = f"Auto-pause: BB {'+'.join(resources_to_check)} full using '{storage_full_preset}' preset (Gold: {bb_gold_percent}%, Elixir: {bb_elixir_percent}%)"
        else:
            # Check main base storages
            # Note: track_resources is called internally by read_own_base_storages()
            storages = read_own_base_storages()
            if storages['success']:
                # Check if 3-consecutive-same-readings triggered a pause
                if check_and_pause_if_storages_full(base_type='main_base'):
                    return True  # Already paused by consecutive readings check

                # Calculate percentages using preset's max values
                gold_percent = min(100, int((storages['gold_absolute'] / max_gold) * 100)) if max_gold > 0 else 0
                elixir_percent = min(100, int((storages['elixir_absolute'] / max_elixir) * 100)) if max_elixir > 0 else 0
                de_percent = min(100, int((storages['de_absolute'] / max_de) * 100)) if max_de > 0 else 0
                gold_full = gold_percent >= 99
                elixir_full = elixir_percent >= 99
                de_full = de_percent >= 99

                # Check only the resources the user selected
                resources_to_check = []
                full_status = []
                if check_gold:
                    resources_to_check.append('Gold')
                    full_status.append(gold_full)
                if check_elixir:
                    resources_to_check.append('Elixir')
                    full_status.append(elixir_full)
                if check_de:
                    resources_to_check.append('DE')
                    full_status.append(de_full)

                # Debug output
                print(f"[AUTO-PAUSE] Calculated: Gold={gold_percent}% (full:{gold_full}), Elixir={elixir_percent}% (full:{elixir_full}), DE={de_percent}% (full:{de_full})")
                print(f"[AUTO-PAUSE] Checking: {resources_to_check}, Status: {full_status}, All full: {all(full_status) if full_status else False}")

                # Pause if ALL selected resources are full
                if resources_to_check and all(full_status):
                    should_pause = True
                    pause_reason = f"Auto-pause: {'+'.join(resources_to_check)} full using '{storage_full_preset}' preset (Gold: {gold_percent}%, Elixir: {elixir_percent}%, DE: {de_percent}%)"

    if should_pause:
        paused = True
        gui.bot_paused = True
        print(f"[AUTO-PAUSE] {pause_reason}")
        gui.log_message(pause_reason)
        send_discord_debug_log(pause_reason, "INFO")
        root.after(0, update_status)
        return True

    return False

def main_loop():
    global loop_count, paused, running
    global skipped_bases, attacked_bases
    
    # Each iteration covers one full attack cycle
    while running:
        # Check for Discord commands
        check_discord_commands()
        
        # Check if GUI wants to stop
        if not gui.bot_running:
            running = False
            send_discord_debug_log("Bot stopped by GUI", "INFO")
            break
            
        # Check if GUI wants to pause
        paused = gui.bot_paused
        
        # Automatic break check
        global break_time
        if break_time is not None and time.time() >= break_time:
            print("Taking scheduled break.")
            paused = True
            gui.bot_paused = True
            gui.log_message("Taking scheduled break")
            send_discord_debug_log("Taking scheduled break", "INFO")
            root.after(0, update_status)
            
            # Get break duration from settings and schedule auto-resume
            settings = gui.get_settings()
            break_duration = settings.get('break_duration', 5)  # minutes
            root.after(0, lambda: gui.schedule_auto_resume(break_duration))
            
            # schedule next break after auto-resume
            break_time = schedule_next_break()
        
        time.sleep(0.1)
        if paused:
            continue
        time.sleep(0.2)
        if paused:
            continue

        # ===== UNIVERSAL: Return Home Recovery for Main Base Modes =====
        # If stuck on end screen (Return Home button visible), click it and recover
        # BB modes are excluded - they have their own state machine recovery
        settings_check = gui.get_settings()
        bb_mode_active = settings_check.get('bb_elixir_mode', False) or settings_check.get('bb_gold_mode', False)

        if not bb_mode_active:
            return_home_pos = detect_return_home_button(quiet=True)
            if return_home_pos:
                print(f"[MAIN LOOP] !! Return Home detected at loop start - recovering from stuck end screen")
                gui.log_message("Recovery: Clicking Return Home (stuck on end screen)")
                send_discord_debug_log("Main Loop: Return Home recovery triggered", "WARNING")

                # Click Return Home button
                fast_click(*return_home_pos)
                time.sleep(1.5)  # Wait for transition

                # Handle potential star bonus screen
                if detect_star_bonus_screen():
                    print("[MAIN LOOP] Star bonus detected during recovery - closing")
                    fast_click(102, 824)  # Close star bonus
                    time.sleep(0.5)

                # Wait for base screen to load
                wait_for_base_screen(timeout=10)

                print("[MAIN LOOP] Recovery complete - restarting loop iteration")
                continue  # Restart this loop iteration cleanly

        try:
            # Start of attack cycle
            send_discord_debug_log(f"Starting attack cycle {loop_count + 1}")

            # Get current settings from GUI
            settings = gui.get_settings()

            # DEBUG: Check overlay status at start of each cycle
            if gui.overlay_enabled:
                print(f"[OVERLAY] Cycle {loop_count + 1}: Overlay is ENABLED, drawing test marker...")
                overlay_clear()
                # Draw a test marker so we know the overlay is working
                if gui.overlay:
                    gui.overlay.draw_text(100, 50, f"Bot Cycle: {loop_count + 1}", '#00FF00')
                    gui.overlay.update()
            else:
                if loop_count == 0:  # Only print once
                    print("[OVERLAY] Overlay is disabled (checkbox not checked)")

            # Check if queue system is active
            queue_enabled = settings.get('queue_enabled', False)

            if queue_enabled and 'queue_manager' in globals() and queue_manager:
                # Ensure queue is started (handles race condition from web GUI)
                if not queue_manager.queue_active:
                    queue_manager.start_queue()

                # Get next mode from queue system
                next_mode = queue_manager.get_next_mode()

                if next_mode is None:
                    # Queue complete - stop bot
                    print("[QUEUE] Queue execution complete")
                    running = False
                    break

                # Set mode flags based on queue's selected mode
                print(f"[QUEUE] Executing mode: {next_mode}")
                derank_mode = (next_mode == 'Derank')
                sgoblin_farm_mode = (next_mode == 'SGoblin Farm')
                sbarb_farm_mode = (next_mode == 'SBarb Farm')
                bb_elixir_mode = (next_mode == 'BB Elixir')
                bb_gold_mode = (next_mode == 'BB Gold')
                achievement_farm_mode = (next_mode == 'Achievement Farm')

                # Update GUI profile to match queue mode
                if gui.current_profile != next_mode:
                    print(f"[QUEUE] Switching profile to: {next_mode}")
                    gui.current_profile = next_mode
                    gui.profile_var.set(next_mode)
                    gui.apply_current_profile(silent=True)  # Silent mode for queue auto-switching
            else:
                # Normal mode - use profile settings
                derank_mode = settings.get('derank_mode', False)
                sgoblin_farm_mode = settings.get('sgoblin_farm_mode', False)
                sbarb_farm_mode = settings.get('sbarb_farm_mode', False)
                bb_elixir_mode = settings.get('bb_elixir_mode', False)
                bb_gold_mode = settings.get('bb_gold_mode', False)
                achievement_farm_mode = settings.get('achievement_farm_mode', False)

            # CRITICAL DEBUG: Print ALL settings to verify
            current_profile = settings.get('current_profile', 'Unknown')
            # Debug logging disabled - uncomment below to re-enable attack cycle debug info
            # print(f"\n{'='*70}")
            # print(f"[DEBUG] === ATTACK CYCLE {loop_count + 1} ===")
            # print(f"[DEBUG] Current profile: {current_profile}")
            # print(f"[DEBUG] Mode flags loaded from settings:")
            # print(f"  - derank_mode: {derank_mode}")
            # print(f"  - sgoblin_farm_mode: {sgoblin_farm_mode}")
            # print(f"  - sbarb_farm_mode: {sbarb_farm_mode} {'← SHOULD BE TRUE FOR SBARB FARM!' if current_profile == 'SBarb Farm' else ''}")
            # print(f"  - bb_elixir_mode: {bb_elixir_mode}")
            # print(f"  - bb_gold_mode: {bb_gold_mode}")
            # print(f"  - achievement_farm_mode: {achievement_farm_mode}")
            # active_count = sum([derank_mode, sgoblin_farm_mode, sbarb_farm_mode, bb_elixir_mode, bb_gold_mode, achievement_farm_mode])
            # if active_count == 0:
            #     print(f"[WARNING] ⚠️  NO MODES ACTIVE - Will use normal attack (with evaluation)!")
            # elif active_count > 1:
            #     print(f"[ERROR] ❌ {active_count} MODES ACTIVE - Should only be 1!")
            # print(f"{'='*70}\n")

            send_discord_debug_log(f"Cycle {loop_count+1} | Profile: {current_profile}")

            # Handle potential star bonus screen and other popups (blind click - no detection)
            # This handles star bonus for BB Gold mode after returning to base
            # Harmless if no popup is present - click location chosen to avoid interfering with UI
            fast_click(73, 820)
            time.sleep(0.1)

            # 1. Open attack GUI (randomized click)
            x1,y1,x2,y2 = config.OPEN_GUI_BUTTON
            click_in_square((x1,y1,x2,y2))
            # Human-like delay with natural variance (0.4-0.7s range)
            humanized_sleep(0.55, variance=0.273)

            # Skip-based fast modes (no evaluation): derank, sgoblin, sbarb, bb modes, achievement
            # Use BB-specific search button for BB Elixir mode (BB Gold uses state machine)
            if bb_elixir_mode or bb_gold_mode:
                # Builder Base modes - skip main base search/attack buttons
                if bb_elixir_mode:
                    mode_name = "BB ELIXIR"

                    # Retry loop for base loading
                    retry_count = 0
                    base_loaded = False

                    while retry_count < config.BB_LOAD_MAX_RETRIES and not base_loaded:
                        # Click BB search button
                        click_in_square(config.BB_SEARCH_BUTTON)
                        print(f"[{mode_name}] Using Builder Base search button")
                        gui.log_message(f"{mode_name}: Searching for base...")
                        send_discord_debug_log(f"{mode_name}: Using Builder Base search button")

                        # Poll for "Attacker" text with timeout
                        print(f"[{mode_name}] Checking for Attacker text...")
                        gui.log_message(f"{mode_name}: Checking for Attacker text...")
                        send_discord_debug_log(f"{mode_name}: Checking for Attacker text")

                        start_time = time.time()
                        found = False

                        while not found and (time.time() - start_time) < config.BB_LOAD_TIMEOUT:
                            if check_bb_attacker_text():
                                found = True
                                base_loaded = True
                                print(f"[{mode_name}] ✓ Attacker text detected - base loaded!")
                                gui.log_message(f"{mode_name}: Base loaded!")
                                send_discord_debug_log(f"{mode_name}: Attacker text detected - base loaded")
                                time.sleep(0.5)
                                break
                            time.sleep(config.BB_LOAD_CHECK_INTERVAL)

                        # If timeout, click return and retry
                        if not found:
                            print(f"[{mode_name}] ⚠️ Base load timeout - no Attacker text found")
                            gui.log_message(f"{mode_name}: Base load timeout")
                            send_discord_debug_log(f"{mode_name}: Base load timeout - no Attacker text found", "WARNING")

                            print(f"[{mode_name}] Clicking return button to recover from ghost attack")
                            gui.log_message(f"{mode_name}: Returning to base...")
                            send_discord_debug_log(f"{mode_name}: Clicking return button to recover from ghost attack")
                            click_in_square(config.BB_RETURN_BUTTON_GHOST)
                            time.sleep(config.BB_RETRY_WAIT_TIME)

                            retry_count += 1

                            if retry_count < config.BB_LOAD_MAX_RETRIES:
                                print(f"[{mode_name}] Retrying search... (attempt {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES})")
                                gui.log_message(f"{mode_name}: Retry {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES}")
                                send_discord_debug_log(f"{mode_name}: Retrying search (attempt {retry_count + 1}/{config.BB_LOAD_MAX_RETRIES})")
                            else:
                                print(f"[{mode_name}] ❌ Base load failed after {config.BB_LOAD_MAX_RETRIES} retries - skipping to next search")
                                gui.log_message(f"{mode_name}: Max retries exceeded - skipping")
                                send_discord_debug_log(f"{mode_name}: Base load failed after {config.BB_LOAD_MAX_RETRIES} retries - skipping", "ERROR")
                                # Skip to next search iteration - don't proceed with attack
                                continue
                # BB Gold mode doesn't need any clicks here - state machine handles everything internally
            else:
                # Main base modes only - click main base search and attack buttons
                click_in_square(config.SEARCH_BUTTON)

                # Wait for army selection screen to appear
                print("Waiting for army selection screen...")
                gui.log_message("Waiting for army screen...")
                send_discord_debug_log("Waiting for army selection screen")

                # Simple fixed delay for army selection screen to load
                time.sleep(0.2)  # Fast delay for army selection screen

                print("Army selection screen should be ready")
                gui.log_message("Army screen ready")
                send_discord_debug_log("Army selection screen ready")

                # Click START_ATTACK_BUTTON (green "Attack!" button) for all home base modes
                print(f"Clicking START_ATTACK_BUTTON at {config.START_ATTACK_BUTTON}")
                send_discord_debug_log(f"Clicking START_ATTACK_BUTTON at {config.START_ATTACK_BUTTON}")
                print(f"Current mouse position: {pyautogui.position()}")

                x_coord, y_coord = config.START_ATTACK_BUTTON
                print(f"Target coordinates: x={x_coord}, y={y_coord}")
                human_like_move_click(x_coord, y_coord)

                print(f"After click, mouse position: {pyautogui.position()}")
                # No fixed delay needed - OCR and base detection will handle timing

            # 2. Fast attack modes (no evaluation) - handle immediately and skip evaluation loop
            # These modes attack every base without checking resources/defenses
            print(f"[DEBUG] Checking fast attack modes...")
            if derank_mode:
                print(f"[DEBUG] ✓ derank_mode matched - using handle_derank_mode()")
                # Derank: attack every base with one troop
                if handle_derank_mode():
                    loop_count += 1
                    gui.update_loop_count(loop_count)
                    state_manager.set("loop_count", loop_count)
                    state_manager.set("bases_attacked", attacked_bases + 1)
                    gui.log_message(f"Derank attack {loop_count} completed")
                    attacked_bases += 1
                    send_discord_debug_log(f"Derank attack {loop_count} completed")
                continue  # Skip to next attack cycle immediately

            elif sbarb_farm_mode:
                print(f"[DEBUG] ✓ ✓ ✓ sbarb_farm_mode matched - using handle_sbarb_farm_mode()")
                print(f"[DEBUG] NO EVALUATION - NO SKIPPING - Attacking base immediately!")
                send_discord_debug_log("SBarb Farm: Mode ACTIVE - NO evaluation, attacking immediately")
                # SBarb Farm: NO EVALUATION, NO SKIPPING - Attack every base immediately
                if handle_sbarb_farm_mode():
                    loop_count += 1
                    gui.update_loop_count(loop_count)
                    state_manager.set("loop_count", loop_count)
                    state_manager.set("bases_attacked", attacked_bases + 1)
                    gui.log_message(f"SBarb Farm attack {loop_count} completed")
                    attacked_bases += 1
                    send_discord_debug_log(f"SBarb Farm attack {loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif bb_elixir_mode:
                # BB Elixir: attack every BB base with one troop
                if handle_bb_elixir_mode():
                    loop_count += 1
                    gui.update_loop_count(loop_count)
                    state_manager.set("loop_count", loop_count)
                    state_manager.set("bases_attacked", attacked_bases + 1)
                    gui.log_message(f"BB Elixir attack {loop_count} completed")
                    attacked_bases += 1
                    send_discord_debug_log(f"BB Elixir attack {loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif bb_gold_mode:
                # BB Gold: deploy troops, wait for 2 stars, surrender
                if handle_bb_gold_mode():
                    loop_count += 1
                    gui.update_loop_count(loop_count)
                    state_manager.set("loop_count", loop_count)
                    state_manager.set("bases_attacked", attacked_bases + 1)
                    gui.log_message(f"BB Gold attack {loop_count} completed")
                    attacked_bases += 1
                    send_discord_debug_log(f"BB Gold attack {loop_count} completed")

                    # Check auto-pause condition
                    if check_auto_pause():
                        continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            elif achievement_farm_mode:
                # Achievement Farm: search for specific building and attack
                should_pause = perform_achievement_farm_attack()
                if should_pause:
                    paused = True
                    gui.bot_paused = True
                    gui.log_message("Bot paused due to full storages. Discord notification sent.")
                    send_discord_debug_log("Bot paused due to full storages", "WARNING")
                    root.after(0, update_status)
                    break  # Exit main loop

                loop_count += 1
                gui.update_loop_count(loop_count)
                state_manager.set("loop_count", loop_count)
                state_manager.set("bases_attacked", attacked_bases + 1)
                gui.log_message(f"Achievement Farm attack {loop_count} completed")
                attacked_bases += 1
                send_discord_debug_log(f"Achievement Farm attack {loop_count} completed successfully")
                root.after(0, lambda: gui.update_skipped_stats(skipped_bases, attacked_bases))

                # Check auto-pause condition
                if check_auto_pause():
                    continue  # Stay paused
                continue  # Skip to next attack cycle immediately

            # 3. Evaluation-based attack modes (may skip bases)
            # These modes check resources/defenses and may skip bases
            print(f"[DEBUG] ❌ No fast modes matched - entering evaluation loop")
            print(f"[DEBUG] Will check: SGoblin Farm or Normal Attack")
            while running:
                if sgoblin_farm_mode:
                    print(f"[DEBUG] ✓ sgoblin_farm_mode matched - using perform_sgoblin_farm_attack()")
                    # Handle SGoblin Farm mode (no TH/AD detection, resource-based only)
                    result = perform_sgoblin_farm_attack()
                    if result == True:
                        # Pause bot due to full storages
                        paused = True
                        gui.bot_paused = True
                        gui.log_message("Bot paused due to full storages. Discord notification sent.")
                        send_discord_debug_log("Bot paused due to full storages", "WARNING")
                        root.after(0, update_status)
                        break  # Exit inner while loop
                    elif result == "skipped":
                        # Base was skipped, increment skipped counter and wait for next base
                        skipped_bases += 1
                        gui.log_message(f"Base skipped (total: {skipped_bases})")
                        send_discord_debug_log(f"SGoblin Farm: Base skipped (total: {skipped_bases})")
                        root.after(0, lambda: gui.update_skipped_stats(skipped_bases, attacked_bases))

                        # Wait for next base to load automatically (skip initiates auto-search)
                        print("Waiting for next base after skip...")
                        base_found = False
                        max_wait_time = 30  # Maximum 30 seconds to find next base
                        start_time = time.time()

                        while not base_found and (time.time() - start_time) < max_wait_time:
                            if is_base_search_ready():
                                base_found = True
                                print("Next base loaded after skip!")
                                gui.log_message("Next base loaded")
                                time.sleep(0.1)  # Small delay to ensure screen is stable
                                break
                            time.sleep(0.2)  # Check every 200ms

                        if not base_found:
                            print("WARNING: Base search timed out after skip")
                            gui.log_message("Base search timeout after skip")
                            send_discord_debug_log("Base search timeout after skip", "WARNING")
                            time.sleep(1)

                        # Continue loop to evaluate next base (don't break - stay in evaluation loop)
                        continue
                    else:
                        # Attack completed successfully
                        loop_count += 1
                        gui.update_loop_count(loop_count)
                        state_manager.set("loop_count", loop_count)
                        state_manager.set("bases_attacked", attacked_bases + 1)
                        gui.log_message(f"SGoblin Farm attack {loop_count} completed")
                        attacked_bases += 1
                        send_discord_debug_log(f"SGoblin Farm attack {loop_count} completed successfully")
                        root.after(0, lambda: gui.update_skipped_stats(skipped_bases, attacked_bases))
                        break  # Exit inner while loop to start a new attack cycle
                else:
                    print(f"[DEBUG] Using NORMAL ATTACK mode (will evaluate and may skip)")
                    # Handle normal attack mode
                    should_pause = perform_normal_attack()
                    if should_pause:
                        paused = True
                        gui.bot_paused = True
                        gui.log_message("Bot paused due to full storages. Discord notification sent.")
                        send_discord_debug_log("Bot paused due to full storages", "WARNING")
                        root.after(0, update_status)
                        break  # Exit inner while loop

                    # Update loop count and continue
                    loop_count += 1
                    gui.update_loop_count(loop_count)
                    state_manager.set("loop_count", loop_count)
                    state_manager.set("bases_attacked", attacked_bases + 1)
                    gui.log_message(f"Attack {loop_count} completed")
                    attacked_bases += 1
                    send_discord_debug_log(f"Attack {loop_count} completed successfully")

                    # Update skipped/ratio statistics in GUI
                    root.after(0, lambda: gui.update_skipped_stats(skipped_bases, attacked_bases))
                    break  # Exit inner while loop to start a new attack cycle

        except pytesseract.pytesseract.TesseractNotFoundError:
            print("OCR engine missing. Pausing.")
            paused = True
            gui.bot_paused = True
            gui.log_message("ERROR: OCR engine missing")
            send_discord_debug_log("OCR engine missing - bot paused", "ERROR")
            root.after(0, update_status)
            time.sleep(5)
        except Exception as e:
            print(f"Error during loop: {e}")
            import traceback
            traceback.print_exc()  # Print full stack trace
            paused = True
            gui.bot_paused = True
            try:
                gui.log_message(f"ERROR: {str(e)}")
            except:
                print("[ERROR] Failed to log message to GUI")
            send_discord_debug_log(f"Error during attack loop: {str(e)}", "ERROR")
            try:
                root.after(0, update_status)
            except:
                print("[ERROR] Failed to update status")
            # --- Error screenshot saving ---
            try:
                error_dir = "errors"
                os.makedirs(error_dir, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(error_dir, f"error_{timestamp}.png")
                img = ImageGrab.grab()
                img.save(screenshot_path)
                print(f"Error screenshot saved: {screenshot_path}")
                gui.log_message(f"Error screenshot saved: {screenshot_path}")
                send_discord_debug_log(f"Error screenshot saved: {screenshot_path}", "WARNING")
            except Exception as err:
                print(f"Failed to save error screenshot: {err}")
                gui.log_message(f"Failed to save error screenshot: {err}")
                send_discord_debug_log(f"Failed to save error screenshot: {err}", "ERROR")

    if attacked_bases > 0:
        skip_ratio = skipped_bases / attacked_bases
    else:
        skip_ratio = 0
    print(f"Bases skipped: {skipped_bases}, Attacks: {attacked_bases}, Skip/Attack ratio: {skip_ratio:.2f}")
    gui.log_message(f"Bases skipped: {skipped_bases}, Attacks: {attacked_bases}, Skip/Attack ratio: {skip_ratio:.2f}")
    send_discord_debug_log(f"Session summary: {skipped_bases} skipped, {attacked_bases} attacked, ratio: {skip_ratio:.2f}")

# Override GUI's run_bot method with our main loop
def gui_run_bot():
    global running, paused
    running = True
    paused = False
    gui.bot_running = True
    gui.bot_paused = False
    gui.log_message("Bot thread started")
    # Update web state
    state_manager.set("running", True)
    state_manager.set("paused", False)
    state_manager.set("status", "RUNNING")
    main_loop()

gui.run_bot = gui_run_bot

# Set Queue Manager callbacks now that all functions are defined
if queue_manager:
    queue_manager.set_callbacks(read_own_base_storages, read_bb_base_storages, switch_village)

# Add window close handler to ensure cleanup
root.protocol("WM_DELETE_WINDOW", exit_app)

# Pre-load achievement building templates for faster detection (SBarb Farm optimization)
print("\n" + "="*70)
print("INITIALIZING TEMPLATE CACHE FOR SBARB FARM OPTIMIZATIONS")
print("="*70)
load_achievement_building_templates()
print("="*70 + "\n")

# Pre-load BB Gold templates for faster BB Gold attacks
print("="*70)
print("INITIALIZING BB GOLD TEMPLATE CACHE")
print("="*70)
load_bb_gold_templates()
print("="*70 + "\n")

# Start connection monitor (checks for connection lost every 5 seconds)
print("="*70)
print("STARTING CONNECTION MONITOR")
print("="*70)
start_connection_monitor()
print("="*70 + "\n")

# Start web server in background thread
print("="*70)
print("STARTING WEB GUI SERVER")
print("="*70)
web_thread = threading.Thread(
    target=start_web_server,
    args=(state_manager, "127.0.0.1", 8000),
    daemon=True
)
web_thread.start()
print("[MAIN] Web GUI available at http://localhost:8000")
print("="*70 + "\n")

# Start the GUI
root.mainloop()








