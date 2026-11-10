# config.py

# Path to the Tesseract executable
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# OCR region for resources: (x1, y1, x2, y2)
# RESOURCES_REGION = (46, 154, 282, 353)

# Reinforcement Configuration
ARMY_BUTTON_TEMPLATE_DIR = "screenshots/reference/reinforcements/"
ARMY_BUTTON_DETECTION_THRESHOLD = 0.8  # Template matching confidence threshold
ARMY_BUTTON_SEARCH_REGION = (0, 0, 2560, 1440)  # Full screen search region (adjust to your resolution)
REINFORCE_REQUEST_COORDS = (2034, 1115)  # Coordinates to click after army button
Confirm_Coords = (1550, 1024)  # Confirmation button coordinates

# Skip button coordinates (x, y)
SKIP_BUTTON = (2384, 1096)
SKIP_DELAY = 5  # seconds
# Resource regions for enemy base viewing (during search)
GOLD_REGION = (106, 154, 282, 206)  # tylko linia z Gold
ELIXIR_REGION = (100, 224, 276, 274)  # tylko linia z Elixir
# (Optionally add Dark elixir region here)

# Resource regions for own base (after returning from attack)
BASE_GOLD_REGION = (2123, 45, 2433, 92)  # Base gold region (to be adjusted)
BASE_ELIXIR_REGION = (2123, 157, 2433, 206)  # Base elixir region (to be adjusted)
BASE_DARK_ELIXIR_REGION = (2257, 266, 2441, 319)

# Builder Base storage regions (when in Builder Base home)
# Calibrate these coordinates using tools/testing/screenshot_region.py
# These are placeholder values - adjust to match your screen resolution
BB_BASE_GOLD_REGION = (2123, 45, 2433, 92)  # BB gold storage (to be calibrated)
BB_BASE_ELIXIR_REGION = (2123, 157, 2433, 206)  # BB elixir storage (to be calibrated)

# Minimum resource threshold
MIN_AMOUNT = 1700000

# Search (find match) button region: updated coords (single point simulated as a square)
SEARCH_BUTTON = (383, 1010, 383, 1010)
SEARCH_DELAY = 1.5  # seconds

# Builder Base (BB) base load detection
BB_SEARCH_BUTTON = (1892, 944, 1892, 944)  # Builder Base search button
BB_ATTACKER_TEXT_REGION = (2306, 12, 2458, 54)  # Region where "Attacker" text appears
BB_RETURN_BUTTON_GHOST = (1275, 1160, 1275, 1160)  # Return button for ghost attack recovery
BB_LOAD_TIMEOUT = 10  # seconds to wait for "Attacker" text
BB_LOAD_CHECK_INTERVAL = 0.5  # seconds between checks
BB_LOAD_MAX_RETRIES = 3  # max search retry attempts
BB_RETRY_WAIT_TIME = 3  # seconds to wait after clicking return

# BB Gold State Machine Configuration
BB_STATE_DETECTION_TIMEOUT = 30  # Max seconds per state transition
BB_END_SCREEN_TIMEOUT = 10  # Max wait for end screen after battle
BB_RETURN_HOME_TIMEOUT = 15  # Max wait for base arrival after return click
ARMY_BUTTON_TEMPLATE_DIR = "screenshots/reference/reinforcements"
ARMY_BUTTON_SEARCH_REGION = None  # Full screen (None means full screen)
ARMY_BUTTON_DETECTION_THRESHOLD = 0.8

# Button to open the attack GUI (left-bottom corner)
OPEN_GUI_BUTTON = (41, 1205, 234, 1389)
OPEN_GUI_DELAY = 1  # seconds

# Start attack button (new - must be clicked before START_BUTTON): (x, y)
START_ATTACK_BUTTON = (2162, 1230)

# Start attack button region: (x1, y1, x2, y2)
START_BUTTON = (1650, 800, 2067, 943)
START_DELAY = 1.5  # seconds


# Black Bar suggests end of battle screen
BLACK_BAR_REGION = (1487, 1331, 1924, 1414)
BLACK_BAR_COLOR = (0, 0, 0)  # np. czarny

# Koordynaty przycisku powrotu (pojedynczy punkt)
RETURN_BUTTON = (1280, 1225)
RETURN_DELAY = 7  # sekundy

