# server/app.py
from flask import(Flask, jsonify,send_from_directory, request,
                  Response, send_file, redirect, url_for, render_template, session)
import subprocess, os, json, time, threading, secrets
from functools import wraps
from datetime import timedelta
from autoroam.common import get_repo_root, get_log_file_path, get_data_dir, get_failed_roams_dir, get_runs_dir
from dotenv import load_dotenv

API_KEY_FILE = os.path.join(os.path.dirname(__file__), "api_key.txt")

# Try to load existing key, otherwise generate and save a new one
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE) as f:
        API_KEY = f.read().strip()
else:
    API_KEY = secrets.token_urlsafe(32)
    with open(API_KEY_FILE, "w") as f:
        f.write(API_KEY)
    print(f"[+] Generated new API key: {API_KEY}")
    print("[!] Keep this safe – stored in api_key.txt")

# Prefer .env, fallback to .env.example for new users
if os.path.exists(".env"):
    load_dotenv(".env")
    print("[INFO] Loaded environment from .env")
elif os.path.exists(".env.example"):
    load_dotenv(".env.example")
    print("[INFO] Loaded environment from .env.example (defaults)")
else:
    print("[WARN] No .env or .env.example found")

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
TEMPLATE_DIR = os.path.join(BASE_DIR, "webui", "templates")
LOG_FILE = get_log_file_path()
MAIN_SCRIPT = os.path.join(BASE_DIR, "start_autoroam_cli.py")


USERNAME = os.getenv("WEB_USER")
PASSWORD = os.getenv("WEB_PASS")

if not USERNAME or not PASSWORD:
    raise RuntimeError("Missing required environment variables: WEB_USER and/or WEB_PASS")



app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    template_folder=TEMPLATE_DIR
)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key")
app.permanent_session_lifetime = timedelta(hours=2)



@app.route("/")
def index():
    return render_template("index.html", api_key=API_KEY)

#Login handling
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == USERNAME and pw == PASSWORD:
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("index"))
        # On invalid login, redisplay the form with error
        return render_template("login.html", error="Invalid credentials")

    # Initial GET
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.before_request
def enforce_login():
    if request.path.startswith("/api/") or request.path.startswith("/static/"):
        return
    if request.endpoint in ("login", "logout"):
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
@app.before_request
def require_api_key_for_api():
    # Only enforce on /api routes
    if not request.path.startswith("/api/"):
        return

    # ✅ Allow logged-in web UI sessions
    if session.get("logged_in"):
        return

    # ✅ Enforce for everything else (external use)
    key = request.headers.get("X-API-Key")
    if not key or key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401



@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith("/api/download_log"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    if request.path == "/login":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response



#start roam process, listen for completion
roam_process = None  # global handle
@app.route('/api/start_roam', methods=['POST'])
def start_roam():
    global roam_process

    # Clear old log and old flag
    open(LOG_FILE, "w").close()
    flag_path = os.path.join(BASE_DIR,"webui", "server", "roam_done.flag")
    if os.path.exists(flag_path):
        os.remove(flag_path)

    data = request.get_json(force=True) or {}
    iface = data.get("iface", "wlan0")
    rssi = str(data.get("rssi", -75))

    cmd = ["python3", "-u", MAIN_SCRIPT, "-i", iface, "-r", rssi]
    print(f"[+] Launching: {' '.join(cmd)}")

    logf = open(LOG_FILE, "a")
    roam_process = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        bufsize=1
    )
    print(f"[+] Spawned roam_process with PID {roam_process.pid}")

    def watch_proc(proc):
        print(f"[~] Watcher thread started for PID {proc.pid}")
        try:
            proc.wait()
            print(f"[!] roam process exited with code {proc.returncode}")

            # Ensure the flag directory exists
            os.makedirs(os.path.join(BASE_DIR, "webui", "server"), exist_ok=True)

            # Use your helper to find the correct run directory
            latest_run = get_latest_run_dir()
            print(latest_run)
            summary_path = os.path.join(latest_run or "", "cycle_summary.json")

            # Only create the flag if the summary doesn’t exist
            if not latest_run or not os.path.exists(summary_path):
                flag_path = os.path.join(BASE_DIR, "webui", "server", "roam_done.flag")
                with open(flag_path, "w") as f:
                    f.write("done\n")
                print(f"[+] Created flag (no summary detected) at {flag_path}")
            else:
                print(f"[✓] Summary detected in {latest_run}, skipping flag creation")

        except Exception as e:
            print(f"[x] Watcher failed: {e}")

    t = threading.Thread(target=watch_proc, args=(roam_process,), daemon=True)
    t.start()
    print("[+] Watcher thread launched")

    return jsonify({"status": "started", "cmd": cmd})

