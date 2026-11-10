"""
Quick test script for multi-engine OCR system.
Tests if Discord logging works.
"""

import sys
import os
# Add parent directory to path so we can import main modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PIL import ImageGrab
import ocr_engines
import ocr_voting
import config

# Grab a test screenshot (adjust coordinates to capture some numbers on your screen)
print("Capturing test screenshot in 3 seconds...")
print("Make sure Clash of Clans is open with a base visible!")
import time
time.sleep(3)

# Test with gold region (change to any region with numbers)
test_img = ImageGrab.grab(bbox=config.GOLD_REGION)

print("\nRunning all OCR engines...")
ocr_results = ocr_engines.run_all_ocr_engines(test_img, context='attack_screen_gold', debug=True)

print("\n" + "="*50)
print("OCR Results:")
for engine, (value, conf) in ocr_results.items():
    print(f"{engine:15} -> {value:8,} (confidence: {conf:.2%})")

print("\n" + "="*50)
print("Getting consensus...")
consensus_value, confidence, has_consensus, vote_details = ocr_voting.get_consensus(
    ocr_results, context='attack_screen_gold', debug=True
)

if has_consensus:
    print(f"\n✅ CONSENSUS: {consensus_value:,} (confidence: {confidence:.2%})")
else:
    print(f"\n❌ NO CONSENSUS")

print("\n" + "="*50)
print("Formatted Discord message:")
formatted = ocr_voting.format_vote_details_for_discord(
    ocr_results, consensus_value, confidence, has_consensus, vote_details, 'attack_screen_gold'
)
print(formatted)

print("\n" + "="*50)
# Test Discord webhook
try:
    from coc_bot.discord_log import send_discord_ocr_log
    print("Sending to Discord...")
    send_discord_ocr_log(formatted)
    print("✅ Sent to Discord! Check your webhook channel.")
except Exception as e:
    print(f"❌ Discord send failed: {e}")
    print("Check that DISCORD_OCR_WEBHOOK_URL is set in config.py")
