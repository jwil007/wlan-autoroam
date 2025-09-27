# wlan-autoroam-cli
This project uses native Linux tools (wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to, and identifies candidate APs to roam to above a configurable RSSI threshold. It will roam back to the original BSSID to leave your connection in it's original state.

## Requirements
A Linux box with a Wi-Fi interface connect to an SSID. Python3, wpa_cli, wpa_supplicant, and journalctl.

## Usage
 `python3 main.py -i wlan0 -r -75 -d 'logfile.txt'`
 
 ### Args:
 
  `-h, --help`          show this help message and exit
  
  `-i, --iface IFACE`   Wi-Fi interface to use. Default: wlan 0
  
  `-r, --rssi RSSI `    Minimum RSSI filter. Default: -75
  
  `-d, --debug [FILE]`  Save raw collected logs to a file (default: roam_debug.log if no FILE provided)

## Sample output:

```
--- Roam Analysis ---
Target BSSID:   24:79:2a:8e:01:f8
Final BSSID:    24:79:2a:8e:01:f8
Final freq:     2462
Key mgmt:       802.1X
FT Used:        False
PMK Cache Used: True
EAP Start:      N/A
EAP Success:    N/A
EAP Failure:    N/A
EAP Duration:   N/A ms
4way start:     2025-09-27 14:26:36.268725
4way success:   2025-09-27 14:26:36.274773
4way duration:  6.05 ms
Disconnect:     False
Disconnect cnt: N/A
Roam Start:     2025-09-27 14:26:36.164589
Roam End:       2025-09-27 14:26:36.274791
Roam Duration:  110.20 ms
----------------------
```
