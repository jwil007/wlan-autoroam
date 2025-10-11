"""
cycle_summary.py
----------------
Aggregates per-cycle Wi-Fi roam test data.

Combines:
  • Environment info (SSID, security, scan candidates)
  • Per-roam derived metrics and phase analysis
  • Execution metadata (timestamps, total duration)
"""
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from log_analyzer import LogAnalysisDerived, LogAnalysisRaw
from phase_breakout import analyze_from_derived


def build_cycle_summary(
    ssid: str,
    security_type: str,
    candidates: List[Dict[str, str]],
    derived_raw_pairs: List[tuple[LogAnalysisDerived, Optional[LogAnalysisRaw]]],
    timestamp: Optional[str] = None,
    execution_duration_s: Optional[float] = None,
) -> Dict:
    """Aggregate all roams and metadata into a single JSON-ready structure."""

    cycle = {
        "ssid": ssid,
        "security_type": security_type,
        "timestamp": timestamp,
        "execution_duration_s": round(execution_duration_s or 0, 2),
        "candidates": candidates,
        "roams": []      
    }

    for idx, (derived, raw) in enumerate(derived_raw_pairs, start=1):
        phases = analyze_from_derived(derived, raw)

        cycle["roams"].append({
            "roam_index": idx,
            "target_bssid": getattr(derived, "roam_target_bssid", None),
            "final_bssid": getattr(derived, "roam_final_bssid", None),
            "final_freq": getattr(derived, "final_freq", None),
            "overall_status": "success" if not getattr(derived, "disconnect_bool", False) else "failure",
            "roam_duration_ms": round(getattr(derived, "roam_duration_ms", 0.0) or 0, 2),
            "failure_log": derived.failure_log,
            "details": {
                "ft_used": str(derived.ft_success),
                "pmksa_cache_used": str(derived.pmksa_cache_used),
                "disconnects": str(derived.disconnect_count or 0)
            },
            "phases": phases
        })

    return cycle


def save_cycle_summary(summary: Dict, output_file: str = "cycle_summary.json"):
    """Write full cycle summary to the repo's data directory."""
    # Correct root is the directory where this script resides
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, output_file)
    tmp_path = output_path + ".tmp"

    with open(tmp_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, output_path)
    print(f"[+] Full cycle summary saved to {output_path}")