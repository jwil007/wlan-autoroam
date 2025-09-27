# wlan-autoroam-cli
This project uses native linux tools (wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam to BSSIDs in your ESS. It checks the current SSID you are connected to, and identifies candidate APs to roam to above a configurable RSSI threshold. It will roam back you the original BSSID to leave your connection in it's original state.

## Requirements
A Linux box with a Wi-Fi interface connect to an SSID. wpa_cli, wpa_supplicant, and journalctl are used.

## Usage
 `python3 main.py -i wlan0 -r -75 -d`
 
 ### Args:
 
 `-i` : Sets interface. Default is wlan0
 
 `-r` : Sets min RSSI cutoff. Defaut is -75
 
 `-d` : Saves wpa_supplicant logs during roams to debuglogs.txt in local directory. 
