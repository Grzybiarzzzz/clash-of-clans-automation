"""
Debug OCR engines to see why they're returning 0.
Shows preprocessed images and OCR results for each engine.
"""

import sys
import os
# Add parent directory to path so we can import main modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PIL import ImageGrab, Image
import ocr_engines
import config
import time

# Create debug output directory
DEBUG_DIR = os.path.join('screenshots', 'debug')
os.makedirs(DEBUG_DIR, exist_ok=True)

print("=" * 60)
print("OCR ENGINE DEBUGGER - BASE RESOURCES")
print("=" * 60)
print("\nWaiting 3 seconds... Switch to your HOME BASE in Clash of Clans!")
print("(Make sure you're on your own base, not attack screen)")
time.sleep(3)

# Capture test image from BASE (not attack screen)
print("\nCapturing BASE gold region...")
test_img = ImageGrab.grab(bbox=config.BASE_GOLD_REGION)
output_path = os.path.join(DEBUG_DIR, "debug_original.png")
test_img.save(output_path)
print(f"✓ Saved: {output_path}")

print("\n" + "=" * 60)
print("PREPROCESSING TESTS")
print("=" * 60)

# Test each preprocessing method
preprocessors = [
    ("thin_digits", ocr_engines.preprocess_thin_digits),
    ("high_contrast", ocr_engines.preprocess_high_contrast),
    ("inverted", ocr_engines.preprocess_inverted),
    ("gaussian_blur", ocr_engines.preprocess_gaussian_blur),
    ("bilateral_filter", ocr_engines.preprocess_bilateral_filter),
]

for name, func in preprocessors:
    try:
        processed = func(test_img)
        output_path = os.path.join(DEBUG_DIR, f"debug_preprocess_{name}.png")
        processed.save(output_path)
        print(f"✓ {name:20} -> Saved {output_path}")
    except Exception as e:
        print(f"✗ {name:20} -> ERROR: {e}")

print("\n" + "=" * 60)
print("TESSERACT TESTS (with debug=True)")
print("=" * 60)

# Test Tesseract variants
tesseract_tests = [
    ("Tess-Thin", ocr_engines.ocr_tesseract_thin),
    ("Tess-Heavy", ocr_engines.ocr_tesseract_heavy),
    ("Tess-Invert", ocr_engines.ocr_tesseract_invert),
    ("Tess-Gauss", ocr_engines.ocr_tesseract_gauss),
    ("Tess-Bilat", ocr_engines.ocr_tesseract_bilat),
]

for name, func in tesseract_tests:
    print(f"\n{name}:")
    try:
        value, conf = func(test_img, debug=True)
        print(f"  Result: {value:,} (confidence: {conf:.2%})")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("NEURAL NETWORK TESTS (with debug=True)")
print("=" * 60)

print("\nEasyOCR:")
try:
    value, conf = ocr_engines.ocr_easyocr(test_img, debug=True)
    print(f"  Result: {value:,} (confidence: {conf:.2%})")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nPaddleOCR:")
try:
    value, conf = ocr_engines.ocr_paddleocr(test_img, debug=True)
    print(f"  Result: {value:,} (confidence: {conf:.2%})")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEMPLATE MATCHING TEST")
print("=" * 60)

print("\nTemplate Matching (for comparison):")
try:
    value, conf = ocr_engines.ocr_template_matching(test_img, context='base_screen', debug=True)
    print(f"  Result: {value:,} (confidence: {conf:.2%})")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
print("=" * 60)
print(f"\nDebug images saved to: {DEBUG_DIR}/")
print("Check the debug_*.png files to see what each preprocessing method produced.")
print("Compare the OCR results above to see which engines are working.")
