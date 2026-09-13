# capture_templates.py
import sys
import os

# Add project root directory to path to import config
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import pyautogui
import time
import keyboard
from PIL import ImageGrab, Image, ImageEnhance
import cv2
import numpy as np
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
import config

def enhance_template_image(img):
    """
    Enhance template image for better matching by improving contrast and sharpness.
    """
    # Convert to PIL Image if it's not already
    if not isinstance(img, Image.Image):
        img = Image.fromarray(img)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.3)
    
    return img

def create_background_variants(img, level):
    """
    Create multiple template variants with different background processing.
    """
    variants = []
    
    # Original image
    variants.append((img, f"air_defense_level_{level}.png"))
    
    # Convert to numpy array for OpenCV processing
    img_array = np.array(img)
    
    # Variant 1: Remove white background (make transparent)
    if len(img_array.shape) == 3:  # RGB image
        # Create mask for white/light background
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_not(mask)
        
        # Apply mask to remove white background
        result = cv2.bitwise_and(img_array, img_array, mask=mask)
        variants.append((Image.fromarray(result), f"air_defense_level_{level}_no_bg.png"))
    
    # Variant 2: Edge detection for shape-based matching
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        variants.append((Image.fromarray(edges), f"air_defense_level_{level}_edges.png"))
    
    return variants

