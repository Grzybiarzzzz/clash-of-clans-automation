"""
Visualization Overlay for Clash of Clans Bot

A transparent overlay window that displays real-time detection visualization:
- OCR regions with extracted values and confidence scores
- Building detections with bounding boxes
- Troop deployment positions and spell targets

Usage:
    overlay = VisualizationOverlay(parent_window)
    overlay.show()
    overlay.draw_rect(100, 100, 200, 50, '#00FF00', 'Gold: 850,000 (94%)')
    overlay.update()
"""

import tkinter as tk
from typing import Optional, Tuple, List
import threading


class VisualizationOverlay:
    """Transparent overlay window for visualizing bot detections."""

    def __init__(self, parent: tk.Tk, width: int = 2560, height: int = 1440):
        """
        Initialize the overlay window.

        Args:
            parent: Parent Tkinter window
            width: Overlay width (should match game resolution)
            height: Overlay height (should match game resolution)
        """
        self.parent = parent
        self.width = width
        self.height = height
        self.enabled = False
        self._draw_queue: List[tuple] = []
        self._lock = threading.Lock()

        # Create overlay window
        self.window = tk.Toplevel(parent)
        self.window.title("Detection Overlay")
        self.window.overrideredirect(True)  # No title bar/borders
        self.window.attributes('-topmost', True)  # Always on top
        self.window.geometry(f'{width}x{height}+0+0')  # Full screen at top-left

        # Try color-keyed transparency first (works on most Windows versions)
        # Using a specific magenta color that's unlikely to be used in drawings
        self.transparent_color = '#010101'  # Near-black that won't appear in drawings
        self.window.attributes('-transparentcolor', self.transparent_color)

        # Create canvas for drawing
        self.canvas = tk.Canvas(
            self.window,
            width=width,
            height=height,
            bg=self.transparent_color,  # Use the transparent color as background
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)

        # Also try alpha transparency (Windows 7+)
        try:
            self.window.attributes('-alpha', 0.95)  # Slight transparency to help with layering
        except:
            pass

        print(f"[Overlay] Window created: {width}x{height} at (0,0)")
        print(f"[Overlay] Transparent color: {self.transparent_color}")

        # Start hidden (click-through will be set when shown)
        self.window.withdraw()

        # Schedule queue processing
        self._process_queue()

        # Schedule periodic topmost refresh to stay above fullscreen games
        self._refresh_topmost()

    def _refresh_topmost(self):
        """Periodically refresh topmost status to stay above fullscreen games."""
        if self.enabled and self.window.winfo_exists():
            try:
                self.window.attributes('-topmost', True)
                self.window.lift()
            except:
                pass
        # Reschedule every 500ms
        if self.window.winfo_exists():
            self.window.after(500, self._refresh_topmost)

    def _set_click_through(self):
        """Make the window click-through using Windows API."""
        try:
            import ctypes

            # Need to update the window first to get valid handle
            self.window.update_idletasks()

            # Get the HWND (window handle) - need to get it from the Tk window
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
            if hwnd == 0:
                # If no parent, use the window id directly
                hwnd = self.window.winfo_id()

            # Constants for extended window styles
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_TOOLWINDOW = 0x80  # Hide from taskbar

            # Get current style
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # Add layered, transparent, and toolwindow styles
            new_style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

            print(f"[Overlay] Click-through enabled (hwnd={hwnd})")
        except Exception as e:
            print(f"Warning: Could not set click-through: {e}")

    def _process_queue(self):
        """Process queued draw commands on the main thread."""
        with self._lock:
            for cmd in self._draw_queue:
                self._execute_draw(cmd)
            self._draw_queue.clear()

        # Schedule next processing
        if self.window.winfo_exists():
            self.window.after(50, self._process_queue)

    def _execute_draw(self, cmd: tuple):
        """Execute a single draw command."""
        cmd_type = cmd[0]

        if cmd_type == 'rect':
            _, x, y, w, h, color, label, dashed = cmd
            if dashed:
                self.canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline=color, width=1, dash=(4, 4)
                )
            else:
                self.canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline=color, width=2
                )
            if label:
                self._draw_outlined_text(x + 5, y - 20, label, color)

        elif cmd_type == 'text':
            _, x, y, text, color = cmd
            self._draw_outlined_text(x, y, text, color)

        elif cmd_type == 'circle':
            _, x, y, radius, color, filled = cmd
            if filled:
                self.canvas.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    outline=color, fill=color, width=2
                )
            else:
                self.canvas.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    outline=color, width=2
                )

        elif cmd_type == 'crosshair':
            _, x, y, size, color, label = cmd
            # Draw crosshair
            self.canvas.create_line(x - size, y, x + size, y, fill=color, width=2)
            self.canvas.create_line(x, y - size, x, y + size, fill=color, width=2)
            # Draw circle around crosshair
            self.canvas.create_oval(
                x - size, y - size, x + size, y + size,
                outline=color, width=2
            )
            if label:
                self._draw_outlined_text(x + size + 5, y - 10, label, color)

        elif cmd_type == 'line':
            _, x1, y1, x2, y2, color = cmd
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

        elif cmd_type == 'side_highlight':
            _, side, color = cmd
            self._draw_side_highlight(side, color)

    def _draw_outlined_text(self, x: int, y: int, text: str, color: str):
        """Draw text with black outline for visibility."""
        # Draw black outline (offset in 8 directions)
        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
            self.canvas.create_text(
                x + dx, y + dy,
                text=text, anchor='nw',
                font=('Consolas', 12, 'bold'),
                fill='black'
            )
        # Draw main text
        self.canvas.create_text(
            x, y, text=text, anchor='nw',
            font=('Consolas', 12, 'bold'),
            fill=color
        )

    def _draw_side_highlight(self, side: str, color: str):
        """Draw an arrow indicating the attack side."""
        margin = 100
        arrow_size = 50

        if side == 'left':
            # Arrow pointing right from left edge
            cx, cy = margin, self.height // 2
            points = [cx, cy - arrow_size, cx + arrow_size * 2, cy, cx, cy + arrow_size]
        elif side == 'right':
            # Arrow pointing left from right edge
            cx, cy = self.width - margin, self.height // 2
            points = [cx, cy - arrow_size, cx - arrow_size * 2, cy, cx, cy + arrow_size]
        elif side == 'up':
            # Arrow pointing down from top edge
            cx, cy = self.width // 2, margin
            points = [cx - arrow_size, cy, cx, cy + arrow_size * 2, cx + arrow_size, cy]
        elif side == 'down':
            # Arrow pointing up from bottom edge
            cx, cy = self.width // 2, self.height - margin
            points = [cx - arrow_size, cy, cx, cy - arrow_size * 2, cx + arrow_size, cy]
        else:
            return

        self.canvas.create_polygon(points, fill=color, outline='white', width=2)
        self._draw_outlined_text(cx - 40, cy + arrow_size + 10, f"ATTACK: {side.upper()}", color)

    def show(self):
        """Show the overlay window."""
        self.enabled = True
        self.window.deiconify()
        self.window.update_idletasks()  # Ensure window is fully created
        self.window.lift()
        self.window.attributes('-topmost', True)
        # Apply click-through after window is visible
        self._set_click_through()
        print("[Overlay] Overlay window shown")

    def hide(self):
        """Hide the overlay window."""
        self.enabled = False
        self.window.withdraw()

    def toggle(self):
        """Toggle overlay visibility."""
        if self.enabled:
            self.hide()
        else:
            self.show()

    def clear(self):
        """Clear all drawings from the canvas."""
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('clear',))
            # Direct clear for responsiveness
            self.window.after(0, lambda: self.canvas.delete('all'))

    def update(self):
        """Force update of the canvas (called after drawing operations)."""
        if self.enabled:
            self.window.after(0, lambda: self.canvas.update_idletasks())

    # === Public Drawing Methods (Thread-Safe) ===

    def draw_rect(self, x: int, y: int, w: int, h: int, color: str,
                  label: str = '', dashed: bool = False):
        """
        Draw a rectangle with optional label.

        Args:
            x, y: Top-left corner coordinates
            w, h: Width and height
            color: Outline color (hex string like '#FF0000')
            label: Optional text label above rectangle
            dashed: If True, draw dashed outline (for OCR regions)
        """
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('rect', x, y, w, h, color, label, dashed))

    def draw_ocr_region(self, region: Tuple[int, int, int, int], value: str,
                        confidence: float, resource_type: str = ''):
        """
        Draw an OCR region with value and confidence.

        Args:
            region: (x1, y1, x2, y2) bounding box
            value: Extracted OCR value
            confidence: Confidence score (0-100)
            resource_type: Optional label like 'GOLD', 'ELIXIR', etc.
        """
        if not self.enabled:
            return

        x1, y1, x2, y2 = region
        w, h = x2 - x1, y2 - y1

        # Color based on confidence
        if confidence >= 80:
            color = '#00FF00'  # Green - high confidence
        elif confidence >= 50:
            color = '#FFFF00'  # Yellow - medium confidence
        else:
            color = '#FF0000'  # Red - low confidence

        label = f"{resource_type}: {value} ({confidence:.0f}%)" if resource_type else f"{value} ({confidence:.0f}%)"
        self.draw_rect(x1, y1, w, h, color, label, dashed=True)

    def draw_detection(self, x: int, y: int, w: int, h: int,
                       building_type: str, level: Optional[int], confidence: float,
                       color: str):
        """
        Draw a building detection box.

        Args:
            x, y: Top-left corner
            w, h: Width and height
            building_type: Type of building detected
            level: Building level (if detected)
            confidence: Match confidence (0-1)
            color: Box color
        """
        if not self.enabled:
            return

        level_str = f" Lv{level}" if level else ""
        label = f"{building_type}{level_str} ({confidence*100:.0f}%)"
        self.draw_rect(x, y, w, h, color, label)

    def draw_text(self, x: int, y: int, text: str, color: str = '#FFFFFF'):
        """Draw text at specified position."""
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('text', x, y, text, color))

    def draw_circle(self, x: int, y: int, radius: int = 10,
                    color: str = '#FFFF00', filled: bool = True):
        """Draw a circle (for troop deployment positions)."""
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('circle', x, y, radius, color, filled))

    def draw_crosshair(self, x: int, y: int, size: int = 20,
                       color: str = '#FF00FF', label: str = ''):
        """Draw a crosshair (for spell targets)."""
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('crosshair', x, y, size, color, label))

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: str = '#FFFFFF'):
        """Draw a line between two points."""
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('line', x1, y1, x2, y2, color))

    def highlight_side(self, side: str, color: str = '#00FF00'):
        """
        Highlight the chosen attack side with an arrow.

        Args:
            side: 'left', 'right', 'up', or 'down'
            color: Arrow color
        """
        if self.enabled:
            with self._lock:
                self._draw_queue.append(('side_highlight', side, color))

    def draw_deployment_plan(self, positions: List[Tuple[int, int]],
                             color: str = '#FFFF00'):
        """
        Draw all planned deployment positions.

        Args:
            positions: List of (x, y) coordinates
            color: Circle color
        """
        for i, (x, y) in enumerate(positions):
            self.draw_circle(x, y, 8, color)
            self.draw_text(x + 10, y - 5, str(i + 1), color)

    def draw_spell_targets(self, targets: List[Tuple[int, int, str]],
                           color: str = '#FF00FF'):
        """
        Draw spell target locations.

        Args:
            targets: List of (x, y, spell_name) tuples
            color: Crosshair color
        """
        for x, y, spell_name in targets:
            self.draw_crosshair(x, y, 25, color, spell_name)

    def save_screenshot(self, folder: str = 'screenshots/debug/overlay'):
        """
        Save a screenshot of the overlay with black background.

        Args:
            folder: Folder to save screenshots (will be created if doesn't exist)

        Returns:
            Path to saved file, or None if failed
        """
        if not self.enabled:
            print("[Overlay] Cannot save screenshot - overlay is disabled")
            return None

        try:
            import os
            from datetime import datetime
            from PIL import ImageGrab

            # Create folder if it doesn't exist
            os.makedirs(folder, exist_ok=True)

            # Temporarily make background solid black (not transparent)
            original_bg = self.canvas.cget('bg')
            self.canvas.configure(bg='#000000')
            self.window.attributes('-transparentcolor', '')  # Disable transparency
            self.window.update_idletasks()
            self.window.update()

            # Small delay to ensure window is rendered
            import time
            time.sleep(0.1)

            # Capture the overlay window area
            x = self.window.winfo_rootx()
            y = self.window.winfo_rooty()
            w = self.window.winfo_width()
            h = self.window.winfo_height()

            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))

            # Restore transparent background
            self.canvas.configure(bg=self.transparent_color)
            self.window.attributes('-transparentcolor', self.transparent_color)
            self.window.update_idletasks()

            # Save with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(folder, f'overlay_{timestamp}.png')
            screenshot.save(filename)

            print(f"[Overlay] Screenshot saved: {filename}")
            return filename

        except Exception as e:
            print(f"[Overlay] Failed to save screenshot: {e}")
            # Try to restore transparency
            try:
                self.canvas.configure(bg=self.transparent_color)
                self.window.attributes('-transparentcolor', self.transparent_color)
            except:
                pass
            return None

    def destroy(self):
        """Destroy the overlay window."""
        try:
            self.window.destroy()
        except:
            pass


