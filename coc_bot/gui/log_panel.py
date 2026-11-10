"""Log, debug and OCR message panels, including stdout capture."""

import tkinter as tk
from datetime import datetime

class LogPanelMixin:
    """Log, debug and OCR message panels, including stdout capture. Mixin for BotGUI."""

    def log_message(self, message, level="info"):
        """Add message to log with timestamp and broadcast to web GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # Broadcast to web GUI
        if self.state_manager:
            self.state_manager.set("log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": level
            })

    def clear_log(self):
        """Clear the bot log text area"""
        self.log_text.delete(1.0, tk.END)

    def clear_debug_log(self):
        """Clear the debug log text area"""
        self.debug_text.delete(1.0, tk.END)

    def debug_message(self, message, level="debug"):
        """Add message to debug log with timestamp and broadcast to web GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        debug_entry = f"[{timestamp}] {message}\n"
        self.debug_text.insert(tk.END, debug_entry)
        self.debug_text.see(tk.END)

        # Broadcast to web GUI
        if self.state_manager:
            self.state_manager.set("debug_log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": level
            })

    def ocr_log(self, ocr_type, value, raw_value=None, confidence=None):
        """Log OCR reading to web GUI only (not to Tkinter to avoid spam)"""
        if self.state_manager:
            message = f"{ocr_type}: {value}"
            if raw_value is not None and raw_value != value:
                message += f" (raw: {raw_value})"
            if confidence is not None:
                message += f" [{confidence:.0f}%]"

            self.state_manager.set("ocr_log", {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "level": "info",
                "ocr_type": ocr_type,
                "value": value,
                "raw_value": raw_value,
                "confidence": confidence
            })

    def capture_console_output(self):
        """Capture console output and redirect to debug log"""
        import sys
        
        class ConsoleCapture:
            def __init__(self, gui):
                self.gui = gui
                self.original_stdout = sys.stdout
                self.original_stderr = sys.stderr
                
            def write(self, text):
                # Write to original console
                self.original_stdout.write(text)
                self.original_stdout.flush()
                
                # Also write to GUI debug log
                if text.strip():  # Only log non-empty lines
                    self.gui.root.after(0, lambda: self.gui.debug_message(text.strip()))
                    
            def flush(self):
                self.original_stdout.flush()

            def isatty(self):
                """Required for uvicorn logging compatibility."""
                return False

        # Set up console capture
        self.console_capture = ConsoleCapture(self)
        sys.stdout = self.console_capture
        sys.stderr = self.console_capture
