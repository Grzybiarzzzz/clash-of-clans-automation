import sys
from PIL import ImageGrab
import ast


def get_coords():
    # If a tuple is provided as a single argument, parse it
    if len(sys.argv) == 2:
        try:
            coords = ast.literal_eval(sys.argv[1])
            if isinstance(coords, (tuple, list)) and len(coords) == 4:
                x1, y1, x2, y2 = map(int, coords)
                return x1, y1, x2, y2
        except Exception:
            print("Invalid tuple argument. Please provide a tuple like (x1, y1, x2, y2)")
    # If 4 separate arguments are provided
    if len(sys.argv) == 5:
        try:
            x1 = int(sys.argv[1])
            y1 = int(sys.argv[2])
            x2 = int(sys.argv[3])
            y2 = int(sys.argv[4])
            return x1, y1, x2, y2
        except ValueError:
            print("Invalid command-line arguments. Please enter integers.")
    # Prompt user for input
    print("Enter coordinates for screenshot region:")
    x1 = int(input("x1: "))
    y1 = int(input("y1: "))
    x2 = int(input("x2: "))
    y2 = int(input("y2: "))
    return x1, y1, x2, y2


def main():
    x1, y1, x2, y2 = get_coords()
    print(f"Capturing region: ({x1}, {y1}, {x2}, {y2})")
    import time
    time.sleep(2)
    img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    img.show()


if __name__ == "__main__":
    main() 