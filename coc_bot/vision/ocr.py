"""OCR of resources, troop counts and destruction percentage."""

import os
import time

import cv2
import numpy as np
import pytesseract
from imutils.object_detection import non_max_suppression
from PIL import Image, ImageGrab

import config
from coc_bot import runtime
from coc_bot.discord_log import send_discord_debug_log, send_discord_ocr_log
from coc_bot.overlay import overlay_clear, overlay_draw_ocr
from coc_bot.profiles import auto_switch_profile_if_needed

# Add a debug flag for attack OCR at the top
ATTACK_OCR_DEBUG = False


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
        runtime.gui.ocr_log("Resources", value, raw_value=cleaned)
        return value
    except ValueError:
        send_discord_ocr_log(f"OCR: ValueError (ocr_resources)")
        runtime.gui.ocr_log("Resources", "ERROR", raw_value=cleaned)
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
                runtime.gui.log_message(f"[OCR FAILSAFE] Loot {k} value {loot[k]} > 4 million. Ignoring this value.")
                send_discord_debug_log(f"OCR failsafe: Loot {k} value {loot[k]} > 4 million, ignoring", "WARNING")
                send_discord_ocr_log(f"OCR: {loot[k]} (loot_{k}, loot_screen) > 4 million, set to 0")
                loot[k] = 0
        print(f"Loot captured - Gold: {loot['gold']:,}, Elixir: {loot['elixir']:,}, Dark Elixir: {loot['dark_elixir']:,}")
        runtime.gui.log_message(f"Loot: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}")
        send_discord_debug_log(f"Loot captured: Gold {loot['gold']:,}, Elixir {loot['elixir']:,}, Dark {loot['dark_elixir']:,}")
        debug_save_loot_ocr_regions()  # Automatically save loot OCR regions after battle
        return loot
    except Exception as e:
        print(f"Error capturing loot: {e}")
        runtime.gui.log_message(f"Error capturing loot: {e}")
        send_discord_debug_log(f"Error capturing loot: {e}", "ERROR")
        send_discord_ocr_log(f"OCR: Exception {e} (ocr_loot)")
        return loot


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
        runtime.gui.log_message("OCR region screenshots saved for debugging.")
    except Exception as e:
        print(f"Error saving OCR region screenshots: {e}")
        runtime.gui.log_message(f"Error saving OCR region screenshots: {e}")


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
        runtime.gui.log_message("Loot OCR region screenshots saved for debugging.")
    except Exception as e:
        print(f"Error saving loot OCR region screenshots: {e}")
        runtime.gui.log_message(f"Error saving loot OCR region screenshots: {e}")


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
                            runtime.gui.ocr_log(resource_label, tesseract_value, raw_value=f"template:{value}")
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
            runtime.gui.ocr_log(resource_label, value, raw_value=result, confidence=avg_conf)
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
