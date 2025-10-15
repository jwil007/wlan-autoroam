#!/usr/bin/env python3
import argparse
from autoroam.roam_runner import run_roam_cycle

import os, sys
# ensure project root is on the import path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def main():
    # CLI Arguments
    parser = argparse.ArgumentParser(description="Wi-Fi Roam Test Tool")
    parser.add_argument("-i", "--iface", default="wlan0", help="Wi-Fi interface to use")
    parser.add_argument("-r", "--rssi", type=int, default=-75, help="Minimum RSSI filter")

    args = parser.parse_args()

    run_roam_cycle(iface=args.iface, min_rssi=args.rssi)


if __name__ == "__main__":
    main()