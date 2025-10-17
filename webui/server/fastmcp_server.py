#!/usr/bin/env python3
"""
FastMCP wrapper for wlan-autoroam
Exposes all Flask REST endpoints as MCP tools.
"""

from fastmcp import FastMCP
import requests, os, urllib3, json

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
BASE_URL = os.getenv("AUTOROAM_BASE_URL", "https://localhost:8443")
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "api_key.txt")

# Load API key (matches Flask server)
with open(API_KEY_FILE) as f:
    API_KEY = f.read().strip()

# Ignore SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
HTTP_OPTS = {
    "verify": False,
    "headers": {"X-API-Key": API_KEY},
    "timeout": 30,
}

mcp = FastMCP("wlan_autoroam")


# ──────────────────────────────────────────────────────────────
# Core helper
# ──────────────────────────────────────────────────────────────
def _get(path, **kwargs):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, **{**HTTP_OPTS, **kwargs})
    r.raise_for_status()
    return r.json()

def _post(path, payload=None):
    url = f"{BASE_URL}{path}"
    r = requests.post(url, json=payload or {}, **HTTP_OPTS)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ──────────────────────────────────────────────────────────────
# MCP Tools (mirroring Flask endpoints)
# ──────────────────────────────────────────────────────────────

@mcp.tool()
def start_roam(iface: str = "wlan0", rssi: int = -75) -> dict:
    """Start a new roam cycle on the given interface."""
    return _post("/api/start_roam", {"iface": iface, "rssi": rssi})


@mcp.tool()
def get_latest_summary() -> dict:
    """Fetch the latest roam summary JSON."""
    return _get("/api/latest_cycle_summary")


@mcp.tool()
def get_logs() -> str:
    """Return live roam logs."""
    data = _get("/api/logs")
    return data.get("log", "")


@mcp.tool()
def download_log(filename: str = "roam_debug.log", dir: str = "") -> bytes:
    """Download a specific roam or failed roam log file."""
    params = {"filename": filename}
    if dir:
        params["dir"] = dir
    url = f"{BASE_URL}/api/download_log"
    r = requests.get(url, params=params, **HTTP_OPTS)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}", "text": r.text}
    return {"filename": filename, "content": r.text}


@mcp.tool()
def save_results(run_dir: str, notes: str = "") -> dict:
    """Mark a run as saved and optionally attach notes."""
    return _post("/api/save_results", {"run_dir": run_dir, "notes": notes})


@mcp.tool()
def list_saved_runs() -> dict:
    """List all saved runs and metadata."""
    return _get("/api/list_saved_runs")


@mcp.tool()
def load_results(dir: str) -> dict:
    """Load a saved run’s results by directory name."""
    params = {"dir": dir}
    url = f"{BASE_URL}/api/load_results"
    r = requests.get(url, params=params, **HTTP_OPTS)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def api_docs() -> dict:
    """Return the OpenAPI or Swagger documentation HTML."""
    url = f"{BASE_URL}/api/docs"
    r = requests.get(url, **HTTP_OPTS)
    return {"status": r.status_code, "html": r.text}


# ──────────────────────────────────────────────────────────────
# Run MCP server (HTTP transport)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", 8765))
    print(f"[✓] FastMCP HTTP server listening on port {port}")
    print(f"    Connected to Flask API at {BASE_URL}")
    mcp.run(transport="http", host="0.0.0.0", port=port)
