"""
phase_breakout.py
-----------------
Per-phase enrichment built on top of log_analyzer.py results.

Uses the existing LogAnalysisDerived (and optionally LogAnalysisRaw)
to produce structured per-phase data for downstream use.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict
import json
from autoroam.log_analyzer import LogAnalysisDerived, LogAnalysisRaw


# ============================================================
#  Phase data container
# ============================================================

@dataclass
class PhaseResult:
    name: str
    start: Optional[datetime]
    end: Optional[datetime]
    duration_ms: Optional[float]
    status: str = "unknown"
    type: str = "unknown"
    errors: List[str] = None
    details: Dict[str, str] = None  # any extra derived info (FT used, PMK cache, etc.)

    def to_dict(self):
        return asdict(self)


# ============================================================
#  Phase analysis using existing derived fields
# ============================================================

def analyze_from_derived(derived: LogAnalysisDerived, raw: Optional[LogAnalysisRaw] = None) -> Dict[str, Dict]:
    """Consume existing derived + raw analysis results and organize by phase."""

    def fmt(ms):
        """Round to 2 decimal places if not None."""
        return round(ms, 2) if isinstance(ms, (int, float)) else None

    # Base info for each phase
    phases: list[PhaseResult] = [
        PhaseResult(
            name="Authentication",
            start=derived.roam_start_time,
            end=derived.auth_complete_time,
            duration_ms=fmt(derived.auth_duration_ms),
            status = "failure" if derived.auth_disco_time else ("success" if derived.auth_complete_time else "unknown"),
            type=derived.auth_type or "unknown",
            errors=[],
            details={},
        ),
        PhaseResult(
            name="Association",
            start=derived.assoc_start_time,
            end=derived.assoc_complete_time,
            duration_ms=fmt(derived.assoc_duration_ms),
            status = "failure" if derived.assoc_disco_time else ("success" if derived.assoc_complete_time else "unknown"),
            type="reassoc" if derived.assoc_start_time else "unknown",
            errors=[],
            details={},
        ),
        PhaseResult(
            name="EAP",
            start=derived.eap_start_time,
            end=derived.eap_success_time or derived.eap_failure_time,
            duration_ms=fmt(derived.eap_duration_ms),
            status=("failure" if derived.eap_failure_time else
                    "success" if derived.eap_success_time else "N/A"),
            type=derived.eap_type or "802.1X",
            errors=[],
            details={},
        ),
        PhaseResult(
            name="4-Way",
            start=derived.fourway_start_time,
            end=derived.fourway_success_time,
            duration_ms=fmt(derived.fourway_duration_ms),
            status = "failure" if derived.fourway_disco_time else ("success" if derived.fourway_success_time else "unknown"),
            type="RSN handshake",
            errors=[],
            details={},
        ),
    ]

    # Enrich with error logs if we have raw data
    if raw:
        if raw.eap_failure_logs:
            for l in raw.eap_failure_logs:
                phases[2].errors.append(l)
        if raw.assoc_err_logs:
            for log in raw.assoc_err_logs:
                phases[1].errors.append(log)
        if raw.noconfig_log:
            phases[0].errors.append(raw.noconfig_log)
        if raw.notarget_log:
            phases[0].errors.append(raw.notarget_log)
        if raw.auth_err_logs:
            for log in raw.auth_err_logs:
                phases[0].errors.append(log)
        if raw.pmksa_err_logs:
            for log in raw.pmksa_err_logs:
                phases[1].errors.append(log)
        if raw.auth_disco_log:
            phases[0].errors.append(raw.auth_disco_log)
        if raw.assoc_disco_log:
            phases[1].errors.append(raw.assoc_disco_log)
        if raw.eap_disco_log:
            phases[2].errors.append(raw.eap_disco_log)
        if raw.fourway_disco_log:
            phases[3].errors.append(raw.fourway_disco_log)


    return {p.name: p.to_dict() for p in phases}


# ============================================================
#  JSON export
# ============================================================

def save_phase_breakout(derived: LogAnalysisDerived, raw: Optional[LogAnalysisRaw] = None,
                        output_path="phase_breakout.json"):
    """Analyze and export per-phase JSON using existing derived results."""
    results = analyze_from_derived(derived, raw)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[+] Phase-level analysis saved to {output_path}")