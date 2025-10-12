# server/app.py
from flask import Flask, jsonify, send_from_directory, request, Response, send_file
import subprocess, os, json, time
from autoroam.common import get_repo_root, get_log_file_path, get_data_dir, get_failed_roams_dir


BASE_DIR = get_repo_root()
STATIC_DIR = os.path.join(BASE_DIR, "webui", "static")
LOG_FILE = get_log_file_path()
MAIN_SCRIPT = os.path.join(BASE_DIR, "start_autoroam_cli.py")


app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

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
    debug = data.get("debug")

    cmd = ["python3", "-u", MAIN_SCRIPT, "-i", iface, "-r", rssi]
    if debug:
        cmd += ["-d", debug]

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
    data_dir = get_data_dir()
    path = os.path.join(data_dir, "cycle_summary.json")
    if not os.path.exists(path):
        print(f"[WARN] JSON not found at {path}")
        return jsonify({"error": "No summary found yet"}), 404

    mtime = os.path.getmtime(path)
    with open(path) as f:
        data = json.load(f)
    return jsonify({"mtime": mtime, "data": data})

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
    safe_name = os.path.basename(filename)  # prevent path traversal

    # Primary log directories
    data_dir = get_data_dir()
    fail_dir = get_failed_roams_dir()

    # Check both possible locations
    candidate_paths = [
        os.path.join(data_dir, safe_name),
        os.path.join(fail_dir, safe_name),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            return send_file(path, as_attachment=True)

    # If nothing found
    return jsonify({"error": f"Log file not found: {filename}"}), 404

#this is a check to see if the optional debug log file exists
@app.route('/api/log_exists')
def log_exists():
    data_dir = get_data_dir()
    filename = request.args.get("filename", "roam_debug.log")
    log_path = os.path.join(data_dir, os.path.basename(filename))


    exists = os.path.exists(log_path)
    return jsonify({"exists": exists})


def run_server(port=8080):
    """Run the Flask server on the specified port."""
    print(f"Starting webserver at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
