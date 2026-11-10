"""Top-level window sections: status, settings, controls, loot and log."""

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

class MainSectionsMixin:
    """Top-level window sections: status, settings, controls, loot and log. Mixin for BotGUI."""

    def create_status_section(self, parent):
        # Status Frame - improved 2-column layout with better spacing
        status_frame = ttk.LabelFrame(parent, text="📊 Bot Status", padding="15")
        status_frame.grid(row=1, column=0, columnspan=2, sticky='we', pady=(0, 15))

        # Store reference for making collapsible after children are added
        self.status_frame = status_frame

        # Configure columns for better distribution
        status_frame.columnconfigure(0, weight=0)
        status_frame.columnconfigure(1, weight=1)
        status_frame.columnconfigure(2, weight=0, pad=40)
        status_frame.columnconfigure(3, weight=1)

        # Left column - Status and Time
        ttk.Label(status_frame, text="Status:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, text="PAUSED", foreground="red", font=('Segoe UI', 11, 'bold'))
        self.status_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(status_frame, text="Running Time:", font=('Segoe UI', 10)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.time_label = ttk.Label(status_frame, text="00:00:00", font=('Segoe UI', 10))
        self.time_label.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        # BB Gold State display (only shown during BB Gold attacks)
        ttk.Label(status_frame, text="BB State:", font=('Segoe UI', 10)).grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.bb_state_label = ttk.Label(status_frame, text="N/A", foreground="gray", font=('Segoe UI', 10))
        self.bb_state_label.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        # Right column - Loops and Rate
        ttk.Label(status_frame, text="Loops Completed:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.loop_label = ttk.Label(status_frame, text="0", font=('Segoe UI', 11, 'bold'))
        self.loop_label.grid(row=0, column=3, sticky=tk.W)

        ttk.Label(status_frame, text="Loops/Hour:", font=('Segoe UI', 10)).grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.rate_label = ttk.Label(status_frame, text="0", font=('Segoe UI', 10))
        self.rate_label.grid(row=1, column=3, sticky=tk.W, pady=(8, 0))

    def create_settings_section(self, parent):
        # Create a frame for 2-column layout (better for vertical monitors)
        settings_outer_frame = ttk.Frame(parent)
        settings_outer_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(0, 10))
        parent.grid_rowconfigure(2, weight=0)  # Allow settings to shrink when collapsed
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # Configure 2-column grid with better spacing
        settings_outer_frame.columnconfigure(0, weight=1, minsize=400)
        settings_outer_frame.columnconfigure(1, weight=1, minsize=400)
        settings_outer_frame.rowconfigure(0, weight=0)
        settings_outer_frame.rowconfigure(1, weight=0)  # Changed from weight=1 to allow collapsible sections to shrink
        settings_outer_frame.rowconfigure(2, weight=0)

        # Profile Selection Frame (spans 2 columns for more visibility)
        profile_frame = ttk.LabelFrame(settings_outer_frame, text="🎯 Profile Selection", padding="12")
        profile_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.profile_frame = profile_frame  # Store for collapsible
        self.create_profile_section(profile_frame)

        # Army Frame
        army_frame = ttk.LabelFrame(settings_outer_frame, text="🪖 Army", padding="12")
        army_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        self.army_frame = army_frame  # Store for collapsible
        self.create_army_section(army_frame)

        # Attack Frame
        attack_frame = ttk.LabelFrame(settings_outer_frame, text="⚡ Attack", padding="12")
        attack_frame.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        self.attack_frame = attack_frame  # Store for collapsible
        self.create_attack_section(attack_frame)

        # Global Frame (now includes all former Functionality settings)
        global_frame = ttk.LabelFrame(settings_outer_frame, text="⚙️ Global Settings", padding="12")
        global_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.global_frame = global_frame  # Store for collapsible
        self.create_global_section(global_frame)

        # Queue System Frame
        queue_frame = ttk.LabelFrame(settings_outer_frame, text="🔄 Queue System", padding="12")
        queue_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.queue_frame = queue_frame  # Store for collapsible
        self.create_queue_section(queue_frame)

        # Achievement Priority Frame (conditionally visible for Achievement Farm and SBarb Farm)
        priority_frame = ttk.LabelFrame(settings_outer_frame, text="🎯 Achievement Building Priority", padding="12")
        priority_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        self.priority_frame = priority_frame  # Store for collapsible
        self.create_achievement_priority_section(priority_frame)

    def create_control_section(self, parent):
        # Control Frame with improved layout
        control_frame = ttk.LabelFrame(parent, text="🎮 Bot Controls", padding="15")
        control_frame.grid(row=3, column=0, columnspan=2, sticky='we', pady=(0, 15))
        self.control_frame = control_frame  # Store for collapsible

        # Make control frame responsive
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)
        control_frame.columnconfigure(3, weight=1)
        control_frame.columnconfigure(4, weight=1)
        control_frame.columnconfigure(5, weight=1)

        # Primary control buttons (row 0) - larger and more prominent
        self.start_button = ttk.Button(control_frame, text="▶ Start Bot", command=self.start_bot)
        self.start_button.grid(row=0, column=0, columnspan=2, sticky='ew', padx=(0, 10))

        self.pause_button = ttk.Button(control_frame, text="⏸ Pause/Resume (F1)", command=self.toggle_pause, state="disabled")
        self.pause_button.grid(row=0, column=2, columnspan=2, sticky='ew', padx=(0, 10))

        self.stop_button = ttk.Button(control_frame, text="⏹ Stop Bot (F2)", command=self.stop_bot, state="disabled")
        self.stop_button.grid(row=0, column=4, columnspan=2, sticky='ew')

        # Secondary buttons (row 1) - utilities
        template_button = ttk.Button(control_frame, text="Template Tools", command=self.open_template_tools)
        template_button.grid(row=1, column=0, columnspan=2, sticky='ew', padx=(0, 10), pady=(10, 0))

        save_button = ttk.Button(control_frame, text="Save Settings", command=lambda: self.save_settings(show_popup=True))
        save_button.grid(row=1, column=2, columnspan=2, sticky='ew', padx=(0, 10), pady=(10, 0))

        reset_profile_button = ttk.Button(control_frame, text="Reset Profile", command=self.reset_profile_to_defaults)
        reset_profile_button.grid(row=1, column=4, columnspan=2, sticky='ew', pady=(10, 0))

        # Auto-pause controls (row 2-4, cleaner layout)
        auto_pause_label = ttk.Label(control_frame, text="Auto-Pause:", font=('Segoe UI', 9))
        auto_pause_label.grid(row=2, column=0, sticky='w', pady=(10, 0))

        # Auto-pause mode variable
        self.auto_pause_mode = tk.StringVar(value="manual")

        # Storage full resource checkboxes (which resources must be full)
        self.storage_full_gold_var = tk.BooleanVar(value=True)
        self.storage_full_elixir_var = tk.BooleanVar(value=True)
        self.storage_full_de_var = tk.BooleanVar(value=False)
        self.storage_full_preset_var = tk.StringVar(value="main")

        # Row 2: Manual option
        manual_frame = ttk.Frame(control_frame)
        manual_frame.grid(row=2, column=1, columnspan=4, sticky='w', pady=(10, 0))

        manual_radio = ttk.Radiobutton(manual_frame, text="Manual", variable=self.auto_pause_mode, value="manual")
        manual_radio.pack(side='left')

        # Row 3: Storage Full option with resource checkboxes
        storage_frame = ttk.Frame(control_frame)
        storage_frame.grid(row=3, column=1, columnspan=4, sticky='w', pady=(5, 0))

        storage_radio = ttk.Radiobutton(storage_frame, text="Storage Full:", variable=self.auto_pause_mode, value="storage_full")
        storage_radio.pack(side='left')

        # Resource checkboxes (compact, inline)
        self.storage_gold_cb = ttk.Checkbutton(storage_frame, text="Gold", variable=self.storage_full_gold_var,
                                                command=self.save_settings)
        self.storage_gold_cb.pack(side='left', padx=(8, 0))

        self.storage_elixir_cb = ttk.Checkbutton(storage_frame, text="Elixir", variable=self.storage_full_elixir_var,
                                                  command=self.save_settings)
        self.storage_elixir_cb.pack(side='left', padx=(4, 0))

        self.storage_de_cb = ttk.Checkbutton(storage_frame, text="DE", variable=self.storage_full_de_var,
                                              command=self.save_settings)
        self.storage_de_cb.pack(side='left', padx=(4, 0))

        # Storage preset dropdown
        ttk.Label(storage_frame, text="Preset:").pack(side='left', padx=(12, 2))
        self.storage_full_preset_dropdown = ttk.Combobox(storage_frame, textvariable=self.storage_full_preset_var,
                                                          state='readonly', width=10)
        self.storage_full_preset_dropdown.pack(side='left')
        self.storage_full_preset_dropdown.bind('<<ComboboxSelected>>', self.on_storage_full_preset_selected)
        # Initialize dropdown values
        self.update_storage_full_preset_dropdown()

        # Row 4: After X attacks option (in a frame for tight spacing)
        attacks_frame = ttk.Frame(control_frame)
        attacks_frame.grid(row=4, column=1, columnspan=4, sticky='w', pady=(5, 0))

        attacks_radio = ttk.Radiobutton(attacks_frame, text="After", variable=self.auto_pause_mode, value="loops")
        attacks_radio.pack(side='left')

        self.auto_pause_value = tk.StringVar(value="50")
        self.attacks_entry = ttk.Entry(attacks_frame, textvariable=self.auto_pause_value, width=6)
        self.attacks_entry.pack(side='left', padx=(3, 3))

        attacks_label = ttk.Label(attacks_frame, text="attacks", font=('Segoe UI', 9))
        attacks_label.pack(side='left')

        # Row 5: After X minutes option (in a frame for tight spacing)
        minutes_frame = ttk.Frame(control_frame)
        minutes_frame.grid(row=5, column=1, columnspan=4, sticky='w', pady=(5, 0))

        time_radio = ttk.Radiobutton(minutes_frame, text="After", variable=self.auto_pause_mode, value="time")
        time_radio.pack(side='left')

        self.minutes_entry = ttk.Entry(minutes_frame, textvariable=self.auto_pause_value, width=6)
        self.minutes_entry.pack(side='left', padx=(3, 3))

        minutes_label = ttk.Label(minutes_frame, text="minutes", font=('Segoe UI', 9))
        minutes_label.pack(side='left')

        # Hotkey info label (moved to row 6)
        hotkey_info = ttk.Label(control_frame, text="Hotkeys: F1=Pause/Resume | F2=Stop | F11=Fullscreen | ESC=Exit Program",
                               font=('Segoe UI', 8), foreground='gray')
        hotkey_info.grid(row=6, column=0, columnspan=6, pady=(8, 0))

    def create_loot_section(self, parent):
        """Create loot statistics section with improved layout"""
        # Loot Frame
        loot_frame = ttk.LabelFrame(parent, text="💰 Loot Statistics", padding="15")
        loot_frame.grid(row=4, column=0, columnspan=2, sticky='we', pady=(0, 15))
        self.loot_frame = loot_frame  # Store for collapsible

        # Configure grid for better responsive layout
        loot_frame.columnconfigure(1, weight=1)
        loot_frame.columnconfigure(3, weight=1)
        loot_frame.columnconfigure(4, weight=1)

        # Initialize loot tracking variables
        self.total_gold = 0
        self.total_elixir = 0
        self.total_dark_elixir = 0
        self.attacks_with_loot = 0
        self.skipped_bases = 0
        self.skip_ratio = 0.0

        # --- CSV-based total statistics with icons ---
        self.gold_img = ImageTk.PhotoImage(Image.open('assets/gold.png').resize((24, 24)))
        self.elixir_img = ImageTk.PhotoImage(Image.open('assets/elixir.png').resize((24, 24)))
        self.dark_img = ImageTk.PhotoImage(Image.open('assets/dark_elixir.png').resize((24, 24)))
        self.csv_gold = 0
        self.csv_elixir = 0
        self.csv_dark_elixir = 0
        self.csv_gold_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.gold_img, compound='left')
        self.csv_gold_label.grid(row=0, column=4, sticky=tk.W, padx=(30, 0))
        self.csv_elixir_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.elixir_img, compound='left')
        self.csv_elixir_label.grid(row=1, column=4, sticky=tk.W, padx=(30, 0))
        self.csv_dark_label = ttk.Label(loot_frame, text="", font=('Arial', 10, 'bold'), image=self.dark_img, compound='left')
        self.csv_dark_label.grid(row=2, column=4, sticky=tk.W, padx=(30, 0))
        self.update_csv_totals()

        # Loot statistics labels - current session
        ttk.Label(loot_frame, text="Total Gold:", font=('Segoe UI', 10)).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.gold_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.gold_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(loot_frame, text="Total Elixir:", font=('Segoe UI', 10)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.elixir_label.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Total Dark Elixir:", font=('Segoe UI', 10)).grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.dark_elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.dark_elixir_label.grid(row=2, column=1, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Attacks with Loot:", font=('Segoe UI', 10)).grid(row=3, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.attacks_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10, 'bold'))
        self.attacks_label.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))

        # Skipped bases and skip/attack ratio
        # ttk.Label(loot_frame, text="Skipped Bases:").grid(row=5, column=0, sticky=tk.W, padx=(0, 10))
        # self.skipped_label = ttk.Label(loot_frame, text="0", font=('Arial', 10))
        # self.skipped_label.grid(row=5, column=1, sticky=tk.W)

        # ttk.Label(loot_frame, text="Skip/Attack Ratio:").grid(row=6, column=0, sticky=tk.W, padx=(0, 10))
        # self.skip_ratio_label = ttk.Label(loot_frame, text="0.00", font=('Arial', 10))
        # self.skip_ratio_label.grid(row=6, column=1, sticky=tk.W)

        # Average loot per attack
        ttk.Label(loot_frame, text="Avg Gold/Attack:", font=('Segoe UI', 10)).grid(row=0, column=2, sticky=tk.W, padx=(30, 10))
        self.avg_gold_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_gold_label.grid(row=0, column=3, sticky=tk.W)

        ttk.Label(loot_frame, text="Avg Elixir/Attack:", font=('Segoe UI', 10)).grid(row=1, column=2, sticky=tk.W, padx=(30, 10), pady=(5, 0))
        self.avg_elixir_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_elixir_label.grid(row=1, column=3, sticky=tk.W, pady=(5, 0))

        ttk.Label(loot_frame, text="Avg Dark/Attack:", font=('Segoe UI', 10)).grid(row=2, column=2, sticky=tk.W, padx=(30, 10), pady=(5, 0))
        self.avg_dark_label = ttk.Label(loot_frame, text="0", font=('Segoe UI', 10))
        self.avg_dark_label.grid(row=2, column=3, sticky=tk.W, pady=(5, 0))

        # Reload CSV stats button
        reload_csv_button = ttk.Button(loot_frame, text="Reload CSV Totals", command=self.update_csv_totals)
        reload_csv_button.grid(row=3, column=4, padx=(30, 0))

        # Reset loot button
        reset_loot_button = ttk.Button(loot_frame, text="Reset Loot Stats", command=self.reset_loot_stats)
        reset_loot_button.grid(row=4, column=0, columnspan=4, pady=(10, 0))

    def create_log_section(self, parent):
        # Log Frame
        log_frame = ttk.LabelFrame(parent, text="📝 Logs", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky='nsew', pady=(0, 10))
        self.log_frame = log_frame  # Store for collapsible
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)
        
        # Create notebook for tabs
        self.log_notebook = ttk.Notebook(log_frame)
        self.log_notebook.grid(row=0, column=0, sticky='nsew')
        
        # Bot Log Tab
        bot_log_frame = ttk.Frame(self.log_notebook)
        self.log_notebook.add(bot_log_frame, text="Bot Log")
        bot_log_frame.columnconfigure(0, weight=1)
        bot_log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(bot_log_frame, height=10, width=70)
        bot_log_scrollbar = ttk.Scrollbar(bot_log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=bot_log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky='nsew')
        bot_log_scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Debug Log Tab
        debug_log_frame = ttk.Frame(self.log_notebook)
        self.log_notebook.add(debug_log_frame, text="Debug Log")
        debug_log_frame.columnconfigure(0, weight=1)
        debug_log_frame.rowconfigure(0, weight=1)
        
        self.debug_text = tk.Text(debug_log_frame, height=10, width=70)
        debug_log_scrollbar = ttk.Scrollbar(debug_log_frame, orient="vertical", command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=debug_log_scrollbar.set)
        
        self.debug_text.grid(row=0, column=0, sticky='nsew')
        debug_log_scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Control buttons frame
        button_frame = ttk.Frame(log_frame)
        button_frame.grid(row=1, column=0, pady=(5, 0))
        
        # Clear buttons
        clear_bot_log_button = ttk.Button(button_frame, text="Clear Bot Log", command=self.clear_log)
        clear_bot_log_button.grid(row=0, column=0, padx=(0, 10))
        
        clear_debug_log_button = ttk.Button(button_frame, text="Clear Debug Log", command=self.clear_debug_log)
        clear_debug_log_button.grid(row=0, column=1)
