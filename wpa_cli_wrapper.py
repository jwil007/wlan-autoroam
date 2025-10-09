import subprocess
from time import sleep
import time
from dataclasses import dataclass, field
import re
from typing import List

#This code contains the wpa_cli commands to get current SSID, get scan list, and initiate roams.

#Set variables for interface and min rssi threshold. May refactor later.
interface = "wlan0"
min_rssi = -75

#Create classes for the data collected
@dataclass
class CurrentConnectionInfo:
    ssid: str | None = None
    bssid: str | None = None

@dataclass
class ParsedScanResults:
    bssid: str | None = None
    freq: int | None = None
    rssi: int | None = None
    auth_suites: list[str] = field(default_factory=list)
    mfp_flag: str | None = None
    supported_rates: str | None = None
    qbss_util_prct: float | None = None
    qbss_sta_count: int | None = None
    ssid: str | None = None


def parse_iw_scan_output(iw_output: str,
                         ssid_filter: str | None = None,
                         mrssi: int = -100) -> List[ParsedScanResults]:
    """
    Parse 'iw dev <iface> scan' output into structured results.
    """
    DEBUG_PARSE = False  # toggle this to False later

    results: List[ParsedScanResults] = []

    # Split blocks robustly (each "BSS ..." starts a new section)
    blocks = re.split(r"(?m)^\s*(?=BSS\s+[0-9A-Fa-f:]{17}\b)", iw_output)
    for raw_block in blocks:
        if not raw_block.strip():
            continue

        lines = raw_block.strip().splitlines()
        bssid_match = re.match(r"BSS\s+([0-9a-f:]{17})", lines[0])
        if not bssid_match:
            continue
        bssid = bssid_match.group(1)

        # Initialize fields
        freq = rssi = qbss_sta_count = None
        qbss_util = None
        ssid = supported_rates = mfp_flag = None
        auth_suites: list[str] = []

        for line in lines:
            line = line.strip()
            if DEBUG_PARSE and (
                "freq:" in line or
                "signal:" in line or
                "SSID:" in line or
                "Authentication suites:" in line or
                "Capabilities:" in line or
                "station count:" in line or
                "channel utilisation:" in line
            ):
                print(f"[{bssid}] {line}")

            if line.startswith("freq:"):
                try:
                    freq = int(float(line.split()[1]))
                except Exception:
                    pass

            elif line.startswith("signal:"):
                try:
                    rssi = int(float(line.split()[1]))
                except Exception:
                    pass

            elif line.startswith("SSID:"):
                ssid = line.split("SSID:")[1].strip()

            elif line.startswith("Supported rates:"):
                supported_rates = line.split("Supported rates:")[1].strip()

            elif "Authentication suites:" in line:
                suites = line.split("Authentication suites:")[1].strip()
                auth_suites.extend(suites.split())

            elif "Capabilities:" in line and "PTKSA" in line:
                if "MFP-required" in line:
                    mfp_flag = "MFP-required"
                elif "MFP-capable" in line:
                    mfp_flag = "MFP-capable"
                elif mfp_flag is None:
                    mfp_flag = "No MFP"

                # debug only: scoped to a single BSS block
                if ssid and (not ssid_filter or ssid == ssid_filter):
                    print(f"[{ssid}] {line}")

            elif "station count:" in line:
                match = re.search(r"\*?\s*station count:\s*(\d+)", line)
                if match:
                    qbss_sta_count = int(match.group(1))

            elif "channel utilisation:" in line:
                match = re.search(r"\*?\s*channel utilisation:\s*(\d+)/255", line)
                if match:
                    qbss_util_prct = round((int(match.group(1)) / 255) * 100, 1)

        # Debug what the filter check looks like
        if DEBUG_PARSE:
            print(f"Filter check → ssid={ssid!r}, ssid_filter={ssid_filter!r}, rssi={rssi}")

        # Filter: match SSID (case-insensitive, ignore stray whitespace)
        if (
            ssid
            and (not ssid_filter or ssid.strip().lower() == ssid_filter.strip().lower())
            and rssi is not None
            and rssi >= mrssi
        ):
            results.append(
                ParsedScanResults(
                    bssid=bssid,
                    freq=freq,
                    rssi=rssi,
                    ssid=ssid,
                    auth_suites=auth_suites,
                    mfp_flag=mfp_flag,
                    supported_rates=supported_rates,
                    qbss_util_prct=qbss_util_prct,
                    qbss_sta_count=qbss_sta_count,
                )
            )

    print(f"[DEBUG] Parsed {len(results)} BSS entries after filtering\n")
    return results