#Serve "roam_done.flag"
@app.route('/server/<path:filename>')
def serve_flag(filename):
    path = os.path.join(BASE_DIR,"webui", "server", filename)
    if os.path.exists(path):
        return send_file(path)
    return Response(status=404)


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

    # Include the run_dir in the response so UI can use it for analysis
    summary["run_dir"] = run_path
    return jsonify(summary)


@app.route('/api/analyze_with_ai', methods=['POST'])
def analyze_with_ai():
    """Run the lightweight analysis + optional deep LLM analysis for the latest summary.

    POST JSON body: { "deep": bool, "deep_limit": int }
    Returns: { summary: {...}, ai: { shallow: str, deep: str|null } }
    """
    data = request.get_json(silent=True) or {}
    deep = bool(data.get('deep'))
    deep_limit = data.get('deep_limit', 1000)

    # Import loopback functions from tools
    try:
        from tools.mcp_loopback_client import get_latest_summary, download_failed_from_summary, analyze_summary, generate_nl_summary
    except Exception as e:
        return jsonify({"error": f"Server import error: {e}"}), 500

    # Determine run_dir: prefer provided run_dir, otherwise use latest
    req_run_dir = data.get('run_dir')
    j = None
    try:
        if req_run_dir:
            # load cycle_summary.json from the provided run_dir (which is a full path or a runs directory name)
            from autoroam.common import get_runs_dir
            runs_dir = get_runs_dir()
            # If the provided path looks like an absolute path and exists, use it; otherwise join with runs_dir
            candidate = req_run_dir if os.path.isabs(req_run_dir) else os.path.join(runs_dir, os.path.basename(req_run_dir))
            summary_path = os.path.join(candidate, 'cycle_summary.json')
            if not os.path.exists(summary_path):
                return jsonify({"error": f"cycle_summary.json not found in run_dir {candidate}"}), 404
            with open(summary_path) as f:
                j = { 'data': json.load(f), 'run_dir': candidate }
        else:
            # fall back to latest
            latest_dir = get_latest_run_dir()
            if not latest_dir:
                return jsonify({"error": "No runs found"}), 404
            summary_path = os.path.join(latest_dir, 'cycle_summary.json')
            if not os.path.exists(summary_path):
                return jsonify({"error": "No summary found yet"}), 404
            with open(summary_path) as f:
                j = { 'data': json.load(f), 'run_dir': latest_dir }
    except Exception as e:
        return jsonify({"error": f"Could not load summary: {e}"}), 500

    # Run local analysis (this prints to server log) and capture textual shallow summary
    try:
        # analyze_summary prints to stdout; we also generate the LLM rephrased shallow summary
        analyze_summary(j)
        # Load saved AI settings (if any) and pass as per-call overrides so the adapter can use them
        settings_path = os.path.join(os.path.dirname(__file__), 'ai_settings.json')
        llm_overrides = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path) as f:
                    s = json.load(f)
                if s.get('api_key'):
                    llm_overrides['_llm_api_key'] = s.get('api_key')
                if s.get('endpoint'):
                    llm_overrides['_llm_provider_endpoint'] = s.get('endpoint')
                if s.get('model'):
                    llm_overrides['_llm_model'] = s.get('model')
                if s.get('temperature') is not None:
                    llm_overrides['_llm_temperature'] = s.get('temperature')
            except Exception:
                pass
        shallow = generate_nl_summary(j.get('data') or {}, [], [], [], llm_overrides=llm_overrides)
    except Exception as e:
        shallow = f"Analysis failed: {e}"

    deep_text = None
    if deep:
        try:
            extra = download_failed_from_summary(j, out_dir=os.path.join(get_repo_root(), 'webui', 'server'), limit_lines=deep_limit)
            data_ctx = j.get('data') or {}
            data_ctx['_extra'] = extra
            data_ctx['_mode'] = 'deep'
            # reuse llm_overrides from above (or reconstruct)
            try:
                if 'llm_overrides' not in locals():
                    llm_overrides = {}
                    if os.path.exists(settings_path):
                        with open(settings_path) as f:
                            s = json.load(f)
                        if s.get('api_key'):
                            llm_overrides['_llm_api_key'] = s.get('api_key')
                        if s.get('endpoint'):
                            llm_overrides['_llm_provider_endpoint'] = s.get('endpoint')
                        if s.get('model'):
                            llm_overrides['_llm_model'] = s.get('model')
                        if s.get('temperature') is not None:
                            llm_overrides['_llm_temperature'] = s.get('temperature')
            except Exception:
                llm_overrides = {}

            deep_text = generate_nl_summary(data_ctx, [], [], [], extra_context=extra, llm_overrides=llm_overrides)
        except Exception as e:
            deep_text = f"Deep analysis failed: {e}"

    return jsonify({
        "summary": j.get('data'),
        "ai": {"shallow": shallow, "deep": deep_text}
    })


