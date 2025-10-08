import argparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo
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
from cycle_summary import build_cycle_summary, save_cycle_summary


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
        )

        print("Candidates:")
        for target in candidates:
            print(f"  BSSID: {target.bssid}  Freq: {target.freq} MHz  RSSI: {target.rssi} dBm")
        print("")


        # ----------------------------------------
        # Track start time for the entire test cycle
        # ----------------------------------------
        cycle_start = time.time()
        cycle_start_ts = datetime.now().astimezone().isoformat()

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
        results = analyze_all_roams(collected)  # → returns list[(derived, raw)]

        if not results:
            print("No roam results detected — skipping post-roam phase analysis.")
        else:
            for idx, (derived, raw) in enumerate(results, start=1):
                #print(pretty_print_derived(derived))
                print(f"--- Phase Analysis for Roam #{idx} ---")
                phase_results = analyze_from_derived(derived, raw)

                for name, pdata in phase_results.items():
                    print(
                        f"{name:15s} | Status: {pdata['status']:8s} | "
                        f"Duration: {pdata['duration_ms'] or 'N/A':>7} ms | "
                        f"Errors: {len(pdata['errors'])}"
                    )

        # ----------------------------------------
        # Build the full cycle summary JSON
        # ----------------------------------------
        # Derive security type from scanned candidates, not log analysis
        if candidates and any(c.auth_suites for c in candidates):
            security_types = sorted({suite for c in candidates for suite in c.auth_suites})
            security_type = ", ".join(security_types)
        else:
            security_type = "Unknown"

        candidates_list = [
            {
                "bssid": c.bssid,
                "freq": c.freq,
                "rssi": c.rssi,
                "ssid": c.ssid,
                "auth_suites": c.auth_suites,
                "mfp_flag": c.mfp_flag,
                "supported_rates": c.supported_rates,
                "qbss_util_prct": c.qbss_util_prct,
                "qbss_sta_count": c.qbss_sta_count,
            }
            for c in candidates
        ]

        execution_duration_s = round(time.time() - cycle_start, 2)
        summary = build_cycle_summary(
            ssid=current.ssid,
            security_type=security_type,
            candidates=candidates_list,
            derived_raw_pairs=results,
            timestamp=cycle_start_ts,
            execution_duration_s=execution_duration_s,
        )

        save_cycle_summary(summary, "cycle_summary.json")

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