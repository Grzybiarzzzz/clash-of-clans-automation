"""
Test Deployment Coordinates
Simple program to test troop deployment coordinates at 16 clicks per second.
Press F4 to deploy troops over the test coordinates.
Press ESC to exit.

Note: This program does NOT move the camera - it only deploys troops by clicking.
"""

import pyautogui
import keyboard
import time

# TEST COORDINATES - Modify these to test different deployment patterns
TEST_COORDINATES = [
    (1399, 28),
    (1406, 32),
    (1429, 48),
    (1439, 56),
    (1455, 67),
    (1458, 69),
    (1484, 87),
    (1512, 109),
    (1548, 134),
    (1559, 141),
    (1567, 146),
    (1578, 153),
    (1601, 171),
    (1624, 188),
    (1635, 198),
    (1656, 217),
    (1685, 234),
    (1719, 250),
    (1728, 254),
    (1759, 277),
    (1787, 300),
    (1811, 321),
    (1849, 349),
    (1877, 371),
    (1899, 387),
    (1929, 413),
    (1946, 428),
    (1982, 462),
    (2006, 483),
    (2034, 503),
    (2052, 516),
    (2079, 535),
    (2095, 545),
    (2122, 561),
    (2149, 583),
    (2183, 608),
    (2210, 630),
    (2223, 646),
    (2224, 680),
    (2207, 722),
    (2184, 755),
    (2167, 767),
    (2147, 783),
    (2129, 806),
    (2106, 832),
    (2093, 844),
    (2073, 862),
    (2033, 886),
    (1991, 911),
    (1941, 939),
    (1910, 956),
    (1877, 975),
    (1845, 995),
    (1817, 1013),
    (1748, 1069),
    (1724, 1106),
    (1704, 1142),
    (1664, 1185),
    (1627, 1218),
    (1576, 1270),
    (1534, 1301),
    (1491, 1328),
    (1441, 1363),
    (1409, 1381),
    (1370, 1403),
    (1335, 1412),
    (1294, 1408),
    (1234, 1399),
    (1197, 1388),
    (1167, 1377),
    (1135, 1351),
    (1098, 1324),
    (1069, 1297),
    (1035, 1270),
    (1009, 1252),
    (970, 1222),
    (940, 1202),
    (886, 1168),
    (876, 1158),
    (843, 1126),
    (789, 1087),
    (748, 1061),
    (704, 1040),
    (634, 1002),
    (576, 964),
    (525, 932),
    (499, 910),
    (480, 892),
    (455, 867),
    (434, 846),
    (403, 814),
    (364, 782),
    (335, 749),
    (312, 710),
    (298, 676),
    (310, 662),
    (351, 633),
    (402, 587),
    (427, 569),
    (481, 536),
    (547, 473),
    (564, 455),
    (622, 423),
    (696, 377),
    (726, 351),
    (772, 316),
    (844, 275),
    (902, 233),
    (929, 206),
    (980, 166),
    (998, 149),
    (1046, 109),
    (1094, 81),
    (1148, 56),
    (1192, 30),
    (1215, 5),
    (1225, 0),
]

def deploy_troops_hold_and_drag(coordinates):
    """
    Deploy troops by clicking at each coordinate at 16 clicks per second.
    NO camera movement - only troop deployment clicking.
    """
    if not coordinates or len(coordinates) == 0:
        print("[ERROR] No coordinates provided!")
        return

    clicks_per_second = 16
    delay_between_clicks = 1.0 / clicks_per_second  # 0.0625 seconds per click

    print(f"[DEPLOY] Starting deployment at {clicks_per_second} clicks/second over {len(coordinates)} coordinates...")
    print(f"[DEPLOY] Delay between clicks: {delay_between_clicks:.4f}s")

    start_time = time.time()

    # Click at each coordinate - NO PRINTING in loop for speed
    for i, coord in enumerate(coordinates):
        pyautogui.moveTo(coord[0], coord[1], duration=0)
        pyautogui.mouseDown()
        pyautogui.mouseUp()

        # Calculate time to sleep to maintain 16 CPS accounting for movement overhead
        elapsed = time.time() - start_time
        target_time = (i + 1) * delay_between_clicks
        sleep_time = target_time - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    total_time = time.time() - start_time
    actual_cps = len(coordinates) / total_time

    print(f"[DEPLOY] ✓ Deployment complete!")
    print(f"[DEPLOY] {len(coordinates)} clicks in {total_time:.2f}s")
    print(f"[DEPLOY] Actual speed: {actual_cps:.2f} clicks/second")

def on_deploy_key():
    """Called when F4 is pressed"""
    print("\n" + "="*60)
    print("[F4 PRESSED] Starting deployment test at 16 clicks/second...")
    print("="*60)
    deploy_troops_hold_and_drag(TEST_COORDINATES)
    print("="*60)
    print("[READY] Press F4 again to repeat, or ESC to exit")
    print("="*60 + "\n")

def main():
    print("="*60)
    print("DEPLOYMENT COORDINATE TESTER")
    print("="*60)
    print(f"Test coordinates loaded: {len(TEST_COORDINATES)} positions")
    print("\nCoordinates:")
    for i, coord in enumerate(TEST_COORDINATES, 1):
        print(f"  {i}. {coord}")
    print("\n" + "="*60)
    print("CONTROLS:")
    print("  F4  - Deploy troops at 16 clicks/second")
    print("  ESC - Exit program")
    print("="*60)
    print("\n[READY] Load into a battle manually, select troop, then press F4 to test deployment")
    print("[NOTE] No camera movement - only troop deployment clicking (16 clicks/sec)")

    # Register hotkeys
    keyboard.on_press_key('F4', lambda _: on_deploy_key())

    # Wait for ESC to exit
    keyboard.wait('esc')

    print("\n[EXIT] Program terminated")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[EXIT] Program interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
