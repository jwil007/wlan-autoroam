
from roam_old  import start_roam_seq
from time import sleep
from log_collector import CollectedLogs, collect_logs, stop_log_collection
from log_analyzer import analyze_all_roams,pretty_print_derived
from wpa_cli_wrapper import set_log_level, restore_log_level


def main():
    iface = "wlan0"
    min_rssi = -75
    #set log level to DEBUG
    r = set_log_level(iface,"DEBUG")
    log_set_result = r[0]
    original_log_level = r[1]
    if log_set_result == True:
        try:
            collected = CollectedLogs()
            proc = collect_logs(collected)

            try:
                start_roam_seq(iface, collected, min_rssi)
            finally:
                stop_log_collection(proc)
                restore_log_level(iface,original_log_level)
            results = analyze_all_roams(collected)
            for r in results:
                print(pretty_print_derived(r))
        except:
            print(Exception)

if __name__ == "__main__":
    main()