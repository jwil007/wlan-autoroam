import re
from dataclasses import dataclass, field
from typing import List

@dataclass
class ParsedScanResults:
    bssid: str | None = None
    freq: int | None = None
    rssi: int | None = None
    auth_suites: list[str] = field(default_factory=list)
    mfp_flag: str | None = None
    supported_rates: str | None = None
    qbss_util_prct: float | None = None
    qbss_sta_count: int | None = None
    ssid: str | None = None


def parse_iw_scan_output(iw_output: str,
                         ssid_filter: str | None = None,
                         mrssi: int = -100) -> List[ParsedScanResults]:
    """
    Parse 'iw dev <iface> scan' output into structured results.
    """
    DEBUG_PARSE = False  # toggle this to False later

    results: List[ParsedScanResults] = []

    # Split blocks robustly (each "BSS ..." starts a new section)
    blocks = re.split(r"(?m)^\s*(?=BSS\s+[0-9A-Fa-f:]{17}\b)", iw_output)
    for raw_block in blocks:
        if not raw_block.strip():
            continue

        lines = raw_block.strip().splitlines()
        bssid_match = re.match(r"BSS\s+([0-9a-f:]{17})", lines[0])
        if not bssid_match:
            continue
        bssid = bssid_match.group(1)

        # Initialize fields
        freq = rssi = qbss_sta_count = None
        qbss_util_prct = None
        ssid = supported_rates = mfp_flag = None
        auth_suites: list[str] = []

        for line in lines:
            line = line.strip()
            if DEBUG_PARSE and (
                "freq:" in line or
                "signal:" in line or
                "SSID:" in line or
                "Authentication suites:" in line or
                "Capabilities:" in line or
                "station count:" in line or
                "channel utilisation:" in line
            ):
                print(f"[{bssid}] {line}")

            if line.startswith("freq:"):
                try:
                    freq = int(float(line.split()[1]))
                except Exception:
                    pass

            elif line.startswith("signal:"):
                try:
                    rssi = int(float(line.split()[1]))
                except Exception:
                    pass

            elif line.startswith("SSID:"):
                ssid = line.split("SSID:")[1].strip()

            elif line.startswith("Supported rates:"):
                supported_rates = line.split("Supported rates:")[1].strip()

            elif "Authentication suites:" in line:
                suites = line.split("Authentication suites:")[1].strip()
                auth_suites.extend(suites.split())

            elif "Capabilities:" in line and "PTKSA" in line:
                if "MFP-required" in line:
                    mfp_flag = "MFP-required"
                elif "MFP-capable" in line:
                    mfp_flag = "MFP-capable"
                elif mfp_flag is None:
                    mfp_flag = "No MFP"

                # debug only: scoped to a single BSS block
                if ssid and (not ssid_filter or ssid == ssid_filter):
                    print(f"[{ssid}] {line}")

            elif "station count:" in line:
                match = re.search(r"\*?\s*station count:\s*(\d+)", line)
                if match:
                    qbss_sta_count = int(match.group(1))

            elif "channel utilisation:" in line:
                match = re.search(r"\*?\s*channel utilisation:\s*(\d+)/255", line)
                if match:
                    qbss_util_prct = round((int(match.group(1)) / 255) * 100, 1)

        # Debug what the filter check looks like
        if DEBUG_PARSE:
            print(f"Filter check → ssid={ssid!r}, ssid_filter={ssid_filter!r}, rssi={rssi}")

        # Filter: match SSID (case-insensitive, ignore stray whitespace)
        if (
            ssid
            and (not ssid_filter or ssid.strip().lower() == ssid_filter.strip().lower())
            and rssi is not None
            and rssi >= mrssi
        ):
            results.append(
                ParsedScanResults(
                    bssid=bssid,
                    freq=freq,
                    rssi=rssi,
                    ssid=ssid,
                    auth_suites=auth_suites,
                    mfp_flag=mfp_flag,
                    supported_rates=supported_rates,
                    qbss_util_prct=qbss_util_prct,
                    qbss_sta_count=qbss_sta_count,
                )
            )

    print(f"[DEBUG] Parsed {len(results)} BSS entries after filtering\n")
    return results