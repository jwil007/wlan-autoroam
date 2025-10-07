# wlan-autoroam-cli
This project uses native Linux tools (iw, wpa_cli, wpa_supplicant, and journalctl) to automatically scan and roam (reassociate) to BSSIDs in your ESS. It checks the current SSID you are connected to and identifies candidate APs to roam to above a configurable RSSI threshold. The roaming process is sequenced in descending order of RSSI, with the final roam being a return to the original BSSID.

## Requirements
A Linux box with a Wi-Fi interface connect to an SSID. Python3, iw, wpa_cli, wpa_supplicant, and journalctl.

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
Target BSSID:   02:e0:fc:d7:9e:cf
Final BSSID:    02:e0:fc:d7:9e:cf
Final freq:     5180
Key mgmt:       802.1X with SHA256
FT Used:        False
PMK Cache Used: False
Auth Start time:2025-10-07 10:23:05.916673
Auth fin time:  2025-10-07 10:23:05.952643
Auth duration:  35.97 ms
Assoc strt time:2025-10-07 10:23:05.952862
Assoc fin time: 2025-10-07 10:23:05.964232
Assoc duration: 11.37 ms
EAP Start:      2025-10-07 10:23:06.106088
EAP Success:    2025-10-07 10:23:06.122105
EAP Failure:    N/A
EAP Duration:   16.02 ms
4way start:     2025-10-07 10:23:06.122888
4way success:   2025-10-07 10:23:06.128503
4way duration:  5.62 ms
Disconnect:     False
Disconnect cnt: N/A
Roam Start:     2025-10-07 10:23:05.916673
Roam End:       2025-10-07 10:23:06.128528
Roam Duration:  211.85 ms
No config err:  False
No target err:  False
----------------------
```
