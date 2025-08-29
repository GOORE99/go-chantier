from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime
from .services.calcul import compute_image_difference
try:
    from PIL import Image
except Exception:
    Image = None
import cv2
import numpy as np

app = Flask(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
DOCS_DIR = os.path.join(UPLOAD_DIR, "docs")
PREVIEWS_DIR = os.path.join(UPLOAD_DIR, "previews")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(PREVIEWS_DIR, exist_ok=True)

IMAGES_JSON = os.path.join(DATA_DIR, "images.json")
PROJECTS_JSON = os.path.join(DATA_DIR, "projects.json")
PROGRESS_JSON = os.path.join(DATA_DIR, "progress.json")
DOCS_JSON = os.path.join(DATA_DIR, "docs.json")
ANNOT_JSON = os.path.join(DATA_DIR, "annotations.json")

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".geotiff"}
ALLOWED_DOC_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _create_preview(src_path: str, dst_path: str, max_side: int = 2048) -> bool:
    if Image is None:
        return False
    try:
        with Image.open(src_path) as im:
            if getattr(im, "n_frames", 1) > 1:
                im.seek(0)
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side))
            im.save(dst_path, format="PNG", optimize=True)
        return True
    except Exception:
        return False

@app.route("/")
def hello_world():
    return render_template("index.html")


@app.route("/suivi")
def suivi_view():
    return render_template("suivi.html")


# ---------- Images API ----------


@app.route("/api/images", methods=["GET"])
def list_images():
    images = _load_json(IMAGES_JSON, [])
    project_id = request.args.get("project_id")
    if project_id:
        images = [img for img in images if img.get("project_id") == project_id]
    return jsonify(images)


@app.route("/api/images/upload", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide."}), 400
    name, ext = os.path.splitext(file.filename)
    original_filename = file.filename
    if ext.lower() not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": f"Extension non supportée: {ext}"}), 400

    unique = uuid.uuid4().hex
    safe_name = secure_filename(f"{unique}{ext.lower()}")
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(save_path)

    date_str = request.form.get("date") or datetime.utcnow().date().isoformat()
    project_id = request.form.get("project_id")
    preview_url = None
    # Generate preview for TIFF/GeoTIFF
    if ext.lower() in {".tif", ".tiff", ".geotiff"}:
        preview_name = f"{unique}.png"
        preview_path = os.path.join(PREVIEWS_DIR, preview_name)
        if _create_preview(save_path, preview_path):
            preview_url = f"/static/uploads/previews/{preview_name}"
    else:
        preview_url = f"/static/uploads/{safe_name}"
    record = {
        "id": unique,
        "filename": safe_name,
        "url": f"/static/uploads/{safe_name}",
        "date": date_str,
        "project_id": project_id,
        "preview_url": preview_url,
        "original_name": original_filename,
    }
    images = _load_json(IMAGES_JSON, [])
    images.append(record)
    _save_json(IMAGES_JSON, images)
    return jsonify(record)


# ---------- Projects API ----------


@app.route("/api/projects", methods=["GET"])
def list_projects():
    projects = _load_json(PROJECTS_JSON, {})
    # store as dict; return list for UI simplicity
    return jsonify(list(projects.values()))


@app.route("/api/projects", methods=["POST"])
def create_project():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if not name or not start_date or not end_date:
        return jsonify({"error": "name, start_date, end_date requis"}), 400
    pid = uuid.uuid4().hex
    project = {
        "id": pid,
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "created_at": datetime.utcnow().isoformat(),
    }
    projects = _load_json(PROJECTS_JSON, {})
    projects[pid] = project
    _save_json(PROJECTS_JSON, projects)
    return jsonify(project), 201


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id: str):
    projects = _load_json(PROJECTS_JSON, {})
    if project_id in projects:
        del projects[project_id]
        _save_json(PROJECTS_JSON, projects)
        return jsonify({"ok": True})
    return jsonify({"error": "Projet introuvable"}), 404


@app.route("/api/projects/<project_id>/progress", methods=["POST"])
def set_progress(project_id: str):
    payload = request.get_json(silent=True) or {}
    value = payload.get("progress")
    if value is None:
        return jsonify({"error": "progress requis"}), 400
    try:
        value = float(value)
    except Exception:
        return jsonify({"error": "progress doit être un nombre"}), 400
    progress = _load_json(PROGRESS_JSON, {})
    progress[project_id] = {"progress": value, "updated_at": datetime.utcnow().isoformat()}
    _save_json(PROGRESS_JSON, progress)
    return jsonify({"ok": True})