@app.route('/api/chat_followup', methods=['POST'])
def chat_followup():
    """Handle follow-up questions about a roaming analysis.
    
    POST JSON body: { "question": str, "run_dir": str }
    Returns: { "answer": str }
    """
    data = request.get_json(silent=True) or {}
    question = data.get('question')
    run_dir = data.get('run_dir')
    
    if not question or not run_dir:
        return jsonify({"error": "Missing question or run_dir"}), 400
        
    try:
        # Load the summary data for context
        run_path = os.path.join(get_runs_dir(), os.path.basename(run_dir))
        summary_path = os.path.join(run_path, 'cycle_summary.json')
        if not os.path.exists(summary_path):
            return jsonify({"error": "Summary data not found"}), 404
            
        with open(summary_path) as f:
            summary_data = json.load(f)
            
        # Get AI settings
        settings_path = os.path.join(os.path.dirname(__file__), 'ai_settings.json')
        llm_overrides = {}
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                s = json.load(f)
                if s.get('api_key'): llm_overrides['_llm_api_key'] = s.get('api_key')
                if s.get('endpoint'): llm_overrides['_llm_provider_endpoint'] = s.get('endpoint')
                if s.get('model'): llm_overrides['_llm_model'] = s.get('model')
                if s.get('temperature') is not None: llm_overrides['_llm_temperature'] = s.get('temperature')
                
        # Load any failure logs if they exist
        extra_context = None
        fail_dir = os.path.join(run_path, "failed_roams")
        if os.path.exists(fail_dir):
            from tools.mcp_loopback_client import download_failed_from_summary
            extra_context = download_failed_from_summary(
                {"data": summary_data, "run_dir": run_path},
                out_dir=os.path.join(get_repo_root(), 'webui', 'server')
            )
            
        print(f"\n[DEBUG] summary_data keys: {summary_data.keys()}")
        print(f"[DEBUG] candidates in summary: {len(summary_data.get('candidates', []))}")
        
        # Add question context to summary data - pass the raw summary data
        context = {
            'data': summary_data,  # Pass the complete raw data
            '_question': question,  # The user's question
            '_context_type': 'chat_followup'  # Help LLM understand this is a chat context
        }
        
        if extra_context:
            context['_extra'] = extra_context
            
        # Get answer from LLM
        from tools.mcp_loopback_client import generate_nl_summary
        answer = generate_nl_summary(context, [], [], [], llm_overrides=llm_overrides)
        
        return jsonify({"answer": answer})
        
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500


@app.route('/api/ai_settings', methods=['GET', 'POST'])
def ai_settings():
    """Get or set AI provider settings stored locally on the server.

    GET returns { api_key, model, endpoint, temperature, max_tokens }
    POST accepts JSON with the same keys and writes them to webui/server/ai_settings.json
    """
    settings_path = os.path.join(os.path.dirname(__file__), 'ai_settings.json')
    if request.method == 'GET':
        if os.path.exists(settings_path):
            try:
                with open(settings_path) as f:
                    return jsonify(json.load(f))
            except Exception as e:
                return jsonify({"error": f"Failed to read settings: {e}"}), 500
        return jsonify({})

    # POST -> save
    data = request.get_json(force=True) or {}
    # Basic validation
    allowed = ['api_key', 'model', 'endpoint', 'temperature', 'max_tokens']
    out = {k: data.get(k) for k in allowed if k in data}
    try:
        with open(settings_path, 'w') as f:
            json.dump(out, f, indent=2)
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": f"Failed to save settings: {e}"}), 500


