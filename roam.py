import wpa_cli_wrapper as wpa_cli
from dataclasses import dataclass
from time import sleep
import time
from log_collector import CollectedLogs

@dataclass
class RoamResults:
    bssid: str | None = None
    roam_time_ms: float | None = None


def wait_for_roam(collected: CollectedLogs, target_bssid: str, start_index: int, timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        new_logs = collected.raw_logs[start_index:]
        for line in new_logs:
            if "CTRL-EVENT-CONNECTED" in line:
                if target_bssid in line:
                    print("Roam succeeded:", target_bssid)
                    return True
                else:
                    print("Connected, but not target BSSID:", line.strip())
                    return True  # still counts as a roam
        time.sleep(0.2)
    return False




def start_roam_seq(iface: str, collected: CollectedLogs, mrssi: int = -75) -> list[RoamResults]:
    results: list[RoamResults] = []
    #get current connection SSID and BSSID
    current_connection = wpa_cli.get_current_connection(iface)
    if not current_connection.ssid:
        print("Wi-Fi interface",iface,"is not connected to a WLAN. Connect to WLAN and try again.")
        return results
    elif not current_connection.bssid:
        print("Wi-Fi interface not connected to WLAN. Connect to WLAN and try again.")
        return results
    print("Current SSID:", current_connection.ssid)
    print("Current BSSID:", current_connection.bssid,"\n")

    #use wpa_cli scan function to get list of candidate BSSIDs for roaming
    candidate_list = wpa_cli.get_scan_results(iface=iface,
                                              mrssi=mrssi,
                                              ssid_filter=current_connection.ssid,
                                              current_bssid=current_connection.bssid)
    
    #roam to each BSSID in candidate list
    for target in candidate_list:
        print("Roaming to", target.bssid)
        start_index = len(collected.raw_logs)
        wpa_cli.roam_to_bssid(iface=iface, bssid=target.bssid)

        if wait_for_roam(collected, target.bssid, start_index):
            print("Roam to", target.bssid, "completed")
        else:
            print("Roam to", target.bssid, "timed out or failed")
