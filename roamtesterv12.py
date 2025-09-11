#!/usr/bin/env python3
"""
roam_test.py

Scan for BSSIDs on the same SSID as the current association (RSSI > threshold),
roam to each candidate (starting with highest RSSI that is NOT the current BSSID),
and measure time from disconnection -> RSNA completion.

Usage:
  sudo python3 roam_test.py -i wlan0 -t -75 --verbose
"""

import subprocess
import time
import re
import sys
import argparse
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

DEFAULT_IFACE = "wlan0"
DEFAULT_THRESHOLD = -75
ROAM_TIMEOUT = 30  # seconds to wait for roam completion (tunable)


def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def get_current_ssid(iface):
    out = run_cmd(["wpa_cli", "-i", iface, "status"])
    for line in out.splitlines():
        if line.startswith("ssid="):
            return line.split("=", 1)[1]
    return None


def get_current_bssid(iface):
    out = run_cmd(["wpa_cli", "-i", iface, "status"])
    for line in out.splitlines():
        if line.startswith("bssid="):
            b = line.split("=", 1)[1].strip()
            if b and b != "(none)":
                return b.lower()
    return None


def get_scan_results(iface, tries=5, sleep_between=4.0):
    run_cmd(["wpa_cli", "-i", iface, "scan"])
    for _ in range(tries):
        time.sleep(sleep_between)
        out = run_cmd(["wpa_cli", "-i", iface, "scan_results"])
        lines = out.splitlines()
        if len(lines) > 1:
            return out
    return out


def parse_scan_results(scan_text, ssid_filter, signal_threshold, current_bssid):
    candidates = []
    for line in scan_text.splitlines():
        if not line.strip() or re.match(r'(?i)^bssid\b', line):
            continue
        parts = re.split(r'\s+', line.strip(), maxsplit=4)
        if len(parts) < 5:
            continue
        bssid = parts[0].lower()
        try:
            signal = int(parts[2])
        except ValueError:
            continue
        ssid_found = parts[4]
        if ssid_found != ssid_filter:
            continue
        if signal <= signal_threshold:
            continue
        if current_bssid and bssid == current_bssid:
            continue
        candidates.append((bssid, signal, ssid_found))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def parse_timestamp_from_journal_line(line):
    m = re.match(r'^(\d+\.\d+)[\s:]', line.lstrip())
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    m = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)([+-]\d{2}:\d{2})', line.lstrip())
    if m:
        ts_str = m.group(1) + m.group(2)
        try:
            return datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            pass
    return time.time()


def human_ts(epoch):
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def colorize(line):
    lower = line.lower()
    if line.startswith("[START]"):
        return Fore.GREEN + line + Style.RESET_ALL
    if line.startswith("[END]"):
        return Fore.CYAN + line + Style.RESET_ALL
    if line.startswith("[***]"):
        return Fore.MAGENTA + Style.BRIGHT + line + Style.RESET_ALL
    if "fail" in lower or "disconnected" in lower:
        return Fore.RED + Style.BRIGHT + line + Style.RESET_ALL
    if "deauth" in lower:
        return Fore.RED + Style.BRIGHT + line + Style.RESET_ALL
    if "success" in lower or "completed" in lower:
        return Fore.GREEN + Style.BRIGHT + line + Style.RESET_ALL
    if "wlan0: state" in lower:
        return Fore.WHITE + line + Style.RESET_ALL
    if "authenticate" in lower:
        return Fore.BLUE + line + Style.RESET_ALL
    if "authen" in lower:
        return Fore.BLUE + line + Style.RESET_ALL
    if "associate" in lower:
        return Fore.BLUE + line + Style.RESET_ALL
    if "eap" in lower:
        return Fore.YELLOW + line + Style.RESET_ALL
    if "eapol" in lower or "ptk" in lower or "gtk" in lower or "4-way" in lower or "pmk" in lower or "4way" in lower or "ft" in lower:
        return Fore.MAGENTA + line + Style.RESET_ALL
    return line


