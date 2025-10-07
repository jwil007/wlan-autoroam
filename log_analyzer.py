from log_collector import CollectedLogs
from datetime import datetime
from dataclasses import dataclass, field
import re

@dataclass
class LogAnalysisRaw:
    iface_control_start: str | None = None
    roam_start_log: str | None = None
    roam_end_log: str | None = None
    auth_complete_log: str | None = None
    assoc_start_log: str | None = None
    assoc_complete_log: str | None = None
    freq_log: str | None = None
    key_mgmt_log: str | None = None
    fourway_start_log: str | None = None
    fourway_success_log: str | None = None
    ft_success_logs: list[str] = field(default_factory=list)
    eap_start_logs: list[str] = field(default_factory=list)
    eap_success_logs: list[str] = field(default_factory=list)
    eap_failure_logs: list[str] = field(default_factory=list)
    disconnect_logs: list[str] = field(default_factory=list)
    pmksa_cache_used_log: str | None = None
    noconfig_log: str | None = None
    notarget_log: str | None = None
    other_logs: list[str] = field(default_factory=list)

@dataclass
class LogAnalysisDerived:
    roam_target_bssid: str | None = None
    roam_final_bssid: str | None = None
    auth_complete_time: datetime | None = None
    auth_duration_ms: datetime | None = None
    assoc_start_time: float | None = None
    assoc_complete_time: datetime | None = None
    assoc_duration_ms: float | None = None
    final_freq: int | None = None
    roam_start_time: datetime | None = None
    roam_end_time: datetime | None = None
    wpa_params: str | None = None
    fourway_start_time: datetime | None = None
    fourway_success_time: datetime | None = None
    fourway_duration_ms: float | None = None
    eap_start_time: datetime | None = None
    eap_success_time: datetime | None = None
    eap_failure_time: datetime | None = None
    roam_duration_ms: float | None = None
    eap_duration_ms: float | None = None 
    key_mgmt : str | None = None
    pmksa_cache_used: bool | None = None
    disconnect_count: int | None = None
    disconnect_bool: bool | None = None
    ft_success: bool | None = None
    noconfig_err: bool | None = None
    notarget_err: bool | None = None

def pretty_print_derived(derived: LogAnalysisDerived) -> str:
    def fmt(val, fmt_str="{:.2f}"):
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return fmt_str.format(val)
        return str(val)

    return (
        f"\n--- Roam Analysis ---\n"
        f"Target BSSID:   {fmt(derived.roam_target_bssid)}\n"
        f"Final BSSID:    {fmt(derived.roam_final_bssid)}\n"
        f"Final freq:     {fmt(derived.final_freq)}\n"
        f"Key mgmt:       {fmt(derived.key_mgmt)}\n"
        f"FT Used:        {fmt(derived.ft_success)}\n"
        f"PMK Cache Used: {fmt(derived.pmksa_cache_used)}\n"
        f"Auth Start time:{fmt(derived.roam_start_time)}\n"
        f"Auth fin time:  {fmt(derived.auth_complete_time)}\n"
        f"Auth duration:  {fmt(derived.auth_duration_ms)} ms\n"
        f"Assoc strt time:{fmt(derived.assoc_start_time)}\n"
        f"Assoc fin time: {fmt(derived.assoc_complete_time)}\n"
        f"Assoc duration: {fmt(derived.assoc_duration_ms)} ms\n"
        f"EAP Start:      {fmt(derived.eap_start_time)}\n"
        f"EAP Success:    {fmt(derived.eap_success_time)}\n"
        f"EAP Failure:    {fmt(derived.eap_failure_time)}\n"
        f"EAP Duration:   {fmt(derived.eap_duration_ms)} ms\n"
        f"4way start:     {fmt(derived.fourway_start_time)}\n"
        f"4way success:   {fmt(derived.fourway_success_time)}\n"
        f"4way duration:  {fmt(derived.fourway_duration_ms)} ms\n"
        f"Disconnect:     {fmt(derived.disconnect_bool)}\n"
        f"Disconnect cnt: {fmt(derived.disconnect_count)}\n"
        f"Roam Start:     {fmt(derived.roam_start_time)}\n"
        f"Roam End:       {fmt(derived.roam_end_time)}\n"
        f"Roam Duration:  {fmt(derived.roam_duration_ms)} ms\n"
        f"No config err:  {fmt(derived.noconfig_err)}\n"
        f"No target err:  {fmt(derived.notarget_err)}\n"
        f"----------------------\n"
    )

