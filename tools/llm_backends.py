"""
LLM backend registry and loader.

Load an adapter by module path (e.g. tools.llm_adapter_openai) or by file path.
Adapter can export either:
 - rephrase(text, context) function, or
 - LLMAdapter class with rephrase(self, text, context) method.

Environment variables:
  MCP_LOOPBACK_LLM - module path to load (default: tools.llm_adapter_openai)

This module returns a simple callable adapter with .rephrase(text, context).
"""
from typing import Callable, Optional
import importlib
import importlib.util
import os
import sys
import inspect
import json

DEFAULT_ADAPTER = os.getenv("MCP_LOOPBACK_LLM", "tools.llm_adapter_openai")


class AdapterWrapper:
    def __init__(self, func: Callable):
        """Wrap various adapter callables and expose a consistent
        rephrase(text, context) -> str API.

        The underlying func may accept either (text, context) or just (text).
        If it only accepts a single positional argument, we merge the context into
        the input text (JSON) so the adapter still receives the extra information.
        """
        self._func = func

        sig = None
        try:
            sig = inspect.signature(func)
        except Exception:
            sig = None

        # Determine how many parameters the callable expects (positional only)
        params = 0
        if sig is not None:
            # count parameters that are not VAR_POSITIONAL or VAR_KEYWORD
            params = sum(1 for p in sig.parameters.values()
                         if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD))

        self._accepts_two = params >= 2

    def rephrase(self, text: str, context: dict) -> str:
        if self._accepts_two:
            # underlying adapter expects (text, context)
            return self._func(text, context)
        # fallback: underlying adapter only accepts a single text arg
        try:
            merged = text + "\n\nCONTEXT_JSON:\n" + json.dumps(context or {}, indent=2)
        except Exception:
            merged = text + "\n\nCONTEXT: (unserializable)"
        return self._func(merged)


def _load_module_by_path(modpath: str):
    # try regular import
    try:
        return importlib.import_module(modpath)
    except Exception:
        # fallback: try to treat modpath as relative file path
        parts = modpath.split('.')
        script_dir = os.path.abspath(os.path.dirname(__file__))
        cwd = os.getcwd()
        candidates = [
            os.path.join(cwd, *parts) + ".py",
            os.path.join(script_dir, *parts) + ".py",
            os.path.join(script_dir, os.pardir, *parts) + ".py",
        ]
        for p in candidates:
            if os.path.exists(p):
                name = f"mcp_llm_adapter_{os.path.splitext(os.path.basename(p))[0]}"
                loader = importlib.machinery.SourceFileLoader(name, p)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                module = importlib.util.module_from_spec(spec)
                loader.exec_module(module)
                sys.modules[name] = module
                return module
    return None


def get_adapter(adapter_path: Optional[str] = None) -> Optional[AdapterWrapper]:
    """Return an AdapterWrapper with .rephrase(text, context).
    adapter_path: module path (e.g. tools.llm_adapter_openai). If None uses DEFAULT_ADAPTER.
    """
    path = adapter_path or DEFAULT_ADAPTER
    mod = _load_module_by_path(path)
    if not mod:
        return None

    # prefer function 'rephrase'
    if hasattr(mod, "rephrase") and callable(getattr(mod, "rephrase")):
        return AdapterWrapper(getattr(mod, "rephrase"))

    # next, a class LLMAdapter with rephrase
    if hasattr(mod, "LLMAdapter"):
        cls = getattr(mod, "LLMAdapter")
        try:
            inst = cls()
            if hasattr(inst, "rephrase") and callable(inst.rephrase):
                return AdapterWrapper(inst.rephrase)
        except Exception:
            pass

    # nothing usable found
    return None


def list_default_candidates():
    return [DEFAULT_ADAPTER]
