import subprocess
import threading
from dataclasses import dataclass, field
import os, re, time, datetime, bisect

@dataclass
class CollectedLogs:
    raw_logs: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

TRACE_ROOT = "/sys/kernel/debug/tracing"
CFG_EVENTS = ["rdev_auth", "rdev_assoc", "cfg80211_send_rx_assoc"]

def _enable_cfg80211_events():
    os.system("mount -t debugfs none /sys/kernel/debug 2>/dev/null || true")
    os.system("mount -t tracefs nodev /sys/kernel/debug/tracing 2>/dev/null || true")
    with open(f"{TRACE_ROOT}/tracing_on", "w") as f: f.write("0\n")
    open(f"{TRACE_ROOT}/trace", "w").close()
    for e in CFG_EVENTS:
        path = f"{TRACE_ROOT}/events/cfg80211/{e}/enable"
        if os.path.exists(path):
            with open(path, "w") as f: f.write("1\n")
    with open(f"{TRACE_ROOT}/trace_clock", "w") as f: f.write("mono\n")
    with open(f"{TRACE_ROOT}/tracing_on", "w") as f: f.write("1\n")

def _disable_cfg80211_events():
    try:
        with open(f"{TRACE_ROOT}/tracing_on", "w") as f: f.write("0\n")
        for e in CFG_EVENTS:
            path = f"{TRACE_ROOT}/events/cfg80211/{e}/enable"
            if os.path.exists(path):
                with open(path, "w") as f: f.write("0\n")
    except Exception:
        pass

# --- timestamp helpers ---

def _parse_timestamp(line: str) -> float:
    """Extract timestamp from 'YYYY-MM-DD HH:MM:SS.UUUUUU' or 'Oct 12 19:20:34.494465'."""
    m = re.search(r'(\d{4}-\d{2}-\d{2}|\w{3}\s+\d{1,2})\s+(\d{2}:\d{2}:\d{2}\.\d{6})', line)
    if not m:
        return 0.0
    date_part, time_part = m.groups()
    try:
        if '-' in date_part:
            dt = datetime.datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S.%f")
        else:
            year = datetime.datetime.now().year
            dt = datetime.datetime.strptime(f"{year} {date_part} {time_part}", "%Y %b %d %H:%M:%S.%f")
        return dt.timestamp()
    except Exception:
        return 0.0

def _format_ts_for_journal(ts_float: float) -> str:
    """Convert monotonic seconds to 'YYYY-MM-DD HH:MM:SS.UUUUUU' format."""
    mono_now = time.monotonic()
    real_now = time.time()
    real_ts = real_now - (mono_now - ts_float)
    dt = datetime.datetime.fromtimestamp(real_ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

# --- threaded readers ---

def _append_ordered(results: CollectedLogs, line: str):
    """Insert a new line into results.raw_logs maintaining chronological order."""
    ts = _parse_timestamp(line)
    with results.lock:
        timestamps = [_parse_timestamp(l) for l in results.raw_logs]
        bisect.insort(timestamps, ts)
        # Find the index where this timestamp belongs
        idx = timestamps.index(ts)
        results.raw_logs.insert(idx, line)

def _cfg80211_reader(results: CollectedLogs, stop_event: threading.Event):
    _enable_cfg80211_events()
    line_re = re.compile(r"(\d+\.\d+):\s+(\S+):\s+(.*)")
    try:
        with open(f"{TRACE_ROOT}/trace_pipe", "r", errors="ignore") as f:
            for line in f:
                if stop_event.is_set():
                    break
                m = line_re.search(line)
                if not m:
                    continue
                ts, evt, msg = m.groups()
                if any(e in evt for e in CFG_EVENTS):
                    tstr = _format_ts_for_journal(float(ts))
                    synthetic = f"{tstr} cfg80211[{evt}]: {msg.strip()}\n"
                    _append_ordered(results, synthetic)
    finally:
        _disable_cfg80211_events()

def collect_logs(results: CollectedLogs):
    """Start collecting both wpa_supplicant and cfg80211 logs, merged chronologically."""
    proc = subprocess.Popen(
        ["journalctl", "-u", "wpa_supplicant", "-o", "short-precise", "-f"],
        stdout=subprocess.PIPE,
        text=True
    )

    stop_event = threading.Event()

    def reader():
        for line in proc.stdout:
            _append_ordered(results, line)

    t1 = threading.Thread(target=reader, daemon=True)
    t1.start()

    t2 = threading.Thread(target=_cfg80211_reader, args=(results, stop_event), daemon=True)
    t2.start()

    return proc, stop_event

def stop_log_collection(proc: subprocess.Popen, stop_event: threading.Event):
    stop_event.set()
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    _disable_cfg80211_events()
    print("Stopped log collection")