def capture_air_defense_template():
    """
    Interactive tool to capture air defense templates from the game screen.
    """
    print("Air Defense Template Capture Tool")
    print("=================================")
    print("1. Navigate to a base with visible air defenses")
    print("2. Press Enter when ready to capture")
    print("3. Position mouse over air defense and press 'R' to capture")
    print("4. Enter the level of the air defense")
    print("5. Template will be saved automatically")
    print("\nTemplate Background Options:")
    print("- In-game screenshots (recommended): Best accuracy")
    print("- Wiki screenshots: May work but less accurate")
    print("- White background: Will be processed to remove background")
    print("\nControls:")
    print("- Press 'R' to capture template at mouse position")
    print("- Press 'Q' to quit")
    print("- Press 'T' to test current templates")
    input("Press Enter when ready...")
    # Create templates directory if it doesn't exist
    templates_dir = "screenshots/reference/air_defenses"
    os.makedirs(templates_dir, exist_ok=True)
    # Template size (will capture a square around mouse position)
    template_size = 60  # pixels (changed from 80)
    while True:
        try:
            print("\nPosition mouse over air defense and press 'R' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")
            # Wait for key press
            while True:
                if keyboard.is_pressed('r'):
                    # Get current mouse position
                    x, y = pyautogui.position()
                    print(f"Capturing at position: ({x}, {y})")
                    # Calculate region around mouse position
                    half_size = template_size // 2
                    region = (x - half_size, y - half_size, x + half_size, y + half_size)
                    # Ensure region is within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )
                    # Capture the region
                    template_img = ImageGrab.grab(bbox=region)
                    # Get level from user
                    level = input("Enter air defense level (1-15): ")
                    try:
                        level = int(level)
                        if level < 1 or level > 15:
                            print("Level must be between 1 and 15")
                            continue
                    except ValueError:
                        print("Invalid level, must be a number")
                        continue
                    # Ask about background type
                    print("\nBackground type:")
                    print("1. In-game screenshot (green background)")
                    print("2. Wiki screenshot (white background)")
                    print("3. Other (will process automatically)")
                    bg_choice = input("Choose background type (1-3): ").strip()
                    # Enhance the image
                    enhanced_img = enhance_template_image(template_img)
                    # Create variants based on background type
                    if bg_choice == "2":  # Wiki screenshot
                        print("Creating variants for wiki screenshot...")
                        variants = create_background_variants(enhanced_img, level)
                    else:  # In-game or other
                        variants = [(enhanced_img, f"air_defense_level_{level}.png")]
                    # Save all variants, ensuring unique filenames
                    for variant_img, filename in variants:
                        base_name, ext = os.path.splitext(filename)
                        save_path = os.path.join(templates_dir, filename)
                        idx = 1
                        # If file exists, append _2, _3, etc.
                        while os.path.exists(save_path):
                            save_path = os.path.join(templates_dir, f"{base_name}_{idx}{ext}")
                            idx += 1
                        variant_img.save(save_path)
                        print(f"Template saved as: {save_path}")
                    # Show preview of main template
                    enhanced_img.show()
                    continue_capture = input("Capture another template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return
                    break  # Break out of the key waiting loop
                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return
                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return
                elif keyboard.is_pressed('t'):
                    test_template_matching()
                    break  # Break out of the key waiting loop
                time.sleep(0.1)  # Small delay to prevent high CPU usage
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    print("Template capture complete!")

def test_template_matching():
    """
    Test template matching with existing templates.
    """
    print("Template Matching Test")
    print("=====================")
    print("This will test how well your templates match against a current base view.")
    
    input("Navigate to a base with air defenses and press Enter...")
    
    # Capture current screen
    print("Capturing current base view...")
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    
    templates_dir = "screenshots/reference/air_defenses"
    if not os.path.exists(templates_dir):
        print("No templates found. Please capture some templates first.")
        return

    print("Testing templates...")
    all_matches = []
    
    for template_file in os.listdir(templates_dir):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                continue
            
            # Extract level from filename
            level = 1
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Test matching
            result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
            
            # Find all matches above threshold
            threshold = 0.5  # Lower threshold for testing
            locations = np.where(result >= threshold)
            
            print(f"\n{template_file} (Level {level}):")
            
            for pt in zip(*locations[::-1]):  # Switch columns and rows
                x, y = pt
                confidence = result[y, x]
                
                # Convert to global coordinates
                global_x = x + config.BASE_VIEW_REGION[0]
                global_y = y + config.BASE_VIEW_REGION[1]
                
                print(f"  Match at ({global_x}, {global_y}) - Confidence: {confidence:.3f}")
                all_matches.append((global_x, global_y, level, confidence))
    
    # Remove duplicates and sort by confidence
    filtered_matches = []
    for match in all_matches:
        x, y, level, conf = match
        is_duplicate = False
        
        for existing in filtered_matches:
            ex, ey, _, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 50:  # 50 pixel threshold for duplicates
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_matches.append(match)
    
    # Sort by confidence
    filtered_matches.sort(key=lambda x: x[3], reverse=True)
    
    print(f"\n=== SUMMARY ===")
    print(f"Total unique matches found: {len(filtered_matches)}")
    
    if filtered_matches:
        print("Detected air defenses:")
        for i, (x, y, level, conf) in enumerate(filtered_matches):
            print(f"  {i+1}. Level {level} at ({x}, {y}) - Confidence: {conf:.3f}")
    else:
        print("No air defenses detected!")
        print("Possible reasons:")
        print("- No templates match the current base")
        print("- Detection threshold too high")
        print("- Templates need to be updated")
        print("- Base view region incorrect")
    
    # Show what would be targeted by lightning spells
    if filtered_matches:
        lightning_targets = [(x, y) for x, y, _, _ in sorted(filtered_matches, key=lambda x: x[2], reverse=True)]
        print(f"\nLightning spell targets (by priority):")
        for i, (x, y) in enumerate(lightning_targets):
            print(f"  {i+1}. Target at ({x}, {y})")

def visual_test_template_matching():
    """
    Visual test that shows detection overlay on the screen.
    """
    print("Visual Template Matching Test")
    print("============================")
    print("This will show detection results as an overlay on your screen.")
    
    while True:
        input("Navigate to a base with air defenses and press Enter...")
        # Capture current screen
        print("Capturing current base view...")
        base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
        base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
        templates_dir = "screenshots/reference/air_defenses"
        if not os.path.exists(templates_dir):
            print("No templates found. Please capture some templates first.")
            return
        # Create a copy for drawing
        result_img = base_cv.copy()
        # Collect all matches from all templates above threshold
        all_matches = []
        for template_file in os.listdir(templates_dir):
            if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                template_path = os.path.join(templates_dir, template_file)
                template = cv2.imread(template_path)
                if template is None:
                    continue
                # Extract level from filename
                level = 1
                if 'level_' in template_file.lower():
                    try:
                        level_str = template_file.lower().split('level_')[1].split('.')[0]
                        level = int(level_str)
                    except (ValueError, IndexError):
                        pass
                # Test matching
                result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
                threshold = 0.5
                locations = np.where(result >= threshold)
                h, w = template.shape[:2]
                for pt in zip(*locations[::-1]):
                    x, y = pt
                    confidence = result[y, x]
                    all_matches.append({'x': x, 'y': y, 'w': w, 'h': h, 'level': level, 'confidence': confidence})
        # Apply non-maximum suppression (NMS) to keep only the best match per air defense
        def nms(matches, iou_threshold=0.3, max_matches=4):
            if not matches:
                return []
            # Sort by confidence
            matches = sorted(matches, key=lambda m: m['confidence'], reverse=True)
            picked = []
            while matches and len(picked) < max_matches:
                best = matches.pop(0)
                picked.append(best)
                matches = [m for m in matches if compute_iou(best, m) < iou_threshold]
            return picked
        def compute_iou(a, b):
            # Intersection over Union for rectangles
            xA = max(a['x'], b['x'])
            yA = max(a['y'], b['y'])
            xB = min(a['x'] + a['w'], b['x'] + b['w'])
            yB = min(a['y'] + a['h'], b['y'] + b['h'])
            interArea = max(0, xB - xA) * max(0, yB - yA)
            boxAArea = a['w'] * a['h']
            boxBArea = b['w'] * b['h']
            iou = interArea / float(boxAArea + boxBArea - interArea + 1e-5)
            return iou
        nms_matches = nms(all_matches, iou_threshold=0.3, max_matches=4)
        # Draw rectangles and text for NMS-filtered matches
        for match in nms_matches:
            x, y, w, h = match['x'], match['y'], match['w'], match['h']
            level = match['level']
            confidence = match['confidence']
            # Draw rectangle with different colors based on confidence
            if confidence >= 0.8:
                color = (0, 255, 0)  # Green for high confidence
            elif confidence >= 0.6:
                color = (0, 255, 255)  # Yellow for medium confidence
            else:
                color = (0, 165, 255)  # Orange for low confidence
            cv2.rectangle(result_img, (x, y), (x + w, y + h), color, 2)
            text = f"L{level} {confidence:.2f}"
            # Draw black outline first (thicker)
            cv2.putText(result_img, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
            # Draw white text on top (thinner)
            cv2.putText(result_img, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow('Air Defense Detection Results', result_img)
        print("Detection overlay shown.")
        print("Close options:")
        print("- Press any key in the image window")
        print("- Press 'Q' in this console")
        print("- Close the image window manually")
        # Wait for key press with timeout
        start_time = time.time()
        while True:
            key = cv2.waitKey(100) & 0xFF
            if key != 255:
                break
            if keyboard.is_pressed('q'):
                break
            if time.time() - start_time > 30:
                print("Timeout - closing automatically")
                break
        cv2.destroyAllWindows()
        print(f"Total matches found (after NMS): {len(nms_matches)}")
        if nms_matches:
            print("Rectangles show the best detected air defenses with level and confidence scores.")
        # Ask user if they want to repeat
        repeat = input("Press Enter to repeat, or Q to quit: ").strip().lower()
        if repeat == 'q':
            break

def capture_town_hall_templates():
    """
    Capture Town Hall templates for level detection.
    """
    print("Town Hall Template Capture Tool")
    print("===============================")
    print("This tool captures Town Hall templates for level detection.")
    
    input("Navigate to a base with visible Town Hall and press Enter...")
    
    # Create templates directory if it doesn't exist
    templates_dir = "screenshots/reference/town_halls"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Template size (Town Halls are larger than air defenses)
    template_size = 120  # pixels
    
    while True:
        try:
            print("\nPosition mouse over Town Hall and press 'R' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")
            
            # Wait for key press
            while True:
                if keyboard.is_pressed('r'):
                    # Get current mouse position
                    x, y = pyautogui.position()
                    print(f"Capturing at position: ({x}, {y})")
                    
                    # Calculate region around mouse position
                    half_size = template_size // 2
                    region = (x - half_size, y - half_size, x + half_size, y + half_size)
                    
                    # Ensure region is within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )
                    
                    # Capture the region
                    template_img = ImageGrab.grab(bbox=region)
                    
                    # Get level from user
                    level = input("Enter Town Hall level (1-16): ")
                    try:
                        level = int(level)
                        if level < 1 or level > 16:
                            print("Level must be between 1 and 16")
                            continue
                    except ValueError:
                        print("Invalid level, must be a number")
                        continue
                    
                    # Save template
                    filename = f"town_hall_level_{level}.png"
                    filepath = os.path.join(templates_dir, filename)
                    template_img.save(filepath)
                    
                    print(f"Town Hall template saved as: {filepath}")
                    
                    # Show preview
                    template_img.show()
                    
                    continue_capture = input("Capture another template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return
                    
                    break  # Break out of the key waiting loop
                    
                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('t'):
                    test_town_hall_matching()
                    break  # Break out of the key waiting loop
                
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("Town Hall template capture complete!")

def test_town_hall_matching():
    """
    Test Town Hall template matching with existing templates.
    """
    print("Town Hall Template Matching Test")
    print("================================")
    print("This will test how well your Town Hall templates match against a current base view.")
    
    input("Navigate to a base with visible Town Hall and press Enter...")
    
    # Capture current screen
    print("Capturing current Town Hall region...")
    th_img = ImageGrab.grab(bbox=config.TOWN_HALL_REGION)
    th_cv = cv2.cvtColor(np.array(th_img), cv2.COLOR_RGB2BGR)
    
    templates_dir = "screenshots/reference/town_halls"
    if not os.path.exists(templates_dir):
        print("No Town Hall templates found. Please capture some templates first.")
        return
    
    print("Testing Town Hall templates...")
    best_match = None
    best_confidence = 0
    
    for template_file in os.listdir(templates_dir):
        if template_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)
            
            if template is None:
                continue
            
            # Extract level from filename
            level = 1
            if 'level_' in template_file.lower():
                try:
                    level_str = template_file.lower().split('level_')[1].split('.')[0]
                    level = int(level_str)
                except (ValueError, IndexError):
                    pass
            
            # Test matching
            result = cv2.matchTemplate(th_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            print(f"{template_file} (Level {level}): Max confidence = {max_val:.3f}")
            
            if max_val > best_confidence:
                best_confidence = max_val
                best_match = (template_file, level, max_val)
    
    print(f"\n=== SUMMARY ===")
    if best_match and best_confidence >= config.TOWN_HALL_DETECTION_THRESHOLD:
        template_file, level, conf = best_match
        print(f"Best match: {template_file} (Level {level}) - Confidence: {conf:.3f}")
    else:
        print("No Town Hall detected!")
        print("Possible reasons:")
        print("- No templates match the current Town Hall")
        print("- Detection threshold too high")
        print("- Templates need to be updated")
        print("- Town Hall region incorrect")

def capture_attack_templates():
    """
    Capture templates during actual attacks to debug detection issues.
    """
    print("Attack Template Capture Tool")
    print("===========================")
    print("This tool helps capture templates during actual attacks.")
    print("Use this when the bot fails to detect air defenses during attacks.")
    
    input("Start an attack and press Enter when ready to capture...")
    
    # Create templates directory if it doesn't exist
    templates_dir = "screenshots/reference/air_defenses"
    os.makedirs(templates_dir, exist_ok=True)

    # Template size (will capture a square around mouse position)
    template_size = 80  # pixels

    while True:
        try:
            print("\nPosition mouse over air defense and press 'R' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")

            # Wait for key press
            while True:
                if keyboard.is_pressed('r'):
                    # Get current mouse position
                    x, y = pyautogui.position()
                    print(f"Capturing at position: ({x}, {y})")

                    # Calculate region around mouse position
                    half_size = template_size // 2
                    region = (x - half_size, y - half_size, x + half_size, y + half_size)

                    # Ensure region is within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )

                    # Capture the region
                    template_img = ImageGrab.grab(bbox=region)

                    # Get level from user
                    level = input("Enter air defense level (1-15): ")
                    try:
                        level = int(level)
                        if level < 1 or level > 15:
                            print("Level must be between 1 and 15")
                            continue
                    except ValueError:
                        print("Invalid level, must be a number")
                        continue

                    # Save with attack-specific naming
                    filename = f"attack_air_defense_level_{level}_{int(time.time())}.png"
                    filepath = os.path.join(templates_dir, filename)
                    template_img.save(filepath)
                    
                    print(f"Attack template saved as: {filepath}")
                    
                    # Show preview
                    template_img.show()
                    
                    continue_capture = input("Capture another template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return
                    
                    break  # Break out of the key waiting loop
                    
                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('t'):
                    test_template_matching()
                    break  # Break out of the key waiting loop
                
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("Attack template capture complete!")


def capture_wall_templates():
    """
    Interactive tool to capture wall templates for wall upgrading feature.
    """
    print("Wall Template Capture Tool")
    print("=========================")
    print("This tool helps capture wall templates for automatic wall upgrading.")
    print("Instructions:")
    print("1. Navigate to your base where walls are visible")
    print("2. Press Enter when ready to capture")
    print("3. Position mouse over a wall and press 'W' to capture")
    print("4. Template will be saved automatically")
    print("\nTips for good wall templates:")
    print("- Capture different walls (various positions)")
    print("- Include some background around the wall")
    print("- Capture walls in different lighting conditions")
    print("- Make sure walls are clearly visible")
    print("\nControls:")
    print("- Press 'W' to capture template at mouse position")
    print("- Press 'Q' to quit")
    print("- Press 'T' to test current templates")
    
    input("Press Enter when ready...")
    
    # Create walls directory if it doesn't exist
    walls_dir = config.WALL_TEMPLATES_DIR
    os.makedirs(walls_dir, exist_ok=True)
    
    # Template size (will capture a square around mouse position)
    template_size = 60  # pixels - smaller for walls
    
    while True:
        try:
            print("\nPosition mouse over a wall and press 'W' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")
            
            # Wait for key press
            while True:
                if keyboard.is_pressed('w'):
                    # Get current mouse position
                    x, y = pyautogui.position()
                    print(f"Capturing wall at position: ({x}, {y})")
                    
                    # Calculate region around mouse position
                    half_size = template_size // 2
                    region = (x - half_size, y - half_size, x + half_size, y + half_size)
                    
                    # Ensure region is within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )
                    
                    # Capture the region
                    template_img = ImageGrab.grab(bbox=region)
                    
                    # Enhance the image
                    enhanced_img = enhance_template_image(template_img)
                    
                    # Generate filename with timestamp
                    timestamp = int(time.time())
                    filename = f"wall_template_{timestamp}.png"
                    filepath = os.path.join(walls_dir, filename)
                    
                    # Save the template
                    enhanced_img.save(filepath)
                    print(f"Wall template saved as: {filepath}")
                    print(f"Template size: {enhanced_img.size[0]}x{enhanced_img.size[1]} pixels")
                    
                    # Show preview
                    enhanced_img.show()
                    
                    # Count templates
                    templates = [f for f in os.listdir(walls_dir) 
                               if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    print(f"Total wall templates: {len(templates)}")
                    
                    continue_capture = input("Capture another wall template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return
                    
                    break  # Break out of the key waiting loop
                    
                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return
                    
                elif keyboard.is_pressed('t'):
                    test_wall_template_matching()
                    break  # Break out of the key waiting loop
                
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("Wall template capture complete!")


def test_wall_template_matching():
    """
    Test wall template matching with existing templates.
    """
    print("Wall Template Matching Test")
    print("===========================")
    print("This will test how well your wall templates match against a current base view.")
    
    input("Navigate to your base where walls are visible and press Enter...")
    
    # Capture current screen
    print("Capturing current base view...")
    base_img = ImageGrab.grab(bbox=config.WALL_DETECTION_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)
    
    walls_dir = config.WALL_TEMPLATES_DIR
    if not os.path.exists(walls_dir):
        print(f"Walls directory not found: {walls_dir}")
        return
    
    template_files = [f for f in os.listdir(walls_dir) 
                     if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not template_files:
        print("No wall templates found!")
        return
    
    print(f"Testing {len(template_files)} wall templates...")
    
    # Test each template
    for template_file in template_files:
        template_path = os.path.join(walls_dir, template_file)
        template = cv2.imread(template_path)
        
        if template is None:
            print(f"Failed to load template: {template_file}")
            continue
        
        # Perform template matching
        result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        print(f"  {template_file}: Max confidence = {max_val:.3f}")
        
        # Show matches above threshold
        locations = np.where(result >= config.WALL_DETECTION_THRESHOLD)
        matches = len(list(zip(*locations[::-1])))
        print(f"    Matches above threshold ({config.WALL_DETECTION_THRESHOLD}): {matches}")
        
        if matches > 0:
            print(f"    Best match position: {max_loc}")
    
    print("\nTest complete!")

def capture_air_sweeper_template():
    """
    Interactive tool to capture air sweeper templates from the game screen.
    """
    print("Air Sweeper Template Capture Tool")
    print("=================================")
    print("1. Navigate to a base with visible air sweepers")
    print("2. Press Enter when ready to capture")
    print("3. Position mouse over air sweeper and press 'R' to capture")
    print("4. Enter the facing direction (1-8 or name, e.g., left, up-left, up, etc.)")
    print("5. Template will be saved automatically")
    print("\nControls:")
    print("- Press 'R' to capture template at mouse position")
    print("- Press 'Q' to quit")
    print("- Press 'T' to test current templates")

    input("Press Enter when ready...")

    # Create templates directory if it doesn't exist
    templates_dir = "screenshots/reference/air_sweepers"
    os.makedirs(templates_dir, exist_ok=True)

    template_size = 60  # Air sweeper is small, use a smaller template

    while True:
        try:
            print("\nPosition mouse over air sweeper and press 'R' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")
            while True:
                if keyboard.is_pressed('r'):
                    x, y = pyautogui.position()
                    print(f"Capturing at position: ({x}, {y})")
                    half_size = template_size // 2
                    region = (x - half_size, y - half_size, x + half_size, y + half_size)
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )
                    template_img = ImageGrab.grab(bbox=region)
                    # Get direction from user
                    print("Directions: 1=left, 2=up-left, 3=up, 4=up-right, 5=right, 6=down-right, 7=down, 8=down-left")
                    direction = input("Enter air sweeper facing direction (1-8 or name): ").strip().lower()
                    if direction in ['1', 'left']:
                        direction = 'left'
                    elif direction in ['2', 'up-left', 'upleft']:
                        direction = 'up_left'
                    elif direction in ['3', 'up']:
                        direction = 'up'
                    elif direction in ['4', 'up-right', 'upright']:
                        direction = 'up_right'
                    elif direction in ['5', 'right']:
                        direction = 'right'
                    elif direction in ['6', 'down-right', 'downright']:
                        direction = 'down_right'
                    elif direction in ['7', 'down']:
                        direction = 'down'
                    elif direction in ['8', 'down-left', 'downleft']:
                        direction = 'down_left'
                    else:
                        print("Invalid direction.")
                        continue
                    filename = f"air_sweeper_{direction}.png"
                    filepath = os.path.join(templates_dir, filename)
                    template_img.save(filepath)
                    print(f"Template saved as: {filepath}")
                    template_img.show()
                    continue_capture = input("Capture another template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return
                    break
                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return
                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return
                elif keyboard.is_pressed('t'):
                    print("(Testing not implemented for air sweepers yet)")
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue
    print("Template capture complete!")


def capture_achievement_building_templates():
    """
    Interactive tool to capture achievement building templates (Eagle, Monolith, X-Bow, Inferno, Scattershot).
    """
    print("Achievement Building Template Capture Tool")
    print("==========================================")
    print("This tool captures templates for achievement farming buildings:")
    print("- Eagle Artillery")
    print("- Monolith")
    print("- X-Bow")
    print("- Inferno Tower")
    print("- Scattershot")
    print("\nInstructions:")
    print("1. Navigate to a base with visible target buildings")
    print("2. Press Enter when ready to capture")
    print("3. Position mouse over building and press 'R' to capture")
    print("4. Select the building type")
    print("5. Template will be saved automatically")
    print("\nControls:")
    print("- Press 'R' to capture template at mouse position")
    print("- Press 'Q' to quit")
    print("- Press 'T' to test current templates")

    input("Press Enter when ready...")

    # Building types for achievement farming
    building_types = {
        '1': 'eagle_artillery',
        '2': 'monolith',
        '3': 'xbow',
        '4': 'inferno_tower',
        '5': 'scattershot',
        '6': 'spell_tower',
        '7': 'multi_archer_tower',
        '8': 'ricochet_cannon',
        '9': 'firespitter',
        '10': 'multi_gear_tower'
    }

    # Template sizes vary by building (width, height) - can be square or rectangular
    template_sizes = {
        'eagle_artillery': (70, 70),  # Large building, square
        'monolith': (55, 80),            # Square
        'xbow': (50, 50),                # Square
        'inferno_tower': (40, 80),       # Slim and tall, rectangular
        'scattershot': (60, 60),         # Square
        'spell_tower': (40, 40),         # Small, square
        'multi_archer_tower': (40, 80),  # Slim and tall, rectangular
        'ricochet_cannon': (50, 50),     # Medium, square
        'firespitter': (50, 50),         # Medium, square
        'multi_gear_tower': (40, 80)     # Slim and tall, rectangular
    }


    while True:
        try:
            print("\nPosition mouse over target building and press 'R' to capture...")
            print("(Press 'Q' to quit, 'T' to test templates)")

            # Wait for key press
            while True:
                if keyboard.is_pressed('r'):
                    # Wait for R key to be released to avoid double-triggering
                    while keyboard.is_pressed('r'):
                        time.sleep(0.05)

                    # Get current mouse position
                    x, y = pyautogui.position()
                    print(f"Capturing at position: ({x}, {y})")

                    # Ask for building type
                    print("\nSelect building type:")
                    print("1. Eagle Artillery")
                    print("2. Monolith")
                    print("3. X-Bow")
                    print("4. Inferno Tower")
                    print("5. Scattershot")
                    print("6. Spell Tower")
                    print("7. Multi-Archer Tower")
                    print("8. Ricochet Cannon")
                    print("9. Firespitter")
                    print("10. Multi-Gear Tower")
                    building_choice = input("Choose building type (1-10): ").strip()

                    if building_choice not in building_types:
                        print(f"Invalid choice: '{building_choice}'")
                        print(f"Valid choices are: {list(building_types.keys())}")
                        print("Please try again...")
                        time.sleep(1)
                        continue

                    building_type = building_types[building_choice]
                    template_size = template_sizes[building_type]

                    # Calculate region around mouse position
                    # template_size can be (width, height) for rectangular or kept as int for backward compatibility
                    if isinstance(template_size, tuple):
                        width, height = template_size
                        half_width = width // 2
                        half_height = height // 2
                        region = (x - half_width, y - half_height, x + half_width, y + half_height)
                    else:
                        half_size = template_size // 2
                        region = (x - half_size, y - half_size, x + half_size, y + half_size)

                    # Ensure region is within screen bounds
                    screen_width, screen_height = pyautogui.size()
                    region = (
                        max(0, region[0]),
                        max(0, region[1]),
                        min(screen_width, region[2]),
                        min(screen_height, region[3])
                    )

                    # Capture the region
                    template_img = ImageGrab.grab(bbox=region)

                    # Enhance the image
                    enhanced_img = enhance_template_image(template_img)

                    # Create directory for this building type
                    templates_dir = f"screenshots/reference/achievement_buildings/{building_type}"
                    os.makedirs(templates_dir, exist_ok=True)

                    # Generate filename with timestamp
                    timestamp = int(time.time())
                    filename = f"{building_type}_{timestamp}.png"
                    filepath = os.path.join(templates_dir, filename)

                    # Save the template
                    enhanced_img.save(filepath)
                    print(f"\n{building_type.replace('_', ' ').title()} template saved as: {filepath}")
                    print(f"Template size: {enhanced_img.size[0]}x{enhanced_img.size[1]} pixels")

                    # Show preview
                    enhanced_img.show()

                    # Count templates for this building type
                    templates = [f for f in os.listdir(templates_dir)
                               if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    print(f"Total {building_type.replace('_', ' ')} templates: {len(templates)}")

                    continue_capture = input("Capture another template? (y/n): ").lower()
                    if continue_capture != 'y':
                        return

                    break  # Break out of the key waiting loop

                elif keyboard.is_pressed('q'):
                    print("\nExiting...")
                    return

                elif keyboard.is_pressed('esc'):
                    print("\nExiting...")
                    return

                elif keyboard.is_pressed('t'):
                    test_achievement_building_matching()
                    break  # Break out of the key waiting loop

                time.sleep(0.1)  # Small delay to prevent high CPU usage

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue

    print("Achievement building template capture complete!")


# Global template cache for F3 scanning
_achievement_templates_cache = {}
_scanning_active = False


def load_achievement_templates_local():
    """
    Load all achievement building templates into memory (local cache for capture_templates.py).
    Similar to load_achievement_building_templates() in main.py.
    """
    global _achievement_templates_cache

    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
                      'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower']
    templates_loaded = 0

    print("[TEMPLATE CACHE] Loading achievement building templates...")

    for building_type in building_types:
        # Use absolute path from PROJECT_ROOT
        templates_dir = os.path.join(PROJECT_ROOT, "screenshots", "reference", "achievement_buildings", building_type)

        if not os.path.exists(templates_dir):
            print(f"[TEMPLATE CACHE] Warning: {building_type} templates directory not found: {templates_dir}")
            _achievement_templates_cache[building_type] = []
            continue

        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"[TEMPLATE CACHE] No {building_type} templates found")
            _achievement_templates_cache[building_type] = []
            continue

        # Load all templates for this building type
        templates = []
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            template = cv2.imread(template_path)

            if template is not None:
                templates.append((template, template_file))
                templates_loaded += 1

        _achievement_templates_cache[building_type] = templates
        print(f"[TEMPLATE CACHE] Loaded {len(templates)} {building_type.replace('_', ' ')} templates")

    print(f"[TEMPLATE CACHE] ✓ Template cache ready: {templates_loaded} total templates loaded")
    return _achievement_templates_cache


# Building sizes from config
BUILDING_SIZES = {
    'eagle_artillery': (70, 70),
    'firespitter': (50, 50),
    'inferno_tower': (40, 80),
    'monolith': (54, 80),
    'multi_archer_tower': (40, 80),
    'multi_gear_tower': (40, 80),
    'ricochet_cannon': (50, 50),
    'scattershot': (60, 60),
    'spell_tower': (40, 40),
    'xbow': (60, 60),
}

# Building-specific thresholds
BUILDING_THRESHOLDS = {
    'monolith': 0.65,
    'spell_tower': 0.78,
    'firespitter': 0.78,
}


def detect_single_building_type(building_type, base_cv, threshold=0.6):
    """
    Detect a single building type from a captured image.
    Used for parallel scanning.

    Args:
        building_type: Type of building to detect
        base_cv: OpenCV image of the base view
        threshold: Detection threshold

    Returns:
        List of (x, y, width, height, confidence, building_type, is_high_conf) tuples
    """
    global _achievement_templates_cache

    if building_type not in _achievement_templates_cache:
        return []

    templates_list = _achievement_templates_cache[building_type]
    if not templates_list:
        return []

    box_w, box_h = BUILDING_SIZES.get(building_type, (70, 70))
    high_threshold = BUILDING_THRESHOLDS.get(building_type, 0.7)

    detections = []

    for template, template_name in templates_list:
        # Perform template matching
        result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)

        locations = np.where(result >= threshold)

        for pt in zip(*locations[::-1]):
            x, y = int(pt[0]), int(pt[1])
            confidence = float(result[y, x])

            # Mark if high confidence
            is_high_conf = confidence >= high_threshold

            detections.append((x, y, box_w, box_h, confidence, building_type, is_high_conf))

    return detections


def detect_buildings_from_image(base_cv, building_types=None, threshold=0.6, parallel=True):
    """
    Detect achievement buildings from a captured image.

    Args:
        base_cv: OpenCV image of the base view
        building_types: List of building types to scan, or None for all
        threshold: Detection threshold (default 0.6 to show low-confidence detections)
        parallel: Use parallel scanning (much faster)

    Returns:
        List of (x, y, width, height, confidence, building_type, is_high_conf) tuples
    """
    global _achievement_templates_cache

    if not _achievement_templates_cache:
        load_achievement_templates_local()

    if building_types is None:
        building_types = list(_achievement_templates_cache.keys())

    all_detections = []

    if parallel:
        # Parallel scanning using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(5, len(building_types))) as executor:
            # Submit all detection tasks
            future_to_building = {
                executor.submit(detect_single_building_type, building_type, base_cv, threshold): building_type
                for building_type in building_types
            }

            # Collect results as they complete
            for future in as_completed(future_to_building):
                try:
                    detections = future.result()
                    all_detections.extend(detections)
                except Exception as e:
                    print(f"[ERROR] Detection failed: {e}")
    else:
        # Sequential scanning
        for building_type in building_types:
            detections = detect_single_building_type(building_type, base_cv, threshold)
            all_detections.extend(detections)

    # Sort by confidence (highest first)
    all_detections.sort(key=lambda d: d[4], reverse=True)

    # Remove duplicates (positions too close)
    filtered = []
    for detection in all_detections:
        x, y, w, h, conf, btype, is_high = detection
        is_duplicate = False
        for existing in filtered:
            ex, ey, _, _, _, _, _ = existing
            distance = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if distance < 80:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append(detection)

    return filtered


def _detect_building_standalone(building_type, base_cv, templates_cache):
    """
    Standalone detection function that doesn't depend on main.py.
    Copied logic from main.py's detect_achievement_building_from_image.

    Returns list of (x, y, confidence) - coordinates are GLOBAL (screen coords).
    """
    if building_type not in templates_cache or not templates_cache[building_type]:
        return []

    templates_list = templates_cache[building_type]
    all_buildings = []

    print(f"  [{building_type}] Testing {len(templates_list)} templates...")

    for template, template_name in templates_list:
        # Use standard OpenCV template matching (CPU)
        result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)

        # Get max value for debug
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        threshold = 0.6
        locations = np.where(result >= threshold)

        num_matches = len(locations[0])
        if num_matches > 0 or max_val > 0.5:
            print(f"    {template_name}: max={max_val:.3f}, matches>0.6: {num_matches}")

        for pt in zip(*locations[::-1]):
            x, y = int(pt[0]), int(pt[1])
            # Convert to global screen coordinates
            global_x = x + config.BASE_VIEW_REGION[0]
            global_y = y + config.BASE_VIEW_REGION[1]
            confidence = float(result[y, x])
            all_buildings.append((global_x, global_y, confidence))

    # Sort by confidence
    all_buildings.sort(key=lambda b: b[2], reverse=True)

    # Remove duplicates
    filtered = []
    for building in all_buildings:
        x, y, conf = building
        is_dup = False
        for ex, ey, _ in filtered:
            dist = ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            if dist < 80:
                is_dup = True
                break
        if not is_dup:
            filtered.append(building)

    if filtered:
        print(f"  [{building_type}] Found {len(filtered)} buildings!")

    return filtered


def scan_achievement_buildings_overlay():
    """
    Single-scan mode for achievement buildings.
    Press F3 to scan once, results stay on screen.
    Press R to capture template at mouse position.
    Press ESC to exit.
    """
    from visualization_overlay import VisualizationOverlay

    print("\n" + "=" * 60)
    print("Achievement Building Scanner (SINGLE SCAN MODE)")
    print("=" * 60)
    print("Controls:")
    print("  F3  - Scan once (results stay on screen)")
    print("  R   - Capture template at mouse position")
    print("  ESC - Exit")
    print("")
    print("Colors: CYAN = high confidence, RED = low confidence")
    print("=" * 60)

    # Load templates
    print("\nLoading templates...")
    templates_cache = load_achievement_templates_local()

    total = sum(len(v) for v in templates_cache.values())
    print(f"Loaded {total} templates across {len([k for k,v in templates_cache.items() if v])} building types")

    building_types = list(templates_cache.keys())

    # Create overlay
    root = tk.Tk()
    root.withdraw()
    overlay = VisualizationOverlay(root)
    overlay.show()

    state = {'running': True, 'scan_requested': False, 'capture_requested': False}
    current_detections = []  # Store last scan results

    def on_f3():
        state['scan_requested'] = True
        print("\n[F3] Scan requested...")

    def on_esc():
        print("\n[EXIT]")
        state['running'] = False

    def on_r():
        state['capture_requested'] = True

    keyboard.add_hotkey('f3', on_f3, suppress=False)
    keyboard.add_hotkey('escape', on_esc, suppress=False)
    keyboard.add_hotkey('r', on_r, suppress=False)

    print("\nReady. Press F3 to scan once (results stay on screen)...")

    def do_single_scan():
        """Perform a single scan and display results."""
        nonlocal current_detections

        print("\n" + "=" * 40)
        print("SCANNING...")
        print("=" * 40)

        overlay.clear()

        # Capture screen
        base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
        base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

        print(f"Captured screen region: {config.BASE_VIEW_REGION}")
        print(f"Image size: {base_cv.shape}")

        # Parallel detection
        all_detections = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_detect_building_standalone, bt, base_cv, templates_cache): bt
                for bt in building_types
            }
            for future in as_completed(futures):
                building_type = futures[future]
                try:
                    results = future.result()
                    if results:
                        box_w, box_h = config.ACHIEVEMENT_BUILDING_SIZES.get(building_type, (70, 70))
                        threshold = config.ACHIEVEMENT_BUILDING_THRESHOLDS.get(building_type, 0.7)
                        for x, y, conf in results:
                            is_high = conf >= threshold
                            all_detections.append((x, y, box_w, box_h, conf, building_type, is_high))
                except Exception as e:
                    print(f"[ERROR] {building_type}: {e}")

        current_detections = all_detections

        # Draw results
        high_count = sum(1 for d in all_detections if d[6])
        low_count = len(all_detections) - high_count

        print("\n" + "=" * 40)
        print(f"SCAN COMPLETE: {high_count} high conf, {low_count} low conf")
        print("=" * 40)

        overlay.draw_text(410, 50,
            f"Scan done: {high_count} high, {low_count} low | F3=rescan R=capture ESC=quit",
            '#00FFFF')

        for x, y, w, h, conf, btype, is_high in all_detections:
            color = '#00FFFF' if is_high else '#FF0000'
            label = f"{btype.replace('_', ' ').title()[:12]} {conf:.2f}"
            overlay.draw_rect(x, y, w, h, color, label)
            print(f"  {btype}: ({x}, {y}) conf={conf:.3f} {'HIGH' if is_high else 'low'}")

        overlay.update()
        print("\nResults displayed. Press F3 to rescan, R to capture, ESC to exit.")

    def check_state():
        if not state['running']:
            keyboard.unhook_all_hotkeys()
            overlay.destroy()
            root.quit()
            return

        try:
            if state['scan_requested']:
                state['scan_requested'] = False
                do_single_scan()

            if state['capture_requested']:
                state['capture_requested'] = False
                capture_template_at_mouse()

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()

        if state['running']:
            root.after(100, check_state)

    root.after(100, check_state)

    try:
        root.mainloop()
    except:
        pass

    try:
        keyboard.unhook_all_hotkeys()
        overlay.destroy()
    except:
        pass

    print("Scanner closed.")


def capture_template_at_mouse():
    """
    Quick capture of a template at the current mouse position.
    Used during F3 scanning mode.
    """
    # Get mouse position
    x, y = pyautogui.position()

    # Check if mouse is within the base view region
    bvr = config.BASE_VIEW_REGION
    if not (bvr[0] <= x <= bvr[2] and bvr[1] <= y <= bvr[3]):
        print(f"[CAPTURE] Mouse position ({x}, {y}) is outside base view region")
        return

    print(f"\n[CAPTURE] Mouse at ({x}, {y})")

    # Building types menu
    building_types = {
        '1': 'eagle_artillery',
        '2': 'monolith',
        '3': 'xbow',
        '4': 'inferno_tower',
        '5': 'scattershot',
        '6': 'spell_tower',
        '7': 'multi_archer_tower',
        '8': 'ricochet_cannon',
        '9': 'firespitter',
        '10': 'multi_gear_tower'
    }

    # Template sizes
    template_sizes = {
        'eagle_artillery': (70, 70),
        'monolith': (55, 80),
        'xbow': (50, 50),
        'inferno_tower': (40, 80),
        'scattershot': (60, 60),
        'spell_tower': (40, 40),
        'multi_archer_tower': (40, 80),
        'ricochet_cannon': (50, 50),
        'firespitter': (50, 50),
        'multi_gear_tower': (40, 80)
    }

    print("Select building type:")
    print("1. Eagle Artillery  2. Monolith  3. X-Bow  4. Inferno Tower  5. Scattershot")
    print("6. Spell Tower  7. Multi-Archer Tower  8. Ricochet Cannon  9. Firespitter  10. Multi-Gear Tower")

    choice = input("Enter number (1-10): ").strip()

    if choice not in building_types:
        print(f"Invalid choice: {choice}")
        return

    building_type = building_types[choice]
    width, height = template_sizes[building_type]

    # Calculate capture region centered on mouse
    half_w = width // 2
    half_h = height // 2
    region = (x - half_w, y - half_h, x + half_w, y + half_h)

    # Capture
    template_img = ImageGrab.grab(bbox=region)
    enhanced_img = enhance_template_image(template_img)

    # Save with absolute path
    templates_dir = os.path.join(PROJECT_ROOT, "screenshots", "reference", "achievement_buildings", building_type)
    os.makedirs(templates_dir, exist_ok=True)

    timestamp = int(time.time())
    filename = f"{building_type}_{timestamp}.png"
    filepath = os.path.join(templates_dir, filename)

    enhanced_img.save(filepath)
    print(f"[SAVED] {filepath}")
    print(f"        Size: {enhanced_img.size[0]}x{enhanced_img.size[1]} pixels")

    # Reload templates to include the new one
    load_achievement_templates_local()

    # Show preview
    enhanced_img.show()


def test_achievement_building_matching():
    """
    Test achievement building template matching with existing templates.
    """
    print("Achievement Building Template Matching Test")
    print("===========================================")
    print("This will test how well your achievement building templates match.")

    input("Navigate to a base with visible achievement buildings and press Enter...")

    # Capture current screen
    print("Capturing current base view...")
    base_img = ImageGrab.grab(bbox=config.BASE_VIEW_REGION)
    base_cv = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    achievement_buildings_dir = "screenshots/reference/achievement_buildings"

    if not os.path.exists(achievement_buildings_dir):
        print(f"Achievement buildings directory not found: {achievement_buildings_dir}")
        return

    # Test each building type
    building_types = ['eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot']

    for building_type in building_types:
        building_dir = os.path.join(achievement_buildings_dir, building_type)

        if not os.path.exists(building_dir):
            print(f"\n{building_type.replace('_', ' ').title()}: No templates found")
            continue

        template_files = [f for f in os.listdir(building_dir)
                         if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not template_files:
            print(f"\n{building_type.replace('_', ' ').title()}: No templates found")
            continue

        print(f"\n{building_type.replace('_', ' ').title()} ({len(template_files)} templates):")

        best_match = None
        best_confidence = 0

        for template_file in template_files:
            template_path = os.path.join(building_dir, template_file)
            template = cv2.imread(template_path)

            if template is None:
                continue

            # Test matching
            result = cv2.matchTemplate(base_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            print(f"  {template_file}: Max confidence = {max_val:.3f}")

            if max_val > best_confidence:
                best_confidence = max_val
                best_match = (template_file, max_val, max_loc)

        if best_match and best_confidence >= 0.7:
            template_file, conf, pos = best_match
            print(f"  >>> Best match: {template_file} - Confidence: {conf:.3f} at position {pos}")
        else:
            print(f"  No strong matches found (threshold: 0.7)")

    print("\nTest complete!")


if __name__ == "__main__":
    print("Template Capture Main Menu")
    print("==========================")
    print("1. Capture Air Defense Templates")
    print("2. Capture Town Hall Templates")
    print("3. Capture Attack Templates")
    print("4. Capture Wall Templates")
    print("5. Capture Air Sweeper Templates")
    print("6. Capture Achievement Building Templates (Eagle/Monolith/X-Bow/Inferno/Scattershot)")
    print("7. Visual Test Air Defense Detection")
    print("8. Achievement Building Scanner (F3 Mode) - Live detection overlay")
    print("Q. Quit")
    choice = input("Choose an option: ").strip().lower()
    if choice == '1':
        capture_air_defense_template()
    elif choice == '2':
        capture_town_hall_templates()
    elif choice == '3':
        capture_attack_templates()
    elif choice == '4':
        capture_wall_templates()
    elif choice == '5':
        capture_air_sweeper_template()
    elif choice == '6':
        capture_achievement_building_templates()
    elif choice == '7':
        visual_test_template_matching()
    elif choice == '8':
        scan_achievement_buildings_overlay()
    else:
        print("Exiting...") 