# Standalone test
if __name__ == '__main__':

    print("=" * 60)
    print("VISUALIZATION OVERLAY TEST")
    print("=" * 60)
    print("\nThis test creates a transparent overlay window.")
    print("When enabled, you should see colored rectangles and text")
    print("floating on top of other windows.\n")

    root = tk.Tk()
    root.title("Overlay Test Control")
    root.geometry("400x300+100+100")

    overlay = VisualizationOverlay(root)

    status_var = tk.StringVar(value="Overlay: OFF")

    def toggle_overlay():
        overlay.toggle()
        if overlay.enabled:
            status_var.set("Overlay: ON - Look for colored boxes on screen!")
            # Draw some test elements at various screen positions
            overlay.clear()
            # Draw in center of screen (assuming 2560x1440)
            overlay.draw_text(1200, 100, "=== OVERLAY TEST ===", '#00FF00')
            overlay.draw_ocr_region((100, 100, 300, 140), "850,000", 94, "GOLD")
            overlay.draw_ocr_region((100, 160, 300, 200), "1,200,000", 67, "ELIXIR")
            overlay.draw_ocr_region((100, 220, 300, 260), "5,000", 35, "DARK (low conf)")
            overlay.draw_detection(500, 300, 80, 80, "Air Defense", 12, 0.87, '#FF4444')
            overlay.draw_detection(700, 400, 100, 100, "Town Hall", 15, 0.92, '#AA00FF')
            overlay.draw_detection(900, 350, 70, 70, "Eagle Artillery", None, 0.78, '#FF8800')
            overlay.draw_crosshair(600, 500, 25, '#FF00FF', "Lightning")
            overlay.draw_crosshair(750, 550, 25, '#FF00FF', "Earthquake")
            overlay.draw_circle(400, 600, 10, '#FFFF00')
            overlay.draw_circle(450, 620, 10, '#FFFF00')
            overlay.draw_circle(500, 640, 10, '#FFFF00')
            overlay.highlight_side('left', '#00FF00')
            overlay.update()
            print("[TEST] Overlay enabled - elements drawn")
        else:
            status_var.set("Overlay: OFF")
            print("[TEST] Overlay disabled")

    # UI
    tk.Label(root, text="Overlay Test Control Panel", font=('Arial', 14, 'bold')).pack(pady=10)
    tk.Label(root, textvariable=status_var, font=('Arial', 12)).pack(pady=5)

    tk.Button(root, text="Toggle Overlay (ON/OFF)", command=toggle_overlay,
              font=('Arial', 12), bg='#4CAF50', fg='white').pack(pady=20)

    tk.Label(root, text="When ON, look for:\n"
                        "- Green/Yellow/Red boxes (OCR regions)\n"
                        "- Red box (Air Defense)\n"
                        "- Purple box (Town Hall)\n"
                        "- Orange box (Eagle Artillery)\n"
                        "- Magenta crosshairs (spell targets)\n"
                        "- Yellow circles (deployment)\n"
                        "- Green arrow (attack side)",
             justify='left', font=('Arial', 10)).pack(pady=10)

    tk.Label(root, text="Overlay should appear on TOP of other windows\n"
                        "and you should be able to click THROUGH it.",
             fg='gray', font=('Arial', 9)).pack(pady=5)

    # Debug: solid color mode to verify overlay is visible
    debug_mode = tk.BooleanVar(value=False)

    def toggle_debug_mode():
        if debug_mode.get():
            # Make overlay solid (not transparent) for debugging
            overlay.canvas.configure(bg='#333333')
            overlay.window.attributes('-transparentcolor', '')  # Disable transparency
            overlay.window.attributes('-alpha', 0.7)  # Semi-transparent
            print("[DEBUG] Overlay in SOLID mode - you should see a dark gray overlay")
        else:
            # Restore transparent mode
            overlay.canvas.configure(bg=overlay.transparent_color)
            overlay.window.attributes('-transparentcolor', overlay.transparent_color)
            overlay.window.attributes('-alpha', 0.95)
            print("[DEBUG] Overlay in TRANSPARENT mode")

    tk.Checkbutton(root, text="Debug: Show solid overlay (to verify position)",
                   variable=debug_mode, command=toggle_debug_mode).pack(pady=5)

    print("\nWindow created. Click 'Toggle Overlay' to test.")
    print("The overlay should appear on top of all windows.")
    print("If you can't see anything, try enabling 'Debug: Show solid overlay'")
    print("to verify the overlay window is in the right position.\n")

    root.mainloop()
