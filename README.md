# wlan-autoroam
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

## Features
* Web based UI or CLI mode.
* Automatically selects APs based on your SSID and RSSI cutoff.
* Measure duration (from client perspective) for each stage of the roaming process (auth, reassoc, EAP, RSN handshake).
* Parses scan data to build list of candidate APs - including useful info like QBSS channel utilization.
* Download full logs from the UI.
* Log snippets for failed roams are automatically saved. 

### Requirements:
A Linux device with a Wi-Fi interface connected to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.
 > [!NOTE]
> The iw scan command used may require elevated permissions. If you run into errors, try running the script with sudo, or edit your sudoers file to allow iw to be used without password.

# Usage
## Start UI:
 `python3 start_autoroam_ui.py`
 > [!NOTE]
> The UI is the only thing you need to run, as it has a Run Now button to kick off the roam cycle.
#### Optional args:
`-p, --port` HTTP port to launch webserver on. Default is 8080.
### Saving and loading results
After running a roam cycle, you may want to save the results to analyze in the future. If results are not saved, they will be flushed the next time you start the roam cycle.

To save results, simply click the `💾 Save Results` button. A modal will pop up where you can add optional notes and confirm the operation.

To load results, use the `Load Results...` dropdown. Previous results are saved with the SSID and local-time timestamp of the execution time - i.e. _MySSID (10/13/2025, 3:43:30 PM)_

## CLI:
`python3 start_autoroam_cli.py`
 
 #### Optional args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
 

# UI Screenshot
<img width="1273" height="2187" alt="10 0 10 58_8080_ (2)" src="https://github.com/user-attachments/assets/f1135c07-7978-4273-b66f-6af768a094cf" />



