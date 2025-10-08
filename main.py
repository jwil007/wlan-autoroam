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
from phase_breakout import analyze_from_derived, save_phase_breakout


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
    # ----------------------------------------
    # CLI Arguments
    # ----------------------------------------
    parser = argparse.ArgumentParser(description="Wi-Fi Roam Test Tool")
    parser.add_argument("-i", "--iface", default="wlan0", help="Wi-Fi interface to use")
    parser.add_argument("-r", "--rssi", type=int, default=-75, help="Minimum RSSI filter")
    parser.add_argument(
        "-d", "--debug",
        nargs="?", const="roam_debug.log", metavar="FILE",
        help="Save raw collected logs to a file (default: roam_debug.log if no FILE provided)",
    )
    args = parser.parse_args()

    iface = args.iface
    min_rssi = args.rssi

    # ----------------------------------------
    # Configure wpa_supplicant logging
    # ----------------------------------------
    log_set_result, original_log_level = set_log_level(iface, "DEBUG")
    if not log_set_result:
        print("Failed to set log level to DEBUG")
        return

    collected = CollectedLogs()
    proc = collect_logs(collected)

    try:
        # ----------------------------------------
        # Identify current connection
        # ----------------------------------------
        current = get_current_connection(iface)
        if not current.ssid or not current.bssid:
            print("Wi-Fi interface is not connected to a WLAN.")
            return

        print(f"Current SSID:  {current.ssid}")
        print(f"Current BSSID: {current.bssid}\n")

        # ----------------------------------------
        # Gather candidate APs for roaming
        # ----------------------------------------
        candidates = get_scan_results(
            iface=iface,
            mrssi=min_rssi,
            ssid_filter=current.ssid,
            current_bssid=current.bssid,
            use_iw=True,
        )

        print("Candidates:")
        for target in candidates:
            print(f"  BSSID: {target.bssid}  Freq: {target.freq} MHz  RSSI: {target.rssi} dBm")
        print("")

        # ----------------------------------------
        # Attempt roams
        # ----------------------------------------
        for target in candidates:
            print(f"\n>>> Roaming to {target.bssid} (RSSI {target.rssi} dBm, {target.freq} MHz)")
            start_index = len(collected.raw_logs)

            roam_to_bssid(iface, target.bssid)

            if wait_for_connected(collected, start_index):
                print(f"Roam to {target.bssid} completed successfully")
            else:
                print(f"Roam to {target.bssid} timed out or failed")

        # ----------------------------------------
        # Analyze collected logs
        # ----------------------------------------
        print("\n================== Post-Roam Analysis ==================\n")
        results = analyze_all_roams(collected)

        for idx, (derived, raw) in enumerate(results, start=1):
            print(pretty_print_derived(derived))

            # --- Phase-Level Breakdown ---
            print(f"--- Phase Analysis for Roam #{idx} ---")
            phase_results = analyze_from_derived(derived, raw)

            # Print summary per phase
            for name, pdata in phase_results.items():
                print(
                    f"{name:15s} | Status: {pdata['status']:8s} | "
                    f"Duration: {pdata['duration_ms'] or 'N/A':>7} ms | "
                    f"Errors: {len(pdata['errors'])}"
                )

            # Save JSON output
            out_file = f"phase_breakout_roam{idx}.json"
            save_phase_breakout(derived, raw, out_file)
            print(f"[+] Saved phase analysis to {out_file}\n")

    finally:
        stop_log_collection(proc)
        restore_log_level(iface, original_log_level)

    # ----------------------------------------
    # Optional: save raw logs for debug
    # ----------------------------------------
    if args.debug:
        try:
            with open(args.debug, "w") as f:
                f.writelines(collected.raw_logs)
            print(f"Saved raw logs to {args.debug}")
        except Exception as e:
            print(f"Failed to save debug logs: {e}")


if __name__ == "__main__":
    main()