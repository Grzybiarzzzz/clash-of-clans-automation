"""Night mode and detection-overlay toggles."""

from tkinter import ttk

from coc_bot.gui.overlay_support import OVERLAY_AVAILABLE

class NightModeMixin:
    """Night mode and detection-overlay toggles. Mixin for BotGUI."""

    def toggle_night_mode(self):
        """Toggle night mode on/off and apply styles immediately"""
        # Update from checkbox state
        self.night_mode = self.night_mode_var.get()

        if self.night_mode:
            self.enable_night_mode()
        else:
            self.disable_night_mode()

        # Save settings to persist night mode preference
        self.save_global_settings()

    def toggle_overlay(self):
        """Toggle visualization overlay on/off"""
        self.overlay_enabled = self.overlay_enabled_var.get()
        print(f"[GUI] toggle_overlay called: overlay_enabled = {self.overlay_enabled}")
        print(f"[GUI] self.overlay exists: {self.overlay is not None}")
        print(f"[GUI] OVERLAY_AVAILABLE: {OVERLAY_AVAILABLE}")

        if self.overlay and OVERLAY_AVAILABLE:
            if self.overlay_enabled:
                self.overlay.show()
                self.log_message("Detection overlay enabled")
                print("[GUI] Overlay.show() called")
            else:
                self.overlay.hide()
                self.log_message("Detection overlay disabled")
                print("[GUI] Overlay.hide() called")
        else:
            print("[GUI] WARNING: Overlay not available or not initialized!")

        # Show/hide the "Hide Low Confidence" checkbox based on overlay state
        if self.overlay_enabled:
            if not getattr(self, 'overlay_hide_low_conf_row_visible', False):
                self.overlay_hide_low_conf_label.grid(row=3, column=0, sticky='w', padx=(0, 10))
                self.overlay_hide_low_conf_check.grid(row=3, column=1, sticky='w')
                self.overlay_hide_low_conf_row_visible = True
        else:
            if getattr(self, 'overlay_hide_low_conf_row_visible', False):
                self.overlay_hide_low_conf_label.grid_forget()
                self.overlay_hide_low_conf_check.grid_forget()
                self.overlay_hide_low_conf_row_visible = False

        # Save settings to persist overlay preference
        self.save_global_settings()

    def enable_night_mode(self):
        """Enable dark theme with improved colors"""
        style = ttk.Style()
        style.theme_use('clam')

        # Dark theme colors - more modern palette
        bg_dark = '#1e1e1e'
        bg_frame = '#252525'
        bg_input = '#2d2d2d'
        fg_text = '#e0e0e0'
        fg_accent = '#4a9eff'

        # Configure all ttk widgets
        style.configure('.', background=bg_dark, foreground=fg_text)
        style.configure('TLabel', background=bg_dark, foreground=fg_text)
        style.configure('TLabelframe', background=bg_dark, foreground=fg_text)
        style.configure('TLabelframe.Label', background=bg_dark, foreground=fg_accent, font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', background=bg_frame, foreground=fg_text)
        style.configure('TFrame', background=bg_dark)
        style.configure('TEntry', fieldbackground=bg_input, foreground=fg_text, insertcolor=fg_text)
        style.configure('TCheckbutton', background=bg_dark, foreground=fg_text)
        style.configure('TRadiobutton', background=bg_dark, foreground=fg_text)
        style.configure('TSpinbox', fieldbackground=bg_input, foreground=fg_text, arrowcolor=fg_text)
        style.configure('TCombobox', fieldbackground=bg_input, foreground=fg_text, arrowcolor=fg_text)
        style.configure('TNotebook', background=bg_dark)
        style.configure('TNotebook.Tab', background=bg_frame, foreground=fg_text)

        # Map states for interactive elements
        style.map('TButton',
                  background=[('active', bg_input), ('disabled', bg_frame)],
                  foreground=[('disabled', '#666666')])
        style.map('TCheckbutton',
                  background=[('active', bg_dark)])
        style.map('TCombobox',
                  fieldbackground=[('readonly', bg_input)])

        # Configure root window
        self.root.configure(bg=bg_dark)

        # Update text widgets (non-ttk)
        try:
            self.log_text.configure(bg=bg_input, fg=fg_text, insertbackground=fg_text)
            self.debug_text.configure(bg=bg_input, fg=fg_text, insertbackground=fg_text)
        except:
            pass

    def disable_night_mode(self):
        """Restore default light theme"""
        style = ttk.Style()
        style.theme_use('vista')  # Modern Windows theme

        # Reset to default colors
        style.configure('.', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabel', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabelframe', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TFrame', background='SystemButtonFace')
        style.configure('TEntry', fieldbackground='white', foreground='black')
        style.configure('TCheckbutton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TRadiobutton', background='SystemButtonFace', foreground='SystemButtonText')
        style.configure('TSpinbox', fieldbackground='white', foreground='black')
        style.configure('TCombobox', fieldbackground='white', foreground='black')

        # Configure root window
        self.root.configure(bg='SystemButtonFace')

        # Update text widgets (non-ttk)
        try:
            self.log_text.configure(bg='white', fg='black', insertbackground='black')
            self.debug_text.configure(bg='white', fg='black', insertbackground='black')
        except:
            pass
