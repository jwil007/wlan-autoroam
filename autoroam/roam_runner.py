import argparse
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo
#imports for internal packages
from autoroam.common import get_data_dir
from autoroam.log_collector import CollectedLogs, collect_logs, stop_log_collection
from autoroam.log_analyzer import analyze_all_roams
from autoroam.shell_cmd_wrapper import (
    set_log_level,
    restore_log_level,
    get_current_connection,
    get_scan_results,
    roam_to_bssid,
)
from autoroam.phase_breakout import analyze_from_derived
from autoroam.cycle_summary import build_cycle_summary, save_cycle_summary


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


def run_roam_cycle(iface="wlan0", min_rssi=-75, debug_file=None):

    # Configure wpa_supplicant logging
    log_set_result, original_log_level = set_log_level(iface, "DEBUG")
    if not log_set_result:
        print("Failed to set log level to DEBUG")
        return

    collected = CollectedLogs()
    proc = collect_logs(collected)

    try:
        # Identify current connection
        current = get_current_connection(iface)
        if not current.ssid or not current.bssid:
            print("Wi-Fi interface is not connected to a WLAN.")
            return

        print(f"Current SSID:  {current.ssid}")
        print(f"Current BSSID: {current.bssid}\n")

        # Gather candidate APs for roaming
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


        # Track start time for the entire test cycle
        cycle_start = time.time()
        cycle_start_ts = datetime.now().astimezone().isoformat()

        # Attempt roams
        for target in candidates:
            print(f"\n>>> Roaming to {target.bssid} (RSSI {target.rssi} dBm, {target.freq} MHz)")
            start_index = len(collected.raw_logs)

            roam_to_bssid(iface, target.bssid)

            if wait_for_connected(collected, start_index):
                print(f"Roam to {target.bssid} completed successfully")
            else:
                print(f"Roam to {target.bssid} timed out or failed")

        # Analyze collected logs
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


        # Build the full cycle summary JSON
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

    # Optional: save raw logs for debug
    data_dir = get_data_dir()

    if debug_file:
        try:
            # Ensure the debug path lives in /data
            debug_path = os.path.join(data_dir, os.path.basename(debug_file))
            with open(debug_path, "w") as f:
                f.writelines(collected.raw_logs)
            print(f"[+] Saved raw logs to {debug_path}")
        except Exception as e:
            print(f"[!] Failed to save debug logs: {e}")


if __name__ == "__main__":
    print("This script is intended to be invoked via start_autoroam_cli.py")
    print("Example: python3 start_autoroam_cli.py -i wlan0 -r -70 -d")