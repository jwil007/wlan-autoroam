from log_collector import CollectedLogs
import pickle
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class LogAnalysisRaw:
    iface_control_start: str | None = None
    roam_start_log: str | None = None
    roam_end_log: str | None = None
    ft_success_logs: list[str] = field(default_factory=list)
    eap_start_logs: list[str] = field(default_factory=list)
    eap_success_logs: list[str] = field(default_factory=list)
    eap_failure_logs: list[str] = field(default_factory=list)
    disconnect_logs: list[str] = field(default_factory=list)
    other_logs: list[str] = field(default_factory=list)

class LogAnalysisDerived:
    roam_target_bssid: str | None = None
    roam_final_bssid: str | None = None
    roam_start_time: datetime | None = None
    roam_end_time: datetime | None = None
    eap_start_time: datetime | None = None
    eap_success_time: datetime | None = None
    eap_failure_time: datetime | None = None
    roam_duration_ms: float | None = None
    eap_time_ms: float | None = None 


with open("sample_results.pkl", "rb") as f:
    test_data: CollectedLogs = pickle.load(f)

def split_into_roams(logs: list[str]) -> list[list[str]]:
    """
    Split raw logs into per-roam chunks based on the ROAM command.
    Each chunk starts with 'Control interface command ROAM'
    and ends just before the next 'ROAM', or EOF if it's the last roam.
    """
    chunks: list[list[str]] = []
    current_chunk: list[str] = []

    start_marker = "Control interface command 'ROAM"

    for line in logs:
        if start_marker in line:
            # If we already have a chunk, close it before starting a new one
            if current_chunk:
                chunks.append(current_chunk)
            # Start a new chunk
            current_chunk = [line]
        else:
            if current_chunk:  # only collect lines if inside a roam
                current_chunk.append(line)

    # Append the final chunk (if any)
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def find_raw_logs(logs: list[str]) -> LogAnalysisRaw:
    #String matches for each log type to grab.
    #if multiple markers in list, code will match in order
    iface_cmd_markers = [
    "Control interface command 'ROAM",
    ]
    roam_start_markers = [
    "State: COMPLETED -> AUTHENTICATING",
    ]
    roam_end_markers = [
    "CTRL-EVENT-CONNECTED",
    ]
    ft_success_markers = [
    "FT: Completed successfully",
    ]
    eap_start_markers = [
    "CTRL-EVENT-EAP-START",
    ]
    eap_success_markers = [
    "CTRL-EVENT-EAP-SUCCESS",
    ]
    eap_failure_markers = [
    "CTRL-EVENT-EAP-FAILURE",
    ]
    disconnect_markers = [
    "State: ASSOCIATING -> DISCONNECTED",
    ]
    raw = LogAnalysisRaw()
    for line in logs:
        if any(marker in line for marker in iface_cmd_markers):
            for marker in iface_cmd_markers:
                if marker in line:
                    raw.iface_control_start = line
                    break
        elif any(marker in line for marker in roam_start_markers):
            for marker in roam_start_markers:
                if marker in line:
                    raw.roam_start_log = line
                    break
        elif any(marker in line for marker in roam_end_markers):
            for marker in roam_end_markers:
                if marker in line:
                    raw.roam_end_log = line
                    break
        elif any(marker in line for marker in ft_success_markers):
            for marker in ft_success_markers:
                if marker in line:
                    raw.ft_success_logs.append(line)
        elif any(marker in line for marker in eap_start_markers):
            for marker in eap_start_markers:
                if marker in line:
                    raw.eap_start_logs.append(line)
        elif any(marker in line for marker in eap_success_markers):
            for marker in eap_success_markers:
                if marker in line:
                    raw.eap_success_logs.append(line)
        elif any(marker in line for marker in eap_failure_markers):
            for marker in eap_failure_markers:
                if marker in line:
                    raw.eap_failure_logs.append(line)
        elif any(marker in line for marker in disconnect_markers):
            for marker in disconnect_markers:
                if marker in line:
                    raw.disconnect_logs.append(line)
        elif raw:
            raw.other_logs.append(line)    
    return raw


def derive_metrics(raw: LogAnalysisRaw) -> LogAnalysisDerived:
    derived = LogAnalysisDerived()
    #Get start/end times
    year = datetime.now().year
    if raw.roam_start_log:
        ts = raw.roam_start_log[:22]  # trim to timestamp part
        year = datetime.now().year
        derived.roam_start_time = datetime.strptime(
            f"{year} {ts}", "%Y %b %d %H:%M:%S.%f"
        )

    if raw.roam_end_log:
        ts = raw.roam_end_log[:22]
        year = datetime.now().year
        derived.roam_end_time = datetime.strptime(
            f"{year} {ts}", "%Y %b %d %H:%M:%S.%f"
        )
    if raw.eap_start_logs:
        ts = raw.eap_start_logs[-1][:22]
        derived.eap_start_time = datetime.strptime(
            f"{year} {ts}", "%Y %b %d %H:%M:%S.%f"
        )

    if raw.eap_success_logs:
        ts = raw.eap_start_logs[-1][:22]
        derived.eap_success_time = datetime.strptime(
            f"{year} {ts}", "%Y %b %d %H:%M:%S.%f"
        )

    #calculate duration
    if derived.roam_start_time and derived.roam_end_time:
        duration = derived.roam_end_time - derived.roam_start_time
        derived.roam_duration_ms = duration.total_seconds() * 1000
        print(derived.roam_duration_ms)






def analyze_all_roams(collected: CollectedLogs) -> list[LogAnalysisDerived]:
    """
    High-level orchestrator: split logs → extract raw → compute derived.
    """
    chunks = split_into_roams(collected.raw_logs)
    results: list[LogAnalysisDerived] = []

    for chunk in chunks:
        raw = find_raw_logs(chunk)
        derived = derive_metrics(raw)
        results.append(derived)

    return results

analyze_all_roams(test_data)

