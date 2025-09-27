# wlan-autoroam-cli
This project uses native linux tools (wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam to BSSIDs in your ESS. It checks the current SSID you are connected to, and identifies candidate APs to roam to above a configurable RSSI threshold. It will roam back you the original BSSID to leave your connection in it's original state.

## Requirements
A Linux box with a Wi-Fi interface connect to an SSID. wpa_cli, wpa_supplicant, and journalctl are used.

## Usage
 `python3 main.py -i wlan0 -r -75 -d 'logfile.txt'`
 
 ### Args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan 0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
  
  `-d, --debug [FILE]`  Save raw collected logs to a file (default: roam_debug.log if no FILE provided)
