# wlan-autoroam-cli
Program that uses native Linux tools to automatically roam and gather metrics between multiple APs

## Requirements:
Linux box with a Wi-Fi radio associated to an SSID. The program relies on wpa_supplicant and wpa_cli. If you run this in a VM, make sure the VM has access to the Wi-Fi hardware.

## Usage example:
```python3 wlan-autoroam-cli.py -i wlan0 -t -75```

## Optional params:
```-i``` : Specifies Wi-Fi interface name. Default is ```wlan0```

```-t``` : Specifies minimum RSSI threshold in dBm. Default is ```-75```

```--verbose``` : Prints all wpa_supplicant logs (very verbose)

## Example output:
  
<img width="1048" height="918" alt="image" src="https://github.com/user-attachments/assets/98423e6e-4a05-4fa9-b677-214aebddf099" />

<img width="1095" height="930" alt="image" src="https://github.com/user-attachments/assets/0836c2e7-39ae-4ea7-b026-c5f571abef0d" />