def split_into_roams(logs: list[str]) -> list[list[str]]:
    """
    Split raw logs into per-roam chunks based on the ROAM command.
    Each chunk starts with 'CTRL_IFACE ROAM <MAC>'.
    """
    chunks: list[list[str]] = []
    current_chunk: list[str] = []

    # Regex: CTRL_IFACE ROAM followed by a MAC address
    roam_start_re = re.compile(r"CTRL_IFACE ROAM ([0-9a-f]{2}(:[0-9a-f]{2}){5})", re.IGNORECASE)

    for line in logs:
        if roam_start_re.search(line):
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

#matches raw logs
def find_raw_logs(logs: list[str]) -> LogAnalysisRaw:
    # key = attribute name on LogAnalysisRaw
    # value = (list of markers, allow_multiple flag)
    LOG_MARKERS: dict[str, tuple[list[str], bool]] = {
        "iface_control_start": (["CTRL_IFACE ROAM "], False),
        "roam_start_log":      (["nl80211: Authentication request send successfully"], False),
        "roam_end_log":        (["CTRL-EVENT-CONNECTED"], False),
        "auth_complete_log":   (["State: AUTHENTICATING -> ASSOCIATING"], False),
        "assoc_start_log":     (["nl80211: Association request send successfully"], False),
        "assoc_complete_log":  (["State: ASSOCIATING -> ASSOCIATED"], False),
        "ft_success_logs":     (["FT: Completed successfully"], True),
        "eap_start_logs":      (["CTRL-EVENT-EAP-START"], True),
        "eap_success_logs":    (["CTRL-EVENT-EAP-SUCCESS"], True),
        "eap_failure_logs":    (["CTRL-EVENT-EAP-FAILURE"], True),
        "disconnect_logs":     (["State: ASSOCIATING -> DISCONNECTED","-> DISCONNECTED",], True),
        "key_mgmt_log":        (["WPA: using KEY_MGMT","RSN: using KEY_MGMT"], False),
        "fourway_start_log":   (["WPA: RX message 1 of 4-Way Handshake"], False),
        "fourway_success_log": (["WPA: Key negotiation completed"], False),
        "pmksa_cache_used_log":(["PMKSA caching was used"], False),
        "freq_log":            (["Operating frequency changed from"], False),
        "noconfig_log":        (["No network configuration known"], False),
        "notarget_log":        (["Target AP not found from BSS table"], False)

    }

    raw = LogAnalysisRaw()

    for line in logs:
        for attr, (markers, allow_multiple) in LOG_MARKERS.items():
            for marker in markers:   # preserve order
                if marker in line:
                    if allow_multiple:
                        getattr(raw, attr).append(line)
                    else:
                         if getattr(raw, attr) is None:   # only set first match
                            setattr(raw, attr, line)
                    break   # stop checking further markers for this attribute
    return raw

#Helper to extract timestamp
def parse_ts_from_line(line: str, year: int) -> datetime | None:
    try:
        ts = line[:22]
        return datetime.strptime(f"{year} {ts}", "%Y %b %d %H:%M:%S.%f")
    except Exception:
        return None
    
