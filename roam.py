import wpa_cli_wrapper as wpa_cli
from dataclasses import dataclass
from time import sleep

@dataclass
class RoamResults:
    bssid: str | None = None
    roam_time_ms: float | None = None


def start_roam_seq(iface: str, mrssi: int = -75) -> list[RoamResults]:
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
        print("Roaming to",target.bssid,
              "RSSI:",target.rssi,"dBm",
              "Frequency:",target.freq,"MHz")
        wpa_cli.roam_to_bssid(iface=iface,
                              bssid=target.bssid)
        sleep(2)



start_roam_seq("wlan0")