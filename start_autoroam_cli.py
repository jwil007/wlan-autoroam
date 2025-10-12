#!/usr/bin/env python3
import argparse
from autoroam.roam_runner import run_roam_cycle

def main():
    # CLI Arguments
    parser = argparse.ArgumentParser(description="Wi-Fi Roam Test Tool")
    parser.add_argument("-i", "--iface", default="wlan0", help="Wi-Fi interface to use")
    parser.add_argument("-r", "--rssi", type=int, default=-75, help="Minimum RSSI filter")
    parser.add_argument(
        "-d", "--debug",
        nargs="?", const="roam_debug.log", metavar="FILE",
        help="Save raw collected logs to a file (default: roam_debug.log if no FILE provided)",
    )
    args = parser.parse_args()

    run_roam_cycle(iface=args.iface, min_rssi=args.rssi, debug_file=args.debug)


if __name__ == "__main__":
    main()