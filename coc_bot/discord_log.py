"""Discord webhook notifications and buffered debug logging."""

import time

import requests

import config

# Debug logging configuration
DEBUG_LOG_ENABLED = getattr(config, "DEBUG_LOG_ENABLED", True)
DEBUG_LOG_INTERVAL = getattr(config, "DEBUG_LOG_INTERVAL", 5)  # Send debug logs every 30 seconds
DEBUG_LOG_LEVEL = getattr(config, "DEBUG_LOG_LEVEL", "INFO")
last_debug_log = 0
debug_log_buffer = []


# Helper functions
def send_discord_ocr_log(message):
    """
    Send an OCR read log to a dedicated Discord channel using a webhook URL.
    Set your webhook URL in DISCORD_OCR_WEBHOOK_URL in config.py.
    """
    import config

    webhook_url = getattr(config, "DISCORD_OCR_WEBHOOK_URL", None)
    if not webhook_url:
        print("No Discord OCR webhook URL set in config.py (DISCORD_OCR_WEBHOOK_URL)")
        return
    # Format numbers in the message with dots as thousands separators
    import re

    def format_number(match):
        num = int(match.group(0))
        return f"{num:,}".replace(",", ".")

    formatted_message = re.sub(r"(?<![\w.])\d{4,}(?![\w.])", format_number, str(message))
    data = {"content": formatted_message}
    try:
        # Add 5-second timeout to prevent hanging
        response = requests.post(webhook_url, json=data, timeout=5)
        # Success is silent, only report failures
        if response.status_code != 204:
            print(f"[Discord OCR] Warning: Failed with status {response.status_code}")
    except Exception as e:
        print(f"[Discord OCR] Warning: {type(e).__name__} - {e}")


def send_discord_notification(message):
    """
    Send a notification to a Discord channel using a webhook URL with robust error handling.
    Set your webhook URL in DISCORD_WEBHOOK_URL in config.py.
    Bot continues running even if Discord is unreachable.
    """
    import config

    # Check if Discord logging is enabled
    if not getattr(config, "DEBUG_LOG_ENABLED", True):
        return

    webhook_url = getattr(config, "DISCORD_WEBHOOK_URL", None)
    if not webhook_url:
        return  # Silently skip if no webhook configured

    data = {"content": message}

    try:
        # Add 5-second timeout to prevent hanging
        response = requests.post(webhook_url, json=data, timeout=5)
        if response.status_code != 204:
            print(f"[Discord] Warning: Message failed with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        # Catch all network errors: DNS failures, timeouts, connection errors
        print(f"[Discord] Warning: Could not send message - {type(e).__name__}")
        # Bot continues running - Discord failure doesn't stop execution
    except Exception as e:
        # Catch any other unexpected errors
        print(f"[Discord] Warning: Unexpected error - {e}")


def send_discord_debug_log(message, level="INFO"):
    """
    Send debug log to Discord channel.
    Levels: DEBUG, INFO, WARNING, ERROR
    """
    global debug_log_buffer, last_debug_log

    if not DEBUG_LOG_ENABLED:
        return

    # Check if level meets minimum threshold
    level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_priority = level_priority.get(DEBUG_LOG_LEVEL, 1)
    current_priority = level_priority.get(level, 1)

    if current_priority < min_priority:
        return

    # Add timestamp and format message
    timestamp = time.strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] [{level}] {message}"

    # Add to buffer
    debug_log_buffer.append(formatted_message)

    # Send immediately for errors and warnings
    if level in ["ERROR", "WARNING"]:
        send_discord_notification(f"🚨 **{level}**: {message}")
        return

    # Send buffered logs periodically
    current_time = time.time()
    if current_time - last_debug_log >= DEBUG_LOG_INTERVAL and debug_log_buffer:
        # Combine multiple messages
        combined_message = "📊 **Debug Log Update:**\n" + "\n".join(debug_log_buffer[-10:])  # Last 10 messages
        send_discord_notification(combined_message)
        debug_log_buffer.clear()
        last_debug_log = current_time
