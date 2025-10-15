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



### Prerequisites
This project is built around Linux Debian based distros. It uses iw, wpa_cli, and journalctl. Your Linux client needs to have an active Wi-Fi interface connected to an SSID. Make a note of your interface name, which you can get with `ip link`.
 > [!NOTE]
> On some sytems, wpa_cli and iw require root. If you get errors, run the script with sudo.


On recent Debian/Ubuntu systems, the system Python is *externally managed*, so dependencies must be installed in a virtual environment.

#### Setup
```bash
# Install required tools
sudo apt install python3-venv -y

# Create and activate virtual environment
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Run the app (requires root for iw / wpa_cli)
sudo venv/bin/python start_autoroam_ui.py
```
# Usage
## Web UI:

The UI is the only thing you need to run, as it has a Run Now button to kick off the roam cycle.
1. Rename `.env.example` to `.env`.  replace placeholder WEB_USER and WEB_PASS values with your preferred username and password. Set FLASK_SECRET to any random string.
2. Run startup script `sudo venv/bin/python3 start_autoroam_ui.py`. This spins up HTTPS web server at localhost port 8443. If you want to change the port, use the `-p` flag - for example  `-p 10443`.
3. Log in at https://localhost:8443 (or whatever port you set).
4. Set the iface and min_rssi params on the top right of the UI, or leave defaults `wlan0` and `-75`. Click Run Now to kick off the test.
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
`sudo venv/bin/python3 start_autoroam_cli.py`
 
 #### Optional args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
 

# UI Screenshot
<img width="1273" height="1991" alt="10 0 10 58_8443_ (2)" src="https://github.com/user-attachments/assets/ee1238f5-19b2-452b-8046-f6f9e762c3a8" />





