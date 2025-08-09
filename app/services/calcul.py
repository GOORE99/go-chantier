import cv2
import numpy as np
import matplotlib.pyplot as plt

# utils
def detecter_classe(pixel_rgb):
    R, G, B = pixel_rgb
    for classe, interv in intervalles_rgb.items():
        if interv["R"][0] <= R <= interv["R"][1] and \
           interv["G"][0] <= G <= interv["G"][1] and \
           interv["B"][0] <= B <= interv["B"][1]:
            return classe
    return "Inconnu"

# function
def clasification_image_drone(image_path):
    # read image
    image_bgr = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = image_rgb.shape
    
    # classes intervals
    intervalles_rgb = {
        "Argile": {"R": (111, 228), "G": (20, 141), "B": (0, 90)},
        "GNT": {"R": (150, 222), "G": (146, 228), "B": (145, 222)},
        "Bitume": {"R": (20, 114), "G": (34, 110), "B": (19, 168)}
    }
    couleurs_classe = {
        "Argile": [255, 200, 0],
        "GNT": [160, 160, 160],
        "Bitume": [0, 0, 0],
        "Inconnu": [255, 0, 255]
    }
    
    # apply pixel classification
    image_classifiee = np.zeros((h, w, 3), dtype=np.uint8)
    classes_detectees = {"Argile": 0, "GNT": 0, "Bitume": 0, "Inconnu": 0}

    for y in range(h):
        for x in range(w):
            pixel = image_rgb[y, x]
            classe = detecter_classe(pixel)
            classes_detectees[classe] += 1
            image_classifiee[y, x] = couleurs_classe[classe]
            
    return image_rgb, image_classifiee, classes_detectees

def show_image_classified(image_rgb, image_classifiee):
    plt.figure(figsize=(14, 6))
    plt.subplot(1, 2, 1)
    plt.imshow(image_rgb)
    plt.title("Image drone originale")
    plt.axis("off")

    plt.subplot(1, 2, 2)
    plt.imshow(image_classifiee)
    plt.title("Image classifiée par seuil RGB")
    plt.axis("off")
    plt.show()
    
def show_classes_results(classes_detectees):
    print("📊 Nombre de pixels détectés par classe :")
    for classe, nb in classes_detectees.items():
        pourcentage = (nb / (h * w)) * 100
        print(f"- {classe} : {nb} pixels ({pourcentage:.2f}%)")