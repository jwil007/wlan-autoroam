# wlan-autoroam
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

#### UI mode and CLI mode:
1. `start_autoroam_ui.py` - Starts a web UI via HTTP on localhost. The web UI is fully featured, in that you can start the roam, view results, and download logs from it.
2. `start_autoroam_cli.py` - Runs the roam cycle a single time from your shell. Stdout will print basic results, detailed output (json for all roams, debug logs, logs for failed roams) is saved to the data directory, which is automatically.




### Requirements:
A Linux device with a Wi-Fi interface connected to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.

# Usage
## Launch UI
 `python3 start_autoroam_ui.py`
#### Optional args:
`-p, --port` HTTP port to launch webserver on. Default is 8080.

## Run from CLI:
`python3 start_autoroam_cli.py`
 
 #### Optional args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
  
  `-d, --debug [FILE]`  Save raw collected logs to a file (default: roam_debug.log if no FILE provided)

# UI Screenshot
<img width="1273" height="2055" alt="10 0 10 58_8080_ (1)" src="https://github.com/user-attachments/assets/d0e894fc-6632-4509-bbca-9d499392984b" />


