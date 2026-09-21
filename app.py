#!/usr/bin/env python3
"""Local web UI for script_to_images.

Single-user, local-only Flask app. Serves templates/index.html (a
complete, finished front end -- see design_handoff_web_ui/) and the API
it calls. All actual generation goes through generate_images.run_pipeline;
nothing here reimplements pipeline logic. See design_handoff_web_ui/BACKEND.md
for the full contract this file implements.

Run with: python app.py
"""

import json
import queue
import tempfile
import threading
import zipfile
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from generate_images import (
    TEXT_MODEL_MAP,
    MissingAPIKeyError,
    build_client,
    compute_versions_bytes,
    load_existing_shots,
    load_reference_images,
    read_script_lines,
    run_pipeline,
)
from segmentation import build_shot_plan, load_plan, save_plan, script_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = BASE_DIR / "script.txt"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_REFERENCES_DIR = BASE_DIR / "reference_photos"

DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
DEFAULT_REFERENCES_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# ---------------------------------------------------------------------
# Module-level state. Single user, no auth, no database.
# ---------------------------------------------------------------------
_state_lock = threading.Lock()
_session_key = None
_running = False
_stop_flag = False
_settings = {
    "model": "flash", "text_model": None, "aspect": "16:9",
    "start": None, "end": None, "dry_run": False, "rule_based": False,
    "output": "output", "references": "reference_photos",
}
_subscribers = []  # list[queue.Queue] -- one per connected /api/stream client
_job_queue = queue.Queue()


def _script_name_and_text():
    if SCRIPT_PATH.exists():
        return SCRIPT_PATH.name, SCRIPT_PATH.read_text(encoding="utf-8")
    return "script.txt", ""


def _output_dir():
    return BASE_DIR / _settings["output"]


def _references_dir():
    return BASE_DIR / _settings["references"]


def _broadcast(event_name, payload):
    data = json.dumps(payload)
    for q in list(_subscribers):
        q.put(f"event: {event_name}\ndata: {data}\n\n")


def _on_event(name, payload):
    global _running
    if name == "run_start":
        with _state_lock:
            _running = True
    elif name == "run_done":
        with _state_lock:
            _running = False
    _broadcast(name, payload)


def _safe_ref_path(name):
    safe = secure_filename(name)
    if not safe or safe != name:
        return None
    path = (_references_dir() / safe).resolve()
    if _references_dir().resolve() not in path.parents:
        return None
    return path


def _safe_output_path(filename):
    safe = secure_filename(filename)
    if not safe:
        return None
    path = (_output_dir() / safe).resolve()
    out_dir = _output_dir().resolve()
    if out_dir != path.parent:
        return None
    return path


# ---------------------------------------------------------------------
# Worker: one background thread, one job at a time -- so retries,
# backoff, and "never two Gemini calls in parallel" behave exactly like
# the CLI. Reroll requests queue behind whatever job is currently running.
# ---------------------------------------------------------------------

def _run_job(job):
    settings = job["settings"]
    global _stop_flag
    with _state_lock:
        _stop_flag = False
    try:
        run_pipeline(
            SCRIPT_PATH,
            output_dir=settings["output"],
            references_dir=settings["references"],
            start=settings["start"], end=settings["end"],
            model=settings["model"], text_model=settings["text_model"],
            aspect=settings["aspect"],
            dry_run=settings["dry_run"], rule_based=settings["rule_based"],
            api_key=_session_key,
            keep_versions=True,
            on_event=_on_event,
            should_stop=lambda: _stop_flag,
        )
    except Exception as exc:
        _fail_job(settings, exc)


def _reroll_job(job):
    n = job["n"]
    settings = job["settings"]
    try:
        run_pipeline(
            SCRIPT_PATH,
            output_dir=settings["output"],
            references_dir=settings["references"],
            start=n, end=n,
            model=settings["model"], text_model=settings["text_model"],
            aspect=settings["aspect"],
            dry_run=settings["dry_run"], rule_based=settings["rule_based"],
            api_key=_session_key,
            keep_versions=True,
            on_event=_on_event,
            should_stop=lambda: False,
        )
    except Exception as exc:
        _fail_job(settings, exc)


