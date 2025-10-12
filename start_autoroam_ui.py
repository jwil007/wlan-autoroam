#!/usr/bin/env python3
import argparse
from autoroam.common import get_repo_root
import sys, os

# Add repo root to path (so we can import webui.server.app easily)
repo_root = get_repo_root()
sys.path.insert(0, os.path.join(repo_root, "webui", "server"))

from webui.server.app import run_server

def main():
    parser = argparse.ArgumentParser(description="Start the AutoRoam Web UI")
    parser.add_argument("--port", "-p", type=int, default=8080, help="HTTP port (default: 8080)")
    args = parser.parse_args()

    run_server(port=args.port)

if __name__ == "__main__":
    main()