# Loot tracking regions (after battle, before return button)
# Format: (x1, y1, x2, y2) - top left and bottom right coordinates
LOOT_GOLD_REGION = (988, 597, 1313, 675)  # Gold loot region
LOOT_ELIXIR_REGION = (1000, 692, 1313, 771)  # Elixir loot region
LOOT_DARK_ELIXIR_REGION = (1069, 783, 1313, 861)  # Dark Elixir loot region

# Delay after battle ends to capture loot (seconds)
LOOT_CAPTURE_DELAY = 1

# Troop Count Detection Configuration (during attack)
TROOP_COUNT_REGION = (419, 1229, 506, 1270)  # Region where remaining troop count is displayed (format: "xN")

# Air Defense Detection Configuration
AIR_DEFENSE_TEMPLATES_DIR = "screenshots/reference/air_defenses/"
BASE_VIEW_REGION = (400, 100, 2160, 1200)  # Region where base is visible during attack
AIR_DEFENSE_DETECTION_THRESHOLD = 0.70  # Template matching confidence threshold
AIR_DEFENSE_MAX_COUNT = 4  # Maximum number of air defenses to expect

# Town Hall Detection Configuration
TOWN_HALL_TEMPLATES_DIR = "screenshots/reference/town_halls/"
TOWN_HALL_DETECTION_THRESHOLD = 0.7  # Template matching confidence threshold
TOWN_HALL_REGION = (800, 400, 1760, 1000)  # Region where Town Hall is typically located

# Queen Giant Arrow Detection Configuration
QUEEN_ARROW_TEMPLATES_DIR = "screenshots/reference/giant_arrow/"  # Directory kept for reference (no longer used)
# Detection now uses color-based tracking of cyan/green glow trail (no templates needed)
QUEEN_ARROW_FRAME_COUNT = 6  # Number of frames to capture (at 0.12s intervals)
QUEEN_ARROW_FRAME_INTERVAL = 0.12  # Seconds between frame captures

# Air Defense characteristics
AIR_DEFENSE_RANGE = 10  # Tiles range (approximate)
AIR_DEFENSE_PRIORITY = {
    "level_1": 1,
    "level_2": 2,
    "level_3": 3,
    "level_4": 4,
    "level_5": 5,
    "level_6": 6,
    "level_7": 7,
    "level_8": 8,
    "level_9": 9,
    "level_10": 10,
    "level_11": 11,
    "level_12": 12,
    "level_13": 13,
    "level_14": 14,
    "level_15": 15,
}

# Air Defense HP values by level
AIR_DEFENSE_HP = {
    1: 800,
    2: 850,
    3: 900,
    4: 950,
    5: 1000,
    6: 1050,
    7: 1100,
    8: 1210,
    9: 1300,
    10: 1400,
    11: 1500,
    12: 1650,
    13: 1750,
    14: 1850,
    15: 1950,
}

# Default lightning spell damage (can be adjusted in GUI)
DEFAULT_LIGHTNING_DAMAGE = 300  # Damage per lightning spell

# Deploy settings
KEYS = {
    "troop1": "1",
    "troop2": "2",
    "troop3": "3",
    "troop4": "4",
    "troop5": "5",
    "troop6": "6",
    "troop7": "7",
    "queen": "q",
    "king": "w",
    "warden": "e",
    "rc": "r",
    "siege": "z",
    "haste": "a",
    "rage": "s",
    "lightning": "a",  # Lightning spell key
}

# Electro Dragon placement locations (9)
E_DRAG_LOCATIONS = [
    (459, 547),
    (631, 699),
    (830, 841),
    (1083, 1027),
    (1031, 1027),
    (1543, 1009),
    (1791, 814),
    (1983, 668),
    (2190, 515),
]

# Balloon deployment
BALLOON_COUNT = 2
BALLOON_POS1 = (631, 699)
BALLOON_POS2 = (1983, 668)
BALLOON_POSITIONS = [(631, 699), (1983, 668)]
# Hero and siege deployments
HERO_ROLES = ["queen", "king", "warden", "rc", "siege"]
HERO_DEPLOY_POS = (1301, 1152)
HERO_DELAY = 0.05
POST_DEPLOY_DELAY = 0.03

# Spell deployment locations\ n
HASTE_LOCATIONS = [(740, 557), (962, 746), (1147, 884), (1308, 825), (1514, 774), (1710, 670), (1873, 546)]

RAGE_LOCATIONS = [(1121, 558), (1460, 558)]

