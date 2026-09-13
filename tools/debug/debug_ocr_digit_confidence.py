import sys
import os

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import keyboard
import config
from PIL import ImageGrab
import numpy as np
import cv2
from imutils.object_detection import non_max_suppression

# Copy of the digit OCR logic, but prints all digit match confidences

def debug_ocr_digits(img, context):
    """
    For a given image and context, print all digit match confidences found by template matching, sorted left-to-right, with NMS to remove duplicates.
    """
    templates = {}
    digits_dir = os.path.join('Reference Screenshots', 'digits', context)
    if not os.path.exists(digits_dir):
        print(f"[Template OCR] Context directory not found: {digits_dir}")
        return
    for digit in range(10):
        tpl_path = os.path.join(digits_dir, f'{digit}.png')
        tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            continue
        _, tpl_bin = cv2.threshold(
            tpl, 0, 255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
        )
        templates[digit] = tpl_bin
    if not templates:
        print(f"[Template OCR] No templates loaded for context: {context}")
        return
    img_np = np.array(img.convert('RGB'))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    print(f"\n--- OCR Debug for context: {context} ---")
    detections = []
    for digit, tpl in templates.items():
        tpl_h, tpl_w = tpl.shape
        score_map = cv2.matchTemplate(thresh, tpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(score_map >= 0.7)
        for (y, x) in zip(ys, xs):
            score = float(score_map[y, x])
            x1, y1 = x, y
            x2, y2 = x + tpl_w, y + tpl_h
            detections.append((x1, y1, x2, y2, score, digit))
    if not detections:
        print("No digit matches found.")
        return
    # Apply NMS
    boxes = np.array([d[:4] for d in detections])
    scores = np.array([d[4] for d in detections])
    keep_boxes = non_max_suppression(boxes, probs=scores, overlapThresh=0.3)
    # For each kept box, print the best digit and its confidence
    final = []
    for (x1, y1, x2, y2) in keep_boxes:
        cands = [
            (scr, dig, x1) for (bx1, by1, bx2, by2, scr, dig) in detections
            if bx1 == x1 and by1 == y1 and bx2 == x2 and by2 == y2
        ]
        if not cands:
            continue
        best_score, best_digit, x = max(cands, key=lambda x: x[0])
        final.append((x, best_digit, best_score, y1))
    # Sort left-to-right
    final.sort(key=lambda t: t[0])
    for x, digit, score, y in final:
        print(f"Digit {digit} at (x={x}, y={y}) - Confidence: {score:.3f}")

if __name__ == "__main__":
    print("Press F2 to capture and debug OCR for base resources...")
    keyboard.wait('f2')
    print("Capturing base resource regions...")
    gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
    elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
    dark_img = None
    if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
        dark_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
    debug_ocr_digits(gold_img, 'base_screen')
    debug_ocr_digits(elixir_img, 'base_screen')
    if dark_img:
        debug_ocr_digits(dark_img, 'base_dark_elixir')
    print("Done.") 