#Set log level DEBUG - needed for log parsing.
def set_log_level(iface: str, level = str) -> tuple[bool, str | None]:
    #check current log level
    current_log_level = subprocess.run(
        ["wpa_cli","-i",iface,"log_level"],
                capture_output = True,
                text = True,
                check = True
    )
    for line in current_log_level.stdout.splitlines():
        if line.startswith("Current level:"):
            original_log_level = line.split(":")[1].strip()
            print("Log level currently set to",original_log_level)
            if original_log_level == level:
                print ("log level already set correctly")
                return True, original_log_level
            else:
                try:
                    result = subprocess.run(
                        ["wpa_cli","-i",iface,"log_level",level],
                        capture_output = True,
                        text = True,
                        check = True
                    )
                    print("changing log level to",level,result.stdout)
                    return True, original_log_level
                except subprocess.CalledProcessError as e:
                    print(f"Failed to set log level: {e.stderr.strip()}")
                    return False, original_log_level
            
def restore_log_level(iface = str, original_log_level = str) -> bool:
    try:    
        r = subprocess.run(
            ["wpa_cli","-i",iface,"log_level",original_log_level],
            capture_output = True,
            text = True,
            check = True
        )
        print("returned log level to original value:",original_log_level,r.stdout)
        return (True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to set log level: {e.stderr.strip()}")
        return False

#Uses wpa_cli status to find current connection stats
def get_current_connection(iface: str = interface) -> CurrentConnectionInfo:
    r = subprocess.run(["wpa_cli","-i",iface,"status"],
                       capture_output=True,
                       text=True)
    conn = CurrentConnectionInfo()
    for line in r.stdout.splitlines():
        if line.startswith("ssid"):
            conn.ssid = line.split("=",1)[1]
        elif line.startswith("bssid"):
            conn.bssid = line.split("=",1)[1]
    return conn

#Use wpa_cli scan and scan_results to build candidate list
def get_scan_results(
    iface: str,
    mrssi: int = -75,
    ssid_filter: str | None = None,
    current_bssid: str | None = None,
) -> List[ParsedScanResults]:
    """
    Retrieve Wi-Fi scan results using `iw dev <iface> scan`.
    Filters by SSID and minimum RSSI, sorts by RSSI descending,
    and moves the current BSSID (if any) to the end of the list.
    """
    MAX_RETRIES = 5
    RETRY_DELAY = 2.0
    results_output = None

    print(f"Scanning with iw on {iface}...")
    scan_cmd = ["sudo", "iw", "dev", iface, "scan"]
    if ssid_filter:
        scan_cmd += ["ssid", ssid_filter]

    for attempt in range(1, MAX_RETRIES + 1):
        r = subprocess.run(scan_cmd, capture_output=True, text=True)
        if r.stdout.strip():
            results_output = r.stdout
            break
        print(f"[iw scan] attempt {attempt}/{MAX_RETRIES} returned no results, retrying...")
        time.sleep(RETRY_DELAY)

    if results_output is None:
        print("[iw scan] no scan results after retries.")
        return []

    # --- Parse results ---
    results = parse_iw_scan_output(results_output, ssid_filter=ssid_filter, mrssi=mrssi)

    # --- Sort results by RSSI descending ---
    results.sort(key=lambda r: r.rssi or -999, reverse=True)

    # --- Move current BSSID to the end, if known ---
    if current_bssid:
        non_current = [res for res in results if res.bssid != current_bssid]
        current = [res for res in results if res.bssid == current_bssid]
        results = non_current + current

    # --- Print summary for debug ---
    # print("\n=== Parsed iw scan results ===\n")
    # for ap in results:
    #     print(f"BSSID: {ap.bssid}")
    #     print(f"  SSID:             {ap.ssid}")
    #     print(f"  Freq:             {ap.freq} MHz")
    #     print(f"  RSSI:             {ap.rssi} dBm")
    #     print(f"  Supported rates:  {ap.supported_rates}")
    #     print(f"  Auth suites:      {', '.join(ap.auth_suites) if ap.auth_suites else 'N/A'}")
    #     print(f"  MFP flag:         {ap.mfp_flag}")
    #     print(f"  QBSS util prct:   {ap.qbss_util_prct if ap.qbss_util_prct is not None else 'N/A'}%")
    #     print(f"  QBSS STA count:   {ap.qbss_sta_count if ap.qbss_sta_count is not None else 'N/A'}\n")
    # print("====================================\n")

    return results

#wpa_cli command to initiate roam
def roam_to_bssid(iface: str, bssid: str) -> None:
    subprocess.run(["wpa_cli", "-i", iface, "roam", bssid],
                   capture_output=True, text=True)