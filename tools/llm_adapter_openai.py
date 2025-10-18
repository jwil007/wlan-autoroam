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
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo-16k")  # Use 16k context model by default
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_EXAMPLES = int(os.getenv("LLM_MAX_EXAMPLES", "6"))


def _build_context_summary(data: Dict[str, Any]) -> str:
    # Extract the actual data from the wrapper if needed
    actual_data = data.get('data', data) if isinstance(data, dict) else data
    
    # Build a focused context based on the data we need
    out = {
        "ssid": actual_data.get("ssid"),
        "security_type": actual_data.get("security_type"),
        # Always include candidate APs for RSSI questions
        "candidates": actual_data.get("candidates", []) if isinstance(actual_data, dict) else [],
        # Include roams data for all attempts
        "roams": [
            {
                "roam_index": r.get("roam_index"),
                "overall_status": r.get("overall_status"),
                "target_bssid": r.get("target_bssid"),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "roam_duration_ms": r.get("roam_duration_ms"),
                "final_bssid": r.get("final_bssid"),
                "final_freq": r.get("final_freq"),
                "details": r.get("details", {}),
                # Include filtered phase info
                "phases": {
                    k: {
                        "status": v.get("status"),
                        "type": v.get("type"),
                        "duration_ms": v.get("duration_ms"),
                        "errors": v.get("errors", [])
                    } for k, v in r.get("phases", {}).items()
                }
            } for r in actual_data.get("roams", [])
        ],
        # Include summary stats
        "_computed": {
            "total_roams": len(actual_data.get("roams", [])),
            "successful_roams": sum(1 for r in actual_data.get("roams", []) if r.get("overall_status") == "success"),
            "avg_roam_time_ms": sum(r.get("roam_duration_ms", 0) for r in actual_data.get("roams", [])) / max(len(actual_data.get("roams", [])), 1),
        }
    }
    
    # Debug logging
    print(f"\n[DEBUG] Data structure:")
    print(f"Input data type: {type(data)}")
    print(f"Actual data type: {type(actual_data)}")
    print(f"Keys in actual_data: {actual_data.keys() if isinstance(actual_data, dict) else 'not a dict'}")
    if isinstance(actual_data, dict):
        if 'candidates' in actual_data:
            print(f"Number of candidates: {len(actual_data['candidates'])}")
            print(f"First candidate RSSI: {actual_data['candidates'][0].get('rssi') if actual_data['candidates'] else 'none'}")
        if 'roams' in actual_data:
            print(f"Number of roams: {len(actual_data['roams'])}")
            print(f"Sample roam status: {actual_data['roams'][0].get('overall_status') if actual_data['roams'] else 'none'}")
    return json.dumps(out, indent=2)


def _mock_rephrase(text: str, context: Dict[str, Any]) -> str:
    # Deprecated: Previously returned deterministic mock for missing API key.
    # We no longer provide mock responses; callers should detect lack of AI and handle gracefully.
    raise RuntimeError("LLM mock disabled: no API key configured")


def _load_wifi_codes():
    """Load WiFi status and reason codes from JSON file"""
    try:
        with open(os.path.join(os.path.dirname(__file__), 'wifi_status_codes.json')) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load WiFi codes: {e}")
        return {"status_codes": {}, "reason_codes": {}}

