import sys
import os
import cv2
import numpy as np
import time
from PIL import ImageGrab

# Base center point for side detection (replaces old corner-based distance calculation)
BASE_CENTER_X = 1298
BASE_CENTER_Y = 697

# Town Hall detection config
TOWN_HALL_TEMPLATES_DIR = "Reference Screenshots/town_halls/"
TOWN_HALL_DETECTION_THRESHOLD = 0.7
TOWN_HALL_REGION = (800, 400, 1760, 1000)

def detect_town_hall():
    """
    Detect Town Hall using template matching. Returns (x, y, level, confidence) or None.
    """
    th_img = ImageGrab.grab(bbox=TOWN_HALL_REGION)
    th_cv = cv2.cvtColor(np.array(th_img), cv2.COLOR_RGB2BGR)
    if not os.path.exists(TOWN_HALL_TEMPLATES_DIR):
        print(f"Town Hall templates directory not found: {TOWN_HALL_TEMPLATES_DIR}")
        return None
    best_match = None
    best_confidence = 0
    for template_file in os.listdir(TOWN_HALL_TEMPLATES_DIR):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(TOWN_HALL_TEMPLATES_DIR, template_file)
            template = cv2.imread(template_path)
            if template is None:
                continue
            result = cv2.matchTemplate(th_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            level = 1
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            if max_val >= TOWN_HALL_DETECTION_THRESHOLD and max_val > best_confidence:
                x, y = max_loc
                global_x = x + TOWN_HALL_REGION[0]
                global_y = y + TOWN_HALL_REGION[1]
                best_match = (global_x, global_y, level, max_val)
                best_confidence = max_val
    return best_match

def determine_side(th_x, th_y):
    """
    Determine which side of the base center the town hall is located.
    Returns the side name and debug information.
    """
    # Calculate relative position from base center
    x_diff = th_x - BASE_CENTER_X
    y_diff = th_y - BASE_CENTER_Y
    
    # Determine side based on which quadrant the town hall is in
    if abs(x_diff) > abs(y_diff):
        # Town hall is more horizontally offset
        if x_diff > 0:
            side = 'right'
        else:
            side = 'left'
    else:
        # Town hall is more vertically offset
        if y_diff > 0:
            side = 'down'
        else:
            side = 'up'
    
    return side, x_diff, y_diff

def main():
    print("Attempting automatic Town Hall detection...")
    print("Waiting 3 seconds before detection...")
    time.sleep(3)
    th_result = detect_town_hall()
    if th_result:
        th_x, th_y, level, conf = th_result
        # Adjust to center of Town Hall
        th_x += 60
        th_y += 75
        print(f"Detected Town Hall at ({th_x}, {th_y}) [center-adjusted], level {level}, confidence {conf:.2f}")
        print(f"Base center at ({BASE_CENTER_X}, {BASE_CENTER_Y})")
        
        side, x_diff, y_diff = determine_side(th_x, th_y)
        print(f"Town Hall is on the {side} side of base center")
        print(f"X difference: {x_diff:.1f}, Y difference: {y_diff:.1f}")
        print()
    else:
        print("Automatic detection failed. Enter Town Hall coordinates (x y), or 'q' to quit:")
        while True:
            user_input = input('TH x y: ').strip()
            if user_input.lower() == 'q':
                break
            try:
                th_x, th_y = map(int, user_input.split())
            except Exception:
                print("Invalid input. Please enter two integers separated by space.")
                continue
            
            print(f"Base center at ({BASE_CENTER_X}, {BASE_CENTER_Y})")
            side, x_diff, y_diff = determine_side(th_x, th_y)
            print(f"Town Hall is on the {side} side of base center")
            print(f"X difference: {x_diff:.1f}, Y difference: {y_diff:.1f}")
            print()

if __name__ == '__main__':
    main() 