@app.route('/api/ai_test', methods=['POST'])
def ai_test():
    """Quick smoke test for the saved AI settings. Returns {ok:true, info:...} or error."""
    # Allow callers to POST temporary settings (so Test can run without Save)
    req = request.get_json(silent=True) or {}

    settings_path = os.path.join(os.path.dirname(__file__), 'ai_settings.json')
    cfg = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path) as f:
                cfg = json.load(f) or {}
        except Exception:
            cfg = {}

    # Merge: prefer request payload values if provided
    merged = {
        'endpoint': req.get('endpoint') or cfg.get('endpoint'),
        'api_key': req.get('api_key') or cfg.get('api_key'),
        'model': req.get('model') or cfg.get('model'),
        'temperature': req.get('temperature') if req.get('temperature') is not None else cfg.get('temperature'),
        'max_tokens': req.get('max_tokens') if req.get('max_tokens') is not None else cfg.get('max_tokens'),
    }
    # Validate essential fields
    endpoint = merged.get('endpoint')
    api_key = merged.get('api_key')
    model = merged.get('model') or 'gpt-4o-mini'
    if not endpoint or not api_key:
        return jsonify({"ok": False, "error": "AI settings incomplete (endpoint and api_key are required)", "details": json.dumps(merged)}), 200

    # Build an OpenAI-compatible chat/completions test payload
    test_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a test agent."},
            {"role": "user", "content": "Please reply with the single token: OK"}
        ],
        "temperature": float(cfg.get('temperature') or 0.2),
        "max_tokens": 8
    }

    # Resolve URL similarly to provider driver
    def _build_url(ep: str) -> str:
        if ep.endswith('/v1') or ep.endswith('/v1/'):
            return ep.rstrip('/') + '/chat/completions'
        if ep.endswith('/chat/completions'):
            return ep
        return ep.rstrip('/') + '/v1/chat/completions'

    url = _build_url(endpoint)

    import requests
    try:
        resp = requests.post(url, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }, json=test_payload, timeout=8)
    except Exception as e:
        detail = str(e)
        return jsonify({"ok": False, "error": "Connection failed", "details": detail}), 200

    # If non-2xx, return failure with status and snippet
    if resp.status_code < 200 or resp.status_code >= 300:
        body = ''
        try:
            body = resp.text[:1600]
        except Exception:
            body = '<unreadable response body>'
        short = f"Provider HTTP {resp.status_code}"
        return jsonify({"ok": False, "error": short, "details": body}), 200

    # Try to parse JSON and validate structure
    try:
        j = resp.json()
    except Exception as e:
        return jsonify({"ok": False, "error": "Response not JSON", "details": resp.text[:1600]}), 200

    # Expect choices[0].message.content or choices[0].text
    text = None
    try:
        if isinstance(j, dict) and 'choices' in j and len(j['choices']) > 0:
            c = j['choices'][0]
            if isinstance(c.get('message'), dict):
                text = c.get('message', {}).get('content')
            elif c.get('text'):
                text = c.get('text')
    except Exception:
        text = None

    if not text:
        return jsonify({"ok": False, "error": "No completion in provider response", "details": json.dumps(j)[:1600]}), 200

    return jsonify({"ok": True, "text": text.strip(), "usage": j.get('usage')}), 200

@app.route("/api/docs")
def api_docs():
    docs_dir = os.path.join(BASE_DIR, "docs")
    return send_from_directory(docs_dir, "swagger.html")

@app.route("/api/docs/<path:filename>")
def api_docs_assets(filename):
    docs_dir = os.path.join(BASE_DIR, "docs")
    return send_from_directory(docs_dir, filename)



def run_server(port=8443):
    """Run the Flask server with HTTPS using self-signed certs."""
    cert_dir = os.path.join(os.path.dirname(__file__), "certs")
    cert_path = os.path.join(cert_dir, "server.crt")
    key_path  = os.path.join(cert_dir, "server.key")

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("[!] HTTPS certificate not found.")
        print("    Generate one with:")
        print("    openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj '/CN=localhost'")
        print("Falling back to HTTP.")
        ssl_context = None
    else:
        ssl_context = (cert_path, key_path)
        print(f"[✓] Using HTTPS certificate from {cert_dir}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        ssl_context=ssl_context
    )