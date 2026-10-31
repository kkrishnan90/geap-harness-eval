"""Harness adapter registry. Variants: dsh -> web-ptc (default), web-native (PTC-off control), acp-ptc."""

from __future__ import annotations

from importlib import import_module

ADAPTERS: dict[str, list[str]] = {
    "claude_code": ["default"],
    "pi": ["default"],
    "omp": ["default"],
    "dsh": ["web-ptc", "web-native", "acp-ptc"],
    "agy": ["default"],
}
_MODULES = {"claude_code": "claude_code", "pi": "pi", "omp": "omp", "dsh": "dsh", "agy": "agy"}


def get_adapter(name: str, variant: str = "default"):
    if name not in ADAPTERS:
        raise KeyError(f"unknown harness {name}")
    if variant == "default":
        variant = ADAPTERS[name][0]
    mod = import_module(f".{_MODULES[name]}", __name__)
    return mod.ADAPTER(variant)
