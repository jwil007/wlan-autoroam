#!/usr/bin/env python3
"""
Simple MCP loopback client for wlan-autoroam

This script is a minimal client that uses the FastMCP wrapper (if available)
or falls back to direct HTTP calls to the Flask API. It exercises the same
endpoints exposed by `webui/server/fastmcp_server.py` and prints concise
summaries of results.

Usage examples:
  python3 tools/mcp_loopback_client.py --start --iface wlan0 --rssi -70
  python3 tools/mcp_loopback_client.py --summary
  python3 tools/mcp_loopback_client.py --logs
  python3 tools/mcp_loopback_client.py --loop 30 --summary --logs

Environment variables:
  AUTOROAM_BASE_URL  - Base URL of the Flask server (default: https://localhost:8443)
  AUTOROAM_API_KEY   - API key from webui/server/api_key.txt (if not provided, script
                       will try to read webui/server/api_key.txt in the repo)

The script prints short human-readable summaries to stdout and exits.
"""

import os
import sys
import time
import argparse
import json
from typing import Optional

# Ensure repo root (one level up) is on sys.path so 'tools' package imports work
try:
    script_dir = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
except Exception:
    pass

try:
    import requests
except Exception as e:
    print("Missing dependency: requests. Install with 'pip install requests'")
    raise

# Optional FastMCP client support
try:
    from fastmcp import FastMCP
    HAVE_FASTMCP = True
except Exception:
    FastMCP = None
    HAVE_FASTMCP = False

BASE_URL = os.getenv("AUTOROAM_BASE_URL", "https://localhost:8443")
API_KEY = os.getenv("AUTOROAM_API_KEY")
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "webui", "server", "api_key.txt")
if not API_KEY and os.path.exists(os.path.abspath(API_KEY_FILE)):
    try:
        with open(os.path.abspath(API_KEY_FILE)) as f:
            API_KEY = f.read().strip()
    except Exception:
        pass

HTTP_OPTS = {"verify": False, "headers": {"X-API-Key": API_KEY}, "timeout": 30}


def _get(path: str, params: dict = None):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, params=params or {}, **HTTP_OPTS)
    r.raise_for_status()
    return r


def _post(path: str, payload: dict = None):
    url = f"{BASE_URL}{path}"
    r = requests.post(url, json=payload or {}, **HTTP_OPTS)
    r.raise_for_status()
    return r


def start_roam(iface: str = "wlan0", rssi: int = -75):
    r = _post("/api/start_roam", {"iface": iface, "rssi": rssi})
    print(json.dumps(r.json(), indent=2))


def get_logs():
    r = _get("/api/logs")
    data = r.json()
    print(data.get("log", ""))


def get_latest_summary():
    try:
        r = _get("/api/latest_cycle_summary")
    except requests.HTTPError as e:
        print(f"HTTP error: {e}")
        return None
    j = r.json()
    data = j.get("data")
    run_dir = j.get("run_dir")
    mtime = j.get("mtime")
    print(f"Run dir: {run_dir}")
    print(f"Summary mtime: {mtime}")
    if data:
        # Pretty print top-level fields
        print(f"SSID: {data.get('ssid')}")
        print(f"Security: {data.get('security_type')}")
        print(f"Execution duration (s): {data.get('execution_duration_s')}")
        print(f"Candidate count: {len(data.get('candidates', []))}")
        print(f"Roam count: {len(data.get('roams', []))}")
        # Print per-roam brief
        for r in data.get('roams', []):
            print(f"  Roam #{r.get('roam_index')}: target={r.get('target_bssid')} final={r.get('final_bssid')} status={r.get('overall_status')} dur_ms={r.get('roam_duration_ms')}")
    return j


def _use_fastmcp_tool(tool_name: str, *args, **kwargs):
    """If fastmcp is available and reachable, call the tool and return the result.
    This allows agents to call the MCP tools directly if desired.
    """
    if not HAVE_FASTMCP:
        raise RuntimeError("fastmcp not available")
    # we make a short-lived client pointed at the same BASE_URL
    mcp = FastMCP("wlan_autoroam")
    # FastMCP default transport is local; override to HTTP transport
    # instantiate the http client by running mcp.run? Instead, use requests fallback.
    # Note: FastMCP doesn't expose a simple HTTP client constructor here; fall back to HTTP.
    raise RuntimeError("FastMCP HTTP client usage not implemented; falling back to HTTP")


def download_log(filename: str = "roam_debug.log", dir: str = None):
    params = {"filename": filename}
    if dir:
        params["dir"] = dir
    r = _get("/api/download_log", params=params)
    # If binary or attachment, requests will return raw text; the server returns file content
    if r.status_code == 200:
        content = r.content
        print(f"Downloaded {len(content)} bytes for {filename}")
        return content
    else:
        print(r.json())
        return None


def list_saved_runs():
    r = _get("/api/list_saved_runs")
    arr = r.json()
    print(json.dumps(arr, indent=2))


def load_results(dir: str):
    r = _get("/api/load_results", params={"dir": dir})
    data = r.json()
    print(json.dumps(data, indent=2))


