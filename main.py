
from roam  import start_roam_seq
from time import sleep
from log_collector import CollectedLogs, collect_logs, stop_log_collection
from log_analyzer import analyze_all_roams,pretty_print_derived


def main():
    iface = "wlan0"
    min_rssi = -75

    collected = CollectedLogs()
    proc = collect_logs(collected)

    try:
        start_roam_seq(iface, collected, min_rssi)
    finally:
        stop_log_collection(proc)
    
    results = analyze_all_roams(collected)
    for r in results:
        print(pretty_print_derived(r))







if __name__ == "__main__":
    main()