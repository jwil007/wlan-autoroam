# wlan-autoroam
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

A web UI is hosted on the local machine via HTTP - you can start the roam process and view the results directly in the web UI. You can also run the script directly to view results in stdout. Files (json output, raw logs) are saved in the data directory, which is created automatically if it is not present. 

### UI Features:
1. Graphs broken out by phase (Auth, Assoc, EAP, 4way handshake) for timing comparison.
2. Details for each roam, including relevent error logs in a text box on the UI.
3. If a roam fails, logs are automatically saved, and you can download from the web UI.
4. JSON upload if you happen to have the right file format (you don't). 


### Requirements:
A Linux device with a Wi-Fi interface connect to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.

# Usage
## Launch UI
 `python3 start_autoroam_ui.py -p 8080`
#### Optional args:
`-p, --port` HTTP port to launch webserver on. Default is 8080.

## Run from CLI:
`python3 start_autoroam_cli.py -i wlan0 -r -75 -d "roam_debug.log"`
 
 #### Optional args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
  
  `-d, --debug [FILE]`  Save raw collected logs to a file (default: roam_debug.log if no FILE provided)

# UI Screenshot
<img width="1273" height="2055" alt="10 0 10 58_8080_ (1)" src="https://github.com/user-attachments/assets/d0e894fc-6632-4509-bbca-9d499392984b" />


