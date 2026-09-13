# test_storage_reading_gui.py
"""
GUI test tool for storage reading with improved OCR.
Click button to read all storages (Main Base + Builder Base).
No screenshots saved - results print to console.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk

# Add parent directory to path to import main and config
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# CRITICAL: Change working directory to parent so relative paths work
os.chdir(parent_dir)
print(f"[INIT] Working directory: {os.getcwd()}")

# Verify template directories exist
template_base = os.path.join('Reference Screenshots', 'digits')
if os.path.exists(template_base):
    print(f"[INIT] ✓ Template directory found: {template_base}")
    contexts = os.listdir(template_base)
    print(f"[INIT] Available contexts: {contexts}")
else:
    print(f"[INIT] ✗ Template directory NOT FOUND: {template_base}")

import time
import config
from PIL import ImageGrab
import pytesseract
import numpy as np
import cv2

# Set tesseract path
pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


def non_max_suppression(boxes, probs=None, overlapThresh=0.3):
    """Non-maximum suppression for bounding boxes."""
    if len(boxes) == 0:
        return []

    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")

    pick = []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = y2

    if probs is not None:
        idxs = probs

    idxs = np.argsort(idxs)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        overlap = (w * h) / area[idxs[:last]]

        idxs = np.delete(idxs, np.concatenate(([last],
            np.where(overlap > overlapThresh)[0])))

    return boxes[pick].astype("int")


def ocr_attack_resource_template_digits(img, debug=False, context='base_screen'):
    """
    IMPROVED OCR with zero detection fixes:
    - Lower threshold for '0' digit
    - Stricter NMS to prevent merging adjacent zeros
    - Tesseract fallback for suspiciously small numbers
    """
    try:
        if context is None:
            raise ValueError("Context must be specified")

        # 1. Load & binarize templates
        templates = {}
        digits_dir = os.path.join('Reference Screenshots', 'digits', context)
        if not os.path.exists(digits_dir):
            if debug:
                print(f"    [OCR] Context dir not found: {digits_dir}, trying fallback...")
            digits_dir = os.path.join('Reference Screenshots', 'digits', 'base_screen')
            if not os.path.exists(digits_dir):
                if debug:
                    print(f"    [OCR] Fallback dir not found: {digits_dir}")
                return 0

        if debug:
            print(f"    [OCR] Loading templates from: {digits_dir}")

        for digit in range(10):
            tpl_path = os.path.join(digits_dir, f'{digit}.png')
            tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                if debug:
                    print(f"    [OCR] Failed to load: {tpl_path}")
                continue
            _, tpl_bin = cv2.threshold(tpl, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            templates[digit] = tpl_bin

        if debug:
            print(f"    [OCR] Loaded {len(templates)} digit templates")

        if not templates:
            if debug:
                print(f"    [OCR] No templates loaded!")
            return 0

        # 2. Convert input to OpenCV binary
        img_np = np.array(img.convert('RGB'))
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

        # 3. Template matching with balanced threshold for thick-outlined digits
        detections = []
        if context in ('base_screen', 'base_dark_elixir', 'bb_base_screen'):
            base_threshold = 0.68  # Middle ground: not too strict, not too lenient
        else:
            base_threshold = 0.72

        for digit, tpl in templates.items():
            # Slightly lower for commonly missed digits (0, 4, 7)
            if digit in (0, 4, 7):
                match_threshold = base_threshold - 0.03
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
            return 0

        # 4. Non-Max Suppression tuned for thick-outlined digits with grouping
        # Overlap threshold of 0.2 (20%) - filters false positives while keeping adjacent digits
        boxes = np.array([d[:4] for d in detections])
        scores = np.array([d[4] for d in detections])
        keep_boxes = non_max_suppression(boxes, probs=scores, overlapThresh=0.2)

        if len(keep_boxes) == 0:
            return 0

        # 5. Pick best digit per kept box
        final = []
        for (x1, y1, x2, y2) in keep_boxes:
            cands = [(scr, dig) for (bx1, by1, bx2, by2, scr, dig) in detections
                     if bx1 == x1 and by1 == y1 and bx2 == x2 and by2 == y2]
            if not cands:
                continue
            best_score, best_digit = max(cands, key=lambda x: x[0])
            final.append((x1, best_digit))

        # 6. Sort left-to-right
        final = sorted(final, key=lambda x: x[0])
        result = ''.join(str(d) for _, d in final)

        if result.isdigit():
            value = int(result)

            # Tesseract fallback for suspiciously small numbers
            if context in ('base_screen', 'bb_base_screen') and value > 0 and value < 10000 and len(result) < 5:
                try:
                    tesseract_result = pytesseract.image_to_string(
                        img.convert('L'),
                        config='--psm 7 -c tessedit_char_whitelist=0123456789'
                    )
                    tesseract_cleaned = ''.join(ch for ch in tesseract_result if ch.isdigit())

                    if tesseract_cleaned and tesseract_cleaned.isdigit():
                        tesseract_value = int(tesseract_cleaned)
                        if tesseract_value > value * 10:
                            print(f"    [Tesseract fallback: {value} → {tesseract_value}]")
                            return tesseract_value
                except:
                    pass

            return value
        else:
            return 0

    except Exception as e:
        if debug:
            print(f"[OCR Error] {e}")
        return 0


def read_all_storages(text_widget, max_gold, max_elixir, max_de, max_bb_gold, max_bb_elixir):
    """Read all storages and print results"""
    text_widget.delete('1.0', tk.END)

    def log(msg=""):
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
        text_widget.update()

    log("="*70)
    log("READING ALL STORAGES")
    log("="*70)
    log()

    # MAIN BASE STORAGES
    log("=== MAIN BASE ===")
    log("Reading in 2 seconds... (make sure you're at main base home screen)")
    time.sleep(2)

    try:
        # Read gold
        log("  📊 Reading Gold...")
        base_gold_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
        gold_absolute = ocr_attack_resource_template_digits(base_gold_img, debug=True, context='base_screen')
        gold_percent = min(100, int((gold_absolute / max_gold) * 100)) if max_gold > 0 else 0
        log(f"    Gold: {gold_absolute:,} ({gold_percent}%)")

        # Read elixir
        log("  📊 Reading Elixir...")
        base_elixir_img = ImageGrab.grab(bbox=config.BASE_ELIXIR_REGION)
        elixir_absolute = ocr_attack_resource_template_digits(base_elixir_img, debug=True, context='base_screen')
        elixir_percent = min(100, int((elixir_absolute / max_elixir) * 100)) if max_elixir > 0 else 0
        log(f"    Elixir: {elixir_absolute:,} ({elixir_percent}%)")

        # Read dark elixir
        log("  📊 Reading Dark Elixir...")
        if hasattr(config, 'BASE_DARK_ELIXIR_REGION'):
            base_dark_elixir_img = ImageGrab.grab(bbox=config.BASE_DARK_ELIXIR_REGION)
            de_absolute = ocr_attack_resource_template_digits(base_dark_elixir_img, debug=True, context='base_dark_elixir')
            de_percent = min(100, int((de_absolute / max_de) * 100)) if max_de > 0 else 0
            log(f"    Dark Elixir: {de_absolute:,} ({de_percent}%)")
        else:
            de_absolute = 0
            de_percent = 0
            log("    Dark Elixir: [Region not configured]")

        log()
        log("📋 Main Base Summary:")
        log(f"  Gold: {gold_absolute:,} / {max_gold:,} ({gold_percent}%)")
        log(f"  Elixir: {elixir_absolute:,} / {max_elixir:,} ({elixir_percent}%)")
        log(f"  Dark Elixir: {de_absolute:,} / {max_de:,} ({de_percent}%)")

        if gold_percent >= 100 and elixir_percent >= 100:
            log("  ✅ Main base storages FULL - Queue would switch to BB")
        else:
            log(f"  ⏳ Continue farming (need {100-gold_percent}% gold, {100-elixir_percent}% elixir)")

    except Exception as e:
        log(f"❌ ERROR reading main base: {e}")
        import traceback
        log(traceback.format_exc())

    log()
    log("="*70)
    log()

    # BUILDER BASE STORAGES
    log("=== BUILDER BASE ===")

    if not hasattr(config, 'BB_BASE_GOLD_REGION') or not hasattr(config, 'BB_BASE_ELIXIR_REGION'):
        log("⚠ BB storage regions not configured in config.py")
        log("="*70)
        return

    log("Switch to Builder Base, then press the button again")
    log("Reading BB storages in 2 seconds...")
    time.sleep(2)

    try:
        # Read BB gold
        log("  📊 Reading BB Gold...")
        bb_gold_img = ImageGrab.grab(bbox=config.BB_BASE_GOLD_REGION)
        bb_gold_absolute = ocr_attack_resource_template_digits(bb_gold_img, debug=True, context='bb_base_screen')
        bb_gold_percent = min(100, int((bb_gold_absolute / max_bb_gold) * 100)) if max_bb_gold > 0 else 0
        log(f"    BB Gold: {bb_gold_absolute:,} ({bb_gold_percent}%)")

        # Read BB elixir
        log("  📊 Reading BB Elixir...")
        bb_elixir_img = ImageGrab.grab(bbox=config.BB_BASE_ELIXIR_REGION)
        bb_elixir_absolute = ocr_attack_resource_template_digits(bb_elixir_img, debug=True, context='bb_base_screen')
        bb_elixir_percent = min(100, int((bb_elixir_absolute / max_bb_elixir) * 100)) if max_bb_elixir > 0 else 0
        log(f"    BB Elixir: {bb_elixir_absolute:,} ({bb_elixir_percent}%)")

        log()
        log("📋 Builder Base Summary:")
        log(f"  Gold: {bb_gold_absolute:,} / {max_bb_gold:,} ({bb_gold_percent}%)")
        log(f"  Elixir: {bb_elixir_absolute:,} / {max_bb_elixir:,} ({bb_elixir_percent}%)")

        if bb_gold_percent >= 100 and bb_elixir_percent >= 100:
            log("  ✅ BB storages FULL - Queue would complete")
        else:
            log(f"  ⏳ Continue BB farming (need {100-bb_gold_percent}% gold, {100-bb_elixir_percent}% elixir)")

    except Exception as e:
        log(f"❌ ERROR reading BB: {e}")
        import traceback
        log(traceback.format_exc())

    log()
    log("="*70)
    log("✅ DONE - No screenshots saved")
    log("="*70)


def main():
    """Create GUI window"""
    root = tk.Tk()
    root.title("Storage Reading Test Tool")
    root.geometry("800x600")

    # Settings frame
    settings_frame = ttk.LabelFrame(root, text="Max Storage Settings", padding="10")
    settings_frame.pack(padx=10, pady=10, fill='x')

    # Max storage entries
    ttk.Label(settings_frame, text="Max Gold:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
    max_gold_var = tk.StringVar(value="18000000")
    ttk.Entry(settings_frame, textvariable=max_gold_var, width=15).grid(row=0, column=1, padx=5, pady=2)

    ttk.Label(settings_frame, text="Max Elixir:").grid(row=0, column=2, sticky='w', padx=5, pady=2)
    max_elixir_var = tk.StringVar(value="14000000")
    ttk.Entry(settings_frame, textvariable=max_elixir_var, width=15).grid(row=0, column=3, padx=5, pady=2)

    ttk.Label(settings_frame, text="Max Dark Elixir:").grid(row=1, column=0, sticky='w', padx=5, pady=2)
    max_de_var = tk.StringVar(value="240000")
    ttk.Entry(settings_frame, textvariable=max_de_var, width=15).grid(row=1, column=1, padx=5, pady=2)

    ttk.Label(settings_frame, text="Max BB Gold:").grid(row=1, column=2, sticky='w', padx=5, pady=2)
    max_bb_gold_var = tk.StringVar(value="5000000")
    ttk.Entry(settings_frame, textvariable=max_bb_gold_var, width=15).grid(row=1, column=3, padx=5, pady=2)

    ttk.Label(settings_frame, text="Max BB Elixir:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
    max_bb_elixir_var = tk.StringVar(value="5000000")
    ttk.Entry(settings_frame, textvariable=max_bb_elixir_var, width=15).grid(row=2, column=1, padx=5, pady=2)

    # Read button
    def on_read_click():
        max_gold = int(max_gold_var.get())
        max_elixir = int(max_elixir_var.get())
        max_de = int(max_de_var.get())
        max_bb_gold = int(max_bb_gold_var.get())
        max_bb_elixir = int(max_bb_elixir_var.get())
        read_all_storages(text_widget, max_gold, max_elixir, max_de, max_bb_gold, max_bb_elixir)

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)

    read_button = ttk.Button(button_frame, text="📊 READ ALL STORAGES", command=on_read_click, width=30)
    read_button.pack()

    ttk.Label(button_frame, text="(Make sure you're at main base home screen)",
              font=('Arial', 9, 'italic')).pack(pady=5)

    # Results text area
    results_frame = ttk.LabelFrame(root, text="Results", padding="10")
    results_frame.pack(padx=10, pady=10, fill='both', expand=True)

    text_widget = tk.Text(results_frame, wrap='word', font=('Courier', 10))
    text_widget.pack(side='left', fill='both', expand=True)

    scrollbar = ttk.Scrollbar(results_frame, command=text_widget.yview)
    scrollbar.pack(side='right', fill='y')
    text_widget.config(yscrollcommand=scrollbar.set)

    # Initial message
    text_widget.insert('1.0', "Storage Reading Test Tool\n")
    text_widget.insert(tk.END, "="*70 + "\n\n")
    text_widget.insert(tk.END, "Features:\n")
    text_widget.insert(tk.END, "  ✅ Improved OCR with zero detection fixes\n")
    text_widget.insert(tk.END, "  ✅ Lower threshold for '0' digit detection\n")
    text_widget.insert(tk.END, "  ✅ Stricter NMS to prevent merging adjacent zeros\n")
    text_widget.insert(tk.END, "  ✅ Tesseract fallback for small numbers\n\n")
    text_widget.insert(tk.END, "Instructions:\n")
    text_widget.insert(tk.END, "  1. Adjust max storage values above if needed\n")
    text_widget.insert(tk.END, "  2. Open Clash of Clans at main base home screen\n")
    text_widget.insert(tk.END, "  3. Click 'READ ALL STORAGES' button\n")
    text_widget.insert(tk.END, "  4. Wait for results (no screenshots saved)\n\n")
    text_widget.insert(tk.END, "="*70 + "\n")
    text_widget.insert(tk.END, "Ready! Click the button when ready.\n")

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
