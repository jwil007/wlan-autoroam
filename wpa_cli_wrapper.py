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


