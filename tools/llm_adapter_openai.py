"""
OpenAI LLM adapter for the MCP loopback client.

Expose rephrase(text, context) -> str. If OPENAI_API_KEY is not set, a deterministic
mock response is returned for development and CI testing.

Configure via environment:
  OPENAI_API_KEY - your OpenAI API key (optional for test mode)
  LLM_MODEL - model name (default: gpt-4o-mini)
  LLM_TEMPERATURE - float (default: 0.2)
"""
import os
import json
import textwrap
import requests
from typing import Any, Dict
from tools.llm_providers import call_provider

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_EXAMPLES = int(os.getenv("LLM_MAX_EXAMPLES", "6"))


def _build_context_summary(data: Dict[str, Any]) -> str:
    out = {
        "ssid": data.get("ssid"),
        "security_type": data.get("security_type"),
        "execution_duration_s": data.get("execution_duration_s"),
        "candidate_count": len(data.get("candidates", [])),
    }
    roams = []
    for r in data.get("roams", [])[:MAX_EXAMPLES]:
        phases = {}
        for pname, pdata in (r.get("phases") or {}).items():
            phases[pname] = {
                "status": pdata.get("status"),
                "duration_ms": pdata.get("duration_ms"),
                "errors": len(pdata.get("errors") or []),
            }
        roams.append({
            "roam_index": r.get("roam_index"),
            "target_bssid": r.get("target_bssid"),
            "final_bssid": r.get("final_bssid"),
            "overall_status": r.get("overall_status"),
            "roam_duration_ms": r.get("roam_duration_ms"),
            "failure_log": r.get("failure_log"),
            "phases": phases,
        })
    out["sample_roams"] = roams
    return json.dumps(out, indent=2)


def _mock_rephrase(text: str, context: Dict[str, Any]) -> str:
    # Deterministic mock used when OPENAI_API_KEY is not set - helpful for tests
    total = len(context.get("roams", []))
    failures = sum(1 for r in context.get("roams", []) if r.get("overall_status") != "success")
    return f"Mock AI: {failures}/{total} failed roams. Inspect failure logs for details. Severity: Medium."


def rephrase(text: str, context: Dict[str, Any]) -> str:
    """Rephrase/expand the template summary using OpenAI Chat API if API key available,
    otherwise return a deterministic mock response for local testing.
    """
    # Build compact context
    try:
        ctx_json = _build_context_summary(context)
    except Exception:
        ctx_json = json.dumps({"note": "context serialization failed"})

    if not OPENAI_API_KEY:
        return _mock_rephrase(text, context)

    try:
        import openai
    except Exception as e:
        return f"(openai package not installed) Fallback: {text}"

    openai.api_key = OPENAI_API_KEY

    system_msg = (
        "You are an expert Wi-Fi connectivity engineer. Given a concise summary and a small JSON\n"
        "context of a roam test, produce a 1-3 sentence diagnostic, 3 prioritized recommendations,\n"
        "and 1-3 concrete CLI/debug commands to gather more evidence. Keep it concise and actionable."
    )

    user_msg = textwrap.dedent(f"""
    Summary:
    {text}

    Context (JSON, truncated):
    {ctx_json}

    Produce the three sections requested. Use short bullets and a final short severity tag (Low/Medium/High).
    """)

    try:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        res = call_provider(messages=messages, model=LLM_MODEL, temperature=LLM_TEMPERATURE, max_tokens=450)
        # res: {text, raw, usage, capabilities}
        return res.get("text") or json.dumps(res.get("raw"))
    except Exception as e:
        return f"(LLM request failed: {e})\n\nFallback summary:\n{text}"

    return text
