"""
GPU-accelerated template matching using PyTorch CUDA.
Offloads template matching from CPU to GPU to reduce CPU load.
"""

import cv2
import numpy as np

# Try to import torch, fall back to CPU-only mode if not available
try:
    import torch
    import torch.nn.functional as F

    GPU_AVAILABLE = torch.cuda.is_available()
    if GPU_AVAILABLE:
        DEVICE = torch.device("cuda")
        print(f"[GPU] CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        DEVICE = torch.device("cpu")
        print("[GPU] CUDA not available, using CPU")
except ImportError:
    GPU_AVAILABLE = False
    DEVICE = None
    print("[GPU] PyTorch not installed, using CPU-only OpenCV")


def gpu_match_template(image, template, method="TM_CCOEFF_NORMED"):
    """
    GPU-accelerated template matching using PyTorch convolutions.
    Matches OpenCV's TM_CCOEFF_NORMED algorithm exactly.

    Args:
        image: Base image (numpy array, BGR or grayscale)
        template: Template to find (numpy array, BGR or grayscale)
        method: Matching method (only TM_CCOEFF_NORMED supported for now)

    Returns:
        Result array same as cv2.matchTemplate output
    """
    if not GPU_AVAILABLE:
        # Fall back to CPU OpenCV
        return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

    # Convert to grayscale if needed (faster matching)
    if len(image.shape) == 3:
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        image_gray = image

    if len(template.shape) == 3:
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    else:
        template_gray = template

    th, tw = template_gray.shape[:2]
    n_pixels = float(th * tw)

    # Use float32 for speed (accuracy is still good enough for thresholding)
    img = torch.from_numpy(image_gray.astype(np.float32)).to(DEVICE)
    tpl = torch.from_numpy(template_gray.astype(np.float32)).to(DEVICE)

    # Prepare tensors for conv2d: (batch, channels, height, width)
    img_4d = img.unsqueeze(0).unsqueeze(0)

    # Template statistics (computed once)
    tpl_mean = tpl.mean()
    tpl_zm = tpl - tpl_mean  # zero-mean template
    tpl_norm_sq = (tpl_zm**2).sum()  # Σ(T - mean(T))²

    # Create kernels for convolutions
    ones_kernel = torch.ones(1, 1, th, tw, dtype=torch.float32, device=DEVICE)
    tpl_kernel = tpl.unsqueeze(0).unsqueeze(0)  # Original template

    # Compute local sums efficiently via convolution
    # local_sum[y,x] = Σ I(y+h, x+w) for all h,w in template region
    local_sum = F.conv2d(img_4d, ones_kernel)

    # local_sum_sq[y,x] = Σ I(y+h, x+w)² for all h,w in template region
    local_sum_sq = F.conv2d(img_4d**2, ones_kernel)

    # Cross-correlation: Σ I(y+h, x+w) * T(h,w)
    # Note: PyTorch conv2d already does correlation (not convolution), no flip needed
    cross_corr = F.conv2d(img_4d, tpl_kernel)

    # TM_CCOEFF_NORMED formula:
    # numerator = Σ(I - mean(I_patch)) * (T - mean(T))
    #           = Σ I*T - mean(I_patch)*Σ T - mean(T)*Σ I + n*mean(I_patch)*mean(T)
    #           = Σ I*T - n*mean(I_patch)*mean(T)
    #           = cross_corr - (local_sum/n) * n * mean(T)
    #           = cross_corr - local_sum * mean(T)
    numerator = cross_corr - local_sum * tpl_mean

    # denominator = sqrt(Σ(I - mean(I_patch))² * Σ(T - mean(T))²)
    # Σ(I - mean(I_patch))² = Σ I² - n * mean(I_patch)² = local_sum_sq - local_sum²/n
    local_var = local_sum_sq - (local_sum**2) / n_pixels
    local_var = torch.clamp(local_var, min=0)  # Numerical stability

    denominator = torch.sqrt(local_var * tpl_norm_sq)
    denominator = torch.clamp(denominator, min=1e-10)  # Avoid division by zero

    result = numerator / denominator

    # Clamp to valid correlation range [-1, 1]
    result = torch.clamp(result, -1.0, 1.0)

    return result.squeeze().cpu().numpy().astype(np.float32)


def gpu_match_multiple_templates(image, templates_list, threshold=0.6):
    """
    Match multiple templates against one image on GPU.
    Reuses the base image tensor for efficiency.

    Args:
        image: Base image (numpy array, BGR)
        templates_list: List of (template, template_name) tuples
        threshold: Minimum confidence threshold

    Returns:
        List of (x, y, confidence, template_name) for all matches above threshold
    """
    if not GPU_AVAILABLE or not templates_list:
        # Fall back to CPU
        results = []
        for template, name in templates_list:
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= threshold)
            for pt in zip(*locations[::-1]):
                x, y = pt
                conf = result[y, x]
                results.append((x, y, float(conf), name))
        return results

    # Convert base image to grayscale tensor once
    if len(image.shape) == 3:
        image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        image_gray = image

    img = torch.from_numpy(image_gray.astype(np.float32)).to(DEVICE)
    img_4d = img.unsqueeze(0).unsqueeze(0)
    img_sq = img_4d**2

    all_results = []

    # Process each template
    for template, template_name in templates_list:
        if len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template

        th, tw = template_gray.shape[:2]
        n_pixels = float(th * tw)

        tpl = torch.from_numpy(template_gray.astype(np.float32)).to(DEVICE)

        # Template statistics
        tpl_mean = tpl.mean()
        tpl_zm = tpl - tpl_mean
        tpl_norm_sq = (tpl_zm**2).sum()

        # Kernels
        ones_kernel = torch.ones(1, 1, th, tw, dtype=torch.float32, device=DEVICE)
        tpl_kernel = tpl.unsqueeze(0).unsqueeze(0)

        # Local sums
        local_sum = F.conv2d(img_4d, ones_kernel)
        local_sum_sq = F.conv2d(img_sq, ones_kernel)

        # Cross-correlation (PyTorch conv2d already does correlation, no flip needed)
        cross_corr = F.conv2d(img_4d, tpl_kernel)

        # TM_CCOEFF_NORMED: numerator = cross_corr - local_sum * tpl_mean
        numerator = cross_corr - local_sum * tpl_mean

        # Denominator
        local_var = local_sum_sq - (local_sum**2) / n_pixels
        local_var = torch.clamp(local_var, min=0)
        denominator = torch.sqrt(local_var * tpl_norm_sq)
        denominator = torch.clamp(denominator, min=1e-10)

        result = numerator / denominator
        result = torch.clamp(result, -1.0, 1.0)

        # Find matches above threshold
        result_np = result.squeeze().cpu().numpy()
        locations = np.where(result_np >= threshold)
        for pt in zip(*locations[::-1]):
            x, y = pt
            conf = result_np[y, x]
            all_results.append((x, y, float(conf), template_name))

    return all_results


