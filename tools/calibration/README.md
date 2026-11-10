# Arrow-color calibration

Capture a frame with the Giant Arrow glow visible, then run this command from the project root:

```bash
python tools/calibration/calibrate_arrow_hsv.py "path/to/screenshot.png"
```

Sample the glow and adjust the HSV sliders while inspecting the mask. Check both the trail and unrelated bright objects before using the selected ranges in `detect_queen_arrow_projectile` in `coc_bot/attacks/queen_arrow.py`. A setting that works for one capture may need adjustment for another scene.
