import subprocess
from dataclasses import dataclass,field
import threading
from typing import Optional

@dataclass
class CollectedLogs:
    iface_command: Optional[str] = None #log for when the interface receives the roam command. Not strictly the same as the roam start
    start_roam: Optional[str] = None
    end_roam: Optional[str] = None
    other_logs: list [str] = field(default_factory=list) #Grab all log entries during each roam event



def collect_logs(results: list[CollectedLogs]):
    
    #define strings which will be used to collect the useful logs
    control_interface_command = "Control interface command 'ROAM"

    start_markers = [
    "State: COMPLETED -> AUTHENTICATING",
    ]

    end_markers = [
    "CTRL-EVENT-CONNECTED",
    ]



    #Start collecting wpa_supplicant logs
    proc = subprocess.Popen(["journalctl","-u","wpa_supplicant","-o","short-precise","-f"],
                       stdout=subprocess.PIPE,
                       text=True
                       )
    #Parse collected log files
    def parser()  -> list[CollectedLogs]:
        active_roam = None
        for line in proc.stdout:
            if control_interface_command in line:
                active_roam = CollectedLogs(iface_command= line)
            elif start_markers[0] in line:
                active_roam.start_roam = line            
            elif end_markers[0] in line:
                active_roam.end_roam = line
                results.append(active_roam)
                active_roam = None
            elif active_roam:
                active_roam.other_logs.append(line)

        
    
    #Use thread to run as daemon 
    t = threading.Thread(target=parser, daemon=True)
    t.start()
    return proc


#Stop log collecting
def stop_log_collection(proc: subprocess.Popen):
    proc.terminate()
    proc.wait()