from flask import Flask, render_template
from .services.calcul import clasification_image_drone, show_image_classified, show_classes_results

app = Flask(__name__)

@app.route("/")
def hello_world():
    return render_template("index.html")


@app.route("/suivi")
def suivi_page():
    return render_template("suivi.html")


@app.route("/calcul")
def calcul_page():
    image_path = "app/static/images/image.jpg"
    image_rgb, image_classifiee, classes_detectees = clasification_image_drone(image_path)
    show_image_classified(image_rgb, image_classifiee)
    show_classes_results(classes_detectees)
    return render_template("calcul.html")