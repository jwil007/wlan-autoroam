import subprocess
from time import sleep
import time
from dataclasses import dataclass
import re
from typing import List
from autoroam.iw_scan_parser import parse_iw_scan_output, ParsedScanResults

#Various shell commands live here

#Set variables for interface and min rssi threshold. May refactor later.
interface = "wlan0"
min_rssi = -75

#Create classes for the data collected
@dataclass
class CurrentConnectionInfo:
    ssid: str | None = None
    bssid: str | None = None


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

    return results

#wpa_cli command to initiate roam
def roam_to_bssid(iface: str, bssid: str) -> None:
    subprocess.run(["wpa_cli", "-i", iface, "roam", bssid],
                   capture_output=True, text=True)