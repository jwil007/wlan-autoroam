#!/usr/bin/env python3
import argparse
import threading
from autoroam.common import get_repo_root
import sys, os

# Add repo root to path (so we can import webui packages easily)
repo_root = get_repo_root()
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from webui.server.app import run_server
from webui.server.fastmcp_server import run_mcp_server

def main():
    parser = argparse.ArgumentParser(description="Start the AutoRoam Web UI and MCP Server")
    parser.add_argument("--ui-port", "-p", type=int, default=8443, help="UI HTTP port (default: 8443)")
    parser.add_argument("--mcp-port", "-m", type=int, default=8765, help="MCP server port (default: 8765)")
    args = parser.parse_args()

    # Start MCP server in a separate thread
    mcp_thread = threading.Thread(
        target=run_mcp_server,
        args=(args.mcp_port, args.ui_port),
        daemon=True
    )
    mcp_thread.start()
    print(f"[+] Started MCP server on port {args.mcp_port}")

    # Start UI server in main thread
    print(f"[+] Starting UI server on port {args.ui_port}")
    run_server(port=args.ui_port)

if __name__ == "__main__":
    main()
