"""Achievement building priority list."""

import tkinter as tk
from tkinter import messagebox, ttk

class PriorityPanelMixin:
    """Achievement building priority list. Mixin for BotGUI."""

    def create_achievement_priority_section(self, frame):
        """Create achievement building priority list section"""
        frame.columnconfigure(0, weight=1)

        # Subtitle explaining usage
        subtitle = ttk.Label(frame,
            text="Top = highest priority, used by Achievement/SBarb Farm modes",
            font=('Segoe UI', 8, 'italic'),
            foreground='gray')
        subtitle.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Create modern styled frame for priority list
        self.achievement_priority_frame = ttk.Frame(frame, relief='solid', borderwidth=1)

        # Create canvas with scrollbar for modern scrollable list
        priority_canvas_frame = ttk.Frame(self.achievement_priority_frame)
        priority_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.achievement_priority_canvas = tk.Canvas(priority_canvas_frame, height=250, bg='#f0f0f0', highlightthickness=0)
        self.achievement_priority_scrollbar = ttk.Scrollbar(priority_canvas_frame, orient="vertical", command=self.achievement_priority_canvas.yview)
        self.achievement_priority_scroll_frame = ttk.Frame(self.achievement_priority_canvas)

        self.achievement_priority_scroll_frame.bind(
            "<Configure>",
            lambda e: self.achievement_priority_canvas.configure(scrollregion=self.achievement_priority_canvas.bbox("all"))
        )

        self.achievement_priority_canvas.create_window((0, 0), window=self.achievement_priority_scroll_frame, anchor="nw")
        self.achievement_priority_canvas.configure(yscrollcommand=self.achievement_priority_scrollbar.set)

        self.achievement_priority_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.achievement_priority_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store building card references for updates
        self.priority_building_cards = []

        # Grid the priority list frame
        self.achievement_priority_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Buttons frame with modern styling
        self.achievement_priority_buttons_frame = ttk.Frame(frame)
        self.achievement_move_up_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="⬆ Move Up",
            command=self.move_building_up,
            width=15
        )
        self.achievement_move_up_btn.pack(side=tk.LEFT, padx=5)

        self.achievement_move_down_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="⬇ Move Down",
            command=self.move_building_down,
            width=15
        )
        self.achievement_move_down_btn.pack(side=tk.LEFT, padx=5)

        self.achievement_reset_priority_btn = ttk.Button(
            self.achievement_priority_buttons_frame,
            text="🔄 Reset Order",
            command=self.reset_building_priority,
            width=15
        )
        self.achievement_reset_priority_btn.pack(side=tk.LEFT, padx=5)

        # Grid buttons
        self.achievement_priority_buttons_frame.grid(row=2, column=0, sticky=tk.W)

        # Initialize priority list from current profile
        profile_settings = self.profiles.get(self.current_profile, {})
        self.achievement_priority_list = profile_settings.get('achievement_priority_list', [
            'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
            'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
        ])
        self.selected_priority_building = None
        self.update_priority_listbox()

    def update_priority_section_visibility(self):
        """Show/hide entire priority section based on profile"""
        current_profile = self.profile_var.get()

        # Show for Achievement Farm and SBarb Farm only
        relevant_profiles = ['Achievement Farm', 'SBarb Farm']

        if current_profile in relevant_profiles:
            # Show priority section
            self.priority_frame.grid()
        else:
            # Hide priority section completely
            self.priority_frame.grid_remove()

    def update_priority_listbox(self):
        """Update the priority list display with modern card-based design"""
        # Clear existing cards
        for card in self.priority_building_cards:
            card.destroy()
        self.priority_building_cards.clear()

        building_display_names = {
            'eagle_artillery': 'Eagle Artillery',
            'monolith': 'Monolith',
            'xbow': 'X-Bow',
            'inferno_tower': 'Inferno Tower',
            'scattershot': 'Scattershot',
            'spell_tower': 'Spell Tower',
            'multi_archer_tower': 'Multi-Archer Tower',
            'ricochet_cannon': 'Ricochet Cannon',
            'firespitter': 'Firespitter',
            'multi_gear_tower': 'Multi-Gear Tower'
        }

        # Priority badge emojis (or numbers)
        priority_badges = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

        # Create card for each building
        for index, building in enumerate(self.achievement_priority_list):
            display_name = building_display_names.get(building, building.replace('_', ' ').title())

            # Create card frame with gradient-like colors (higher priority = stronger color)
            card_frame = tk.Frame(
                self.achievement_priority_scroll_frame,
                relief='raised',
                borderwidth=1,
                padx=10,
                pady=8,
                bg=self.get_priority_color(index)
            )
            card_frame.pack(fill=tk.X, pady=3, padx=5)

            # Priority badge
            badge_label = tk.Label(
                card_frame,
                text=priority_badges[index] if index < len(priority_badges) else f"{index+1}.",
                font=('Segoe UI', 12, 'bold'),
                bg=self.get_priority_color(index),
                fg='#333333'
            )
            badge_label.pack(side=tk.LEFT, padx=(0, 10))

            # Building name
            name_label = tk.Label(
                card_frame,
                text=display_name,
                font=('Segoe UI', 10),
                bg=self.get_priority_color(index),
                fg='#000000',
                anchor='w'
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Priority rank text
            rank_label = tk.Label(
                card_frame,
                text=f"Priority #{index+1}",
                font=('Segoe UI', 8, 'italic'),
                bg=self.get_priority_color(index),
                fg='#666666'
            )
            rank_label.pack(side=tk.RIGHT, padx=(10, 0))

            # Store building ID with the card
            card_frame.building_id = building

            # Make card clickable for selection
            def make_select_handler(card, bldg):
                def handler(event):
                    self.select_priority_building(card, bldg)
                return handler

            for widget in [card_frame, badge_label, name_label, rank_label]:
                widget.bind('<Button-1>', make_select_handler(card_frame, building))

            # Add hover effect
            def on_enter(event, card=card_frame):
                if card != self.selected_priority_building:
                    card.config(relief='solid', borderwidth=2)

            def on_leave(event, card=card_frame):
                if card != self.selected_priority_building:
                    card.config(relief='raised', borderwidth=1)

            card_frame.bind('<Enter>', on_enter)
            card_frame.bind('<Leave>', on_leave)

            self.priority_building_cards.append(card_frame)

        # Update canvas scroll region
        self.achievement_priority_scroll_frame.update_idletasks()
        self.achievement_priority_canvas.configure(scrollregion=self.achievement_priority_canvas.bbox("all"))

    def get_priority_color(self, index):
        """Get color for priority card based on index (gradient from high to low priority)"""
        # Gradient from gold (high priority) to light blue (low priority)
        colors = [
            '#FFD700',  # Gold
            '#FFA500',  # Orange
            '#FFB347',  # Light Orange
            '#FFDAB9',  # Peach
            '#FFFACD',  # Lemon
            '#E0FFE0',  # Light Green
            '#B0E0E6',  # Powder Blue
            '#ADD8E6',  # Light Blue
            '#D3D3D3',  # Light Gray
            '#E0E0E0'   # Lighter Gray
        ]
        return colors[index] if index < len(colors) else '#F0F0F0'

    def select_priority_building(self, card_frame, building_id):
        """Select a building card for move operations"""
        # Deselect previous selection
        if self.selected_priority_building:
            # Check if old selection still exists in current cards list
            if self.selected_priority_building in self.priority_building_cards:
                index = self.priority_building_cards.index(self.selected_priority_building)
                self.selected_priority_building.config(relief='raised', borderwidth=1, bg=self.get_priority_color(index))

        # Select new card
        self.selected_priority_building = card_frame
        card_frame.config(relief='solid', borderwidth=3, bg='#4A90E2')  # Blue highlight

        # Update all labels in the selected card to match the blue background
        for child in card_frame.winfo_children():
            if isinstance(child, tk.Label):
                child.config(bg='#4A90E2', fg='white')

    def on_parallel_scan_toggle(self):
        """Show warning when parallel scanning is enabled"""
        if self.achievement_parallel_scan_var.get():
            from tkinter import messagebox
            messagebox.showwarning(
                "CPU Warning",
                "Parallel scanning is faster but may cause:\n\n"
                "• CPU spikes up to 28-32%\n"
                "• Possible game crashes on slower systems\n"
                "• Brief system lag during scans\n\n"
                "Sequential scanning (default) is slower but stable.\n\n"
                "Only enable parallel mode if you have a fast CPU and "
                "haven't experienced crashes."
            )

    def move_building_up(self):
        """Move selected building up in priority list"""
        if not self.selected_priority_building:
            messagebox.showinfo("No Selection", "Please select a building card to move.")
            return

        # Find index of selected building
        index = self.priority_building_cards.index(self.selected_priority_building)

        if index == 0:
            return  # Already at top

        # Swap with previous item
        self.achievement_priority_list[index], self.achievement_priority_list[index-1] = \
            self.achievement_priority_list[index-1], self.achievement_priority_list[index]

        # Rebuild display and maintain selection
        selected_building = self.selected_priority_building.building_id
        self.update_priority_listbox()

        # Re-select the moved building
        if index-1 < len(self.priority_building_cards):
            self.select_priority_building(self.priority_building_cards[index-1], selected_building)
            # Scroll to show the selected card
            self.achievement_priority_canvas.yview_moveto(max(0, (index-1) / len(self.priority_building_cards)))

        # Save changes to settings
        self.save_settings()

    def move_building_down(self):
        """Move selected building down in priority list"""
        if not self.selected_priority_building:
            messagebox.showinfo("No Selection", "Please select a building card to move.")
            return

        # Find index of selected building
        index = self.priority_building_cards.index(self.selected_priority_building)

        if index == len(self.achievement_priority_list) - 1:
            return  # Already at bottom

        # Swap with next item
        self.achievement_priority_list[index], self.achievement_priority_list[index+1] = \
            self.achievement_priority_list[index+1], self.achievement_priority_list[index]

        # Rebuild display and maintain selection
        selected_building = self.selected_priority_building.building_id
        self.update_priority_listbox()

        # Re-select the moved building
        if index+1 < len(self.priority_building_cards):
            self.select_priority_building(self.priority_building_cards[index+1], selected_building)
            # Scroll to show the selected card
            self.achievement_priority_canvas.yview_moveto(min(1.0, (index+1) / len(self.priority_building_cards)))

        # Save changes to settings
        self.save_settings()

    def reset_building_priority(self):
        """Reset building priority to default order"""
        default_order = [
            'eagle_artillery', 'monolith', 'xbow', 'inferno_tower', 'scattershot',
            'spell_tower', 'multi_archer_tower', 'ricochet_cannon', 'firespitter', 'multi_gear_tower'
        ]
        self.achievement_priority_list = default_order.copy()
        self.selected_priority_building = None
        self.update_priority_listbox()
        self.save_settings()
        messagebox.showinfo("Priority Reset", "Building priority order has been reset to default.")