def _fail_job(settings, exc):
    global _running
    _broadcast("log", {"line": f"[worker] {exc}"})
    _broadcast("run_done", {"success": 0, "failed": 0, "dry_run": 0, "stopped": True})
    with _state_lock:
        _running = False


def _worker_loop():
    while True:
        job = _job_queue.get()
        if job["type"] == "run":
            _run_job(job)
        elif job["type"] == "reroll":
            _reroll_job(job)


threading.Thread(target=_worker_loop, daemon=True).start()


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR / "templates", "index.html")


@app.route("/api/state")
def api_state():
    name, text = _script_name_and_text()
    references = _list_references()
    shots = _list_shots()
    return jsonify({
        "running": _running,
        "key_set": _session_key is not None,
        "settings": _settings,
        "script": {"name": name, "text": text},
        "references": references,
        "shots": shots,
        "plan": _plan_for_current_script(text),
    })


def _plan_for_current_script(text):
    """The cached segmentation plan, if it matches the current script text."""
    plan = load_plan(_output_dir())
    if plan and plan.get("script_hash") == script_hash(text) and plan.get("shots"):
        return {"shots": plan["shots"]}
    return None


def _list_references():
    return [
        {"name": path.name, "size": path.stat().st_size}
        for path, _mime in load_reference_images(_references_dir())
    ]


def _list_shots():
    csv_path = _output_dir() / "shots.csv"
    rows = load_existing_shots(csv_path)
    shots = []
    for n in sorted(rows):
        row = rows[n]
        out_path = _output_dir() / row["filename"]
        versions, size_bytes = compute_versions_bytes(out_path)
        shots.append({
            "shot_number": n,
            "narration_line": row["narration_line"],
            "prompt": row["prompt"],
            "filename": row["filename"],
            "status": row["status"],
            "versions": versions,
            "bytes": size_bytes,
        })
    return shots


@app.route("/api/script", methods=["POST"])
def api_script_post():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    SCRIPT_PATH.write_text(text, encoding="utf-8")
    lines = read_script_lines(SCRIPT_PATH)
    return jsonify({"lines": len(lines)})


@app.route("/api/segment", methods=["POST", "PUT"])
def api_segment():
    """POST: (re-)run the LLM segmentation pass, biased toward more shots
    than lines. PUT: save a user-edited shot list directly, no LLM call."""
    _, text = _script_name_and_text()
    if not text.strip():
        return "no script loaded", 400

    if request.method == "PUT":
        data = request.get_json(force=True, silent=True) or {}
        shots = [s.strip() for s in data.get("shots", []) if s and s.strip()]
        if not shots:
            return "shots list is empty", 400
        save_plan(_output_dir(), text, shots)
        return jsonify({"shots": shots})

    data = request.get_json(force=True, silent=True) or {}
    force = bool(data.get("force"))
    rule_based = bool(data.get("rule_based"))
    model = data.get("model") or _settings.get("model") or "flash"
    text_model = data.get("text_model") or TEXT_MODEL_MAP.get(model, "gemini-3.6-flash")

    if rule_based:
        client = None
    elif _session_key is None:
        return "GEMINI_API_KEY required to segment with AI (or pass rule_based)", 400
    else:
        try:
            client = build_client(_session_key)
        except MissingAPIKeyError as exc:
            return str(exc), 400

    try:
        shots = build_shot_plan(
            text, _output_dir(), client=client, text_model=text_model,
            force_resegment=force,
        )
    except Exception as exc:
        return f"segmentation failed: {exc}", 502

    return jsonify({"shots": shots})


@app.route("/api/references", methods=["GET", "POST"])
def api_references():
    if request.method == "GET":
        return jsonify({"references": _list_references()})

    refs_dir = _references_dir()
    refs_dir.mkdir(parents=True, exist_ok=True)
    for f in request.files.getlist("files"):
        safe = secure_filename(f.filename)
        if not safe:
            continue
        f.save(refs_dir / safe)
    return jsonify({"references": _list_references()})


