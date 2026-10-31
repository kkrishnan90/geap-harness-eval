"""Minimal labelled counters, rendered in Prometheus text exposition format."""

from collections import defaultdict
from typing import Dict, Tuple


class Metrics:
    def __init__(self, prefix: str = "clinlog"):
        self.prefix = prefix
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], int] = defaultdict(int)

    def inc(self, name: str, amount: int = 1, **labels) -> None:
        key = (name, tuple(sorted(labels.items())))
        self._counters[key] += amount

    def get(self, name: str, **labels) -> int:
        return self._counters.get((name, tuple(sorted(labels.items()))), 0)

    def total(self, name: str) -> int:
        return sum(v for (n, _), v in self._counters.items() if n == name)

    def render(self) -> str:
        lines = []
        for (name, labels), value in sorted(self._counters.items()):
            label_txt = ",".join(f'{k}="{v}"' for k, v in labels)
            full = f"{self.prefix}_{name}_total"
            lines.append(f"{full}{{{label_txt}}} {value}" if label_txt else f"{full} {value}")
        return "\n".join(lines) + ("\n" if lines else "")
