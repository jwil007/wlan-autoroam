# wlan-autoroam-cli
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

A UI is presented on a simple HTTP webpage for quick analysis of log results.

### UI Features:
1. Graphs broken out by phase (Auth, Assoc, EAP, 4way handshake) for timing comparison.
2. Details for each roam, including relevent error logs in a text box on the UI.
3. If a roam fails, logs are automatically saved, and you can download from the web UI.
4. JSON upload if you happen to have the right file format (you don't). 


## Requirements
A Linux box with a Wi-Fi interface connect to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.

## Usage
 `python3 main.py -i wlan0 -r -75 -d 'logfile.txt'`
 
 To start the UI on port 8080: `python3 webui/server/app.py `
 
 ### Args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan 0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
  
  `-d, --debug [FILE]`  Save raw collected logs to a file (default: roam_debug.log if no FILE provided)

# UI Screenshot
<img width="1273" height="1941" alt="10 0 10 58_8080_" src="https://github.com/user-attachments/assets/0726a00a-36b5-4059-9b5c-e587fb4d2ed9" />

