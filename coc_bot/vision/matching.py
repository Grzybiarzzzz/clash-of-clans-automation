"""Template matching entry point with optional GPU acceleration."""

import cv2

from coc_bot import runtime

# Always try to load GPU module, but use it only when GUI setting is enabled
try:
    from coc_bot.gpu_template_matching import gpu_match_template as _gpu_match_template, GPU_AVAILABLE

    if GPU_AVAILABLE:
        print("[GPU] GPU template matching AVAILABLE - toggle in Global Settings")
    else:
        print("[GPU] PyTorch CUDA not available - GPU option will use CPU fallback")
except ImportError as e:
    print(f"[GPU] gpu_template_matching module not found: {e}")
    GPU_AVAILABLE = False
    _gpu_match_template = None


def gpu_match_template(image, template, method="TM_CCOEFF_NORMED"):
    """Wrapper that checks GUI setting to decide GPU vs CPU"""
    # Check if GUI exists and GPU scanning is enabled
    use_gpu = GPU_AVAILABLE and hasattr(runtime.gui, "gpu_scanning_var") and runtime.gui.gpu_scanning_var.get()
    if use_gpu and _gpu_match_template:
        return _gpu_match_template(image, template, method)
    else:
        return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
