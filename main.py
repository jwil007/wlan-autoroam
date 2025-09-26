from time import sleep
import time
from log_collector import CollectedLogs, collect_logs, stop_log_collection
from log_analyzer import analyze_all_roams, pretty_print_derived
from wpa_cli_wrapper import set_log_level, restore_log_level, get_current_connection, get_scan_results, roam_to_bssid


def wait_for_connected(collected: CollectedLogs, start_index: int, timeout: float = 10.0) -> bool:
    """
    Watch logs for a CTRL-EVENT-CONNECTED message after a roam attempt.
    Returns True if seen, False if timed out.
    """
    start = time.time()
    while time.time() - start < timeout:
        new_logs = collected.raw_logs[start_index:]
        for line in new_logs:
            if "CTRL-EVENT-CONNECTED" in line:
                print("Connected event:", line.strip())
                return True
        time.sleep(0.2)
    return False


def main():
    iface = "wlan0"
    min_rssi = -75

    # set log level to DEBUG (restore later)
    log_set_result, original_log_level = set_log_level(iface, "DEBUG")

    if not log_set_result:
        print("Failed to set log level to DEBUG")
        return

    collected = CollectedLogs()
    proc = collect_logs(collected)

    try:
        # get current SSID/BSSID
        current = get_current_connection(iface)
        if not current.ssid or not current.bssid:
            print("Wi-Fi interface is not connected to a WLAN.")
            return

        print("Current SSID:", current.ssid)
        print("Current BSSID:", current.bssid, "\n")

        # get candidate list
        candidates = get_scan_results(
            iface=iface,
            mrssi=min_rssi,
            ssid_filter=current.ssid,
            current_bssid=current.bssid,
        )

        # roam to each candidate
        for target in candidates:
            print(f"Roaming to {target.bssid} (RSSI {target.rssi} dBm, Freq {target.freq} MHz)")
            start_index = len(collected.raw_logs)

            roam_to_bssid(iface, target.bssid)

            if wait_for_connected(collected, start_index):
                print("Roam to", target.bssid, "completed")
            else:
                print("Roam to", target.bssid, "timed out or failed")

        # analyze logs afterwards
        results = analyze_all_roams(collected)
        for r in results:
            print(pretty_print_derived(r))

    finally:
        stop_log_collection(proc)
        restore_log_level(iface, original_log_level)


if __name__ == "__main__":
    main()