def follow_logs_and_measure(iface, verbose=False, timeout=ROAM_TIMEOUT):
    cmd = [
        "journalctl",
        "-u", "wpa_supplicant",
        "-u", f"wpa_supplicant@{iface}.service",
        "-f", "-o", "short-unix", "--since", "now",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    start_ts = None
    fallback_first_line_ts = None

    start_markers = ("nl80211: Authenticate event","nl80211: Connect request send successfully",) 

    end_markers_priority = [
        "WPA: Key negotiation completed",
        "RSN: Authentication completed",
   #     "CTRL-EVENT-EAP-SUCCESS",
        "CTRL-EVENT-CONNECTED",
    ]

    frame_needles = tuple(s.lower() for s in (
        "state: ", "sme: trying to authenticate", "sme: authentication response",
        "trying to associate with", "nl80211: associate event",
        "nl80211: associated on", "associated with",
        "rsn: pmksa cache entry found", "rsn: pmkid", "ft:",
        "using sae auth_alg", "wpa: rx message", "wpa: sending eapol-key",
        "wpa: installing ptk", "wpa: installing gtk", "wpa: rekeying gtk",
        "eapol authentication completed - result=success",
        "supplicant port status: authorized", "ctrl-event-eap-success","eap","wlan0: consecutive connection failure","wlan0: deauth","wlan0:  * reason",
    ))

    drop_needles = tuple(s.lower() for s in (
        "ignored event", "hexdump(", "dbus", "external notification -",
        "supp_pae entering state", "supp_be entering state", "eap entering state",
        "maintaining eap method data", "enable timer tick",
        "setting authentication timeout", "event eapol_rx",
        "event eapol_tx_status", "eapol-key type=", "eapol-key mic using",
        "decrypted eapol-key key data", "rsn ie in eapol-key",
        "gtk in eapol-key", "rrm:", "wmm ac:", "tdls:",
        "scan results indicate bss status","netlink: Operstate","based on lower layer success","eapol: getsupp", "eapol: txsupp",
    ))

    start_time_outer = time.time()
    try:
        while True:
            if time.time() - start_time_outer > timeout:
                if verbose:
                    print(colorize("[!] Timeout waiting for roam events."))
                return None

            line = proc.stdout.readline()
            if line == "":
                time.sleep(0.02)
                continue

            ts_epoch = parse_timestamp_from_journal_line(line)
            ts_human = human_ts(ts_epoch)
            line_stripped = re.sub(r"^\d+\.\d+", ts_human, line.strip())

            if verbose:
                print(colorize(line_stripped))

            if fallback_first_line_ts is None:
                fallback_first_line_ts = ts_epoch

            if start_ts is None and any(marker in line for marker in start_markers):
                start_ts = ts_epoch
                print(colorize(f"[START] {line_stripped}"))
                continue

            if start_ts is not None:
                msg_lower = line_stripped.lower()
                if any(n in msg_lower for n in frame_needles) and not any(d in msg_lower for d in drop_needles):
                    print(colorize(line_stripped))

            for marker in end_markers_priority:
                if marker in line:
                    end_ts = ts_epoch
                    if start_ts is None:
                        start_ts = fallback_first_line_ts or end_ts
                        print(colorize(f"[START] (fallback) {line_stripped}"))
                    print(colorize(f"[END] {line_stripped}"))
                    roam_time = end_ts - start_ts
                    ms = roam_time * 1000.0
                    if ms < 10:
                        print(colorize(f"[***] Roam completed in {ms:.3f} ms (end marker: '{marker}')"))
                    else:
                        print(colorize(f"[***] Roam completed in {roam_time:.3f} s ({ms:.1f} ms, end marker: '{marker}')"))
                    return roam_time
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def roam_to_bssid(iface, bssid):
    print(f"[*] Triggering roam to {bssid} ...")
    run_cmd(["wpa_cli", "-i", iface, "roam", bssid])


def main():
    p = argparse.ArgumentParser(description="Roam tester using wpa_cli + journalctl")
    p.add_argument("-i", "--iface", default=DEFAULT_IFACE)
    p.add_argument("-t", "--threshold", type=int, default=DEFAULT_THRESHOLD)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--timeout", type=int, default=ROAM_TIMEOUT)
    args = p.parse_args()

    iface = args.iface
    sig_thresh = args.threshold
    verbose = args.verbose
    timeout = args.timeout

    ssid = get_current_ssid(iface)
    if not ssid:
        print("[-] Not currently connected to an SSID. Aborting.")
        sys.exit(1)
    current_bssid = get_current_bssid(iface)
    print(f"[+] Connected SSID: {ssid}")
    if current_bssid:
        print(f"[+] Current BSSID: {current_bssid}")
    else:
        print("[!] Could not determine current BSSID")

    print(f"[*] Scanning for APs on SSID '{ssid}' with signal > {sig_thresh} dBm ...")
    scan_text = get_scan_results(iface)
    candidates = parse_scan_results(scan_text, ssid, sig_thresh, current_bssid)

    if not candidates:
        print("[-] No candidate APs found. Exiting.")
        sys.exit(1)

    print(f"[+] Found {len(candidates)} candidate AP(s):")
    for bssid, sig, _ in candidates:
        print(f"    {bssid}  {sig} dBm")
#The below code block allws for a roam back to original BSSID
    if current_bssid:
        for line in scan_text.splitlines():
            if line.lower().startswith(current_bssid):
                parts = re.split(r'\s+', line.strip(), maxsplit=4)
                if len(parts) >= 5:
                    try:
                        sig = int(parts[2])
                    except ValueError:
                        sig = 0
                    ssid_found = parts[4]
                    candidates.append((current_bssid, sig, ssid_found))
                    print(f"    (back to original) {current_bssid}  {sig} dBm")
                break

    results = []
    for bssid, sig, _ in candidates:
        roam_to_bssid(iface, bssid)
        roam_time = follow_logs_and_measure(iface, verbose=verbose, timeout=timeout)
        if roam_time is not None:
            print(f"[***] Roam to {bssid} completed in {roam_time:.3f} seconds\n")
            results.append((bssid, sig, roam_time))
        else:
            print(f"[!!!] Roam to {bssid} did NOT complete within {timeout}s\n")
            results.append((bssid, sig, None))
        time.sleep(2)

    print("=== Summary ===")
    for bssid, sig, rt in results:
        status = f"{rt:.3f} s" if rt is not None else "FAILED"
        print(f"{bssid}  {sig} dBm  -> {status}")


if __name__ == "__main__":
    main()
