#!/usr/bin/env python3
"""
Test script for Discord debug logging functionality.
This script demonstrates how the debug logging system works.
"""

import sys
import os

# Add project root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import requests
from datetime import datetime
import config

# Discord webhook URL (same as in config.py)
DISCORD_WEBHOOK_URL = getattr(config, 'DISCORD_WEBHOOK_URL', None)

def send_discord_notification(message):
    """Send a notification to Discord channel"""
    try:
        data = {"content": message}
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print(f"✅ Discord notification sent: {message}")
        else:
            print(f"❌ Failed to send Discord notification: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Error sending Discord notification: {e}")

def test_debug_logging():
    """Test different types of debug logs"""
    print("🧪 Testing Discord Debug Logging System")
    print("=" * 50)
    
    # Test different log levels
    test_messages = [
        ("DEBUG", "This is a debug message - detailed technical info"),
        ("INFO", "This is an info message - general status update"),
        ("WARNING", "This is a warning message - something to watch out for"),
        ("ERROR", "This is an error message - something went wrong")
    ]
    
    for level, message in test_messages:
        print(f"\n📤 Sending {level} level message...")
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"🧪 **TEST {level}**: {message}"
        send_discord_notification(formatted_message)
        time.sleep(1)  # Small delay between messages
    
    # Test buffered logging simulation
    print(f"\n📤 Sending buffered debug log update...")
    buffered_messages = [
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Resource OCR: Gold 2,450,000, Elixir 1,800,000",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Sufficient resources found: 4,250,000 >= 2,000,000",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Air defense detection completed: 4 defenses found",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Base selected for attack: 4 air defenses, 4,250,000 resources",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Attack side chosen: left (TH-based)",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Deploying lightning spells on 4 air defenses",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Moving camera to left side",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Deployed 9 Electro Dragons",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Deployed 2 Balloons",
        f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Hero abilities activated"
    ]
    
    combined_message = "📊 **Debug Log Update:**\n" + "\n".join(buffered_messages)
    send_discord_notification(combined_message)
    
    print("\n✅ Debug logging test completed!")
    print("\n📋 What you should see in Discord:")
    print("   • Individual test messages for each log level")
    print("   • A buffered log update with multiple messages")
    print("   • Different emojis and formatting for different message types")
    print("\n🔧 To configure debug logging in the main bot:")
    print("   • Edit config.py to set DEBUG_LOG_ENABLED = True/False")
    print("   • Adjust DEBUG_LOG_INTERVAL for buffering frequency")
    print("   • Set DEBUG_LOG_LEVEL to control which messages are sent")

if __name__ == "__main__":
    test_debug_logging() 