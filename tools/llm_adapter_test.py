"""
Simple test runner for the LLM adapter. Runs in mock mode if OPENAI_API_KEY is not set.

Usage:
  python3 tools/llm_adapter_test.py
"""
import json
from llm_adapter_openai import rephrase


def main():
    # Create a tiny fake context similar to cycle_summary.data
    data = {
        "ssid": "TestNet",
        "security_type": "WPA2-PSK",
        "execution_duration_s": 5.2,
        "candidates": [],
        "roams": [
            {"roam_index": 1, "overall_status": "success", "roam_duration_ms": 120},
            {"roam_index": 2, "overall_status": "failure", "roam_duration_ms": 450, "failure_log": "roam_fail.log"},
        ],
    }

    template = "SSID TestNet — 1/2 successful roams. 1 roams failed; check attached failure logs. Recommend downloading failure logs and inspecting Authentication/Association phases."

    out = rephrase(template, data)
    print("=== Adapter Output ===")
    print(out)


if __name__ == '__main__':
    main()