def benchmark_gpu_vs_cpu(image, template, iterations=10):
    """
    Benchmark GPU vs CPU template matching.
    """
    import time

    # CPU benchmark
    start = time.perf_counter()
    for _ in range(iterations):
        cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    cpu_time = (time.perf_counter() - start) / iterations * 1000

    # GPU benchmark (if available)
    if GPU_AVAILABLE:
        # Warmup
        gpu_match_template(image, template)
        torch.cuda.synchronize()

        start = time.perf_counter()
        for _ in range(iterations):
            gpu_match_template(image, template)
            torch.cuda.synchronize()
        gpu_time = (time.perf_counter() - start) / iterations * 1000
    else:
        gpu_time = None

    return cpu_time, gpu_time


# Test on import
if __name__ == "__main__":
    print("\n=== GPU Template Matching Test ===")

    # Create test images (grayscale - matches bot's actual usage)
    image = np.random.randint(0, 255, (1440, 2560), dtype=np.uint8)
    template = np.random.randint(0, 255, (70, 70), dtype=np.uint8)

    cpu_time, gpu_time = benchmark_gpu_vs_cpu(image, template, iterations=20)

    print(f"CPU time: {cpu_time:.2f}ms per match")
    if gpu_time:
        print(f"GPU time: {gpu_time:.2f}ms per match")
        print(f"Speedup: {cpu_time / gpu_time:.2f}x")

    # Verify results match
    cpu_result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    gpu_result = gpu_match_template(image, template)

    max_diff = np.abs(cpu_result - gpu_result).max()
    print(f"Max difference CPU vs GPU: {max_diff:.8f}")
    print("Results match!" if max_diff < 0.001 else "WARNING: Results differ significantly!")
