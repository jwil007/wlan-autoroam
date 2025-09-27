import subprocess
from dataclasses import dataclass,field
import threading

@dataclass
class CollectedLogs:
    raw_logs: list [str] = field(default_factory=list)

def collect_logs(results: CollectedLogs):
    #Start collecting wpa_supplicant logs
    proc = subprocess.Popen(
        ["journalctl","-u","wpa_supplicant","-o","short-precise","-f"],
        stdout=subprocess.PIPE,
        text=True
    )

    #save logs as class attribute
    def reader():
        for line in proc.stdout:
            results.raw_logs.append(line)


    #Use thread to run as daemon 
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    return proc

#Stop log collecting
def stop_log_collection(proc: subprocess.Popen):
    proc.terminate()
    proc.wait()
    print("Stopped log collection")