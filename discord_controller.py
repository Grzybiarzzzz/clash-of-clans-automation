import discord
from discord.ext import commands
import json
import os
import threading
import time
from datetime import datetime
import requests
import config

# Bot configuration
DISCORD_TOKEN = getattr(config, 'DISCORD_TOKEN', None)
AUTHORIZED_USERS = getattr(config, 'AUTHORIZED_USERS', [])
CONTROL_CHANNEL_ID = getattr(config, 'CONTROL_CHANNEL_ID', None)

# Global bot state
bot_state = {
    'running': False,
    'paused': True,
    'loop_count': 0,
    'start_time': None,
    'last_status': 'STOPPED'
}

# Settings that can be changed remotely
remote_settings = {
    'min_resources': 2000000,
    'max_th_level': 13,
    'edrag_count': 9,
    'balloon_count': 2,
    'auto_pause_enabled': False,
    'break_interval': 45,
    'break_duration': 5,
    'lightning_damage': 580,
    'reinforcements_enabled': True
}

# Create Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def is_authorized(ctx):
    """Check if user is authorized to control the bot"""
    return ctx.author.id in AUTHORIZED_USERS

def save_settings():
    """Save current settings to bot_settings.json"""
    try:
        # Load existing settings first
        existing_settings = {}
        if os.path.exists('data/bot_settings.json'):
            with open('data/bot_settings.json', 'r') as f:
                existing_settings = json.load(f)
        
        # Only update with remote settings if they were explicitly changed
        # Don't overwrite existing settings with defaults
        for key, value in remote_settings.items():
            if key not in existing_settings:
                existing_settings[key] = value
        
        # Add Discord control flags
        existing_settings['discord_running'] = bot_state['running']
        existing_settings['discord_paused'] = bot_state['paused']
        
        with open('data/bot_settings.json', 'w') as f:
            json.dump(existing_settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def save_single_setting(setting_name, value):
    """Save a single setting without affecting other settings"""
    try:
        # Load existing settings first
        existing_settings = {}
        if os.path.exists('data/bot_settings.json'):
            with open('data/bot_settings.json', 'r') as f:
                existing_settings = json.load(f)
        
        # Update only the specific setting
        existing_settings[setting_name] = value
        
        # Add Discord control flags (preserve existing ones)
        existing_settings['discord_running'] = bot_state['running']
        existing_settings['discord_paused'] = bot_state['paused']
        
        with open('data/bot_settings.json', 'w') as f:
            json.dump(existing_settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving setting: {e}")
        return False

def load_settings():
    """Load settings from bot_settings.json"""
    try:
        with open('data/bot_settings.json', 'r') as f:
            loaded_settings = json.load(f)
            # Only update remote settings with values that exist in the file
            # Don't overwrite our defaults with file values
            for key, value in loaded_settings.items():
                if key in remote_settings:
                    remote_settings[key] = value
        return True
    except Exception as e:
        print(f"Error loading settings: {e}")
        return False

def send_discord_debug_log(message, level="INFO"):
    """
    Send debug log to Discord channel.
    Levels: DEBUG, INFO, WARNING, ERROR
    """
    try:
        # Use the same webhook URL as the main bot
        webhook_url = getattr(config, 'DISCORD_WEBHOOK_URL', None)
        if not webhook_url:
            return
        
        # Add timestamp and format message
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # Send immediately for errors and warnings
        if level in ["ERROR", "WARNING"]:
            data = {"content": f"🚨 **{level}**: {message}"}
            requests.post(webhook_url, json=data)
            return
        
        # For info messages, send directly
        data = {"content": f"📊 **Debug**: {message}"}
        requests.post(webhook_url, json=data)
        
    except Exception as e:
        print(f"Error sending Discord debug log: {e}")

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f'{bot.user} has connected to Discord!')
    load_settings()
    
    # Send startup message to control channel
    if not isinstance(CONTROL_CHANNEL_ID, int):
        print(f"CONTROL_CHANNEL_ID is not set or not an integer: {CONTROL_CHANNEL_ID}")
        channel = None
    else:
        channel = bot.get_channel(CONTROL_CHANNEL_ID)
    if channel and isinstance(channel, discord.TextChannel):
        try:
            embed = discord.Embed(
                title="🤖 Clash of Clans Bot Controller",
                description="Bot is online and ready for commands!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Status", value="🟢 ONLINE", inline=True)
            embed.add_field(name="Bot State", value="⏸️ PAUSED", inline=True)
            embed.add_field(name="Commands", value="Use `!commands` to see available commands", inline=False)
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Could not send startup message to channel: {e}")
    else:
        print(f"Control channel not found or not accessible: {CONTROL_CHANNEL_ID}")

@bot.command(name='start')
async def start_bot(ctx):
    """Start the bot"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        send_discord_debug_log(f"Unauthorized start attempt by {ctx.author.name} ({ctx.author.id})", "WARNING")
        return
    
    if bot_state['running']:
        await ctx.send("⚠️ Bot is already running!")
        send_discord_debug_log(f"Start command ignored - bot already running by {ctx.author.name}", "WARNING")
        return
    
    bot_state['running'] = True
    bot_state['paused'] = False
    bot_state['start_time'] = time.time()
    bot_state['last_status'] = 'RUNNING'
    
    # Update bot_settings.json to signal the main bot
    save_settings()
    
    send_discord_debug_log(f"Bot started by {ctx.author.name}")
    
    embed = discord.Embed(
        title="🚀 Bot Started",
        description="The Clash of Clans bot is now running!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value="🟢 RUNNING", inline=True)
    embed.add_field(name="Start Time", value=datetime.now().strftime("%H:%M:%S"), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='stop')
async def stop_bot(ctx):
    """Stop the bot"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        send_discord_debug_log(f"Unauthorized stop attempt by {ctx.author.name} ({ctx.author.id})", "WARNING")
        return
    
    if not bot_state['running']:
        await ctx.send("⚠️ Bot is not running!")
        send_discord_debug_log(f"Stop command ignored - bot not running by {ctx.author.name}", "WARNING")
        return
    
    bot_state['running'] = False
    bot_state['paused'] = True
    bot_state['last_status'] = 'STOPPED'
    
    # Update bot_settings.json to signal the main bot
    save_settings()
    
    send_discord_debug_log(f"Bot stopped by {ctx.author.name}")
    
    embed = discord.Embed(
        title="⏹️ Bot Stopped",
        description="The Clash of Clans bot has been stopped.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value="🔴 STOPPED", inline=True)
    embed.add_field(name="Total Loops", value=str(bot_state['loop_count']), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='pause')
async def pause_bot(ctx):
    """Pause the bot"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        send_discord_debug_log(f"Unauthorized pause attempt by {ctx.author.name} ({ctx.author.id})", "WARNING")
        return
    
    if not bot_state['running']:
        await ctx.send("⚠️ Bot is not running!")
        send_discord_debug_log(f"Pause command ignored - bot not running by {ctx.author.name}", "WARNING")
        return
    
    if bot_state['paused']:
        await ctx.send("⚠️ Bot is already paused!")
        send_discord_debug_log(f"Pause command ignored - bot already paused by {ctx.author.name}", "WARNING")
        return
    
    bot_state['paused'] = True
    bot_state['last_status'] = 'PAUSED'
    
    # Update bot_settings.json to signal the main bot
    save_settings()
    
    send_discord_debug_log(f"Bot paused by {ctx.author.name}")
    
    embed = discord.Embed(
        title="⏸️ Bot Paused",
        description="The Clash of Clans bot has been paused.",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value="🟡 PAUSED", inline=True)
    embed.add_field(name="Loops Completed", value=str(bot_state['loop_count']), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='resume')
async def resume_bot(ctx):
    """Resume the bot"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        send_discord_debug_log(f"Unauthorized resume attempt by {ctx.author.name} ({ctx.author.id})", "WARNING")
        return
    
    if not bot_state['running']:
        await ctx.send("⚠️ Bot is not running! Use `!start` to start it.")
        send_discord_debug_log(f"Resume command ignored - bot not running by {ctx.author.name}", "WARNING")
        return
    
    if not bot_state['paused']:
        await ctx.send("⚠️ Bot is not paused!")
        send_discord_debug_log(f"Resume command ignored - bot not paused by {ctx.author.name}", "WARNING")
        return
    
    bot_state['paused'] = False
    bot_state['last_status'] = 'RUNNING'
    
    # Update bot_settings.json to signal the main bot
    save_settings()
    
    send_discord_debug_log(f"Bot resumed by {ctx.author.name}")
    
    embed = discord.Embed(
        title="▶️ Bot Resumed",
        description="The Clash of Clans bot has been resumed.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value="🟢 RUNNING", inline=True)
    embed.add_field(name="Loops Completed", value=str(bot_state['loop_count']), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='status')
async def bot_status(ctx):
    """Get current bot status"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        return
    
    # Calculate running time
    running_time = "00:00:00"
    if bot_state['start_time']:
        elapsed = time.time() - bot_state['start_time']
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        running_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Calculate loops per hour
    loops_per_hour = 0
    if bot_state['start_time'] and elapsed > 0:
        loops_per_hour = (bot_state['loop_count'] / elapsed) * 3600
    
    embed = discord.Embed(
        title="📊 Bot Status",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    status_emoji = "🟢" if bot_state['last_status'] == 'RUNNING' else "🟡" if bot_state['last_status'] == 'PAUSED' else "🔴"
    embed.add_field(name="Status", value=f"{status_emoji} {bot_state['last_status']}", inline=True)
    embed.add_field(name="Loops Completed", value=str(bot_state['loop_count']), inline=True)
    embed.add_field(name="Running Time", value=running_time, inline=True)
    embed.add_field(name="Loops/Hour", value=f"{loops_per_hour:.1f}", inline=True)
    embed.add_field(name="Start Time", value=datetime.fromtimestamp(bot_state['start_time']).strftime("%H:%M:%S") if bot_state['start_time'] else "N/A", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='settings')
async def show_settings(ctx):
    """Show current bot settings"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        return
    
    embed = discord.Embed(
        title="⚙️ Current Settings",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for key, value in remote_settings.items():
        embed.add_field(name=key.replace('_', ' ').title(), value=str(value), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='set')
async def set_setting(ctx, setting_name: str, value):
    """Set a bot setting"""
    if not is_authorized(ctx):
        await ctx.send("❌ You are not authorized to control this bot.")
        send_discord_debug_log(f"Unauthorized setting change attempt by {ctx.author.name} ({ctx.author.id})", "WARNING")
        return
    
    if setting_name not in remote_settings:
        await ctx.send(f"❌ Unknown setting: {setting_name}")
        send_discord_debug_log(f"Unknown setting '{setting_name}' attempted by {ctx.author.name}", "WARNING")
        return
    
    try:
        # Convert value to appropriate type
        if isinstance(remote_settings[setting_name], bool):
            remote_settings[setting_name] = value.lower() in ['true', '1', 'yes', 'on']
        elif isinstance(remote_settings[setting_name], int):
            remote_settings[setting_name] = int(value)
        else:
            remote_settings[setting_name] = value
        
        # Save to file using single setting save to avoid overwriting other settings
        if save_single_setting(setting_name, remote_settings[setting_name]):
            send_discord_debug_log(f"Setting '{setting_name}' changed to '{value}' by {ctx.author.name}")
            embed = discord.Embed(
                title="✅ Setting Updated",
                description=f"**{setting_name}** has been set to **{value}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to save setting to file.")
            send_discord_debug_log(f"Failed to save setting '{setting_name}' to file", "ERROR")
            
    except ValueError:
        await ctx.send(f"❌ Invalid value for {setting_name}. Expected {type(remote_settings[setting_name]).__name__}.")
        send_discord_debug_log(f"Invalid value '{value}' for setting '{setting_name}' by {ctx.author.name}", "WARNING")

@bot.command(name='commands')
async def show_commands(ctx):
    """Show available commands"""
    embed = discord.Embed(
        title="🤖 Bot Control Commands",
        description="Available commands to control the Clash of Clans bot:",
        color=discord.Color.blue()
    )
    
    commands_info = [
        ("!start", "Start the bot"),
        ("!stop", "Stop the bot"),
        ("!pause", "Pause the bot"),
        ("!resume", "Resume the bot"),
        ("!status", "Show current bot status"),
        ("!settings", "Show current settings"),
        ("!set <setting> <value>", "Change a setting (e.g., !set min_resources 3000000)"),
        ("!commands", "Show this help message")
    ]
    
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.add_field(name="Settings", value="min_resources, max_th_level, edrag_count, balloon_count, auto_pause_enabled, break_interval, break_duration, lightning_damage, reinforcements_enabled", inline=False)
    
    await ctx.send(embed=embed)

def run_discord_bot():
    """Run the Discord bot"""
    if not isinstance(DISCORD_TOKEN, str) or not DISCORD_TOKEN.strip():
        print("❌ DISCORD_TOKEN is not set or not a valid string in private_config.py.")
        return
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Failed to start Discord bot: {e}")

if __name__ == "__main__":
    print("Starting Discord bot controller...")
    run_discord_bot() 