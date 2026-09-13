# Giant Arrow detection

The detector uses color-segmented glow observations rather than image templates. See the [computer-vision walkthrough](../../../docs/computer-vision.md) for line fitting, outlier rejection, and fallback behavior. Capture timing is configured in `config.py`; HSV thresholds are in `detect_queen_arrow_projectile` in `main.py`.
