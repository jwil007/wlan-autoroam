#!/usr/bin/env python3
"""
FastMCP wrapper for wlan-autoroam
---------------------------------
Exposes key Flask REST API endpoints as MCP tools/resources so an MCP client
or LLM agent can trigger roams or fetch data.

Run on the same host as your Flask server:
    python3 fastmcp_server.py
"""

from fastmcp import FastMCP
from autoroam.common import get_repo_root
import requests, os, urllib3

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
BASE_URL = os.getenv(get_repo_root(), "https://localhost:8443")
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "api_key.txt")

# Load API key (matches the Flask server)
with open(API_KEY_FILE) as f:
    API_KEY = f.read().strip()

# Disable SSL verification warnings (for self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HTTP_OPTS = {
    "verify": False,                           # ignore self-signed cert
    "headers": {"X-API-Key": API_KEY},         # authenticate to Flask API
    "timeout": 30,
}

mcp = FastMCP("wlan_autoroam")


# ──────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────
@mcp.tool()
def start_roam(iface: str = "wlan0", rssi: int = -75) -> dict:
    """Kick off a roaming cycle on the given interface and RSSI threshold."""
    url = f"{BASE_URL}/api/start_roam"
    payload = {"iface": iface, "rssi": rssi}
    r = requests.post(url, json=payload, **HTTP_OPTS)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def get_latest_summary() -> dict:
    """Return the most recent cycle_summary.json contents."""
    url = f"{BASE_URL}/api/latest_cycle_summary"
    r = requests.get(url, **HTTP_OPTS)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def get_logs() -> str:
    """Fetch the live roam debug log."""
    url = f"{BASE_URL}/api/logs"
    r = requests.get(url, **HTTP_OPTS)
    r.raise_for_status()
    data = r.json()
    return data.get("log", "")


# ──────────────────────────────────────────────────────────────
# Run MCP server (HTTP transport, compatible with all FastMCP)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", 8765))
    print(f"[✓] FastMCP HTTP server (via transport='http') listening on port {port}")
    print(f"    Connected to Flask API at {BASE_URL}")
    # Use the transport parameter
    mcp.run(transport="http", host="0.0.0.0", port=port)


