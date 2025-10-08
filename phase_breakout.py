
"""
phase_breakout.py
-----------------
Post-analysis module for wlan-autoroam-cli.

Takes LogAnalysisDerived (and optionally raw logs) to produce structured
per-phase results with success/fail status, type, duration, and errors.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict
import json
import re

# ============================================================
#  Phase Base + Subclasses
# ============================================================

@dataclass
class PhaseBase:
    name: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "unknown"
    type: str = "unknown"
    errors: List[str] = None
    log_snippets: List[str] = None

    def __post_init__(self):
        self.errors = [] if self.errors is None else self.errors
        self.log_snippets = [] if self.log_snippets is None else self.log_snippets

    def analyze(self, logs: List[str]):
        """Default phase analysis (to be overridden)."""
        pass

    def to_dict(self):
        return asdict(self)


class AuthPhase(PhaseBase):
    def analyze(self, logs: List[str]):
        for l in logs:
            if "SAE" in l:
                self.type = "SAE"
            elif "FT" in l:
                self.type = "FT"
            elif "open system" in l.lower():
                self.type = "Open"
            if any(x in l for x in ["auth failed", "timeout", "challenge failed"]):
                self.errors.append(l)
        self.status = "failure" if self.errors else "success"


class AssocPhase(PhaseBase):
    def analyze(self, logs: List[str]):
        for l in logs:
            if "Associated with" in l:
                self.status = "success"
            if any(x in l for x in ["Association request", "reject", "timeout"]):
                self.errors.append(l)
        if self.errors:
            self.status = "failure"


class EapPhase(PhaseBase):
    def analyze(self, logs: List[str]):
        if any("EAP-Success" in l for l in logs):
            self.status = "success"
        if any("EAP-Failure" in l for l in logs):
            self.status = "failure"
        if any("TLS" in l for l in logs):
            self.type = "TLS"
        elif any("PEAP" in l for l in logs):
            self.type = "PEAP"


class FourWayPhase(PhaseBase):
    def analyze(self, logs: List[str]):
        if any("4-Way Handshake failed" in l for l in logs):
            self.status = "failure"
            self.errors = [l for l in logs if "4-Way Handshake failed" in l]
        elif any("WPA: Key negotiation completed" in l for l in logs):
            self.status = "success"


# ============================================================
#  Log filtering helpers
# ============================================================

def extract_timestamp(line: str) -> Optional[datetime]:
    """Try to parse the timestamp from a syslog-style line."""
    try:
        match = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2}\.\d+)", line)
        if not match:
            return None
        month_str, day, timestr = match.groups()
        ts_str = f"{month_str} {day} {timestr}"
        return datetime.strptime(ts_str, "%b %d %H:%M:%S.%f")
    except Exception:
        return None


def filter_logs_by_time(raw_logs: List[str], start: datetime, end: datetime) -> List[str]:
    """Return log lines that fall between the given timestamps."""
    if not start or not end:
        return []
    subset = []
    for line in raw_logs:
        ts = extract_timestamp(line)
        if ts and start <= ts <= end:
            subset.append(line)
    return subset


# ============================================================
#  Orchestration
# ============================================================

def analyze_all_phases(derived, raw_logs: List[str]) -> Dict[str, Dict]:
    """Create and run per-phase analyzers using time windows from LogAnalysisDerived."""
    phases = []

    mapping = [
        ("Authentication", AuthPhase, derived.auth_start_time or derived.roam_start_time, derived.auth_complete_time, derived.auth_duration_ms),
        ("Association", AssocPhase, derived.assoc_start_time, derived.assoc_complete_time, derived.assoc_duration_ms),
        ("EAP", EapPhase, derived.eap_start_time, derived.eap_success_time or derived.eap_failure_time, derived.eap_duration_ms),
        ("4-Way", FourWayPhase, derived.fourway_start_time, derived.fourway_success_time, derived.fourway_duration_ms),
    ]

    for name, cls, start, end, dur in mapping:
        phase = cls(name=name, start=start, end=end, duration_ms=dur)
        phase_logs = filter_logs_by_time(raw_logs, start, end)
        phase.analyze(phase_logs)
        phases.append(phase)

    return {p.name: p.to_dict() for p in phases}


def save_phase_breakout(derived, raw_logs: List[str], output_path="phase_breakout.json"):
    results = analyze_all_phases(derived, raw_logs)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[+] Phase-level analysis saved to {output_path}")


