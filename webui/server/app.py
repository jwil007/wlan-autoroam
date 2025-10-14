# server/app.py
from flask import Flask, jsonify, send_from_directory, request, Response, send_file
import subprocess, os, json, time
from autoroam.common import get_repo_root, get_log_file_path, get_data_dir, get_failed_roams_dir, get_runs_dir

def get_latest_run_dir():
    """Return the absolute path to the newest run directory, or None if none exist."""
    runs_dir = get_runs_dir()
    run_dirs = [
        os.path.join(runs_dir, d)
        for d in os.listdir(runs_dir)
        if os.path.isdir(os.path.join(runs_dir, d))
    ]
    return max(run_dirs, key=os.path.getmtime) if run_dirs else None



BASE_DIR = get_repo_root()
STATIC_DIR = os.path.join(BASE_DIR, "webui", "static")
LOG_FILE = get_log_file_path()
MAIN_SCRIPT = os.path.join(BASE_DIR, "start_autoroam_cli.py")


app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith("/api/download_log"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/start_roam', methods=['POST'])
def start_roam():
    # Clear old log
    open(LOG_FILE, "w").close()

    data = request.get_json(force=True) or {}
    iface = data.get("iface", "wlan0")
    rssi = str(data.get("rssi", -75))

    cmd = ["python3", "-u", MAIN_SCRIPT, "-i", iface, "-r", rssi]

    print(f"[+] Launching: {' '.join(cmd)}")

    logf = open(LOG_FILE, "a")
    subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        bufsize=1
    )

    return jsonify({"status": "started", "cmd": cmd})

#gets json output which fills out data on the UI. 
@app.route('/api/latest_cycle_summary')
def latest_summary():
    latest_dir = get_latest_run_dir()
    if not latest_dir:
        return jsonify({"error": "No runs found yet"}), 404

    summary_path = os.path.join(latest_dir, "cycle_summary.json")

    if not os.path.exists(summary_path):
        print(f"[WARN] JSON not found at {summary_path}")
        return jsonify({"error": "No summary found yet"}), 404

    mtime = os.path.getmtime(summary_path)
    with open(summary_path) as f:
        data = json.load(f)

    return jsonify({
        "mtime": mtime,
        "data": data,
        "run_dir": latest_dir
    })


#this is the stdout when running the script, not wpa_supplicant logs... sorry
@app.route('/api/logs')
def get_logs():
    if not os.path.exists(LOG_FILE):
        return jsonify({"log": ""})
    with open(LOG_FILE, "r") as f:
        lines = f.read()
    return jsonify({"log": lines})

#This will download logs with a specified file name. Works for full debug logs and failed roam logs. 
@app.route('/api/download_log')
def download_log():
    filename = request.args.get("filename", "roam_debug.log")
    safe_name = os.path.basename(filename)
    run_dir_arg = request.args.get("dir")

    # Use provided run_dir (from UI) if available, otherwise fall back to latest
    if run_dir_arg:
        run_dir = os.path.join(get_runs_dir(), os.path.basename(run_dir_arg))
    else:
        run_dir = get_latest_run_dir()

    if not run_dir or not os.path.isdir(run_dir):
        return jsonify({"error": "No valid run directory found"}), 404

    fail_dir = os.path.join(run_dir, "failed_roams")
    candidate_paths = [
        os.path.join(run_dir, safe_name),
        os.path.join(fail_dir, safe_name),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            return send_file(path, as_attachment=True, conditional=False)

    return jsonify({"error": f"Log file not found: {filename}"}), 404



# ====== Save/Load Results API ======

@app.route('/api/save_results', methods=['POST'])
def save_results():
    """
    Marks a run directory as saved and optionally adds notes.
    """
    data = request.get_json(force=True)
    run_dir = data.get("run_dir")
    notes = data.get("notes", "")

    if not run_dir:
        return jsonify({"error": "Missing run_dir"}), 400

    meta_path = os.path.join(run_dir, "metadata.json")
    if not os.path.exists(meta_path):
        return jsonify({"error": f"metadata.json not found in {run_dir}"}), 404

    with open(meta_path) as f:
        meta = json.load(f)

    meta["saved"] = True
    meta["notes"] = notes

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[+] Marked run as saved: {run_dir}")
    return jsonify({"status": "saved", "run_dir": run_dir, "notes": notes})


@app.route('/api/list_saved_runs')
def list_saved_runs():
    """
    Returns metadata for all saved runs.
    """
    from autoroam.common import list_saved_runs
    runs = list_saved_runs()
    return jsonify(runs)


@app.route('/api/load_results')
def load_results():
    """
    Loads a saved run’s cycle_summary.json for UI display.
    Also merges in notes from metadata.json if present.
    """
    from autoroam.common import get_runs_dir

    run_dir = request.args.get("dir")
    if not run_dir:
        return jsonify({"error": "Missing dir parameter"}), 400

    run_path = os.path.join(get_runs_dir(), os.path.basename(run_dir))
    summary_path = os.path.join(run_path, "cycle_summary.json")
    meta_path = os.path.join(run_path, "metadata.json")

    if not os.path.exists(summary_path):
        return jsonify({"error": "cycle_summary.json not found"}), 404

    with open(summary_path) as f:
        summary = json.load(f)

    # --- merge in metadata.json if it exists ---
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as mf:
                meta = json.load(mf)
            summary["notes"] = meta.get("notes", "")
            summary["saved"] = meta.get("saved", False)
        except Exception as e:
            print(f"[WARN] Could not read metadata.json for {run_dir}: {e}")

    return jsonify(summary)





def run_server(port=8080):
    """Run the Flask server on the specified port."""
    print(f"Starting webserver at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