def rephrase(text: str, context: Dict[str, Any]) -> str:
    """Rephrase/expand the template summary using OpenAI Chat API if API key available,
    otherwise return a deterministic mock response for local testing.
    """
    # Build compact context
    try:
        ctx_json = _build_context_summary(context)
        # Load WiFi codes for context
        wifi_codes = _load_wifi_codes()
    except Exception:
        ctx_json = json.dumps({"note": "context serialization failed"})
        wifi_codes = {"status_codes": {}, "reason_codes": {}}

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
    # Build status and reason code documentation
    # Format as exact numerical matches to help AI parse correctly
    status_docs = "\n".join(f"   - Status code {int(code):02d}: {desc}" 
                           for code, desc in sorted(wifi_codes["status_codes"].items(), key=lambda x: int(x[0])))
    reason_docs = "\n".join(f"   - Reason code {int(code):02d}: {desc}"
                           for code, desc in sorted(wifi_codes["reason_codes"].items(), key=lambda x: int(x[0])))
    
    system_msg = (
        "You are an expert Wi-Fi connectivity engineer having a friendly conversation about roaming test results. "
        "CRITICAL RULES:"
        "\n1. NEVER make up data or MAC addresses"
        "\n2. If an array is empty, say 'I see the array is empty'"
        "\n3. If an array has data, list the actual values"
        "\n4. Only mention FT/PMKSA if specifically asked about them"
        "\n5. If unsure about having certain data, check the JSON structure first"
        "\n6. When you see error codes, determine if it's a status or reason code by context:"
        "\n   - Status codes appear in responses (Auth/Assoc responses)"
        "\n   - Reason codes appear in disconnection frames (Deauth/Disassoc)"
        "\n   - Always match the exact numerical code value"
        "\n   - Never confuse status code X with reason code X"
        f"\n7. IEEE 802.11 Status Codes (used in responses):\n{status_docs}"
        f"\n\n8. IEEE 802.11 Reason Codes (used in disconnections):\n{reason_docs}"
        "\n\nIMPORTANT: Status code 17 means 'Too Many STAs' (AP full), NOT 'Association Needs QoS' (that's status 35)"
        "\n\nWhen asked about APs or RSSI:"
        "\n1. Look in the 'candidates' array"
        "\n2. Check if it exists and has data"
        "\n3. Give real values from the data, not made up ones"
        "\n4. Include the exact BSSID and RSSI values"
        
        "\n\nWhen answering questions:"
        "\n1. Focus on what was actually asked"
        "\n2. Use real values from the data"
        "\n3. Be friendly but precise"
        "\n4. If you can't find data, explain what you looked for"
        "\n5. Don't add unrelated commentary about FT/PMKSA unless asked"
        
        "\n\nData structure hints:"
        "\n- candidates: List of APs with RSSI/frequency"
        "\n- roams: Roaming attempt details"
        "\n- _computed: Summary statistics")    # Check if this is a follow-up question
    # Build a consistent context for both initial analysis and follow-up questions
    base_context = {
        "Test Data": ctx_json,
        "Previous Analysis": text if text else "No previous analysis"
    }

    if context.get('_question'):
        user_msg = textwrap.dedent(f"""
        Test Context:
        {json.dumps(base_context, indent=2)}
        
        Question: {context['_question']}
        
        Engineering Analysis Guidelines:
        1. Look for correlating evidence in the data:
           - Cross-reference status codes with actual AP metrics (QBSS count, utilization, etc.)
           - Compare behavior across multiple roam attempts to the same AP
           - Look for patterns that might indicate AP bugs or misconfigurations
        
        2. Think critically about error conditions:
           - Status codes are AP-reported and might not reflect reality
           - Consider whether the reported error makes sense given other metrics
           - Look for contradictions between reported status and observable state
        
        3. Consider multiple hypotheses:
           - Don't assume first explanation is correct
           - Look for alternative explanations supported by the data
           - Consider common failure modes vs unusual conditions
        
        4. Use the complete dataset:
           - All roam attempts are in the 'roams' array with full phase details
           - Candidate APs have RSSI, QBSS, and utilization metrics
           - Compare metrics across different phases and attempts
        
        5. Maintain consistency:
           - Verify previous analysis against all available data
           - If contradictions found, explain what new evidence changes the conclusion
           - Be explicit about uncertainty and speculation
        """)
    else:
        user_msg = textwrap.dedent(f"""
        Test Context:
        {json.dumps(base_context, indent=2)}
        
        Analyze these roaming test results and provide:
        1. Brief analysis of success/failure patterns
        2. Most likely cause of any failures
        3. 1-2 specific recommendations

        Use the complete test data above, including:
        - All roam attempts and their detailed phase information
        - Candidate AP list with RSSI values
        - Success/failure statistics
        """)

    try:
        model_to_use = override_model or LLM_MODEL
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        # Allow for longer responses when using a large context
        # Debug: print first 1000 chars of context
        print(f"\n[DEBUG] Context preview:\n{ctx_json[:1000]}\n")
        print(f"[DEBUG] Question: {context.get('_question')}\n")
        
        res = call_provider(messages=messages, model=model_to_use, temperature=LLM_TEMPERATURE, max_tokens=2000, provider_config=provider_config)
        # res: {text, raw, usage, capabilities}
        return res.get("text") or json.dumps(res.get("raw"))
    except Exception as e:
        return f"(LLM request failed: {e})\n\nFallback summary:\n{text}"

    return text