# ---------- Docs API (Rapports) ----------


@app.route("/api/docs", methods=["GET"])
def list_docs():
    docs = _load_json(DOCS_JSON, [])
    return jsonify(docs)


@app.route("/api/docs/upload", methods=["POST"])
def upload_doc():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide."}), 400
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_DOC_EXT:
        return jsonify({"error": f"Extension non supportée: {ext}"}), 400
    unique = uuid.uuid4().hex
    safe_name = secure_filename(f"{unique}{ext.lower()}")
    save_path = os.path.join(DOCS_DIR, safe_name)
    file.save(save_path)
    record = {"id": unique, "filename": safe_name, "url": f"/static/uploads/docs/{safe_name}"}
    docs = _load_json(DOCS_JSON, [])
    docs.append(record)
    _save_json(DOCS_JSON, docs)
    return jsonify(record)


# ---------- Annotations API ----------


@app.route("/api/annotations", methods=["GET"])
def list_annotations():
    data = _load_json(ANNOT_JSON, {"images": []})
    return jsonify(data)


@app.route("/api/annotations", methods=["POST"])
def add_annotation():
    payload = request.get_json(silent=True) or {}
    image_id = payload.get("image_id")
    text = payload.get("text")
    lat = payload.get("lat")
    lng = payload.get("lng")
    if not image_id or text is None or lat is None or lng is None:
        return jsonify({"error": "image_id, text, lat, lng requis"}), 400
    data = _load_json(ANNOT_JSON, {"images": []})
    # find existing for image
    found = None
    for item in data["images"]:
        if item.get("id") == image_id:
            found = item
            break
    if not found:
        found = {"id": image_id, "annotations": []}
        data["images"].append(found)
    ann = {
        "id": uuid.uuid4().hex,
        "text": text,
        "lat": float(lat),
        "lng": float(lng),
        "created_at": datetime.utcnow().isoformat(),
    }
    found["annotations"].append(ann)
    _save_json(ANNOT_JSON, data)
    return jsonify(ann), 201


# ---------- Analysis API (uses services/calcul.py) ----------


@app.route("/api/analysis/diff", methods=["POST"])
def analysis_diff():
    payload = request.get_json(silent=True) or {}
    image_id_a = payload.get("image_id_a")
    image_id_b = payload.get("image_id_b")
    if not image_id_a or not image_id_b:
        return jsonify({"error": "image_id_a et image_id_b requis"}), 400
    images = _load_json(IMAGES_JSON, [])
    lookup = {img["id"]: img for img in images}
    if image_id_a not in lookup or image_id_b not in lookup:
        return jsonify({"error": "Image introuvable"}), 404
    path_a = os.path.join(UPLOAD_DIR, lookup[image_id_a]["filename"])
    path_b = os.path.join(UPLOAD_DIR, lookup[image_id_b]["filename"])
    out_name = f"{uuid.uuid4().hex}.png"
    out_path = os.path.join(UPLOAD_DIR, "diffs", out_name)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Compute stats (low/medium/high change proportions)
    stats = None
    try:
        img_a = cv2.imread(path_a, cv2.IMREAD_COLOR)
        img_b = cv2.imread(path_b, cv2.IMREAD_COLOR)
        if img_a is not None and img_b is not None:
            if img_a.shape[:2] != img_b.shape[:2]:
                img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
            diff = cv2.absdiff(img_a, img_b)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
            total = int(norm.size)
            low = int((norm <= 30).sum())
            med = int(((norm > 30) & (norm <= 120)).sum())
            high = int((norm > 120).sum())
            stats = {"faible": low, "moyen": med, "fort": high, "total": total}
    except Exception:
        stats = None

    ok = compute_image_difference(path_a, path_b, out_path)
    if not ok and stats is None:
        return jsonify({"error": "Echec du calcul de différence"}), 500
    return jsonify({
        "url": f"/static/uploads/diffs/{out_name}",
        "filename": out_name,
        "stats": stats,
    })