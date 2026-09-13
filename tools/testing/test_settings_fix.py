#!/usr/bin/env python3
"""
Test script to verify the settings popup fix.
This script simulates the Discord controller updating settings to test if the infinite popup issue is resolved.
"""

import json
import time
import os

def test_settings_update():
    """Test updating settings via file to simulate Discord controller"""
    print("Testing settings popup fix...")
    
    # Create initial settings
    initial_settings = {
        'min_resources': 2000000,
        'max_th_level': 13,
        'edrag_count': 9,
        'balloon_count': 2,
        'auto_pause_enabled': False,
        'break_interval': 45,
        'break_duration': 5,
        'lightning_damage': 580,
        'reinforcements_enabled': True,
        'ad_target_mode': 'level',
        'attack_side_mode': 'th_side',
        'auto_wall_upgrade_enabled': True,
        'current_profile': 'Farming',
        'discord_running': False,
        'discord_paused': True
    }
    
    # Save initial settings
    with open('bot_settings.json', 'w', encoding='utf-8') as f:
        json.dump(initial_settings, f, indent=2)
    
    print("Initial settings saved")
    print("Starting main bot to test...")
    print("The bot should now start without infinite popups when settings are changed via Discord.")
    print("You can test by:")
    print("1. Starting the Discord controller")
    print("2. Using !set max_th_level 15 in Discord")
    print("3. The GUI should update without showing popups")
    print("4. Manual saves via 'Save Settings' button should still show popups")
    
    # Simulate a few setting updates
    for i in range(3):
        time.sleep(2)
        print(f"\nSimulating Discord setting update {i+1}...")
        
        # Update a setting
        updated_settings = initial_settings.copy()
        updated_settings['max_th_level'] = 13 + i
        updated_settings['min_resources'] = 2000000 + (i * 500000)
        
        with open('bot_settings.json', 'w', encoding='utf-8') as f:
            json.dump(updated_settings, f, indent=2)
        
        print(f"Updated max_th_level to {13 + i}, min_resources to {2000000 + (i * 500000)}")
        print("Check if the GUI updates without popups...")
    
    print("\nTest completed!")
    print("If you didn't see infinite popups, the fix is working correctly.")

if __name__ == "__main__":
    test_settings_update() 