def save_results(run_dir: str, notes: str = ""):
    r = _post("/api/save_results", {"run_dir": run_dir, "notes": notes})
    print(json.dumps(r.json(), indent=2))


def analyze_summary(j: dict):
    """Lightweight analysis of the latest cycle_summary.json JSON returned by /api/latest_cycle_summary.
    extra_context may include raw failure logs under keys matching filenames.
    """
    data = j.get("data")
    if not data:
        print("No summary data available for analysis")
        return

    print("\n=== Analysis ===")
    failures = []
    slow_roams = []
    phase_issues = []
    scores = []

    for r in data.get("roams", []):
        status = r.get("overall_status")
        dur = float(r.get("roam_duration_ms") or 0)
        phases = r.get("phases") or {}

        # Identify failures
        if status != "success":
            failures.append(r)

        # Heuristic: consider >300 ms as slow
        if dur and dur > 300:
            slow_roams.append((r, dur))

        # Per-phase checks: high auth duration, missing phases, many errors
        for pname, pdata in phases.items():
            pstat = pdata.get("status")
            pdur = pdata.get("duration_ms") or 0
            perrors = len(pdata.get("errors", [])) if pdata.get("errors") is not None else 0
            if pstat != "success" and pstat != "N/A":
                phase_issues.append((r, pname, pstat, pdur, perrors))
            # heuristics: auth >150ms is suspect, assoc >100ms suspect
            if pname.lower().startswith("authentication") and pdur and pdur > 150:
                phase_issues.append((r, pname, "slow", pdur, perrors))
            if pname.lower().startswith("association") and pdur and pdur > 100:
                phase_issues.append((r, pname, "slow", pdur, perrors))

        # Score the roam (lower is better)
        score = 0
        if status != "success":
            score += 100
        score += int(dur / 50)
        score += sum(len((pdata.get("errors") or [])) * 10 for pdata in phases.values())
        scores.append((r.get("roam_index"), score))

    if failures:
        print(f"{len(failures)} failed roams:")
        for f in failures:
            print(f"  Roam #{f.get('roam_index')}: target={f.get('target_bssid')} failure_log={f.get('failure_log')}")
    else:
        print("No failed roams detected.")

    if slow_roams:
        print(f"{len(slow_roams)} slow roams (>300 ms):")
        for r, d in slow_roams:
            print(f"  Roam #{r.get('roam_index')}: dur_ms={d} target={r.get('target_bssid')}")
    else:
        print("No slow roams detected (threshold 300 ms).")

    if phase_issues:
        print(f"Detected {len(phase_issues)} phase-level issues:")
        for r, pname, pstat, pdur, perrs in phase_issues:
            print(f"  Roam #{r.get('roam_index')}: phase={pname} status={pstat} dur_ms={pdur} errors={perrs}")

    # Show worst-scoring roams
    scores.sort(key=lambda x: x[1], reverse=True)
    if scores:
        worst = scores[:3]
        print("\nWorst roams (higher score is worse):")
        for idx, sc in worst:
            print(f"  Roam #{idx}: score={sc}")

    # Simple recommendation rules
    print("\nRecommendations:")
    if failures:
        print(" - Download failure logs and review authentication/association errors.")
    if slow_roams:
        print(" - Investigate network/driver timing for slow roams; check FT/PMKSA usage in details.")
    if phase_issues:
        print(" - Phase-level issues detected; inspect phase errors (EAP/4-way) and consider driver/roam policy changes.")
    if not failures and not slow_roams and not phase_issues:
        print(" - Cycle looks healthy. Consider increasing candidate diversity for more stress tests.")

    # Generate a short natural language summary (template fallback)
    nl = generate_nl_summary(data, failures, slow_roams, phase_issues)
    print("\nNatural-language summary:\n")
    print(nl)


def generate_nl_summary(data: dict, failures: list, slow_roams: list, phase_issues: list, extra_context: dict = None, llm_overrides: dict = None) -> str:
    """Produce a short human-readable paragraph summarizing the run. This function
    is intentionally small so an LLM backend can be optionally used to rephrase.
    """
    ssid = data.get("ssid")
    total = len(data.get("roams", []))
    ok = total - len(failures)
    parts = [f"SSID {ssid} — {ok}/{total} successful roams."]
    if failures:
        parts.append(f"{len(failures)} roams failed; check attached failure logs.")
    if slow_roams:
        parts.append(f"{len(slow_roams)} roams were slow (>{300} ms).")
    if phase_issues:
        parts.append(f"Phase-level issues were detected in {len(phase_issues)} events.")
    parts.append("Recommend downloading failure logs and inspecting Authentication/Association phases; consider enabling FT/PMKSA caching if applicable.")
    text = " ".join(parts)
    # If an LLM plugin is available, prefer it to rephrase
    ctx = dict(data)
    if extra_context:
        ctx["_extra"] = extra_context
    # Inject per-call LLM overrides into top-level context (e.g. _llm_api_key, _llm_model)
    if llm_overrides and isinstance(llm_overrides, dict):
        for k, v in llm_overrides.items():
            ctx[k] = v
    llm_text = try_llm_rephrase(text, ctx)
    return llm_text or text


