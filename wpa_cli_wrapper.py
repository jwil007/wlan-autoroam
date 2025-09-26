import subprocess
from time import sleep
from dataclasses import dataclass

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
    freq: str | None = None
    rssi: int | None = None
    flags: str | None = None
    ssid: str | None = None

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
    iface: str = interface,
    mrssi: int = min_rssi,
    ssid_filter: str | None = None,
    current_bssid: str | None = None,
)-> list[ParsedScanResults]:
    subprocess.run(["wpa_cli","-i",iface,"scan"],
                    capture_output=True,
                    text=True)
    sleep(5)
    r = subprocess.run(["wpa_cli","scan_results"],
                       capture_output=True,
                       text=True)
    results: list[ParsedScanResults] = []
    for line in r.stdout.splitlines():
        if ssid_filter and ssid_filter in line:
            parts = line.split(maxsplit=4)
            if len(parts) < 5:
                continue

            if int(parts[2]) >= mrssi:
                result = ParsedScanResults(
                    bssid = parts[0],
                    freq = parts[1],
                    rssi= int(parts[2]),
                    flags = parts[3],
                    ssid = parts [4]
                )
                results.append(result)
    #Sort results by RSSI
    results.sort(key=lambda r: r.rssi, reverse=True)
    #move current BSSID entry to bottom
    reordered: list[ParsedScanResults]=[]
    for res in results:
        if not current_bssid or res.bssid != current_bssid:
            reordered.append(res)
    for res in results:
        if current_bssid and res.bssid == current_bssid:
            reordered.append(res)
    results = reordered
    return results

#wpa_cli command to initiate roam
def roam_to_bssid(iface: str, bssid: str) -> None:
    subprocess.run(["wpa_cli", "-i", iface, "roam", bssid],
                   capture_output=True, text=True)
