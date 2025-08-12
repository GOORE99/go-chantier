from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
import json
import os
import uuid
from datetime import datetime
import shutil

from .services.calcul import compute_image_difference
app = Flask(__name__, static_folder="static", template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
UPLOAD_DIR = BASE_DIR / "app" / "static" / "uploads"
DIFF_DIR = UPLOAD_DIR / "diffs"

for d in [DATA_DIR, UPLOAD_DIR, DIFF_DIR]:
    d.mkdir(parents=True, exist_ok=True)

PROJECTS_FILE = DATA_DIR / "projects.json"
IMAGES_FILE = DATA_DIR / "images.json"
DOCS_FILE = DATA_DIR / "docs.json"
PROGRESS_FILE = DATA_DIR / "progress.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


@app.route("/")
def index_page():
    return render_template("index.html")


@app.route("/suivi")
def suivi_page():
    return render_template("suivi.html")


# -------- Projects --------
@app.get("/api/projects")
def api_list_projects():
    projects = _read_json(PROJECTS_FILE, [])
    # augment with last image if any
    images = _read_json(IMAGES_FILE, [])
    project_id_to_last = {}
    for img in images:
        pid = img.get("projectId")
        if not pid:
            continue
        dt = img.get("date") or ""
        key = (dt, img.get("id"))
        if pid not in project_id_to_last or key > project_id_to_last[pid][0]:
            project_id_to_last[pid] = (key, img)
    for p in projects:
        p["lastImage"] = (project_id_to_last.get(p.get("id")) or (None, None))[1]
    return jsonify(projects)


@app.get("/api/projects/search")
def api_search_projects():
    q = (request.args.get("q") or "").strip().lower()
    projects = _read_json(PROJECTS_FILE, [])
    if not q:
        return jsonify(projects)
    matches = [p for p in projects if q in (p.get("name", "").lower())]
    return jsonify(matches)


@app.post("/api/projects")
def api_create_project():
    payload = request.json or {}
    name = (payload.get("name") or "").strip()
    start_date = (payload.get("startDate") or "").strip()
    end_date = (payload.get("endDate") or "").strip()
    if not name or not start_date or not end_date:
        return jsonify({"error": "name, startDate, endDate requis"}), 400
    projects = _read_json(PROJECTS_FILE, [])
    new_project = {
        "id": uuid.uuid4().hex,
        "name": name,
        "startDate": start_date,
        "endDate": end_date,
        "createdAt": datetime.utcnow().isoformat()
    }
    projects.append(new_project)
    _write_json(PROJECTS_FILE, projects)
    # initialize progress per project
    progress_data = _read_json(PROGRESS_FILE, {})
    progress_data[new_project["id"]] = {"progress": 0.0, "updated_at": datetime.utcnow().isoformat()}
    _write_json(PROGRESS_FILE, progress_data)
    return jsonify(new_project), 201


@app.get("/api/projects/<project_id>")
def api_get_project(project_id: str):
    projects = _read_json(PROJECTS_FILE, [])
    for p in projects:
        if p.get("id") == project_id:
            return jsonify(p)
    return jsonify({"error": "Projet introuvable"}), 404


@app.delete("/api/projects/<project_id>")
def api_delete_project(project_id: str):
    # Remove project entry
    projects = _read_json(PROJECTS_FILE, [])
    projects = [p for p in projects if p.get("id") != project_id]
    _write_json(PROJECTS_FILE, projects)

    # Remove images entries and files
    images = _read_json(IMAGES_FILE, [])
    remaining_images = [i for i in images if i.get("projectId") != project_id]
    _write_json(IMAGES_FILE, remaining_images)
    proj_dir = UPLOAD_DIR / project_id
    if proj_dir.exists():
        try:
            shutil.rmtree(proj_dir)
        except Exception:
            pass

    # Remove docs entries (and already removed in rmtree above)
    docs = _read_json(DOCS_FILE, [])
    docs = [d for d in docs if d.get("projectId") != project_id]
    _write_json(DOCS_FILE, docs)

    # Remove progress
    progress_data = _read_json(PROGRESS_FILE, {})
    if project_id in progress_data:
        del progress_data[project_id]
        _write_json(PROGRESS_FILE, progress_data)

    return ("", 204)


# -------- Images (orthophotos) --------
@app.get("/api/images")
def api_list_images():
    project_id = request.args.get("project_id")
    images = _read_json(IMAGES_FILE, [])
    if project_id:
        images = [i for i in images if i.get("projectId") == project_id]
    images.sort(key=lambda x: (x.get("date") or "", x.get("filename") or ""))
    return jsonify(images)


@app.post("/api/upload/image")
def api_upload_image():
    project_id = request.form.get("project_id")
    date_str = request.form.get("date")
    file = request.files.get("file")
    if not file or not project_id:
        return jsonify({"error": "file et project_id requis"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    new_id = uuid.uuid4().hex
    subdir = UPLOAD_DIR / project_id
    subdir.mkdir(parents=True, exist_ok=True)
    filename = f"{new_id}{ext or '.tif'}"
    save_path = subdir / filename
    file.save(str(save_path))
    url = f"/static/uploads/{project_id}/{filename}"
    images = _read_json(IMAGES_FILE, [])
    images.append({
        "id": new_id,
        "projectId": project_id,
        "filename": filename,
        "url": url,
        "date": date_str
    })
    _write_json(IMAGES_FILE, images)
    return jsonify({"id": new_id, "url": url, "date": date_str}), 201


# -------- Docs (rapports) --------
@app.get("/api/docs")
def api_list_docs():
    project_id = request.args.get("project_id")
    docs = _read_json(DOCS_FILE, [])
    if project_id:
        docs = [d for d in docs if d.get("projectId") == project_id]
    return jsonify(docs)


@app.post("/api/upload/doc")
def api_upload_doc():
    project_id = request.form.get("project_id")
    file = request.files.get("file")
    if not file or not project_id:
        return jsonify({"error": "file et project_id requis"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
    if ext not in allowed:
        return jsonify({"error": "Type de fichier non supporté"}), 400
    new_id = uuid.uuid4().hex
    subdir = UPLOAD_DIR / project_id / "docs"
    subdir.mkdir(parents=True, exist_ok=True)
    filename = f"{new_id}{ext}"
    save_path = subdir / filename
    file.save(str(save_path))
    url = f"/static/uploads/{project_id}/docs/{filename}"
    docs = _read_json(DOCS_FILE, [])
    docs.append({
        "id": new_id,
        "projectId": project_id,
        "filename": filename,
        "url": url,
        "uploadedAt": datetime.utcnow().isoformat()
    })
    _write_json(DOCS_FILE, docs)
    return jsonify({"id": new_id, "url": url}), 201


# -------- Progress --------
@app.post("/api/progress")
def api_update_progress():
    payload = request.json or {}
    project_id = payload.get("project_id")
    progress = payload.get("progress")
    if project_id is None or progress is None:
        return jsonify({"error": "project_id et progress requis"}), 400
    progress_data = _read_json(PROGRESS_FILE, {})
    progress_data[str(project_id)] = {"progress": float(progress), "updated_at": datetime.utcnow().isoformat()}
    _write_json(PROGRESS_FILE, progress_data)
    return jsonify(progress_data[str(project_id)])


# -------- Analyse (difference) --------
@app.post("/api/analyse/diff")
def api_analyse_diff():
    payload = request.json or {}
    path_a = payload.get("imageA")
    path_b = payload.get("imageB")
    if not path_a or not path_b:
        return jsonify({"error": "imageA et imageB requis (URL statique)"}), 400
    # Convert URLs like /static/uploads/... to filesystem paths
    def url_to_fs(url: str) -> Path:
        url = url.split("?")[0]
        assert url.startswith("/static/uploads/")
        rel = url[len("/static/uploads/"):]
        return UPLOAD_DIR / rel

    src_a = url_to_fs(path_a)
    src_b = url_to_fs(path_b)
    if not (src_a.exists() and src_b.exists()):
        return jsonify({"error": "Images introuvables"}), 404
    out_name = f"diff_{uuid.uuid4().hex}.png"
    out_path = DIFF_DIR / out_name
    ok = compute_image_difference(str(src_a), str(src_b), str(out_path))
    if not ok:
        return jsonify({"error": "Echec du calcul"}), 500
    return jsonify({"resultUrl": f"/static/uploads/diffs/{out_name}"})


@app.get("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)