@app.route("/api/references/<name>", methods=["GET", "DELETE"])
def api_reference_item(name):
    path = _safe_ref_path(name)
    if not path:
        return "invalid filename", 400
    if request.method == "DELETE":
        if path.exists():
            path.unlink()
        return jsonify({"references": _list_references()})
    if not path.is_file():
        return "not found", 404
    return send_from_directory(_references_dir(), path.name)


@app.route("/api/session/key", methods=["POST"])
def api_session_key():
    global _session_key
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return "key is empty", 400
    _session_key = key
    return "", 204


def _resolved_settings(payload):
    total = len(read_script_lines(SCRIPT_PATH))
    model = payload.get("model") or "flash"
    start = payload.get("start")
    end = payload.get("end")
    start = max(1, int(start)) if start else None
    end = min(total, int(end)) if end and total else end
    return {
        "model": model,
        "text_model": payload.get("text_model") or None,
        "aspect": payload.get("aspect") or "16:9",
        "start": start,
        "end": end,
        "dry_run": bool(payload.get("dry_run")),
        "rule_based": bool(payload.get("rule_based")),
        "output": payload.get("output") or "output",
        "references": payload.get("references") or "reference_photos",
    }


@app.route("/api/run", methods=["POST"])
def api_run():
    global _settings
    payload = request.get_json(force=True, silent=True) or {}
    total = len(read_script_lines(SCRIPT_PATH))
    if not total:
        return "no script loaded", 400

    settings = _resolved_settings(payload)
    needs_key = (not settings["dry_run"]) or (not settings["rule_based"])
    if needs_key and _session_key is None:
        return "GEMINI_API_KEY required (paste it in the settings panel)", 400

    _settings = settings
    _job_queue.put({"type": "run", "settings": settings})
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _stop_flag
    with _state_lock:
        _stop_flag = True
    return jsonify({"ok": True})


@app.route("/api/reroll/<int:n>", methods=["POST"])
def api_reroll(n):
    global _settings
    payload = request.get_json(force=True, silent=True) or {}
    settings = _resolved_settings(payload)
    needs_key = (not settings["dry_run"]) or (not settings["rule_based"])
    if needs_key and _session_key is None:
        return "GEMINI_API_KEY required (paste it in the settings panel)", 400

    _settings = settings
    _job_queue.put({"type": "reroll", "n": n, "settings": settings})
    return jsonify({"ok": True})


@app.route("/api/stream")
def api_stream():
    q = queue.Queue()
    _subscribers.append(q)

    def gen():
        try:
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield msg
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

    return Response(gen(), mimetype="text/event-stream")


@app.route("/api/errors")
def api_errors():
    log_path = _output_dir() / "errors.log"
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return jsonify({"text": text})


@app.route("/api/shots.csv")
def api_shots_csv():
    csv_path = _output_dir() / "shots.csv"
    if not csv_path.exists():
        return "no shots.csv yet", 404
    return send_file(csv_path, as_attachment=True, download_name="shots.csv")


@app.route("/api/download.zip")
def api_download_zip():
    out_dir = _output_dir()
    include_errors = request.args.get("errors") != "0"

    tmp = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for png in sorted(out_dir.glob("*.png")):
            # Exclude version files (NNN_slug.vK.png has two suffixes);
            # keep only the live NNN_slug.png frame for each shot.
            if len(png.suffixes) > 1:
                continue
            zf.write(png, png.name)
        csv_path = out_dir / "shots.csv"
        if csv_path.exists():
            zf.write(csv_path, "shots.csv")
        if include_errors:
            log_path = out_dir / "errors.log"
            if log_path.exists():
                zf.write(log_path, "errors.log")
    tmp.seek(0)
    return send_file(tmp, as_attachment=True, download_name="output.zip", mimetype="application/zip")


@app.route("/api/output/<path:filename>")
def api_output_file(filename):
    path = _safe_output_path(filename)
    if not path or not path.is_file():
        return "not found", 404
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(_output_dir(), path.name, as_attachment=as_attachment)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
