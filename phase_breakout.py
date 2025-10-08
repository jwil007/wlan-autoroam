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
from log_analyzer import LogAnalysisDerived, LogAnalysisRaw


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

    # Base info for each phase
    phases: list[PhaseResult] = [
        PhaseResult(
            name="Authentication",
            start=derived.roam_start_time,
            end=derived.auth_complete_time,
            duration_ms=derived.auth_duration_ms,
            status="success" if derived.auth_complete_time else "unknown",
            type=derived.auth_type or "unknown",
            errors=[],
            details={
                "ft_used": str(derived.ft_success),
                "pmksa_cache_used": str(derived.pmksa_cache_used),
            },
        ),
        PhaseResult(
            name="Association",
            start=derived.assoc_start_time,
            end=derived.assoc_complete_time,
            duration_ms=derived.assoc_duration_ms,
            status="success" if derived.assoc_complete_time else "unknown",
            type="reassoc" if derived.assoc_start_time else "unknown",
            errors=[],
            details={"disconnects": str(derived.disconnect_count or 0)},
        ),
        PhaseResult(
            name="EAP",
            start=derived.eap_start_time,
            end=derived.eap_success_time or derived.eap_failure_time,
            duration_ms=derived.eap_duration_ms,
            status=("failure" if derived.eap_failure_time else
                    "success" if derived.eap_success_time else "unknown"),
            type=derived.eap_type or "802.1X",
            errors=[],
            details={},
        ),
        PhaseResult(
            name="4-Way",
            start=derived.fourway_start_time,
            end=derived.fourway_success_time,
            duration_ms=derived.fourway_duration_ms,
            status="success" if derived.fourway_success_time else "unknown",
            type="RSN handshake",
            errors=[],
            details={
                "pmksa_cache_used": str(derived.pmksa_cache_used),
            },
        ),
    ]

    # Enrich with error logs if we have raw data
    if raw:
        if raw.eap_failure_logs:
            for l in raw.eap_failure_logs:
                phases[2].errors.append(l)
        if raw.disconnect_logs:
            for l in raw.disconnect_logs:
                phases[1].errors.append(l)
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