# Random sleep between clicks (milliseconds)
SLEEP_MIN = 60
SLEEP_MAX = 130

ABILITY_WAIT = 15  # seconds before activating abilities
ABILITY_DELAY = 0.05  # delay between ability hotkeys

# Camera adjustment
CAMERA_ZOOM_AMOUNT = 500  # wartość scrolla na zoom out
CAMERA_DRAG_START = (1280, 700)  # np. środek ekranu
CAMERA_DRAG_DISTANCE = 400  # ile pikseli przeciągnąć myszką

# Drag to scroll view after starting attack
DRAG_START = (1284, 522)
DRAG_END = (1305, 220)
DRAG_DURATION_START = 0.01  # seconds for initial move
DRAG_DURATION_END = 0.02  # seconds for drag move
DRAG_DELAY = 0.05  # seconds between actions
DRAG_POST_DELAY = 3  # seconds to wait after drag

# Wall Upgrading Configuration
# Resource threshold for wall upgrades (1.5M)
WALL_UPGRADE_THRESHOLD = 1500000

# Wall templates directory for detection
WALL_TEMPLATES_DIR = "screenshots/reference/walls/"

# Wall upgrade button coordinates
WALL_GOLD_UPGRADE_BUTTON = (1487, 1156)  # Left button - gold upgrade (to be provided)
WALL_ELIXIR_UPGRADE_BUTTON = (1699, 1156)  # Right button - elixir upgrade (to be provided)
WALL_CONFIRM_BUTTON = (1788, 1253)  # Confirmation button (to be provided)

# Wall detection region (where walls are typically located)
WALL_DETECTION_REGION = (400, 200, 2160, 1200)  # Same as base view region initially

# Wall detection threshold
WALL_DETECTION_THRESHOLD = 0.7

# Delays for wall upgrading
WALL_CLICK_DELAY = 0.5  # seconds
WALL_UPGRADE_DELAY = 1.0  # seconds

# Automatic Wall Upgrading Configuration
AUTO_WALL_UPGRADE_ENABLED = True
MAX_WALL_LEVEL = 15  # Maximum wall level to upgrade to
WALL_UPGRADE_COST = 1500000  # Cost per wall upgrade (1.5M)

# Resource collection coordinates (to collect resources from generators before wall upgrading)
RESOURCE_COLLECTION_COORDS = [
    (1191, 203),  # Coordinate 1
    (1273, 140),  # Coordinate 2
    (1362, 205),  # Coordinate 3
]

# Wall coordinates will be stored in a separate file: wall_coordinates.json
# Format: {"x,y": {"upgraded": bool, "level": int}}
WALL_COORDINATES_FILE = "wall_coordinates.json"

# Wall upgrade button coordinates (updated with user's coordinates)
WALL_UPGRADE_BUTTONS = {
    "gold": (1487, 1149),  # Gold upgrade button
    "elixir": (1699, 1152),  # Elixir upgrade button
    "confirm": (1774, 1249),  # Confirm upgrade button
}

# --- PERSONAL/PRIVATE VARIABLES ---
# NOTE: Make sure to add 'private_config.py' to your .gitignore so it is not tracked by version control!
try:
    import private_config  # type: ignore  # Standard import for script-based projects

    for k in dir(private_config):
        if k.isupper():
            globals()[k] = getattr(private_config, k)
except ImportError:
    # If private_config.py is missing, define dummy values (for public repo)
    DISCORD_WEBHOOK_URL = None
    DISCORD_OCR_WEBHOOK_URL = None
    COC_API_TOKEN = None
    COC_PLAYER_TAG = None
    DISCORD_TOKEN = None
    AUTHORIZED_USERS = []
    CONTROL_CHANNEL_ID = None

# Debug Logging Configuration
DEBUG_LOG_ENABLED = True  # Set to False to disable debug logging to Discord
DEBUG_LOG_INTERVAL = 30  # Send debug logs every 30 seconds (buffered)
DEBUG_LOG_LEVEL = "INFO"  # Minimum level to log: DEBUG, INFO, WARNING, ERROR
DEBUG_DESTRUCTION_PERCENTAGE = False  # Set to False to disable destruction percentage debug logging

