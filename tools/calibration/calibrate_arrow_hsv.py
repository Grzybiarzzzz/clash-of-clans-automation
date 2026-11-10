"""
Interactive HSV Calibration Tool for Queen Giant Arrow Detection

This tool helps you find the perfect HSV range by:
1. Loading a screenshot with the arrow visible
2. Letting you click on arrow glow pixels to sample them
3. Showing real-time mask updates as you adjust HSV sliders
4. Providing the optimal HSV values for your detection

Instructions:
- Take a screenshot when the Queen arrow is visible (Print Screen)
- Save it as 'arrow_sample.png' in the bot's main directory
- Run this program
- Click on the arrow glow to sample pixels (5-10 clicks along the trail)
- Adjust sliders to tune the detection
- Copy the final HSV values to coc_bot/attacks/queen_arrow.py
"""

import sys
import os
import cv2
import numpy as np
from tkinter import Tk, Scale, Button, Label, HORIZONTAL, Frame, Text, END, Scrollbar, RIGHT, Y

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

class HSVCalibrator:
    def __init__(self, image_path):
        self.image_path = image_path
        self.original = None
        self.hsv = None
        self.sampled_pixels = []

        # Default HSV range (current from debug program)
        self.h_min = 70
        self.h_max = 100
        self.s_min = 50
        self.s_max = 255
        self.v_min = 100
        self.v_max = 255

        # Initialize GUI
        self.root = Tk()
        self.root.title("Queen Arrow HSV Calibrator")
        self.root.geometry("800x900")

        self.setup_gui()
        self.load_image()

    def load_image(self):
        """Load the image and convert to HSV"""
        if not os.path.exists(self.image_path):
            self.log(f"ERROR: Image not found: {self.image_path}")
            self.log("Please save a screenshot as 'arrow_sample.png' and restart.")
            return False

        self.original = cv2.imread(self.image_path)
        if self.original is None:
            self.log(f"ERROR: Failed to load image: {self.image_path}")
            return False

        self.hsv = cv2.cvtColor(self.original, cv2.COLOR_BGR2HSV)
        self.log(f"✓ Loaded image: {self.image_path}")
        self.log(f"  Size: {self.original.shape[1]}x{self.original.shape[0]}")
        self.log("\nClick on arrow glow pixels to sample them!")

        # Show original image
        cv2.imshow("Original - Click on Arrow Glow", self.original)
        cv2.setMouseCallback("Original - Click on Arrow Glow", self.on_mouse_click)

        self.update_mask()
        return True

    def on_mouse_click(self, event, x, y, flags, param):
        """Handle mouse clicks to sample pixels"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.hsv is not None:
                h, s, v = self.hsv[y, x]
                self.sampled_pixels.append((h, s, v, x, y))

                self.log(f"Sample {len(self.sampled_pixels)}: pos=({x},{y}) HSV=[{h:3d}, {s:3d}, {v:3d}]")

                # Draw circle on original image
                display = self.original.copy()
                for i, (_, _, _, px, py) in enumerate(self.sampled_pixels):
                    cv2.circle(display, (px, py), 5, (0, 255, 255), -1)
                    cv2.putText(display, str(i+1), (px+10, py),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                cv2.imshow("Original - Click on Arrow Glow", display)

                # Auto-adjust sliders based on samples
                if len(self.sampled_pixels) >= 3:
                    self.auto_adjust_from_samples()

    def auto_adjust_from_samples(self):
        """Automatically adjust HSV ranges based on sampled pixels"""
        if len(self.sampled_pixels) < 3:
            return

        h_values = [p[0] for p in self.sampled_pixels]
        s_values = [p[1] for p in self.sampled_pixels]
        v_values = [p[2] for p in self.sampled_pixels]

        # Set ranges with some margin (±5 for hue, ±30 for sat/val)
        self.h_min = max(0, min(h_values) - 5)
        self.h_max = min(180, max(h_values) + 5)
        self.s_min = max(0, min(s_values) - 30)
        self.s_max = 255  # Keep max at 255
        self.v_min = max(0, min(v_values) - 30)
        self.v_max = 255  # Keep max at 255

        # Update sliders
        self.slider_h_min.set(self.h_min)
        self.slider_h_max.set(self.h_max)
        self.slider_s_min.set(self.s_min)
        self.slider_s_max.set(self.s_max)
        self.slider_v_min.set(self.v_min)
        self.slider_v_max.set(self.v_max)

        self.log(f"\n[AUTO-ADJUST] Updated HSV range based on {len(self.sampled_pixels)} samples:")
        self.log(f"  LOWER = [{self.h_min:3d}, {self.s_min:3d}, {self.v_min:3d}]")
        self.log(f"  UPPER = [{self.h_max:3d}, {self.s_max:3d}, {self.v_max:3d}]")

    def update_mask(self, *args):
        """Update the mask based on current HSV values"""
        if self.hsv is None:
            return

        lower = np.array([self.h_min, self.s_min, self.v_min])
        upper = np.array([self.h_max, self.s_max, self.v_max])

        mask = cv2.inRange(self.hsv, lower, upper)

        # Calculate coverage
        total_pixels = mask.shape[0] * mask.shape[1]
        white_pixels = np.sum(mask == 255)
        coverage = (white_pixels / total_pixels) * 100

        # Create colored overlay
        overlay = self.original.copy()
        overlay[mask == 255] = [0, 255, 255]  # Cyan highlight

        # Create side-by-side view
        combined = np.hstack([self.original, overlay])

        # Add text overlay with current values
        text_y = 30
        cv2.putText(combined, f"HSV Range: [{self.h_min},{self.s_min},{self.v_min}] to [{self.h_max},{self.s_max},{self.v_max}]",
                   (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        text_y += 30
        cv2.putText(combined, f"Coverage: {coverage:.2f}% ({white_pixels} pixels)",
                   (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        text_y += 30
        cv2.putText(combined, f"Samples: {len(self.sampled_pixels)}",
                   (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Mask Result (Original | Overlay)", combined)

    def on_slider_change(self, val):
        """Handle slider value changes"""
        self.h_min = self.slider_h_min.get()
        self.h_max = self.slider_h_max.get()
        self.s_min = self.slider_s_min.get()
        self.s_max = self.slider_s_max.get()
        self.v_min = self.slider_v_min.get()
        self.v_max = self.slider_v_max.get()

        self.update_mask()

    def clear_samples(self):
        """Clear all sampled pixels"""
        self.sampled_pixels = []
        self.log("\n[CLEARED] All samples removed. Click on arrow glow to resample.")
        cv2.imshow("Original - Click on Arrow Glow", self.original)

    def export_values(self):
        """Export the current HSV values"""
        self.log("\n" + "="*70)
        self.log("FINAL HSV VALUES - Copy these to coc_bot/attacks/queen_arrow.py:")
        self.log("="*70)
        self.log(f"lower_cyan = np.array([{self.h_min}, {self.s_min}, {self.v_min}])")
        self.log(f"upper_cyan = np.array([{self.h_max}, {self.s_max}, {self.v_max}])")
        self.log("\nUpdate these lines in detect_queen_arrow_projectile (coc_bot/attacks/queen_arrow.py):")
        self.log("="*70)

    def log(self, message):
        """Add message to log window"""
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)

    def setup_gui(self):
        """Setup the GUI with sliders and controls"""
        # Title
        Label(self.root, text="Queen Arrow HSV Calibrator",
              font=("Arial", 16, "bold")).pack(pady=10)

        # Instructions
        Label(self.root, text="1. Click on arrow glow in the image window (5-10 clicks)\n2. Adjust sliders if needed\n3. Click Export when satisfied",
              justify="left", fg="blue").pack()

        # Sliders frame
        sliders_frame = Frame(self.root)
        sliders_frame.pack(pady=10, padx=20, fill="x")

        # Hue sliders
        Label(sliders_frame, text="Hue (H)", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=3, pady=5)

        Label(sliders_frame, text="Min:").grid(row=1, column=0)
        self.slider_h_min = Scale(sliders_frame, from_=0, to=180, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_h_min.set(self.h_min)
        self.slider_h_min.grid(row=1, column=1, columnspan=2)

        Label(sliders_frame, text="Max:").grid(row=2, column=0)
        self.slider_h_max = Scale(sliders_frame, from_=0, to=180, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_h_max.set(self.h_max)
        self.slider_h_max.grid(row=2, column=1, columnspan=2)

        # Saturation sliders
        Label(sliders_frame, text="Saturation (S)", font=("Arial", 12, "bold")).grid(row=3, column=0, columnspan=3, pady=(15,5))

        Label(sliders_frame, text="Min:").grid(row=4, column=0)
        self.slider_s_min = Scale(sliders_frame, from_=0, to=255, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_s_min.set(self.s_min)
        self.slider_s_min.grid(row=4, column=1, columnspan=2)

        Label(sliders_frame, text="Max:").grid(row=5, column=0)
        self.slider_s_max = Scale(sliders_frame, from_=0, to=255, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_s_max.set(self.s_max)
        self.slider_s_max.grid(row=5, column=1, columnspan=2)

        # Value sliders
        Label(sliders_frame, text="Value (V)", font=("Arial", 12, "bold")).grid(row=6, column=0, columnspan=3, pady=(15,5))

        Label(sliders_frame, text="Min:").grid(row=7, column=0)
        self.slider_v_min = Scale(sliders_frame, from_=0, to=255, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_v_min.set(self.v_min)
        self.slider_v_min.grid(row=7, column=1, columnspan=2)

        Label(sliders_frame, text="Max:").grid(row=8, column=0)
        self.slider_v_max = Scale(sliders_frame, from_=0, to=255, orient=HORIZONTAL,
                                   length=300, command=self.on_slider_change)
        self.slider_v_max.set(self.v_max)
        self.slider_v_max.grid(row=8, column=1, columnspan=2)

        # Buttons
        button_frame = Frame(self.root)
        button_frame.pack(pady=10)

        Button(button_frame, text="Clear Samples", command=self.clear_samples,
               bg="orange", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        Button(button_frame, text="Export Values", command=self.export_values,
               bg="green", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=5)

        # Log window
        Label(self.root, text="Log:", font=("Arial", 10, "bold")).pack(pady=(10,0))

        log_frame = Frame(self.root)
        log_frame.pack(pady=5, padx=20, fill="both", expand=True)

        scrollbar = Scrollbar(log_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.log_text = Text(log_frame, height=15, yscrollcommand=scrollbar.set,
                            font=("Courier", 9))
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

    def run(self):
        """Start the GUI"""
        self.root.mainloop()
        cv2.destroyAllWindows()

def main():
    print("="*70)
    print("QUEEN ARROW HSV CALIBRATOR")
    print("="*70)
    print("\nPreparation:")
    print("1. Take a screenshot when Queen arrow is visible (Print Screen)")
    print("2. Save it as 'arrow_sample.png' in the bot directory")
    print("3. Run this program")
    print("\nAlternatively, specify image path as argument:")
    print("  python calibrate_arrow_hsv.py path/to/screenshot.png")
    print("="*70 + "\n")

    # Get image path
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = "arrow_sample.png"

    calibrator = HSVCalibrator(image_path)
    calibrator.run()

if __name__ == "__main__":
    main()
