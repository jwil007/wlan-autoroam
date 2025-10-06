import argparse
import time
from log_collector import CollectedLogs, collect_logs, stop_log_collection
from log_analyzer import analyze_all_roams, pretty_print_derived
from wpa_cli_wrapper import (
    set_log_level,
    restore_log_level,
    get_current_connection,
    get_scan_results,
    roam_to_bssid,
)
import subprocess


def wait_for_connected(collected: CollectedLogs, start_index: int, timeout: float = 20.0) -> bool:
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

    #Definte input params
    parser = argparse.ArgumentParser(description="Wi-Fi Roam Test Tool")
    parser.add_argument("-i", "--iface", default="wlan0", help="Wi-Fi interface to use")
    parser.add_argument("-r", "--rssi", type=int, default=-75, help="Minimum RSSI filter")
    parser.add_argument(
        "-d", "--debug",
        nargs="?", const="roam_debug.log", metavar="FILE",
        help="Save raw collected logs to a file (default: roam_debug.log if no FILE provided)"
    )
    args = parser.parse_args()

    iface = args.iface
    min_rssi = args.rssi
    

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
            use_iw=True
        )
        print("Candidates\n")
        for target in candidates:
            print (f"BSSID:",target.bssid,"freq:",target.freq,"rssi:",target.rssi)
        # roam to each candidate
        print("\n")
        for target in candidates:
            print(f"Roaming to {target.bssid} (RSSI {target.rssi} dBm, Freq {target.freq} MHz)")
            start_index = len(collected.raw_logs)

            # perform the roam
            roam_to_bssid(iface, target.bssid)

            if wait_for_connected(collected, start_index):
                print(f"Roam to {target.bssid} completed")
                # small delay to let the connection settle
                time.sleep(1)
                # trigger a controlled deauth (instead of full disconnect)
                subprocess.run(["wpa_cli", "-i", iface, "deauthenticate", target.bssid],
                            capture_output=True, text=True)
                time.sleep(0.5)
            else:
                print(f"Roam to {target.bssid} timed out or failed")



        # analyze logs afterwards
        results = analyze_all_roams(collected)
        for r in results:
            print(pretty_print_derived(r))

    finally:
        stop_log_collection(proc)
        restore_log_level(iface, original_log_level)
    
    if args.debug:
        try:
            with open(args.debug, "w") as f:
                f.writelines(collected.raw_logs)
            print(f"Saved raw logs to {args.debug}")
        except Exception as e:
            print(f"Failed to save debug logs: {e}")


if __name__ == "__main__":
    main()