# Side-based deployment coordinates
SIDE_DEPLOYMENT_COORDS = {
    "left": {
        "hero": (324, 638),
        "units": [
            (443, 654),
            (530, 572),
            (695, 493),
            (763, 429),
            (841, 370),
            (888, 323),
            (956, 280),
            (1000, 245),
            (1063, 192),
            (1131, 144),
            (391, 823),
            (430, 840),
            (496, 891),
            (536, 933),
            (570, 966),
            (613, 1003),
            (658, 1032),
            (681, 1047),
            (766, 1064),
            (633, 983),
            (545, 939),
            (461, 884),
            (381, 790),
            (418, 634),
            (568, 534),
            (695, 453),
            (825, 384),
            (899, 344),
            (963, 290),
            (1015, 247),
            (1055, 210),
            (1101, 170),
            (1116, 157),
        ],
    },
    "up": {
        "hero": (1299, 121),  # Middle position from captured coordinates
        "units": [
            (229, 903),
            (250, 889),
            (271, 876),
            (292, 865),
            (313, 854),
            (334, 840),
            (355, 825),
            (376, 811),
            (397, 797),
            (418, 783),
            (439, 768),
            (460, 750),
            (481, 730),
            (502, 715),
            (523, 697),
            (538, 676),
            (559, 656),
            (580, 639),
            (601, 626),
            (622, 611),
            (643, 600),
            (664, 590),
            (685, 579),
            (706, 569),
            (727, 556),
            (748, 543),
            (769, 527),
            (790, 507),
            (809, 486),
            (827, 465),
            (848, 448),
            (869, 432),
            (890, 416),
            (911, 404),
            (932, 388),
            (953, 373),
            (974, 355),
            (995, 337),
            (1016, 317),
            (1037, 303),
            (1058, 286),
            (1079, 269),
            (1100, 252),
            (1121, 236),
            (1142, 222),
            (1163, 204),
            (1176, 183),
            (1194, 162),
            (1215, 148),
            (1236, 138),
            (1257, 129),
            (1278, 123),
            (1299, 121),
            (1320, 128),
            (1341, 146),
            (1362, 164),
            (1383, 180),
            (1404, 199),
            (1425, 219),
            (1446, 238),
            (1467, 257),
            (1488, 274),
            (1509, 288),
            (1530, 300),
            (1551, 311),
            (1572, 320),
            (1593, 332),
            (1614, 347),
            (1635, 366),
            (1656, 386),
            (1677, 402),
            (1698, 420),
            (1719, 436),
            (1740, 447),
            (1761, 461),
            (1782, 474),
            (1803, 489),
            (1824, 503),
            (1845, 516),
            (1866, 529),
            (1887, 543),
            (1908, 559),
            (1929, 578),
            (1949, 599),
            (1970, 617),
            (1991, 630),
            (2012, 646),
            (2033, 661),
            (2054, 679),
            (2075, 695),
            (2096, 714),
            (2117, 734),
            (2138, 753),
            (2159, 770),
            (2180, 785),
            (2201, 799),
            (2222, 810),
            (2243, 823),
            (2264, 835),
            (2285, 848),
            (2306, 866),
            (2324, 887),
            (2330, 894),
        ],
    },
    "right": {
        "hero": (2226, 682),
        "units": [
            (1472, 85),
            (1534, 132),
            (1575, 171),
            (1620, 207),
            (1684, 251),
            (1726, 282),
            (1767, 318),
            (1797, 350),
            (1844, 386),
            (1886, 420),
            (1924, 446),
            (1975, 482),
            (2045, 531),
            (2091, 562),
            (2195, 641),
            (2251, 691),
            (2244, 763),
            (2178, 833),
            (2121, 882),
            (2028, 937),
            (1981, 965),
            (1914, 1000),
            (1876, 1021),
            (1823, 1055),
            (1771, 1086),
            (1727, 1117),
            (1678, 1153),
            (1636, 1183),
        ],
    },
    "down": {
        "hero": (1281, 1143),  # Middle position from captured coordinates
        "units": [
            (273, 415),
            (294, 431),
            (315, 446),
            (336, 463),
            (357, 478),
            (378, 496),
            (399, 513),
            (420, 528),
            (441, 547),
            (462, 567),
            (483, 583),
            (504, 600),
            (525, 618),
            (546, 632),
            (567, 648),
            (588, 663),
            (609, 681),
            (630, 697),
            (651, 711),
            (672, 724),
            (693, 739),
            (714, 751),
            (735, 762),
            (756, 775),
            (777, 790),
            (798, 804),
            (819, 818),
            (840, 831),
            (861, 846),
            (882, 863),
            (903, 878),
            (924, 894),
            (945, 912),
            (966, 929),
            (987, 946),
            (1008, 964),
            (1029, 982),
            (1050, 1001),
            (1071, 1020),
            (1092, 1040),
            (1113, 1059),
            (1134, 1074),
            (1155, 1088),
            (1176, 1102),
            (1197, 1116),
            (1218, 1126),
            (1239, 1133),
            (1260, 1138),
            (1281, 1143),
            (1302, 1147),
            (1323, 1149),
            (1344, 1149),
            (1365, 1148),
            (1386, 1147),
            (1407, 1140),
            (1428, 1125),
            (1449, 1105),
            (1464, 1084),
            (1483, 1063),
            (1501, 1042),
            (1522, 1025),
            (1543, 1009),
            (1564, 995),
            (1585, 981),
            (1606, 965),
            (1627, 952),
            (1648, 933),
            (1669, 918),
            (1690, 904),
            (1711, 888),
            (1732, 871),
            (1753, 858),
            (1774, 840),
            (1795, 821),
            (1816, 802),
            (1837, 784),
            (1858, 765),
            (1879, 744),
            (1900, 729),
            (1921, 718),
            (1942, 709),
            (1963, 698),
            (1977, 677),
            (1987, 656),
            (2008, 636),
            (2029, 622),
            (2050, 606),
            (2071, 593),
            (2092, 580),
            (2113, 565),
            (2133, 544),
            (2154, 525),
            (2175, 509),
            (2196, 496),
            (2217, 484),
            (2238, 470),
            (2259, 454),
            (2280, 438),
            (2301, 424),
        ],
    },
}

