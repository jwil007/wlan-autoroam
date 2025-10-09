# server/app.py
from flask import Flask, jsonify, send_from_directory, request, Response
import subprocess, os, json, time


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATIC_DIR = os.path.join(BASE_DIR, "webui", "static")
LOG_FILE = os.path.join(BASE_DIR, "data", "current_run.log")
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")


app = Flask(__name__, static_folder=STATIC_DIR)

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


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


@app.route('/api/latest_cycle_summary')
def latest_summary():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "cycle_summary.json"))
    if not os.path.exists(path):
        print(f"[WARN] JSON not found at {path}")
        return jsonify({"error": "No summary found yet"}), 404

    mtime = os.path.getmtime(path)
    with open(path) as f:
        data = json.load(f)
    return jsonify({"mtime": mtime, "data": data})

@app.route('/api/logs')
def get_logs():
    if not os.path.exists(LOG_FILE):
        return jsonify({"log": ""})
    with open(LOG_FILE, "r") as f:
        lines = f.read()
    return jsonify({"log": lines})

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=8080, debug=True)
