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

DEFAULT_ADAPTER = os.getenv("MCP_LOOPBACK_LLM", "tools.llm_adapter_openai")


class AdapterWrapper:
    def __init__(self, func: Callable[[str, dict], str]):
        self.rephrase = func


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
