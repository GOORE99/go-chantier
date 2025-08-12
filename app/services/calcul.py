import cv2
import numpy as np


def compute_image_difference(path_a: str, path_b: str, out_path: str) -> bool:
    """Compute absolute difference between two images and save a heatmap PNG.

    Returns True on success, False otherwise.
    """
    try:
        img_a = cv2.imread(path_a, cv2.IMREAD_COLOR)
        img_b = cv2.imread(path_b, cv2.IMREAD_COLOR)
        if img_a is None or img_b is None:
            return False
        # Resize B to A if needed
        if img_a.shape[:2] != img_b.shape[:2]:
            img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        diff = cv2.absdiff(img_a, img_b)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        # Normalize to 0..255
        norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        # Apply color map for visibility
        heat = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        return cv2.imwrite(out_path, heat)
    except Exception:
        return False