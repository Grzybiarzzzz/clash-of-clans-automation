import cv2
import numpy as np
import matplotlib.pyplot as plt

# Load image
path = 'image.jpg'
img = cv2.imread(path)

# Convert BGR (OpenCV default) to RGB (Matplotlib default) for display
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# Convert to HSV for data reading
hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

def onclick(event):
    # Check if the click was inside the image axes
    if event.xdata is not None and event.ydata is not None:
        x = int(event.xdata)
        y = int(event.ydata)

        # Get HSV value
        pixel = hsv_img[y, x]
        hue = pixel[0]
        saturation = pixel[1]
        value = pixel[2]

        print(f"Clicked at ({x}, {y})")
        print(f"HSV Value: [{hue}, {saturation}, {value}]")
        print(f"Lower Bound: [{max(0, hue-10)}, {max(0, saturation-40)}, {max(0, value-40)}]")
        print(f"Upper Bound: [{min(179, hue+10)}, {min(255, saturation+40)}, {min(255, value+40)}]")
        print("-" * 30)

fig, ax = plt.subplots()
ax.imshow(img_rgb)
ax.set_title("Click on a color to see HSV values")

# Connect the click event
cid = fig.canvas.mpl_connect('button_press_event', onclick)

plt.show()