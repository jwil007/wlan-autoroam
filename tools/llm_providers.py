"""
Provider driver for LLM backends.

This module implements a small, provider-agnostic caller with a default
OpenAI-compatible REST mode and a generic fallback. It returns a canonical
response dict with keys: text, raw, usage, capabilities.

Config via environment variables (defaults):
  LLM_PROVIDER_TYPE: openai | openai_compatible | generic
  LLM_PROVIDER_ENDPOINT: base URL for provider (e.g. https://api.openai.com)
  LLM_API_KEY: API key (Bearer)
  LLM_MODEL: model name (e.g. gpt-4o-mini)
  LLM_TEMPERATURE: float
  LLM_MAX_TOKENS: int

"""
from typing import List, Dict, Any, Optional
import os
import requests
import json


def _env(name: str, default=None):
    return os.getenv(name, default)


def load_config() -> Dict[str, Any]:
    return {
        "type": _env("LLM_PROVIDER_TYPE", "openai_compatible"),
        "endpoint": _env("LLM_PROVIDER_ENDPOINT", "https://api.openai.com"),
        "api_key": _env("LLM_API_KEY", _env("OPENAI_API_KEY")),
        "model": _env("LLM_MODEL", "gpt-4o-mini"),
        "temperature": float(_env("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(_env("LLM_MAX_TOKENS", "512")),
    }


def _call_openai_compatible(endpoint: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # endpoint should be base URL (e.g. https://api.openai.com) or full path
    if endpoint.endswith("/v1") or endpoint.endswith("/v1/"):
        url = endpoint.rstrip('/') + "/chat/completions"
    elif endpoint.endswith("/chat/completions"):
        url = endpoint
    else:
        url = endpoint.rstrip('/') + "/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def call_provider(messages: List[Dict[str, str]],
                  model: Optional[str] = None,
                  temperature: Optional[float] = None,
                  max_tokens: Optional[int] = None,
                  provider_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call configured provider and return canonical result.

    messages: list of {role, content}
    Returns: { text, raw, usage, capabilities }
    """
    cfg = provider_config or load_config()
    
    # Handle prefixed overrides (_llm_api_key -> api_key)
    if cfg:
        prefixed = {k: v for k, v in cfg.items() if k.startswith('_llm_')}
        for k, v in prefixed.items():
            unprefixed = k[5:]  # remove '_llm_'
            cfg[unprefixed] = v
    
    model = model or cfg.get("model")
    temperature = temperature if temperature is not None else cfg.get("temperature")
    max_tokens = max_tokens or cfg.get("max_tokens")

    if not cfg.get("api_key"):
        raise RuntimeError("LLM API key not found in environment (LLM_API_KEY or OPENAI_API_KEY)")

    # build payload for OpenAI-compatible chat completions
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Currently default to OpenAI-compatible REST
    try:
        resp_json = _call_openai_compatible(cfg.get("endpoint"), cfg.get("api_key"), payload)
    except Exception as e:
        # bubble up with context
        raise RuntimeError(f"Provider call failed: {e}")

    # parse into canonical text
    text = None
    usage = resp_json.get("usage") if isinstance(resp_json, dict) else None

    if isinstance(resp_json, dict) and "choices" in resp_json and len(resp_json["choices"]) > 0:
        c = resp_json["choices"][0]
        if isinstance(c.get("message"), dict):
            text = c.get("message", {}).get("content")
        elif c.get("text"):
            text = c.get("text")

    if text is None:
        # best effort: stringify body
        text = json.dumps(resp_json)[:2000]

    return {
        "text": text.strip() if isinstance(text, str) else str(text),
        "raw": resp_json,
        "usage": usage,
        "capabilities": {"stream": False, "function_call": False},
    }
