# wlan_autoroam/common.py
import os

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

def get_failed_roams_dir():
    path = os.path.join(get_data_dir(), "failed_roams")
    os.makedirs(path, exist_ok=True)
    return path

