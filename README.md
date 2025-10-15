# wlan-autoroam
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

## Features
* Web based UI or CLI mode.
* Automatically selects APs based on your SSID and RSSI cutoff.
* Measure duration (from client perspective) for each stage of the roaming process (auth, reassoc, EAP, RSN handshake).
* Parses scan data to build list of candidate APs - including useful info like QBSS channel utilization.
* Download full logs from the UI.
* Log snippets for failed roams are automatically saved.
* REST API (Beta)

### Requirements:
A Linux device with a Wi-Fi interface connected to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.
 > [!NOTE]
> The iw scan command used may require elevated permissions. If you run into errors, try running the script with sudo, or edit your sudoers file to allow iw to be used without password.

# Usage
## Web UI:

The UI is the only thing you need to run, as it has a Run Now button to kick off the roam cycle.
1. Rename `.env.example` to `.env`.  replace placeholder WEB_USER and WEB+PASS values with your preferred username and password. Set FLASK_SECRET to any random string.
2. Run startup script `python3 start_autoroam_ui.py`. This spins up HTTPS web server at localhost port 8443. If you want to change the port, use the `-p` flag - for example  `python3 start_autoroam_ui.py -p 10443`.
3. Log in at https://localhost:8443 (or whatever port you set).
4. Kick off the roam cycle with the Run Now button.
  > [!NOTE]
> The cert for HTTPS is self signed, so you will need to click through the browser warning. If you prefer to replace the certs, the files are `server.crt` and `server.key` in `webui/server/certs `.
### Saving and loading results
After running a roam cycle, you may want to save the results to analyze in the future. If results are not saved, they will be flushed the next time you start the roam cycle.

To save results, simply click the `💾 Save Results` button. A modal will pop up where you can add optional notes and confirm the operation.

To load results, use the `Load Results...` dropdown. Previous results are saved with the SSID and local-time timestamp of the execution time - i.e. _MySSID (10/13/2025, 3:43:30 PM)_

### REST API
There is an experimental REST API. Swagger documentation is at https://<WEB_SERVER_IP:PORT>/api/docs. There's a handy button on the UI to link to the docs once you're logged in.

To make API calls you need an X-API-Key header using the key stored in webui/server/api_key.txt.

## CLI:
`python3 start_autoroam_cli.py`
 
 #### Optional args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
 

# UI Screenshot
<img width="1273" height="2275" alt="10 0 10 58_8443_" src="https://github.com/user-attachments/assets/33250a7a-5af9-41b1-b904-e23920a33e4b" />




