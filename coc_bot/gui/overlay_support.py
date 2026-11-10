"""Optional import of the detection overlay."""

try:
    from coc_bot.visualization_overlay import VisualizationOverlay  # noqa: F401 (re-exported)
    OVERLAY_AVAILABLE = True
except ImportError:
    OVERLAY_AVAILABLE = False
    VisualizationOverlay = None
    print("Warning: visualization_overlay module not found. Overlay feature disabled.")
