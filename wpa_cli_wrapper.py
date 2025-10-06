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
    use_iw: bool = False,
) -> list[ParsedScanResults]:
    """
    Retrieve scan results using wpa_cli (default) or iw (if use_iw=True).
    Filters by ssid_filter and min RSSI, and sorts by RSSI descending.
    """
    results: list[ParsedScanResults] = []

    if not use_iw:
        print("scanning with wpa_cli")
        # --- existing wpa_cli path ---
        subprocess.run(["wpa_cli", "-i", iface, "scan"], capture_output=True, text=True)
        sleep(5)
        r = subprocess.run(["wpa_cli", "-i", iface, "scan_results"],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if ssid_filter and ssid_filter in line:
                parts = line.split(maxsplit=4)
                if len(parts) < 5:
                    continue
                try:
                    rssi_val = int(parts[2])
                except ValueError:
                    continue
                if rssi_val >= mrssi:
                    results.append(ParsedScanResults(
                        bssid=parts[0],
                        freq=parts[1],
                        rssi=rssi_val,
                        flags=parts[3],
                        ssid=parts[4]
                    ))
    else:
        print("scanning with iw")
        # --- new iw path ---
        # Perform an active scan for the target SSID
        scan_cmd = ["sudo", "iw", "dev", iface, "scan"]
        if ssid_filter:
            scan_cmd += ["ssid", ssid_filter]
        subprocess.run(scan_cmd, capture_output=True, text=True)

        r = subprocess.run(["sudo", "iw", "dev", iface, "scan"],
                           capture_output=True, text=True)

        bssid, freq, ssid, rssi = None, None, None, None
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("BSS "):
                # Commit previous entry
                if bssid and ssid and rssi is not None:
                    if (not ssid_filter or ssid_filter in ssid) and rssi >= mrssi:
                        results.append(ParsedScanResults(
                            bssid=bssid,
                            freq=freq,
                            rssi=rssi,
                            flags="(iw)",
                            ssid=ssid
                        ))

                # Start a new BSS
                bssid_raw = line.split()[1]
                bssid = bssid_raw.split("(")[0]  # clean off "(on"
                freq, ssid, rssi = None, None, None

            elif line.startswith("freq:"):
                try:
                    freq = int(float(line.split()[1].strip()))
                except (ValueError, IndexError):
                 freq = None
            elif line.startswith("signal:"):
                try:
                    rssi = int(float(line.split()[1]))
                except ValueError:
                    pass
            elif line.startswith("SSID:"):
                ssid = line.split("SSID:")[1].strip()

        # Commit last entry
        if bssid and ssid and rssi is not None:
            if (not ssid_filter or ssid_filter in ssid) and rssi >= mrssi:
                results.append(ParsedScanResults(
                    bssid=bssid,
                    freq=freq,
                    rssi=rssi,
                    flags="(iw)",
                    ssid=ssid
                ))

    # Sort by RSSI descending
    results.sort(key=lambda r: r.rssi, reverse=True)

    # Move current BSSID (if known) to the end of the list
    if current_bssid:
        non_current = [res for res in results if res.bssid != current_bssid]
        current = [res for res in results if res.bssid == current_bssid]
        results = non_current + current

    return results

#wpa_cli command to initiate roam
def roam_to_bssid(iface: str, bssid: str) -> None:
    subprocess.run(["wpa_cli", "-i", iface, "roam", bssid],
                   capture_output=True, text=True)