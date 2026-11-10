"""Queue section: smart mode controls and the manual task schedule."""

import tkinter as tk
from tkinter import messagebox, ttk

from coc_bot import runtime

class QueuePanelMixin:
    """Queue section: smart mode controls and the manual task schedule. Mixin for BotGUI."""

    def create_queue_section(self, frame):
        """Create Queue System configuration section"""
        frame.columnconfigure(1, weight=1)

        # Queue Enable/Disable
        ttk.Label(frame, text="Enable Queue:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.queue_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.queue_enabled_var, command=self.on_queue_enabled_changed).grid(row=0, column=1, sticky=tk.W)

        # Queue Mode (Smart/Manual)
        ttk.Label(frame, text="Queue Mode:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.queue_mode_var = tk.StringVar(value="smart")
        queue_mode_combo = ttk.Combobox(frame, textvariable=self.queue_mode_var, values=["smart", "manual"], state='readonly', width=15)
        queue_mode_combo.grid(row=1, column=1, sticky=tk.W)
        queue_mode_combo.bind('<<ComboboxSelected>>', self.on_queue_mode_changed)

        # Smart Mode Configuration (collapsible)
        self.smart_mode_frame = ttk.LabelFrame(frame, text="Smart Mode Settings", padding="10")
        self.smart_mode_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_smart_mode_controls(self.smart_mode_frame)

        # Manual Mode Configuration (collapsible)
        self.manual_mode_frame = ttk.LabelFrame(frame, text="Manual Mode Settings", padding="10")
        self.manual_mode_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_manual_mode_controls(self.manual_mode_frame)

        # Achievement Farm End Behavior
        self.achievement_end_frame = ttk.LabelFrame(frame, text="Achievement Farm End Behavior", padding="10")
        self.achievement_end_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.create_achievement_end_controls(self.achievement_end_frame)

        # Update visibility based on queue mode
        self.update_queue_mode_visibility()

    def create_smart_mode_controls(self, frame):
        """Create Smart Mode configuration controls"""
        frame.columnconfigure(1, weight=1)

        # Main Base Mode Selection
        ttk.Label(frame, text="Main Base Mode:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_main_mode_var = tk.StringVar(value="SBarb Farm")
        main_mode_combo = ttk.Combobox(frame, textvariable=self.smart_main_mode_var,
                                       values=["SBarb Farm", "SGoblin Farm"], state='readonly', width=15)
        main_mode_combo.grid(row=0, column=1, sticky=tk.W)

        # Storage Thresholds
        ttk.Label(frame, text="Gold Threshold (%):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_gold_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_gold_threshold_var, width=15).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(frame, text="Elixir Threshold (%):").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_elixir_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_elixir_threshold_var, width=15).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(frame, text="DE Threshold (%):").grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_de_threshold_var = tk.StringVar(value="100")
        ttk.Spinbox(frame, from_=50, to=100, increment=5, textvariable=self.smart_de_threshold_var, width=15).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(frame, text="Wait for DE:").grid(row=4, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_wait_de_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.smart_wait_de_var).grid(row=4, column=1, sticky=tk.W)

        # BB Settings
        ttk.Label(frame, text="BB Auto-Select:").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_bb_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, variable=self.smart_bb_auto_var).grid(row=5, column=1, sticky=tk.W)

        ttk.Label(frame, text="BB Gold/Elixir Ratio:").grid(row=6, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_bb_ratio_var = tk.StringVar(value="3.0")
        ttk.Spinbox(frame, from_=1.0, to=10.0, increment=0.5, textvariable=self.smart_bb_ratio_var, width=15).grid(row=6, column=1, sticky=tk.W)

        ttk.Label(frame, text="After BB Behavior:").grid(row=7, column=0, sticky=tk.W, padx=(0, 10))
        self.smart_after_bb_var = tk.StringVar(value="stop")
        after_bb_combo = ttk.Combobox(frame, textvariable=self.smart_after_bb_var,
                                      values=["stop", "achievement_farm"], state='readonly', width=15)
        after_bb_combo.grid(row=7, column=1, sticky=tk.W)

    def create_manual_mode_controls(self, frame):
        """Create Manual Mode schedule editor"""
        frame.columnconfigure(0, weight=1)

        # Subtitle explaining usage
        subtitle = ttk.Label(frame,
            text="Define a sequence of tasks to execute in order. Each task runs until its condition is met.",
            font=('Segoe UI', 8, 'italic'),
            foreground='gray')
        subtitle.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Create frame for schedule list with scrollbar
        self.manual_schedule_frame = ttk.Frame(frame, relief='solid', borderwidth=1)

        schedule_canvas_frame = ttk.Frame(self.manual_schedule_frame)
        schedule_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.manual_schedule_canvas = tk.Canvas(schedule_canvas_frame, height=200, bg='#f0f0f0', highlightthickness=0)
        self.manual_schedule_scrollbar = ttk.Scrollbar(schedule_canvas_frame, orient="vertical", command=self.manual_schedule_canvas.yview)
        self.manual_schedule_scroll_frame = ttk.Frame(self.manual_schedule_canvas)

        self.manual_schedule_scroll_frame.bind(
            "<Configure>",
            lambda e: self.manual_schedule_canvas.configure(scrollregion=self.manual_schedule_canvas.bbox("all"))
        )

        self.manual_schedule_canvas.create_window((0, 0), window=self.manual_schedule_scroll_frame, anchor="nw")
        self.manual_schedule_canvas.configure(yscrollcommand=self.manual_schedule_scrollbar.set)

        self.manual_schedule_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.manual_schedule_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store task card references
        self.manual_task_cards = []
        self.manual_selected_task_index = None

        # Grid the schedule list frame
        self.manual_schedule_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Buttons frame
        self.manual_buttons_frame = ttk.Frame(frame)

        ttk.Button(
            self.manual_buttons_frame,
            text="➕ Add Task",
            command=self.add_manual_task,
            width=12
        ).grid(row=0, column=0, padx=(0, 5))

        ttk.Button(
            self.manual_buttons_frame,
            text="✏️ Edit Task",
            command=self.edit_manual_task,
            width=12
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="❌ Remove",
            command=self.remove_manual_task,
            width=12
        ).grid(row=0, column=2, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="⬆ Move Up",
            command=self.move_manual_task_up,
            width=12
        ).grid(row=0, column=3, padx=5)

        ttk.Button(
            self.manual_buttons_frame,
            text="⬇ Move Down",
            command=self.move_manual_task_down,
            width=12
        ).grid(row=0, column=4, padx=(5, 0))

        # Clear All button on second row
        ttk.Button(
            self.manual_buttons_frame,
            text="🗑️ Clear All Tasks",
            command=self.clear_all_manual_tasks,
            width=20
        ).grid(row=1, column=0, columnspan=2, pady=(5, 0), padx=(0, 5))

        self.manual_buttons_frame.grid(row=2, column=0, pady=(5, 0))

        # Initialize task list display
        self.refresh_manual_schedule_display()

    def create_achievement_end_controls(self, frame):
        """Create Achievement Farm end behavior controls"""
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Enable:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.achievement_end_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.achievement_end_enabled_var).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(frame, text="Duration (minutes):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.achievement_end_duration_var = tk.StringVar(value="20")
        ttk.Spinbox(frame, from_=5, to=120, increment=5, textvariable=self.achievement_end_duration_var, width=15).grid(row=1, column=1, sticky=tk.W)

    def on_queue_enabled_changed(self):
        """Handle queue enable/disable toggle"""
        print(f"[GUI] on_queue_enabled_changed called, checkbox value: {self.queue_enabled_var.get()}")

        # Start or stop the queue manager
        try:
            queue_manager = runtime.queue_manager
            print(f"[GUI] queue_manager reference: {queue_manager}")

            if self.queue_enabled_var.get():
                # Queue enabled - start it
                if queue_manager:
                    queue_manager.start_queue()
                    self.log_message("Queue System: STARTED")
                    print("[GUI] ✓ Queue system started successfully")
                else:
                    print("[GUI] ERROR: queue_manager not found")
                    self.log_message("Queue System: ERROR - queue_manager not initialized")
            else:
                # Queue disabled - reset it
                if queue_manager:
                    queue_manager.reset_queue()
                    self.log_message("Queue System: STOPPED")
                    print("[GUI] ✓ Queue system stopped")
                else:
                    print("[GUI] WARNING: queue_manager not found (queue already stopped)")
        except Exception as e:
            print(f"[GUI] ERROR toggling queue: {e}")
            import traceback
            traceback.print_exc()

        self.save_global_settings()

    def on_queue_mode_changed(self, event=None):
        """Handle queue mode selection"""
        self.update_queue_mode_visibility()
        self.save_global_settings()

    def update_queue_mode_visibility(self):
        """Show/hide Smart/Manual mode controls based on selection"""
        mode = self.queue_mode_var.get()

        if mode == "smart":
            self.smart_mode_frame.grid()
            self.manual_mode_frame.grid_remove()
        else:
            self.smart_mode_frame.grid_remove()
            self.manual_mode_frame.grid()

    def refresh_manual_schedule_display(self):
        """Refresh the manual mode schedule display"""
        # Clear existing cards
        for widget in self.manual_schedule_scroll_frame.winfo_children():
            widget.destroy()

        self.manual_task_cards = []

        # Get schedule from settings or instance variable
        if hasattr(self, 'manual_mode_schedule'):
            schedule = self.manual_mode_schedule
        else:
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])

        if not schedule:
            # Show empty state message
            empty_label = ttk.Label(
                self.manual_schedule_scroll_frame,
                text="No tasks in schedule. Click 'Add Task' to begin.",
                foreground='gray',
                font=('Segoe UI', 9, 'italic')
            )
            empty_label.pack(pady=30)
            return

        # Create task cards
        for i, task in enumerate(schedule):
            self.create_manual_task_card(i, task)

    def create_manual_task_card(self, index, task):
        """Create a visual card for a manual mode task"""
        # Main card frame
        card_frame = ttk.Frame(self.manual_schedule_scroll_frame, relief='raised', borderwidth=1)
        card_frame.pack(fill=tk.X, padx=5, pady=3)

        # Configure colors based on selection
        bg_color = '#e3f2fd' if index == self.manual_selected_task_index else '#ffffff'

        # Inner frame with padding
        inner_frame = tk.Frame(card_frame, bg=bg_color, padx=10, pady=8)
        inner_frame.pack(fill=tk.BOTH, expand=True)

        # Task number and mode
        mode = task.get('mode', 'Unknown')
        header_label = tk.Label(
            inner_frame,
            text=f"Task {index + 1}: {mode}",
            font=('Segoe UI', 10, 'bold'),
            bg=bg_color,
            fg='#1976d2'
        )
        header_label.pack(anchor=tk.W)

        # Condition details
        condition_type = task.get('condition_type', 'time')
        if condition_type == 'time':
            condition_text = f"⏱️ Run for {task.get('time_minutes', 30)} minutes"
        else:  # storage
            storage_target = task.get('storage_target', {})
            parts = []
            if 'gold' in storage_target and storage_target['gold'] is not None:
                parts.append(f"Gold {storage_target['gold']}%")
            if 'elixir' in storage_target and storage_target['elixir'] is not None:
                parts.append(f"Elixir {storage_target['elixir']}%")
            if 'de' in storage_target and storage_target['de'] is not None:
                parts.append(f"DE {storage_target['de']}%")
            condition_text = f"📦 Until storage: {', '.join(parts) if parts else 'No targets set'}"

        condition_label = tk.Label(
            inner_frame,
            text=condition_text,
            font=('Segoe UI', 9),
            bg=bg_color,
            fg='#555555'
        )
        condition_label.pack(anchor=tk.W, pady=(2, 0))

        # Make card clickable
        def make_click_handler(idx):
            def handler(event):
                self.select_manual_task(idx)
            return handler

        for widget in [card_frame, inner_frame, header_label, condition_label]:
            widget.bind('<Button-1>', make_click_handler(index))

        # Hover effects
        def on_enter(event, card=inner_frame):
            if index != self.manual_selected_task_index:
                card.config(bg='#f5f5f5')

        def on_leave(event, card=inner_frame):
            if index != self.manual_selected_task_index:
                card.config(bg='#ffffff')

        card_frame.bind('<Enter>', on_enter)
        card_frame.bind('<Leave>', on_leave)

        self.manual_task_cards.append(card_frame)

    def select_manual_task(self, index):
        """Select a task in the manual schedule"""
        self.manual_selected_task_index = index
        self.refresh_manual_schedule_display()

    def add_manual_task(self):
        """Open dialog to add a new task"""
        self.show_manual_task_dialog(mode='add')

    def edit_manual_task(self):
        """Open dialog to edit selected task"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to edit.")
            return

        self.show_manual_task_dialog(mode='edit', task_index=self.manual_selected_task_index)

    def remove_manual_task(self):
        """Remove selected task from schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to remove.")
            return

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if 0 <= self.manual_selected_task_index < len(schedule):
            removed_task = schedule.pop(self.manual_selected_task_index)
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()
            print(f"[GUI] Removed task from manual schedule: {removed_task}")

    def clear_all_manual_tasks(self):
        """Remove all tasks from manual schedule"""
        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if not schedule:
            messagebox.showinfo("No Tasks", "Manual schedule is already empty.")
            return

        # Confirm with user
        result = messagebox.askyesno(
            "Clear All Tasks",
            f"Are you sure you want to remove all {len(schedule)} task(s) from the manual schedule?\n\nThis action cannot be undone."
        )

        if result:
            self.manual_mode_schedule = []
            self.manual_selected_task_index = None
            self.save_global_settings()
            self.refresh_manual_schedule_display()
            print(f"[GUI] Cleared all {len(schedule)} tasks from manual schedule")
            self.log_message(f"Cleared all manual schedule tasks ({len(schedule)} removed)")

    def move_manual_task_up(self):
        """Move selected task up in the schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to move.")
            return

        if self.manual_selected_task_index == 0:
            return  # Already at top

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        idx = self.manual_selected_task_index
        schedule[idx], schedule[idx - 1] = schedule[idx - 1], schedule[idx]
        self.manual_selected_task_index = idx - 1

        self.save_global_settings()
        self.refresh_manual_schedule_display()

    def move_manual_task_down(self):
        """Move selected task down in the schedule"""
        if self.manual_selected_task_index is None:
            messagebox.showinfo("No Selection", "Please select a task to move.")
            return

        settings = self.get_settings()
        schedule = settings.get('manual_mode_schedule', [])

        if self.manual_selected_task_index >= len(schedule) - 1:
            return  # Already at bottom

        idx = self.manual_selected_task_index
        schedule[idx], schedule[idx + 1] = schedule[idx + 1], schedule[idx]
        self.manual_selected_task_index = idx + 1

        self.save_global_settings()
        self.refresh_manual_schedule_display()

    def show_manual_task_dialog(self, mode='add', task_index=None):
        """Show dialog to add or edit a manual task"""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Task" if mode == 'add' else "Edit Task")
        dialog.geometry("450x400")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Get existing task data if editing
        existing_task = None
        if mode == 'edit' and task_index is not None:
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])
            if 0 <= task_index < len(schedule):
                existing_task = schedule[task_index]

        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Mode selection
        ttk.Label(main_frame, text="Attack Mode:", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        mode_var = tk.StringVar(value=existing_task.get('mode', 'SBarb Farm') if existing_task else 'SBarb Farm')
        mode_combo = ttk.Combobox(main_frame, textvariable=mode_var, state='readonly', width=25)
        mode_combo['values'] = [
            'Farming', 'Trophy Push', 'Derank', 'SGoblin Farm', 'SBarb Farm',
            'Achievement Farm', 'BB Elixir', 'BB Gold', 'Custom'
        ]
        mode_combo.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        # Condition type
        ttk.Label(main_frame, text="Completion Condition:", font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        condition_var = tk.StringVar(value=existing_task.get('condition_type', 'time') if existing_task else 'time')
        condition_frame = ttk.Frame(main_frame)
        condition_frame.grid(row=3, column=0, sticky=tk.W, pady=(0, 15))

        ttk.Radiobutton(condition_frame, text="Time-based", variable=condition_var, value='time').pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(condition_frame, text="Storage-based", variable=condition_var, value='storage').pack(side=tk.LEFT)

        # Time-based settings
        time_frame = ttk.LabelFrame(main_frame, text="Time Settings", padding="10")
        time_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(time_frame, text="Duration (minutes):").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        time_var = tk.StringVar(value=str(existing_task.get('time_minutes', 30) if existing_task else 30))
        ttk.Spinbox(time_frame, from_=5, to=300, increment=5, textvariable=time_var, width=15).grid(row=0, column=1, sticky=tk.W)

        # Storage-based settings
        storage_frame = ttk.LabelFrame(main_frame, text="Storage Targets (%)", padding="10")
        storage_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        storage_target = existing_task.get('storage_target', {}) if existing_task else {}

        ttk.Label(storage_frame, text="Gold:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        gold_var = tk.StringVar(value=str(storage_target.get('gold', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=gold_var, width=10).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(storage_frame, text="Elixir:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        elixir_var = tk.StringVar(value=str(storage_target.get('elixir', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=elixir_var, width=10).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(storage_frame, text="Dark Elixir:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        de_var = tk.StringVar(value=str(storage_target.get('de', 100)))
        ttk.Spinbox(storage_frame, from_=0, to=100, increment=5, textvariable=de_var, width=10).grid(row=2, column=1, sticky=tk.W)

        # Show/hide frames based on condition type
        def update_frame_visibility(*args):
            if condition_var.get() == 'time':
                time_frame.grid()
                storage_frame.grid_remove()
            else:
                time_frame.grid_remove()
                storage_frame.grid()

        condition_var.trace('w', update_frame_visibility)
        update_frame_visibility()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, pady=(10, 0))

        def save_task():
            # Build task dictionary
            task = {
                'mode': mode_var.get(),
                'condition_type': condition_var.get()
            }

            if condition_var.get() == 'time':
                task['time_minutes'] = int(time_var.get())
            else:
                task['storage_target'] = {
                    'gold': int(gold_var.get()),
                    'elixir': int(elixir_var.get()),
                    'de': int(de_var.get())
                }

            # Add or update task
            settings = self.get_settings()
            schedule = settings.get('manual_mode_schedule', [])

            if mode == 'add':
                schedule.append(task)
                print(f"[GUI] Added task to manual schedule: {task}")
            else:  # edit
                if 0 <= task_index < len(schedule):
                    schedule[task_index] = task
                    print(f"[GUI] Updated task in manual schedule: {task}")

            # Validate schedule
            from coc_bot.queue_manager import QueueManager
            is_valid, error_msg = QueueManager(self).validate_manual_schedule(schedule)

            if not is_valid:
                messagebox.showerror("Invalid Schedule", f"Cannot save task:\n\n{error_msg}")
                return

            self.save_global_settings()
            self.refresh_manual_schedule_display()
            dialog.destroy()

        ttk.Button(button_frame, text="Save", command=save_task, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)
