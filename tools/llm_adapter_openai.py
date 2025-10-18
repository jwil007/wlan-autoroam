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
        "total_roams": len(data.get("roams", [])),
        "successful_roams": sum(1 for r in data.get("roams", []) if r.get("overall_status") == "success"),
        "avg_roam_time_ms": sum(r.get("roam_duration_ms", 0) for r in data.get("roams", [])) / max(len(data.get("roams", [])), 1)
    }
    
    # Include detailed failure information including error logs
    failures = [r for r in data.get("roams", []) if r.get("overall_status") != "success"]
    if failures:
        out["failures"] = []
        for f in failures:
            failure_info = {
                "roam_index": f.get("roam_index"),
                "duration_ms": f.get("roam_duration_ms"),
                "target_bssid": f.get("target_bssid"),
                "details": f.get("details", {}),
            }
            # Include phase-specific information and error logs
            phases = f.get("phases", {})
            for phase_name, phase in phases.items():
                if phase.get("status") != "success" and phase.get("errors"):
                    failure_info[f"{phase_name}_errors"] = phase["errors"]
            out["failures"].append(failure_info)
    return json.dumps(out, indent=2)


def _mock_rephrase(text: str, context: Dict[str, Any]) -> str:
    # Deprecated: Previously returned deterministic mock for missing API key.
    # We no longer provide mock responses; callers should detect lack of AI and handle gracefully.
    raise RuntimeError("LLM mock disabled: no API key configured")


def rephrase(text: str, context: Dict[str, Any]) -> str:
    """Rephrase/expand the template summary using OpenAI Chat API if API key available,
    otherwise return a deterministic mock response for local testing.
    """
    # Build compact context
    try:
        ctx_json = _build_context_summary(context)
    except Exception:
        ctx_json = json.dumps({"note": "context serialization failed"})

    # Allow per-request provider overrides via context keys
    provider_config = None
    override_key = context.get('_llm_api_key') or context.get('_provider', {}).get('api_key')
    override_model = context.get('_llm_model')
    override_endpoint = context.get('_llm_provider_endpoint') or context.get('_provider', {}).get('endpoint')
    override_temp = context.get('_llm_temperature')
    override_max_tokens = context.get('_llm_max_tokens')
    if override_key or override_model or override_endpoint or override_temp or override_max_tokens:
        provider_config = {}
        if override_key:
            provider_config['api_key'] = override_key
        if override_endpoint:
            provider_config['endpoint'] = override_endpoint
        if override_model:
            provider_config['model'] = override_model
        if override_temp is not None:
            try:
                provider_config['temperature'] = float(override_temp)
            except Exception:
                pass
        if override_max_tokens is not None:
            try:
                provider_config['max_tokens'] = int(override_max_tokens)
            except Exception:
                pass

    # Determine effective API key (either env or per-request override)
    effective_api_key = OPENAI_API_KEY or (provider_config.get('api_key') if provider_config else None)
    if not effective_api_key:
        raise RuntimeError("LLM API key not configured; please set server AI settings or environment variable")

    # Provide detailed domain context for 802.11 roaming analysis
    system_msg = (
        "You are an expert Wi-Fi connectivity engineer specializing in 802.11 roaming analysis. You are having a conversation "
        "with a user about their roaming test results. You should directly answer their questions using the available data. "
        "If they ask about specific metrics like RSSI, look for that data in the context. If they ask an unrelated question "
        "or something not in the data, politely explain that you can only discuss the roaming test data.\n\n"
        
        "Your knowledge includes:"
        "\n- Authentication Phase: Initial 802.11 authentication (Open/SAE/WPA3)"
        "\n- Association Phase: 802.11 reassociation with new AP"
        "\n- 4-Way Handshake: Key exchange after association"
        "\n- Fast Transition (FT): Optional faster roaming (802.11r)"
        "\n- PMKSA Caching: Reusing keys with known APs"
        
        "\n\nCommon issues to watch for:"
        "\n- CTRL-EVENT-ASSOC-REJECT status_code=53: AP rejected PMKID"
        "\n- PMKSA cache rejection: AP doesn't recognize cached key"
        "\n- ASSOCIATING -> DISCONNECTED: Association failed"
        "\n- SAE timeouts: RF issues or AP capacity problems"
        
        "\n\nWhen answering questions:"
        "\n1. Be direct - answer exactly what was asked"
        "\n2. Include specific numbers/values when relevant"
        "\n3. Keep responses clear and concise"
        "\n4. If unsure, say so rather than making assumptions"
        "\n3. Note optimization feature behavior (FT, PMKSA caching success/failure)"
        "\n4. Consider AP behavior (rejection reasons, timeouts, state transitions)"
        "\n5. Examine frequency bands (2.4/5/6 GHz) and their impact"
        
        "\n\nProvide specific recommendations based on actual error messages and behavior patterns observed in the logs."
    )

    # Check if this is a follow-up question
    if context.get('_question'):
        user_msg = textwrap.dedent(f"""
        Given the roaming test data:
        {ctx_json}
        
        Previous context:
        {text}
        
        Question: {context['_question']}
        
        Provide a clear, technical answer focusing on the relevant data and 802.11 behavior.
        """)
    else:
        user_msg = textwrap.dedent(f"""
        Analyze these roaming test results:

        Summary:
        {text}

        Test Metrics:
        {ctx_json}

        Provide:
        1. Brief analysis of success/failure patterns
        2. Most likely cause of any failures
        3. 1-2 specific recommendations

        Keep your response clear and concise. Focus on the metrics and timing data.
        """)

    try:
        model_to_use = override_model or LLM_MODEL
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        res = call_provider(messages=messages, model=model_to_use, temperature=LLM_TEMPERATURE, max_tokens=450, provider_config=provider_config)
        # res: {text, raw, usage, capabilities}
        return res.get("text") or json.dumps(res.get("raw"))
    except Exception as e:
        return f"(LLM request failed: {e})\n\nFallback summary:\n{text}"

    return text
