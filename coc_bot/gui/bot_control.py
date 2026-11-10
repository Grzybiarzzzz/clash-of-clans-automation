"""Start, stop and pause handling, timers and status labels."""

import threading
import time
from tkinter import messagebox

from coc_bot import runtime

class BotControlMixin:
    """Start, stop and pause handling, timers and status labels. Mixin for BotGUI."""

    def update_timer(self):
        """Update the running time display"""
        if self.start_time and not self.bot_paused:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_label.config(text=time_str)
            
            # Calculate loops per hour
            if elapsed > 0:
                loops_per_hour = (self.loop_count / elapsed) * 3600
                self.rate_label.config(text=f"{loops_per_hour:.1f}")
        
        # Schedule next update
        self.root.after(1000, self.update_timer)

    def start_bot(self):
        """Start the bot with 3-second countdown"""
        try:
            # Validate settings
            self.validate_settings()
            
            # Disable start button during countdown
            self.start_button.config(state="disabled", text="Starting...")
            self.log_message("Starting bot in 3 seconds...")
            
            # Start countdown
            self.countdown_thread = threading.Thread(target=self.countdown_and_start, daemon=True)
            self.countdown_thread.start()
            
        except ValueError as e:
            messagebox.showerror("Settings Error", str(e))

    def countdown_and_start(self):
        """Countdown and then start the bot"""
        for i in range(3, 0, -1):
            # Check if bot was cancelled during countdown
            if not hasattr(self, 'bot_running') or self.bot_running is None:
                self.root.after(0, self.cancel_start)
                return
                
            self.root.after(0, lambda count=i: self.status_label.config(text=f"Starting in {count}...", foreground="orange"))
            self.root.after(0, lambda count=i: self.log_message(f"Starting in {count} seconds..."))
            time.sleep(1)
        
        # Check one more time before starting
        if not hasattr(self, 'bot_running') or self.bot_running is None:
            self.root.after(0, self.cancel_start)
            return
            
        # Start the bot
        self.root.after(0, self.actually_start_bot)

    def actually_start_bot(self):
        """Actually start the bot after countdown"""
        # Update bot state
        self.bot_running = True
        self.bot_paused = False
        self.start_time = time.time()
        self.loop_count = 0
        self.auto_pause_start_time = time.time()  # Track auto-pause timer

        # Update GUI
        self.status_label.config(text="RUNNING", foreground="green")
        self.quick_status_label.config(text="● Running", foreground="green")
        self.start_button.config(state="disabled", text="Start Bot")
        self.pause_button.config(state="normal")
        self.stop_button.config(state="normal")

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.update({
                "running": True,
                "paused": False,
                "status": "RUNNING",
                "loop_count": 0
            })

        # Start bot thread
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

        self.log_message("Bot started successfully")

    def stop_bot(self):
        """Stop the bot"""
        self.bot_running = False
        self.bot_paused = True
        self.start_time = None

        # Reset queue system
        try:
            queue_manager = runtime.queue_manager
            if queue_manager:
                queue_manager.reset_queue()
                print("[GUI] Queue manager reset on bot stop")
        except Exception as e:
            print(f"[GUI] Error resetting queue manager: {e}")

        # Clear manual mode schedule
        if self.manual_mode_schedule:
            print(f"[GUI] Clearing {len(self.manual_mode_schedule)} manual tasks on bot stop")
            self.manual_mode_schedule = []
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()

        # Update GUI
        self.status_label.config(text="STOPPED", foreground="red")
        self.quick_status_label.config(text="● Stopped", foreground="red")
        self.start_button.config(state="normal", text="Start Bot")
        self.pause_button.config(state="disabled")
        self.stop_button.config(state="disabled")

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.update({
                "running": False,
                "paused": True,
                "status": "STOPPED"
            })

        self.log_message("Bot stopped")

    def cancel_start(self):
        """Cancel the countdown and reset start button"""
        self.bot_running = False
        self.status_label.config(text="PAUSED", foreground="red")
        self.quick_status_label.config(text="● Paused", foreground="red")
        self.start_button.config(state="normal", text="Start Bot")
        self.log_message("Bot start cancelled")

    def toggle_pause(self):
        """Toggle bot pause/resume"""
        if self.bot_running:
            self.bot_paused = not self.bot_paused

            if self.bot_paused:
                self.status_label.config(text="PAUSED", foreground="orange")
                self.quick_status_label.config(text="● Paused", foreground="orange")
                self.log_message("Bot paused")
            else:
                self.status_label.config(text="RUNNING", foreground="green")
                self.quick_status_label.config(text="● Running", foreground="green")
                self.log_message("Bot resumed")

            # Sync to state manager for web GUI
            if self.state_manager:
                self.state_manager.set("paused", self.bot_paused)
                self.state_manager.set("status", "PAUSED" if self.bot_paused else "RUNNING")

    def open_template_tools(self):
        """Open template capture tools"""
        import subprocess
        try:
            subprocess.Popen(['python', 'capture_templates.py'])
            self.log_message("Template tools opened")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open template tools: {e}")

    def run_bot(self):
        """Main bot loop - this will be called from main.py"""
        # This method will be overridden by the main bot
        pass

    def update_loop_count(self, count):
        """Update loop count from main bot"""
        self.loop_count = count
        self.loop_label.config(text=str(count))

        # Sync to state manager for web GUI
        if self.state_manager:
            self.state_manager.set("loop_count", count)

    def update_bb_gold_state(self, state_name):
        """Update BB Gold state display from main bot (thread-safe)"""
        # Color mapping for different states (dark mode compatible)
        state_colors = {
            'IN_BASE': '#4A9EFF',          # Light blue
            'SEARCHING': '#FFA500',        # Orange
            'ATTACK_READY': '#BB86FC',     # Light purple
            'BATTLE_ACTIVE': '#03DAC6',    # Cyan/teal
            'BATTLE_ENDING': '#00C853',    # Light green
            'END_SCREEN': '#4A9EFF',       # Light blue
            'RETURNING_HOME': '#4A9EFF',   # Light blue
            'ERROR_RECOVERY': '#FF5252'    # Light red
        }

        # Get color for this state
        color = state_colors.get(state_name, '#B0B0B0')  # Light gray default

        # Queue update to main GUI thread (proper threading)
        self.root.after(0, self._update_bb_state_label, state_name, color)

    def _update_bb_state_label(self, state_name, color):
        """Internal method - runs on GUI thread"""
        self.bb_state_label.config(text=state_name, foreground=color)

    def schedule_auto_resume(self, break_duration_minutes):
        """Schedule automatic resume after break duration"""
        if self.bot_running and self.bot_paused:
            # Schedule resume after break duration
            resume_time = time.time() + (break_duration_minutes * 60)
            
            def auto_resume():
                if time.time() >= resume_time and self.bot_running and self.bot_paused:
                    self.bot_paused = False
                    self.status_label.config(text="RUNNING", foreground="green")
                    self.quick_status_label.config(text="● Running", foreground="green")
                    self.log_message("Auto-resumed after break")
                    # Schedule next break
                    self.schedule_next_break()
                elif self.bot_running:
                    # Check again in 10 seconds
                    self.root.after(10000, auto_resume)
            
            self.root.after(10000, auto_resume)  # Start checking after 10 seconds

    def schedule_next_break(self):
        """Schedule the next automatic break"""
        # This will be called from main.py when needed
        pass
