import cv2
import numpy as np

# --- Simple RGB thresholds for demo classification (optional) ---
RGB_INTERVALS = {
    "Argile": {"R": (111, 228), "G": (20, 141), "B": (0, 90)},
    "GNT": {"R": (150, 222), "G": (146, 228), "B": (145, 222)},
    "Bitume": {"R": (20, 114), "G": (34, 110), "B": (19, 168)},
}
RGB_CLASS_COLORS = {
    "Argile": [255, 200, 0],
    "GNT": [160, 160, 160],
    "Bitume": [0, 0, 0],
    "Inconnu": [255, 0, 255],
}


def detecter_classe(pixel_rgb):
    r, g, b = pixel_rgb
    for classe, interv in RGB_INTERVALS.items():
        if interv["R"][0] <= r <= interv["R"][1] and \
           interv["G"][0] <= g <= interv["G"][1] and \
           interv["B"][0] <= b <= interv["B"][1]:
            return classe
    return "Inconnu"


def clasification_image_drone(image_path):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(image_path)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = image_rgb.shape

    image_classifiee = np.zeros((h, w, 3), dtype=np.uint8)
    classes_detectees = {"Argile": 0, "GNT": 0, "Bitume": 0, "Inconnu": 0}

    for y in range(h):
        for x in range(w):
            pixel = image_rgb[y, x]
            classe = detecter_classe(pixel)
            classes_detectees[classe] += 1
            image_classifiee[y, x] = RGB_CLASS_COLORS[classe]

    return image_rgb, image_classifiee, classes_detectees


def show_classes_results(classes_detectees):
    total = sum(classes_detectees.values()) or 1
    lines = {}
    for classe, nb in classes_detectees.items():
        pourcentage = (nb / total) * 100.0
        lines[classe] = {"pixels": nb, "pct": round(pourcentage, 2)}
    return lines


# --- Analysis: difference between two images ---
def compute_image_difference(image_a_path: str, image_b_path: str, output_path: str) -> None:
    """Compute absolute difference between two images and save a heatmap PNG.

    If sizes differ, image B is resized to image A.
    The output is saved at output_path (PNG).
    """
    img_a = cv2.imread(image_a_path)
    img_b = cv2.imread(image_b_path)
    if img_a is None or img_b is None:
        raise FileNotFoundError("One of input images not found")
    if img_a.shape[:2] != img_b.shape[:2]:
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]), interpolation=cv2.INTER_LINEAR)

    diff = cv2.absdiff(img_a, img_b)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    # enhance contrast
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    heatmap = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img_a, 0.6, heatmap, 0.4, 0)
    cv2.imwrite(output_path, overlay)