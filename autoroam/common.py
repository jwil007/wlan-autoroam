# wlan_autoroam/common.py
import os, json, shutil, datetime
from pathlib import Path

def get_repo_root():
    # `__file__` is inside wlan_autoroam/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def get_data_dir():
    path = os.path.join(get_repo_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path

def get_log_file_path():
    data_dir = get_data_dir()
    log_path = os.path.join(data_dir, "current_run.log")
    if not os.path.exists(log_path):
        open(log_path, "w").close()
    return log_path

def get_failed_roams_dir(run_dir=None):
    path = os.path.join(run_dir, "failed_roams")
    os.makedirs(path, exist_ok=True)
    return path

def get_runs_dir():
    """Return the directory where all roam cycle runs are stored."""
    runs_dir = os.path.join(get_data_dir(), "runs")
    os.makedirs(runs_dir, exist_ok=True)
    return runs_dir


def create_run_dir(ssid=None):
    """Create a unique run directory for the current roam cycle."""
    safe_ssid = ssid.replace(" ", "_") if ssid else "unknown"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    dir_name = f"{timestamp}_{safe_ssid}"
    run_dir = os.path.join(get_runs_dir(), dir_name)
    os.makedirs(run_dir, exist_ok=True)

    metadata = {"saved": False, "ssid": ssid or "unknown", "notes": ""}
    with open(os.path.join(run_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    return run_dir


def cleanup_unsaved_runs():
    """Delete run directories that have not been marked as saved."""
    runs_dir = get_runs_dir()
    for entry in os.scandir(runs_dir):
        meta_path = os.path.join(entry.path, "metadata.json")
        if os.path.isdir(entry.path) and os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                if not meta.get("saved", False):
                    shutil.rmtree(entry.path, ignore_errors=True)
            except Exception as e:
                print(f"[WARN] Failed to cleanup {entry.path}: {e}")


def list_saved_runs():
    """Return list of saved runs and metadata."""
    runs = []
    runs_dir = get_runs_dir()
    for entry in os.scandir(runs_dir):
        meta_path = os.path.join(entry.path, "metadata.json")
        if os.path.isdir(entry.path) and os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("saved", False):
                runs.append({
                    "dir": entry.name,
                    **meta
                })
    return sorted(runs, key=lambda x: x["dir"], reverse=True)

