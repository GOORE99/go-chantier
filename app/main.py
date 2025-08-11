from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from .services.calcul import compute_image_difference


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


ensure_dirs()

app = Flask(
    __name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(STATIC_DIR)
)


PROJECTS_FILE = DATA_DIR / "projects.json"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_projects() -> List[Dict[str, Any]]:
    db = read_json(PROJECTS_FILE, {"projects": []})
    return db.get("projects", [])


def save_projects(projects: List[Dict[str, Any]]) -> None:
    write_json(PROJECTS_FILE, {"projects": projects})


def get_project_or_404(project_id: str) -> Dict[str, Any]:
    projects = load_projects()
    for p in projects:
        if p["id"] == project_id:
            return p
    return {}


def persist_project(updated: Dict[str, Any]) -> None:
    projects = load_projects()
    for idx, p in enumerate(projects):
        if p["id"] == updated["id"]:
            projects[idx] = updated
            save_projects(projects)
            return
    # if not found, append
    projects.append(updated)
    save_projects(projects)


@app.route("/")
def home() -> str:
    return render_template("index.html")


@app.get("/api/projects")
def api_list_projects():
    return jsonify({"projects": load_projects()})


@app.post("/api/projects")
def api_create_project():
    payload = request.get_json(silent=True) or request.form
    name = (payload.get("name") or "").strip()
    start_date = (payload.get("startDate") or "").strip()
    end_date = (payload.get("endDate") or "").strip()
    if not name or not start_date or not end_date:
        return jsonify({"error": "Nom, date de début et date de fin sont requis"}), 400
    try:
        # validate dates
        datetime.fromisoformat(start_date)
        datetime.fromisoformat(end_date)
    except Exception:
        return jsonify({"error": "Format de date invalide (YYYY-MM-DD)"}), 400

    project_id = uuid.uuid4().hex
    # create directories
    (UPLOADS_DIR / project_id).mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / project_id / "docs").mkdir(parents=True, exist_ok=True)
    project = {
        "id": project_id,
        "name": name,
        "startDate": start_date,
        "endDate": end_date,
        "images": [],
        "documents": [],
        "progress": 0,
        "createdAt": datetime.utcnow().isoformat(),
    }
    projects = load_projects()
    projects.append(project)
    save_projects(projects)
    return jsonify(project), 201


@app.get("/projets/<project_id>")
def project_redirect(project_id: str):
    # Default to visualisations module
    return redirect(url_for("module_visualisations", project_id=project_id))


@app.get("/projets/<project_id>/visualisations")
def module_visualisations(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return render_template("index.html", error="Projet introuvable"), 404
    return render_template("visualisations.html", project=project)


@app.get("/projets/<project_id>/analyse")
def module_analyse(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return render_template("index.html", error="Projet introuvable"), 404
    return render_template("analyse.html", project=project)


@app.get("/projets/<project_id>/courbes")
def module_courbes(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return render_template("index.html", error="Projet introuvable"), 404
    return render_template("courbes.html", project=project)


@app.get("/projets/<project_id>/rapports")
def module_rapports(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return render_template("index.html", error="Projet introuvable"), 404
    return render_template("rapports.html", project=project)


@app.post("/api/projects/<project_id>/images")
def api_upload_images(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Projet introuvable"}), 404
    if "files" not in request.files and not request.files:
        # Support both single file 'file' and multiple 'files'
        # Flask combines in request.files; iterate over all values
        pass
    saved = []
    for key in request.files:
        file = request.files.get(key)
        if not file or file.filename == "":
            continue
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]:
            continue
        img_id = uuid.uuid4().hex
        # preserve extension
        out_name = f"{img_id}{ext}"
        out_dir = UPLOADS_DIR / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / out_name
        file.save(out_path)
        item = {
            "id": img_id,
            "filename": out_name,
            "url": f"/static/uploads/{project_id}/{out_name}",
            "date": None,
        }
        project.setdefault("images", []).append(item)
        saved.append(item)
    persist_project(project)
    return jsonify({"saved": saved, "project": project})


@app.patch("/api/projects/<project_id>/images/<image_id>")
def api_update_image(project_id: str, image_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Projet introuvable"}), 404
    payload = request.get_json(silent=True) or {}
    date = payload.get("date")
    updated = None
    for img in project.get("images", []):
        if img["id"] == image_id:
            img["date"] = date
            updated = img
            break
    if updated is None:
        return jsonify({"error": "Image introuvable"}), 404
    # recompute progress: percentage of images with a date
    images = project.get("images", [])
    total = len(images)
    done = len([i for i in images if i.get("date")])
    project["progress"] = int(round((done / total) * 100)) if total else 0
    persist_project(project)
    return jsonify({"image": updated, "project": project})


@app.post("/api/projects/<project_id>/analyse/diff")
def api_analyse_diff(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Projet introuvable"}), 404
    payload = request.get_json(silent=True) or request.form
    img1_id = payload.get("imageA")
    img2_id = payload.get("imageB")
    if not img1_id or not img2_id:
        return jsonify({"error": "Sélectionnez deux images"}), 400
    def find_path(img_id: str) -> Path | None:
        for it in project.get("images", []):
            if it["id"] == img_id:
                return UPLOADS_DIR / project_id / it["filename"]
        return None
    p1 = find_path(img1_id)
    p2 = find_path(img2_id)
    if not p1 or not p2 or (not p1.exists()) or (not p2.exists()):
        return jsonify({"error": "Fichiers introuvables"}), 404
    out_dir = UPLOADS_DIR / project_id / "diff"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{uuid.uuid4().hex}.png"
    out_path = out_dir / out_name
    compute_image_difference(str(p1), str(p2), str(out_path))
    url = f"/static/uploads/{project_id}/diff/{out_name}"
    return jsonify({"url": url})


@app.post("/api/projects/<project_id>/documents")
def api_upload_document(project_id: str):
    project = get_project_or_404(project_id)
    if not project:
        return jsonify({"error": "Projet introuvable"}), 404
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Aucun fichier"}), 400
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]:
        return jsonify({"error": "Type non supporté"}), 400
    doc_id = uuid.uuid4().hex
    out_name = f"{doc_id}{ext}"
    out_dir = UPLOADS_DIR / project_id / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    file.save(out_path)
    item = {
        "id": doc_id,
        "filename": out_name,
        "originalName": filename,
        "url": f"/static/uploads/{project_id}/docs/{out_name}",
        "type": ext.lstrip("."),
        "uploadedAt": datetime.utcnow().isoformat(),
    }
    project.setdefault("documents", []).append(item)
    persist_project(project)
    return jsonify(item), 201


@app.get("/download/<path:filepath>")
def download(filepath: str):
    # Security: only within uploads dir
    full = (UPLOADS_DIR / filepath).resolve()
    if not str(full).startswith(str(UPLOADS_DIR.resolve())):
        return "Forbidden", 403
    if not full.exists():
        return "Not found", 404
    return send_from_directory(full.parent, full.name, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)