# Wall Breaker deployment positions for SGoblin Farm (middle of each deployment edge)
# Each side has 2 edges, so 2 wall breaker positions per side
WALL_BREAKER_POSITIONS = {
    "up": [
        (932, 388),  # 1/3 through deployment path (left-center)
        (1677, 402),  # 2/3 through deployment path (right-center)
    ],
    "down": [
        (966, 929),  # 1/3 through deployment path (left-center)
        (1648, 933),  # 2/3 through deployment path (right-center)
    ],
}

# Achievement Building Template Sizes (width, height)
# Used for accurate bounding box drawing and center calculations
ACHIEVEMENT_BUILDING_SIZES = {
    "eagle_artillery": (70, 70),
    "firespitter": (50, 50),
    "inferno_tower": (40, 80),
    "monolith": (54, 80),
    "multi_archer_tower": (40, 80),
    "multi_gear_tower": (40, 80),
    "ricochet_cannon": (50, 50),
    "scattershot": (60, 60),
    "spell_tower": (40, 40),
    "xbow": (60, 60),
}

# Building-specific confidence thresholds (default is 0.7)
# Lower threshold for buildings that are harder to detect
ACHIEVEMENT_BUILDING_THRESHOLDS = {
    "monolith": 0.65,  # Monolith templates need lower threshold
    "spell_tower": 0.78,  # Higher threshold to reduce false positives
    "firespitter": 0.78,  # Higher threshold to reduce false positives
}

# GPU Template Matching (Work In Progress)
# Controlled via GUI checkbox in Global Settings ("GPU Scanning")
# Toggle at runtime - no restart required
# NOTE: Has issues detecting Firespitter and Spell Tower specifically
# GPU offloads CPU but is ~2x slower - main benefit is reduced CPU load

# Visualization Overlay Colors
# Used by visualization_overlay.py for real-time detection display
OVERLAY_COLORS = {
    "ocr_success": "#00FF00",  # Green - high confidence OCR
    "ocr_warning": "#FFFF00",  # Yellow - medium confidence OCR
    "ocr_fail": "#FF0000",  # Red - low confidence OCR
    "air_defense": "#FF4444",  # Light red - air defenses
    "town_hall": "#AA00FF",  # Purple - town hall
    "achievement": "#00FFFF",  # Cyan - achievement buildings (conf >= 0.7)
    "achievement_low": "#FF0000",  # Red - achievement buildings (conf 0.6-0.7, not used in attack)
    "air_sweeper": "#00FFFF",  # Cyan - air sweepers
    "deployment": "#FFFF00",  # Yellow - troop deployment positions
    "spell_target": "#FF00FF",  # Magenta - spell targets
    "side_indicator": "#00FF00",  # Green - attack side indicator
}