#helper with regex to extract MAC addresses
def extract_mac(line: str) -> str | None:
    match = re.search(r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", line)
    if match:
        return match.group(1)
    return None

#parses select raw log lines into metrics, and does operations for stuff like time duration
def derive_metrics(raw: LogAnalysisRaw) -> LogAnalysisDerived:
    derived = LogAnalysisDerived()
    year = datetime.now().year

    TIMESTAMP_FIELDS: dict[str, tuple[str, bool]] = {
        "roam_start_time":     ("roam_start_log", False),
        "roam_end_time":       ("roam_end_log", False),
        "auth_complete_time":  ("auth_complete_log", False),
        "assoc_start_time":    ("assoc_start_log", False),
        "assoc_complete_time": ("assoc_complete_log", False),
        "fourway_start_time":  ("fourway_start_log", False),
        "fourway_success_time":("fourway_success_log", False),
        "eap_start_time":      ("eap_start_logs", True),
        "eap_success_time":    ("eap_success_logs", True),
        "eap_failure_time":    ("eap_failure_logs", True),
    }

    for derived_attr, (raw_attr, is_list) in TIMESTAMP_FIELDS.items():
        value = getattr(raw, raw_attr)
        if not value:
            continue
        if is_list:
            value = value[0]  # take the first log line
        setattr(derived, derived_attr, parse_ts_from_line(value, year))

    #total roam duration
    if derived.roam_start_time and derived.roam_end_time:
        duration = derived.roam_end_time - derived.roam_start_time
        derived.roam_duration_ms = duration.total_seconds() * 1000
    #4way duration
    if derived.fourway_start_time and derived.fourway_success_time:
        duration = derived.fourway_success_time - derived.fourway_start_time
        derived.fourway_duration_ms = duration.total_seconds() * 1000
    #auth duration
    if derived.roam_start_time and derived.auth_complete_time:
        duration = derived.auth_complete_time - derived.roam_start_time
        derived.auth_duration_ms = duration.total_seconds() * 1000
    #assoc duration
    if derived.assoc_start_time and derived.assoc_complete_time:
        duration = derived.assoc_complete_time - derived.assoc_start_time
        derived.assoc_duration_ms = duration.total_seconds() * 1000
    # --- EAP duration ---
    if raw.eap_start_logs:
        start_ts = raw.eap_start_logs[0][:22]
        eap_start_time = datetime.strptime(f"{year} {start_ts}", "%Y %b %d %H:%M:%S.%f")
        derived.eap_start_time = eap_start_time

        # Prefer success, otherwise failure
        if raw.eap_success_logs:
            end_ts = raw.eap_success_logs[0][:22]
            eap_end_time = datetime.strptime(f"{year} {end_ts}", "%Y %b %d %H:%M:%S.%f")
            derived.eap_success_time = eap_end_time
        elif raw.eap_failure_logs:
            end_ts = raw.eap_failure_logs[0][:22]
            eap_end_time = datetime.strptime(f"{year} {end_ts}", "%Y %b %d %H:%M:%S.%f")
            derived.eap_failure_time = eap_end_time
        else:
            eap_end_time = None

        if eap_start_time and eap_end_time:
            derived.eap_duration_ms = (eap_end_time - eap_start_time).total_seconds() * 1000

    #Get MACs for target and final BSSID
    if raw.iface_control_start:
        derived.roam_target_bssid = extract_mac(raw.iface_control_start)

    if raw.roam_end_log:
        derived.roam_final_bssid = extract_mac(raw.roam_end_log)

    #Get Key mgmt string
    if raw.key_mgmt_log:
        derived.key_mgmt = raw.key_mgmt_log.split("KEY_MGMT", 1)[1].strip()

    #Check PMK Cache
    if raw.pmksa_cache_used_log:
        derived.pmksa_cache_used = True
    else:
        derived.pmksa_cache_used = False

    #Get final freq
    if raw.freq_log:
        derived.final_freq = raw.freq_log.split()[-2]

    #Disconnects
    if raw.disconnect_logs:
        derived.disconnect_bool = True
        derived.disconnect_count = len(raw.disconnect_logs)
    else:
        derived.disconnect_bool = False

    #FT Success
    if raw.ft_success_logs:
        derived.ft_success = True
    else:
        derived.ft_success = False

    #Error logs
    if raw.noconfig_log:
        derived.noconfig_err = True
    else:
        derived.noconfig_err = False
    
    if raw.notarget_log:
        derived.notarget_err = True
    else:
        derived.notarget_err = False

    return derived

def analyze_all_roams(collected: CollectedLogs) -> list[LogAnalysisDerived]:
    """
    High-level orchestrator: split logs → extract raw → compute derived.
    """
    chunks = split_into_roams(collected.raw_logs)
    results: list[LogAnalysisDerived] = []

    for chunk in chunks:
        raw = find_raw_logs(chunk)
        print("ROAM START LOG:", raw.roam_start_log)
   #     print(raw.fourway_start_log)
    #    print(raw.notarget_log)
        derived = derive_metrics(raw)
        results.append(derived)

    return results