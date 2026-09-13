#!/usr/bin/env python3
"""
Test script to demonstrate Discord integration with the main bot.
This shows how Discord commands work with the main bot.
"""

import json
import time
import os

def simulate_discord_start():
    """Simulate a Discord start command"""
    print("🟢 Simulating Discord !start command...")
    
    # Load current settings
    settings = {}
    if os.path.exists('bot_settings.json'):
        with open('bot_settings.json', 'r') as f:
            settings = json.load(f)
    
    # Add Discord control flags
    settings['discord_running'] = True
    settings['discord_paused'] = False
    
    # Save back to file
    with open('bot_settings.json', 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Discord start command written to bot_settings.json")
    print("   The main bot should now start automatically!")

def simulate_discord_stop():
    """Simulate a Discord stop command"""
    print("🔴 Simulating Discord !stop command...")
    
    # Load current settings
    settings = {}
    if os.path.exists('bot_settings.json'):
        with open('bot_settings.json', 'r') as f:
            settings = json.load(f)
    
    # Add Discord control flags
    settings['discord_running'] = False
    settings['discord_paused'] = True
    
    # Save back to file
    with open('bot_settings.json', 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Discord stop command written to bot_settings.json")
    print("   The main bot should now stop automatically!")

def simulate_discord_pause():
    """Simulate a Discord pause command"""
    print("🟡 Simulating Discord !pause command...")
    
    # Load current settings
    settings = {}
    if os.path.exists('bot_settings.json'):
        with open('bot_settings.json', 'r') as f:
            settings = json.load(f)
    
    # Add Discord control flags
    settings['discord_running'] = True
    settings['discord_paused'] = True
    
    # Save back to file
    with open('bot_settings.json', 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Discord pause command written to bot_settings.json")
    print("   The main bot should now pause automatically!")

def simulate_discord_resume():
    """Simulate a Discord resume command"""
    print("🟢 Simulating Discord !resume command...")
    
    # Load current settings
    settings = {}
    if os.path.exists('bot_settings.json'):
        with open('bot_settings.json', 'r') as f:
            settings = json.load(f)
    
    # Add Discord control flags
    settings['discord_running'] = True
    settings['discord_paused'] = False
    
    # Save back to file
    with open('bot_settings.json', 'w') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Discord resume command written to bot_settings.json")
    print("   The main bot should now resume automatically!")

def show_current_settings():
    """Show current bot_settings.json contents"""
    print("\n📋 Current bot_settings.json contents:")
    if os.path.exists('bot_settings.json'):
        with open('bot_settings.json', 'r') as f:
            settings = json.load(f)
        
        for key, value in settings.items():
            if key in ['discord_running', 'discord_paused']:
                print(f"   {key}: {value} {'🟢' if value else '🔴'}")
            else:
                print(f"   {key}: {value}")
    else:
        print("   No bot_settings.json file found")

def main():
    print("🤖 Discord Integration Test")
    print("=" * 40)
    print("This script simulates Discord commands to test integration.")
    print("Make sure your main bot (main.py) is running!")
    print()
    
    while True:
        print("\nOptions:")
        print("1. Simulate Discord !start")
        print("2. Simulate Discord !stop") 
        print("3. Simulate Discord !pause")
        print("4. Simulate Discord !resume")
        print("5. Show current settings")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            simulate_discord_start()
        elif choice == '2':
            simulate_discord_stop()
        elif choice == '3':
            simulate_discord_pause()
        elif choice == '4':
            simulate_discord_resume()
        elif choice == '5':
            show_current_settings()
        elif choice == '6':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-6.")
        
        time.sleep(1)

if __name__ == "__main__":
    main() 