from tools.llm_backends import get_adapter


def try_llm_rephrase(text: str, data: dict) -> Optional[str]:
    adapter = get_adapter()
    if not adapter:
        return None
    try:
        return adapter.rephrase(text, data)
    except Exception as e:
        # Surface the error to the caller so it can be shown in the UI
        err = f"(LLM adapter call failed: {e})"
        print(err)
        return err


def download_failed_from_summary(j: dict, out_dir: str = "./", limit_lines: int = None) -> dict:
    """Download any failure log filenames referenced in the summary and save locally.

    Returns a dict mapping filename -> text_contents for inclusion in prompts.
    """
    data = j.get("data")
    if not data:
        print("No summary data available for download")
        return {}

    fetched = {}
    for r in data.get("roams", []):
        fname = r.get("failure_log")
        if fname:
            print(f"Downloading failure log: {fname}")
            content = download_log(fname, dir=os.path.basename(j.get("run_dir") or ""))
            if content:
                local_name = os.path.join(out_dir, fname)
                with open(local_name, "wb") as f:
                    f.write(content)
                print(f"Saved to {local_name}")
                try:
                    text = content.decode('utf-8', errors='replace')
                except Exception:
                    text = str(content)
                # Truncate for LLM context if requested, but keep full file on disk
                if limit_lines and isinstance(text, str):
                    lines = text.splitlines()
                    if len(lines) > limit_lines:
                        tail = lines[-limit_lines:]
                        truncated = "\n".join(tail)
                        truncated = f"[TRUNCATED: last {limit_lines} lines]\n" + truncated
                        fetched[fname] = truncated
                    else:
                        fetched[fname] = text
                else:
                    fetched[fname] = text
    return fetched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="Start a new roam")
    parser.add_argument("--iface", default="wlan0")
    parser.add_argument("--rssi", type=int, default=-75)
    parser.add_argument("--logs", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--download", metavar="FILENAME")
    parser.add_argument("--dir", metavar="DIR")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--load", metavar="DIR")
    parser.add_argument("--save", metavar="RUN_DIR")
    parser.add_argument("--notes", metavar="NOTES", default="")
    parser.add_argument("--loop", metavar="SECS", type=int, help="Repeat selected actions every N seconds")
    parser.add_argument("--analyze", action="store_true", help="Run a lightweight analysis on the latest summary")
    parser.add_argument("--download-failed", action="store_true", help="Download any failed roam logs referenced in the latest summary")
    parser.add_argument("--deep", action="store_true", help="Include raw failure logs in the LLM prompt (may increase token usage)")
    parser.add_argument("--deep-limit", type=int, default=1000, help="When --deep is used, include only the last N lines of each failure log (default: 1000)")

    args = parser.parse_args()

    actions = []
    if args.start:
        actions.append(lambda: start_roam(args.iface, args.rssi))
    if args.logs:
        actions.append(get_logs)
    if args.summary:
        actions.append(get_latest_summary)
    if args.download:
        actions.append(lambda: download_log(args.download, args.dir))
    if args.list:
        actions.append(list_saved_runs)
    if args.load:
        actions.append(lambda: load_results(args.load))
    if args.save:
        actions.append(lambda: save_results(args.save, args.notes))

    if not actions:
        parser.print_help()
        sys.exit(1)

    try:
        if args.loop:
            while True:
                for a in actions:
                    a()
                    # support analyze/download in loop mode
                    if args.analyze:
                        j = get_latest_summary()
                        if j:
                            extra = None
                            if args.download_failed or args.deep:
                                extra = download_failed_from_summary(j)
                            analyze_summary(j)
                            # If deep, call LLM with extra context
                            if args.deep:
                                # regenerate NL summary with extra context and explicit deep mode
                                data = j.get("data") or {}
                                # attach downloaded logs under _extra and set _mode to 'deep' so adapters can detect
                                ctx = dict(data)
                                ctx["_extra"] = extra or {}
                                ctx["_mode"] = "deep"
                                nl = generate_nl_summary(data, [], [], [], extra_context=extra)
                                # Note: try_llm_rephrase will send the context through to the adapter; we ensure deep detection
                                print("\nDeep NL summary:\n")
                                print(nl)
                time.sleep(args.loop)
        else:
            for a in actions:
                a()
                if args.analyze:
                    j = get_latest_summary()
                    if j:
                        extra = None
                        if args.download_failed or args.deep:
                            extra = download_failed_from_summary(j)
                        analyze_summary(j)
                        if args.deep:
                           data = j.get("data") or {}
                           ctx = dict(data)
                           ctx["_extra"] = extra or {}
                           ctx["_mode"] = "deep"
                           nl = generate_nl_summary(data, [], [], [], extra_context=extra)
                           print("\nDeep NL summary:\n")
                           print(nl)
    except KeyboardInterrupt:
        print('\nExiting...')


if __name__ == '__main__':
    main()
