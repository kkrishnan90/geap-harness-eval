"""Kubernetes resource quantity parsing (the subset we use)."""

import re

_CPU_RE = re.compile(r"^(\d+(?:\.\d+)?)(m?)$")
_MEM_RE = re.compile(r"^(\d+(?:\.\d+)?)([A-Za-z]*)$")

_MEMORY_SUFFIXES = {
    "": 1,
    "k": 1000,
    "M": 1000 ** 2,
    "G": 1000 ** 3,
    "T": 1000 ** 4,
    "Ki": 1024,
    "Mi": 1024 ** 2,
    "Gi": 1000 ** 3,
    "Ti": 1024 ** 4,
}


class QuantityError(ValueError):
    pass


def parse_cpu(value):
    """CPU in cores: "500m" -> 0.5, "2" -> 2.0. Integers are accepted as cores."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    m = _CPU_RE.match(str(value))
    if not m:
        raise QuantityError(f"invalid cpu quantity {value!r}")
    number, milli = m.groups()
    return float(number) / 1000 if milli else float(number)


def parse_memory(value):
    """Memory in bytes: "256Mi" -> 268435456, "1G" -> 1000000000."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    m = _MEM_RE.match(str(value))
    if not m or m.group(2) not in _MEMORY_SUFFIXES:
        raise QuantityError(f"invalid memory quantity {value!r}")
    number, suffix = m.groups()
    return int(float(number) * _MEMORY_SUFFIXES[suffix])
